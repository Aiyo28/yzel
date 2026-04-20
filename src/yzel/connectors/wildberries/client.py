"""Wildberries Seller API client.

WB splits its seller API across specialized hosts, all authenticating with the
same JWT `Authorization: <token>` header (no `Bearer ` prefix). Each host has
its own rate-limit budget, so the client applies per-host throttling rather
than a single global limiter.

Hosts covered in MVP:
- common-api       seller-info
- content-api      product card catalog
- marketplace-api  orders, stocks, warehouses
- statistics-api   sales and order statistics (strict rate limits)
- prices-api       prices and discounts

Rate-limit notes (as documented by WB, Apr 2026):
- statistics-api: ≈1 req/min per endpoint (enforce conservatively)
- marketplace-api: 100 req/min
- content-api: 100 req/min
- others: 100 req/min default
WB returns HTTP 429 without a Retry-After header on overrun.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

_HOSTS: dict[str, str] = {
    "common": "https://common-api.wildberries.ru",
    "content": "https://content-api.wildberries.ru",
    "marketplace": "https://marketplace-api.wildberries.ru",
    "statistics": "https://statistics-api.wildberries.ru",
    "prices": "https://discounts-prices-api.wildberries.ru",
}

# Per-host rate limits in requests per second. Conservative — WB enforces
# sliding windows and throttles aggressively on statistics endpoints.
_RATE_LIMITS: dict[str, float] = {
    "common": 1.5,
    "content": 1.5,
    "marketplace": 1.5,
    "statistics": 0.2,  # ~12 req/min — below the doc limit to leave slack
    "prices": 1.0,
}


class RateLimiter:
    """Leaky-bucket rate limiter, per-host instance."""

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


class WildberriesError(Exception):
    """Wildberries API error, parsed from the WB error envelope when present."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"Wildberries error [{status_code}/{code}]: {message}")


def _parse_wb_error(response: httpx.Response) -> WildberriesError:
    """Build a WildberriesError from a 4xx/5xx response.

    WB returns a variety of error shapes across hosts:
      {"title": "...", "detail": "...", "code": "..."}        # RFC 7807-ish
      {"error": true, "errorText": "..."}                     # legacy
      {"errors": [{"message": "..."}]}                        # content v2
    Normalize all of them into (code, message).
    """
    try:
        data = response.json()
    except ValueError:
        return WildberriesError(
            response.status_code,
            str(response.status_code),
            response.text[:200] or response.reason_phrase,
        )

    if isinstance(data, dict):
        if "detail" in data or "title" in data:
            return WildberriesError(
                response.status_code,
                str(data.get("code") or response.status_code),
                data.get("detail") or data.get("title") or "",
            )
        if data.get("error") and "errorText" in data:
            return WildberriesError(
                response.status_code, str(response.status_code), data["errorText"]
            )
        if isinstance(data.get("errors"), list) and data["errors"]:
            first = data["errors"][0]
            return WildberriesError(
                response.status_code,
                str(first.get("code") or response.status_code),
                first.get("message") or str(first),
            )

    return WildberriesError(response.status_code, str(response.status_code), str(data)[:200])


class WildberriesClient:
    """Async client for the Wildberries Seller API (multi-host)."""

    def __init__(self, api_key: str, hosts: dict[str, str] | None = None) -> None:
        self._api_key = api_key
        self._hosts = {**_HOSTS, **(hosts or {})}
        self._client: httpx.AsyncClient | None = None
        self._limiters = {host: RateLimiter(rps) for host, rps in _RATE_LIMITS.items()}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": self._api_key,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _request(
        self,
        host: str,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        if host not in self._hosts:
            raise ValueError(f"Unknown WB host key: {host}")

        limiter = self._limiters.get(host)
        if limiter:
            await limiter.acquire()

        url = f"{self._hosts[host]}{path}"
        client = await self._get_client()
        response = await client.request(method, url, params=params, json=json_body)

        if response.status_code >= 400:
            raise _parse_wb_error(response)

        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    # --- Seller / account ---

    async def get_seller_info(self) -> dict[str, Any]:
        """Получить информацию о продавце / Seller info."""
        return await self._request("common", "GET", "/api/v1/seller-info")

    # --- Warehouses ---

    async def list_warehouses(self) -> list[dict[str, Any]]:
        """Список складов продавца / Seller warehouses."""
        return await self._request("marketplace", "GET", "/api/v3/warehouses") or []

    # --- Orders ---

    async def get_new_orders(self) -> dict[str, Any]:
        """Новые сборочные задания (очередь FBS) / New FBS assembly orders."""
        return await self._request("marketplace", "GET", "/api/v3/orders/new")

    async def get_orders(
        self,
        date_from: int,
        date_to: int | None = None,
        limit: int = 1000,
        next_cursor: int = 0,
    ) -> dict[str, Any]:
        """Список сборочных заданий за период / Orders in date range (unix seconds)."""
        params: dict[str, Any] = {"dateFrom": date_from, "limit": limit, "next": next_cursor}
        if date_to is not None:
            params["dateTo"] = date_to
        return await self._request("marketplace", "GET", "/api/v3/orders", params=params)

    # --- Stocks ---

    async def get_stocks(self, warehouse_id: int, skus: list[str]) -> dict[str, Any]:
        """Остатки по SKU на складе / Stocks by SKU at warehouse."""
        return await self._request(
            "marketplace",
            "POST",
            f"/api/v3/stocks/{warehouse_id}",
            json_body={"skus": skus},
        )

    async def update_stocks(
        self, warehouse_id: int, stocks: list[dict[str, Any]]
    ) -> None:
        """Обновить остатки / Update stocks.

        stocks: list of {"sku": "barcode", "amount": int}
        """
        await self._request(
            "marketplace",
            "PUT",
            f"/api/v3/stocks/{warehouse_id}",
            json_body={"stocks": stocks},
        )

    # --- Statistics ---

    async def get_sales(self, date_from: str, flag: int = 0) -> list[dict[str, Any]]:
        """Продажи с даты (RFC3339) / Sales since date.

        flag=0 → incremental since last change timestamp,
        flag=1 → all sales stamped on that calendar day.
        """
        return (
            await self._request(
                "statistics",
                "GET",
                "/api/v1/supplier/sales",
                params={"dateFrom": date_from, "flag": flag},
            )
            or []
        )

    async def get_order_stats(self, date_from: str, flag: int = 0) -> list[dict[str, Any]]:
        """Статистика по заказам с даты / Order stats since date."""
        return (
            await self._request(
                "statistics",
                "GET",
                "/api/v1/supplier/orders",
                params={"dateFrom": date_from, "flag": flag},
            )
            or []
        )

    # --- Content (product cards) ---

    async def list_cards(
        self, limit: int = 100, cursor: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Список карточек товаров / Product cards list (cursor-paged)."""
        body: dict[str, Any] = {
            "settings": {
                "sort": {"ascending": False},
                "filter": {"withPhoto": -1},
                "cursor": {"limit": limit},
            }
        }
        if cursor:
            body["settings"]["cursor"].update(cursor)
        return await self._request("content", "POST", "/content/v2/get/cards/list", json_body=body)

    # --- Prices ---

    async def get_prices(self, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
        """Цены и скидки / Prices and discounts list."""
        return await self._request(
            "prices",
            "GET",
            "/api/v2/list/goods/filter",
            params={"limit": limit, "offset": offset},
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
