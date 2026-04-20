"""iiko Cloud API client.

iiko Cloud is a F&B-specific POS/ERP backend used by ~35K restaurants in
CIS. The public API exchanges a long-lived `apiLogin` (issued in iikoWeb)
for a 1-hour Bearer token via `POST /api/1/access_token`; every other
endpoint is POST with a JSON body — typically including `organizationIds`.

Auth/refresh model:
- access_token has a documented 1h TTL; we refresh 5 min before expiry
- on a 401, the client retries exactly once after a forced refresh
- refresh failure surfaces as IikoError so callers can alert/recover

Rate limit: iiko docs call out 1000 requests/hour per organization. We
throttle conservatively at ~0.25 rps (≈900/hr) to leave headroom for
parallel reads against multiple organizations on the same apiLogin.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

_REFRESH_MARGIN_SECONDS = 300
_DEFAULT_TOKEN_TTL_SECONDS = 3600


class RateLimiter:
    def __init__(self, max_per_second: float) -> None:
        self._min_interval = 1.0 / max_per_second
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request = time.monotonic()


class IikoError(Exception):
    """iiko Cloud API error."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"iiko error [{status_code}]: {message}")


def _parse_iiko_error(response: httpx.Response) -> IikoError:
    try:
        data = response.json()
    except ValueError:
        return IikoError(
            response.status_code, response.text[:200] or response.reason_phrase
        )
    if isinstance(data, dict):
        message = (
            data.get("errorDescription")
            or data.get("error")
            or data.get("message")
            or str(data)[:200]
        )
        return IikoError(response.status_code, str(message))
    return IikoError(response.status_code, str(data)[:200])


class IikoClient:
    """Async client for iiko Cloud API v1."""

    def __init__(
        self,
        api_login: str,
        base_url: str = "https://api-ru.iiko.services",
        max_per_second: float = 0.25,
    ) -> None:
        self._api_login = api_login
        self._base = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._limiter = RateLimiter(max_per_second=max_per_second)
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._refresh_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _refresh_token(self) -> None:
        client = await self._get_client()
        response = await client.post(
            f"{self._base}/api/1/access_token", json={"apiLogin": self._api_login}
        )
        if response.status_code >= 400:
            raise _parse_iiko_error(response)
        data = response.json()
        self._access_token = data["token"]
        # iiko responses don't carry `expires_in`; anchor to the documented 1h TTL
        self._expires_at = time.time() + _DEFAULT_TOKEN_TTL_SECONDS

    async def _ensure_token(self) -> str:
        async with self._refresh_lock:
            if (
                self._access_token is None
                or time.time() >= self._expires_at - _REFRESH_MARGIN_SECONDS
            ):
                await self._refresh_token()
            assert self._access_token is not None
            return self._access_token

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        await self._limiter.acquire()
        token = await self._ensure_token()
        url = f"{self._base}{path}"
        client = await self._get_client()

        response = await client.post(
            url,
            json=body or {},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )

        if response.status_code == 401:
            # Token likely invalidated server-side; refresh once and retry
            async with self._refresh_lock:
                await self._refresh_token()
                token = self._access_token
            response = await client.post(
                url,
                json=body or {},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )

        if response.status_code >= 400:
            raise _parse_iiko_error(response)

        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    # --- Organizations & topology ---

    async def get_organizations(
        self, organization_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Список организаций (ресторанов) / Organizations list."""
        body: dict[str, Any] = {"returnAdditionalInfo": True}
        if organization_ids is not None:
            body["organizationIds"] = organization_ids
        data = await self._post("/api/1/organizations", body)
        return data.get("organizations", []) if isinstance(data, dict) else []

    async def get_terminal_groups(
        self, organization_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Группы терминалов / Terminal groups per organization."""
        body = {"organizationIds": organization_ids}
        data = await self._post("/api/1/terminal_groups", body)
        return data.get("terminalGroups", []) if isinstance(data, dict) else []

    # --- Menu & stocks ---

    async def get_nomenclature(self, organization_id: str) -> dict[str, Any]:
        """Меню / Menu nomenclature for a single organization."""
        return await self._post(
            "/api/1/nomenclature", {"organizationId": organization_id}
        )

    async def get_stop_list(
        self, organization_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Стоп-лист (товары, которых нет) / Stop list (out-of-stock items)."""
        data = await self._post(
            "/api/1/stop_lists", {"organizationIds": organization_ids}
        )
        return data.get("terminalGroupStopLists", []) if isinstance(data, dict) else []

    # --- Deliveries / orders ---

    async def get_deliveries_by_phone(
        self,
        organization_ids: list[str],
        phone: str,
        delivery_date_from: str | None = None,
        delivery_date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Доставки клиента по телефону / Deliveries for a customer phone."""
        body: dict[str, Any] = {"organizationIds": organization_ids, "phone": phone}
        if delivery_date_from is not None:
            body["deliveryDateFrom"] = delivery_date_from
        if delivery_date_to is not None:
            body["deliveryDateTo"] = delivery_date_to
        data = await self._post(
            "/api/1/deliveries/by_delivery_date_and_phone", body
        )
        return data.get("ordersByOrganizations", []) if isinstance(data, dict) else []

    async def create_delivery(
        self,
        organization_id: str,
        terminal_group_id: str,
        order: dict[str, Any],
    ) -> dict[str, Any]:
        """Создать заказ на доставку / Create delivery order."""
        body = {
            "organizationId": organization_id,
            "terminalGroupId": terminal_group_id,
            "order": order,
        }
        return await self._post("/api/1/deliveries/create", body)

    # --- Reference data ---

    async def get_order_types(
        self, organization_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Типы заказов / Order types (dine-in / takeaway / delivery)."""
        data = await self._post(
            "/api/1/deliveries/order_types", {"organizationIds": organization_ids}
        )
        return data.get("orderTypes", []) if isinstance(data, dict) else []

    async def get_payment_types(
        self, organization_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Типы оплаты / Payment types."""
        data = await self._post(
            "/api/1/payment_types", {"organizationIds": organization_ids}
        )
        return data.get("paymentTypes", []) if isinstance(data, dict) else []

    async def get_employees(
        self, organization_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Сотрудники / Employees per organization."""
        data = await self._post(
            "/api/1/employees", {"organizationIds": organization_ids}
        )
        return data.get("employees", []) if isinstance(data, dict) else []

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
