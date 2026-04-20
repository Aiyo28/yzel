"""AmoCRM (Kommo) REST API v4 client.

OAuth2 auth with automatic token refresh. Key gotchas:
- Access tokens expire in ~20 minutes. We refresh 5 min before expiry.
- Refresh tokens expire after 3 MONTHS of inactivity. If the server is
  down for 3 months, the token silently dies. Must monitor refresh health.
- API base: https://{subdomain}.amocrm.ru/api/v4/
- Token endpoint: https://{subdomain}.amocrm.ru/oauth2/access_token
"""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx

_REFRESH_MARGIN_SECONDS = 300  # Refresh 5 min before expiry
REFRESH_INACTIVITY_LIMIT_DAYS = 90  # AmoCRM silent-death threshold


class AmoCRMClient:
    """Async client for AmoCRM REST API v4 with auto token refresh."""

    def __init__(
        self,
        subdomain: str,
        access_token: str,
        refresh_token: str,
        expires_at: float,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        on_token_refresh: Callable[[str, str, float], None] | None = None,
        refresh_token_updated_at: float | None = None,
    ) -> None:
        self._subdomain = subdomain
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = expires_at
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._on_token_refresh = on_token_refresh
        # None → assume "now" so fresh-install credentials don't trip the guard
        self._refresh_token_updated_at: float = (
            refresh_token_updated_at if refresh_token_updated_at else time.time()
        )
        self._client: httpx.AsyncClient | None = None
        self._base_url = f"https://{subdomain}.amocrm.ru"

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._base_url = value.rstrip("/")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    def _token_needs_refresh(self) -> bool:
        return time.time() >= (self._expires_at - _REFRESH_MARGIN_SECONDS)

    async def _refresh_tokens(self) -> None:
        """Exchange refresh token for a new access + refresh token pair."""
        client = await self._get_client()
        response = await client.post(
            f"{self._base_url}/oauth2/access_token",
            json={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "redirect_uri": self._redirect_uri,
            },
        )

        if response.status_code != 200:
            try:
                body = response.json()
                hint = body.get("hint", body.get("message", ""))
            except (ValueError, KeyError):
                hint = response.text
            raise AmoCRMAuthError(
                f"Ошибка обновления токена: {response.status_code}. {hint}"
            )

        data = response.json()
        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._expires_at = time.time() + data["expires_in"]
        self._refresh_token_updated_at = time.time()

        if self._on_token_refresh:
            self._on_token_refresh(self._access_token, self._refresh_token, self._expires_at)

    async def _ensure_auth(self) -> None:
        if self._token_needs_refresh():
            await self._refresh_tokens()

    # --- Refresh-health guard (3-month silent-death prevention) ---

    @property
    def refresh_token_updated_at(self) -> float:
        """Unix timestamp of the last successful refresh_token exchange."""
        return self._refresh_token_updated_at

    def days_since_refresh(self) -> float:
        """How long since the refresh_token was last exchanged."""
        return (time.time() - self._refresh_token_updated_at) / 86400.0

    def days_until_refresh_expiry(
        self, inactivity_limit_days: int = REFRESH_INACTIVITY_LIMIT_DAYS
    ) -> float:
        """Days remaining before silent-death at the given inactivity limit.

        AmoCRM does not publish the exact limit; 90 days is the figure in
        their docs as of 2026. Pass a lower value to get an earlier warning.
        """
        return inactivity_limit_days - self.days_since_refresh()

    async def ensure_refresh_fresh(self, min_remaining_days: float = 14.0) -> bool:
        """Force a token refresh if the refresh_token is approaching staleness.

        Call this from a scheduled health check (e.g. daily cron). If fewer
        than `min_remaining_days` remain before the inactivity limit, the
        client performs a refresh — which resets the clock on both tokens —
        and returns True. Returns False if no refresh was needed.
        """
        if self.days_until_refresh_expiry() <= min_remaining_days:
            await self._refresh_tokens()
            return True
        return False

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated API request with auto token refresh."""
        await self._ensure_auth()

        client = await self._get_client()
        url = f"{self._base_url}/api/v4/{path.lstrip('/')}"
        response = await client.request(
            method,
            url,
            params=params,
            json=json_data,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )

        if response.status_code == 401:
            # Token may have been invalidated — try one refresh
            await self._refresh_tokens()
            response = await client.request(
                method,
                url,
                params=params,
                json=json_data,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )

        if response.status_code == 204:
            return {}

        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("detail", body.get("title", ""))
                raise AmoCRMError(
                    status=response.status_code,
                    detail=detail,
                )
            except (ValueError, KeyError):
                response.raise_for_status()

        return response.json()

    # --- Leads (Сделки) ---

    async def get_leads(
        self,
        limit: int = 50,
        page: int = 1,
        query: str | None = None,
        filter_params: dict[str, Any] | None = None,
        with_params: list[str] | None = None,
    ) -> dict[str, Any]:
        """Получить список сделок / Get leads."""
        params: dict[str, Any] = {"limit": limit, "page": page}
        if query:
            params["query"] = query
        if filter_params:
            for key, val in filter_params.items():
                params[f"filter[{key}]"] = val
        if with_params:
            params["with"] = ",".join(with_params)
        return await self._request("GET", "leads", params=params)

    async def get_lead(self, lead_id: int, with_params: list[str] | None = None) -> dict[str, Any]:
        """Получить сделку по ID / Get lead by ID."""
        params = {"with": ",".join(with_params)} if with_params else None
        return await self._request("GET", f"leads/{lead_id}", params=params)

    async def create_leads(self, leads: list[dict[str, Any]]) -> dict[str, Any]:
        """Создать сделки (batch) / Create leads."""
        return await self._request("POST", "leads", json_data=leads)

    async def update_lead(self, lead_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить сделку / Update a lead."""
        return await self._request("PATCH", f"leads/{lead_id}", json_data=fields)

    # --- Contacts (Контакты) ---

    async def get_contacts(
        self,
        limit: int = 50,
        page: int = 1,
        query: str | None = None,
        with_params: list[str] | None = None,
    ) -> dict[str, Any]:
        """Получить список контактов / Get contacts."""
        params: dict[str, Any] = {"limit": limit, "page": page}
        if query:
            params["query"] = query
        if with_params:
            params["with"] = ",".join(with_params)
        return await self._request("GET", "contacts", params=params)

    async def get_contact(self, contact_id: int, with_params: list[str] | None = None) -> dict[str, Any]:
        """Получить контакт по ID / Get contact by ID."""
        params = {"with": ",".join(with_params)} if with_params else None
        return await self._request("GET", f"contacts/{contact_id}", params=params)

    async def create_contacts(self, contacts: list[dict[str, Any]]) -> dict[str, Any]:
        """Создать контакты (batch) / Create contacts."""
        return await self._request("POST", "contacts", json_data=contacts)

    async def update_contact(self, contact_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить контакт / Update a contact."""
        return await self._request("PATCH", f"contacts/{contact_id}", json_data=fields)

    # --- Companies (Компании) ---

    async def get_companies(
        self,
        limit: int = 50,
        page: int = 1,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Получить список компаний / Get companies."""
        params: dict[str, Any] = {"limit": limit, "page": page}
        if query:
            params["query"] = query
        return await self._request("GET", "companies", params=params)

    async def get_company(self, company_id: int) -> dict[str, Any]:
        """Получить компанию по ID / Get company by ID."""
        return await self._request("GET", f"companies/{company_id}")

    async def create_companies(self, companies: list[dict[str, Any]]) -> dict[str, Any]:
        """Создать компании (batch) / Create companies."""
        return await self._request("POST", "companies", json_data=companies)

    async def update_company(self, company_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить компанию / Update a company."""
        return await self._request("PATCH", f"companies/{company_id}", json_data=fields)

    # --- Pipelines (Воронки) ---

    async def get_pipelines(self) -> dict[str, Any]:
        """Получить список воронок / Get pipelines."""
        return await self._request("GET", "leads/pipelines")

    async def get_pipeline(self, pipeline_id: int) -> dict[str, Any]:
        """Получить воронку по ID / Get pipeline by ID."""
        return await self._request("GET", f"leads/pipelines/{pipeline_id}")

    # --- Account Info ---

    async def get_account(self, with_params: list[str] | None = None) -> dict[str, Any]:
        """Получить информацию об аккаунте / Get account info."""
        params = {"with": ",".join(with_params)} if with_params else None
        return await self._request("GET", "account", params=params)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class AmoCRMError(Exception):
    """AmoCRM API error."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"AmoCRM error [{status}]: {detail}")


class AmoCRMAuthError(Exception):
    """AmoCRM authentication/token error."""
