"""1C OData v3 client.

Handles Cyrillic entity names, Basic Auth, JSON format enforcement.
Always appends ?$format=json — 1C defaults to XML.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


class OneCODataClient:
    """Async client for 1C Enterprise OData v3 REST API."""

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (username, password)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                auth=self._auth,
                timeout=30.0,
                verify=True,
                headers={"Accept": "application/json"},
            )
        return self._client

    def _build_url(self, entity: str, key: str | None = None, params: dict[str, str] | None = None) -> str:
        """Build OData URL with Cyrillic-safe encoding and mandatory JSON format."""
        # Encode Cyrillic entity names for URL
        encoded_entity = quote(entity, safe="")
        url = f"{self._base_url}/{encoded_entity}"

        if key:
            url = f"{url}(guid'{key}')"

        # Always force JSON format
        query_params = {"$format": "json"}
        if params:
            query_params.update(params)

        query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
        return f"{url}?{query_string}"

    async def get_entity_list(
        self,
        entity: str,
        top: int | None = None,
        skip: int | None = None,
        filter_expr: str | None = None,
        select: list[str] | None = None,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch a list of entities from 1C OData.

        Args:
            entity: Entity name (e.g., 'Catalog_Контрагенты')
            top: Limit number of results
            skip: Skip first N results
            filter_expr: OData $filter expression
            select: List of fields to return
            order_by: OData $orderby expression
        """
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
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()
        return data.get("value", [])

    async def get_entity(self, entity: str, key: str) -> dict[str, Any] | None:
        """Fetch a single entity by GUID key."""
        url = self._build_url(entity, key=key)
        client = await self._get_client()
        response = await client.get(url)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    async def create_entity(self, entity: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new entity in 1C."""
        url = self._build_url(entity)
        client = await self._get_client()
        response = await client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    async def update_entity(self, entity: str, key: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing entity in 1C."""
        url = self._build_url(entity, key=key)
        client = await self._get_client()
        response = await client.patch(url, json=data)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
