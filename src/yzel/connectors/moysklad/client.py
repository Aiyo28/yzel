"""Moysklad JSON API 1.2 client.

Bearer token auth — static token, no refresh needed.
Base URL: https://api.moysklad.ru/api/remap/1.2/

Key gotcha: nested entities (e.g., agent inside an order) return as
UUID references by default. Must pass `expand=agent,organization`
to inline the full nested objects. Without expand, users get useless IDs.
"""

from __future__ import annotations

from typing import Any

import httpx

_DEFAULT_BASE_URL = "https://api.moysklad.ru/api/remap/1.2"


class MoyskladClient:
    """Async client for Moysklad JSON API 1.2."""

    def __init__(self, bearer_token: str, base_url: str = _DEFAULT_BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = bearer_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept-Encoding": "gzip",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated API request.

        Returns:
            Parsed JSON response.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
            MoyskladError: On API-level error with detail message.
        """
        url = f"{self._base_url}/{path.lstrip('/')}"
        client = await self._get_client()
        response = await client.request(method, url, params=params, json=json_data)

        if response.status_code >= 400:
            try:
                body = response.json()
                errors = body.get("errors", [])
                if errors:
                    err = errors[0]
                    raise MoyskladError(
                        code=err.get("code", response.status_code),
                        message=err.get("error", response.reason_phrase or "Unknown error"),
                        more_info=err.get("moreInfo", ""),
                    )
            except (ValueError, KeyError):
                pass
            response.raise_for_status()

        return response.json()

    def _list_params(
        self,
        limit: int | None = None,
        offset: int | None = None,
        filter_expr: str | None = None,
        order: str | None = None,
        expand: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """Build query params for list endpoints."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if filter_expr:
            params["filter"] = filter_expr
        if order:
            params["order"] = order
        if expand:
            params["expand"] = expand
        if search:
            params["search"] = search
        return params

    # --- Counterparties (Контрагенты) ---

    async def get_counterparties(
        self,
        limit: int | None = None,
        offset: int | None = None,
        filter_expr: str | None = None,
        search: str | None = None,
        expand: str | None = None,
    ) -> dict[str, Any]:
        """Получить список контрагентов / Get counterparties."""
        params = self._list_params(limit=limit, offset=offset, filter_expr=filter_expr,
                                   search=search, expand=expand)
        return await self._request("GET", "entity/counterparty", params=params)

    async def get_counterparty(self, entity_id: str, expand: str | None = None) -> dict[str, Any]:
        """Получить контрагента по ID / Get counterparty by ID."""
        params = {"expand": expand} if expand else None
        return await self._request("GET", f"entity/counterparty/{entity_id}", params=params)

    async def create_counterparty(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Создать контрагента / Create a counterparty."""
        return await self._request("POST", "entity/counterparty", json_data=fields)

    async def update_counterparty(self, entity_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить контрагента / Update a counterparty."""
        return await self._request("PUT", f"entity/counterparty/{entity_id}", json_data=fields)

    # --- Products (Товары) ---

    async def get_products(
        self,
        limit: int | None = None,
        offset: int | None = None,
        filter_expr: str | None = None,
        search: str | None = None,
        expand: str | None = None,
    ) -> dict[str, Any]:
        """Получить список товаров / Get products."""
        params = self._list_params(limit=limit, offset=offset, filter_expr=filter_expr,
                                   search=search, expand=expand)
        return await self._request("GET", "entity/product", params=params)

    async def get_product(self, entity_id: str, expand: str | None = None) -> dict[str, Any]:
        """Получить товар по ID / Get product by ID."""
        params = {"expand": expand} if expand else None
        return await self._request("GET", f"entity/product/{entity_id}", params=params)

    async def create_product(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Создать товар / Create a product."""
        return await self._request("POST", "entity/product", json_data=fields)

    async def update_product(self, entity_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить товар / Update a product."""
        return await self._request("PUT", f"entity/product/{entity_id}", json_data=fields)

    # --- Customer Orders (Заказы покупателей) ---

    async def get_customer_orders(
        self,
        limit: int | None = None,
        offset: int | None = None,
        filter_expr: str | None = None,
        expand: str | None = None,
        order: str | None = None,
    ) -> dict[str, Any]:
        """Получить список заказов покупателей / Get customer orders."""
        params = self._list_params(limit=limit, offset=offset, filter_expr=filter_expr,
                                   expand=expand, order=order)
        return await self._request("GET", "entity/customerorder", params=params)

    async def get_customer_order(self, entity_id: str, expand: str | None = None) -> dict[str, Any]:
        """Получить заказ по ID / Get customer order by ID."""
        params = {"expand": expand} if expand else None
        return await self._request("GET", f"entity/customerorder/{entity_id}", params=params)

    async def create_customer_order(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Создать заказ покупателя / Create a customer order."""
        return await self._request("POST", "entity/customerorder", json_data=fields)

    async def update_customer_order(self, entity_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Обновить заказ покупателя / Update a customer order."""
        return await self._request("PUT", f"entity/customerorder/{entity_id}", json_data=fields)

    # --- Stock (Остатки) ---

    async def get_stock_all(
        self,
        limit: int | None = None,
        offset: int | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        """Получить остатки по всем складам / Get stock across all warehouses."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if group_by:
            params["groupBy"] = group_by
        return await self._request("GET", "report/stock/all", params=params)

    async def get_stock_by_store(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Получить остатки по складам / Get stock by warehouse."""
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return await self._request("GET", "report/stock/bystore", params=params)

    # --- Organizations (Юрлица) ---

    async def get_organizations(self) -> dict[str, Any]:
        """Получить список юрлиц / Get organizations."""
        return await self._request("GET", "entity/organization")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class MoyskladError(Exception):
    """Moysklad API error."""

    def __init__(self, code: int | str, message: str, more_info: str = "") -> None:
        self.code = code
        self.message = message
        self.more_info = more_info
        super().__init__(f"Moysklad error [{code}]: {message}")
