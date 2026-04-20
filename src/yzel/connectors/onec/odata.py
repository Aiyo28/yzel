"""1C Enterprise OData v3 client.

Handles Cyrillic entity names, Basic Auth, JSON format enforcement.
Always appends ?$format=json — 1C defaults to XML.

1C Basic Auth has no token: every HTTP call sends base64(user:pass).
No session to cache, no refresh. See CLAUDE.md Critical Gotcha #2.
"""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import quote

import httpx

DeploymentType = Literal["fresh", "on-prem"]


def detect_deployment(base_url: str) -> DeploymentType:
    """Classify a 1C OData URL as 1C:Fresh cloud vs on-prem.

    1C:Fresh tenants are hosted under `1cfresh.com/a/<app>/<tenant_id>/odata/`
    (CLAUDE.md Critical Gotcha #7). Callers may need to branch on this — e.g.
    Fresh endpoints sometimes apply stricter rate limits and reject some
    write verbs that work on-prem.
    """
    return "fresh" if "1cfresh.com/a/" in base_url else "on-prem"


class OneCError(Exception):
    """1C OData application-level error.

    Wraps httpx status errors with parsed OData error payload when available.
    Preserves Russian error text from 1C (`odata.error.message.value`).
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"1C OData error [{status_code}/{code}]: {message}")


def _parse_odata_error(response: httpx.Response) -> OneCError:
    """Build a OneCError from a 4xx/5xx OData response."""
    try:
        data = response.json()
        err = data.get("odata.error", {})
        code = str(err.get("code", response.status_code))
        msg_obj = err.get("message", {})
        message = msg_obj.get("value", "") if isinstance(msg_obj, dict) else str(msg_obj)
        if not message:
            message = response.text[:200]
    except (ValueError, KeyError):
        code = str(response.status_code)
        message = response.text[:200] or response.reason_phrase
    return OneCError(response.status_code, code, message)


class OneCODataClient:
    """Async client for 1C Enterprise OData v3 REST API."""

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (username, password)
        self._client: httpx.AsyncClient | None = None

    @property
    def deployment(self) -> DeploymentType:
        return detect_deployment(self._base_url)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                auth=self._auth,
                timeout=30.0,
                verify=True,
                headers={"Accept": "application/json"},
            )
        return self._client

    def _build_url(
        self,
        entity: str,
        key: str | None = None,
        params: dict[str, str] | None = None,
    ) -> str:
        """Build an OData URL with Cyrillic-safe encoding and mandatory JSON format."""
        encoded_entity = quote(entity, safe="")
        url = f"{self._base_url}/{encoded_entity}"

        if key:
            url = f"{url}(guid'{key}')"

        query_params = {"$format": "json"}
        if params:
            query_params.update(params)

        query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
        return f"{url}?{query_string}"

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        client = await self._get_client()
        response = await client.request(method, url, **kwargs)
        if response.status_code >= 400:
            raise _parse_odata_error(response)
        return response

    async def get_entity_list(
        self,
        entity: str,
        top: int | None = None,
        skip: int | None = None,
        filter_expr: str | None = None,
        select: list[str] | None = None,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch a list of records from a 1C OData entity set."""
        params: dict[str, str] = {}
        if top is not None:
            params["$top"] = str(top)
        if skip is not None:
            params["$skip"] = str(skip)
        if filter_expr:
            params["$filter"] = filter_expr
        if select:
            params["$select"] = ",".join(select)
        if order_by:
            params["$orderby"] = order_by

        url = self._build_url(entity, params=params)
        response = await self._request("GET", url)
        return response.json().get("value", [])

    async def get_entity(self, entity: str, key: str) -> dict[str, Any] | None:
        """Fetch a single record by GUID key. Returns None if not found."""
        url = self._build_url(entity, key=key)
        client = await self._get_client()
        response = await client.get(url)

        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise _parse_odata_error(response)
        return response.json()

    async def count_entities(self, entity: str, filter_expr: str | None = None) -> int:
        """Count records in an entity set via $inlinecount=allpages.

        1C OData v3 doesn't expose `$count` as a standalone endpoint — use
        `$inlinecount=allpages` with `$top=0` to get the total cheaply.
        """
        params = {"$inlinecount": "allpages", "$top": "0"}
        if filter_expr:
            params["$filter"] = filter_expr
        url = self._build_url(entity, params=params)
        response = await self._request("GET", url)
        data = response.json()
        raw_count = data.get("odata.count") or data.get("__count") or len(data.get("value", []))
        return int(raw_count)

    async def create_entity(self, entity: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new record in 1C."""
        url = self._build_url(entity)
        response = await self._request("POST", url, json=data)
        return response.json()

    async def update_entity(self, entity: str, key: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing record in 1C (PATCH semantics)."""
        url = self._build_url(entity, key=key)
        response = await self._request("PATCH", url, json=data)
        return response.json()

    async def delete_entity(self, entity: str, key: str) -> None:
        """Mark a record for deletion in 1C.

        Note: 1C does not hard-delete via OData — this sets DeletionMark=true
        on the referenced record. Physical removal requires a separate posting
        transaction inside 1C itself.
        """
        url = self._build_url(entity, key=key)
        await self._request("DELETE", url)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
