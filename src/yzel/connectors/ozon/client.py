"""Ozon Seller API client.

Single host (`https://api-seller.ozon.ru`, sandbox variant overridable via
credential) with dual-header auth: every request must send BOTH `Client-Id`
and `Api-Key`. Missing or mismatched → HTTP 403.

Nearly every Ozon endpoint is POST with a JSON body, even for read-only
queries — this is the API's house style, not a bug.

Rate limits vary per endpoint family (postings are lenient, analytics is
tight). We apply a single conservative client-side throttle and let Ozon's
429 responses surface as `OzonError` with any `Retry-After` echoed in the
message.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


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


class OzonError(Exception):
    """Ozon API error, parsed from the {code,message,details} envelope."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"Ozon error [{status_code}/{code}]: {message}")


def _parse_ozon_error(response: httpx.Response) -> OzonError:
    retry_after = response.headers.get("retry-after")
    suffix = f" (retry-after={retry_after}s)" if retry_after else ""
    try:
        data = response.json()
    except ValueError:
        return OzonError(
            response.status_code,
            str(response.status_code),
            (response.text[:200] or response.reason_phrase) + suffix,
        )

    if isinstance(data, dict):
        code = str(data.get("code") or response.status_code)
        message = data.get("message") or response.text[:200] or response.reason_phrase
        return OzonError(response.status_code, code, message + suffix)
    return OzonError(response.status_code, str(response.status_code), str(data)[:200] + suffix)


class OzonClient:
    """Async client for the Ozon Seller API."""

    def __init__(
        self,
        client_id: str,
        api_key: str,
        base_url: str = "https://api-seller.ozon.ru",
        max_per_second: float = 5.0,
    ) -> None:
        self._client_id = client_id
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._limiter = RateLimiter(max_per_second=max_per_second)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Client-Id": self._client_id,
                    "Api-Key": self._api_key,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        await self._limiter.acquire()
        url = f"{self._base_url}{path}"
        client = await self._get_client()
        response = await client.post(url, json=body or {})
        if response.status_code >= 400:
            raise _parse_ozon_error(response)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    # --- Warehouses ---

    async def list_warehouses(self) -> list[dict[str, Any]]:
        """Список складов продавца / Seller warehouses."""
        data = await self._post("/v1/warehouse/list")
        return data.get("result", []) if isinstance(data, dict) else []

    # --- Products ---

    async def list_products(
        self,
        limit: int = 100,
        last_id: str = "",
        filter_visibility: str = "ALL",
    ) -> dict[str, Any]:
        """Список товаров (пагинация last_id) / Products list (cursor-paged)."""
        body = {
            "filter": {"visibility": filter_visibility},
            "limit": limit,
            "last_id": last_id,
        }
        return (await self._post("/v3/product/list", body)).get("result", {})

    async def get_product_info(
        self,
        offer_ids: list[str] | None = None,
        product_ids: list[int] | None = None,
        skus: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """Детали товаров по offer_id / product_id / sku."""
        body: dict[str, Any] = {
            "offer_id": offer_ids or [],
            "product_id": product_ids or [],
            "sku": skus or [],
        }
        data = await self._post("/v2/product/info/list", body)
        return data.get("result", {}).get("items", []) if isinstance(data, dict) else []

    async def get_stocks(self, skus: list[int]) -> list[dict[str, Any]]:
        """Остатки по sku / Stocks by sku."""
        body = {"sku": skus}
        data = await self._post("/v4/product/info/stocks", body)
        return data.get("items", []) if isinstance(data, dict) else []

    async def update_stocks(self, stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Обновить остатки. stocks = [{offer_id, stock, warehouse_id}]"""
        body = {"stocks": stocks}
        data = await self._post("/v2/products/stocks", body)
        return data.get("result", []) if isinstance(data, dict) else []

    async def update_prices(self, prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Обновить цены. prices = [{offer_id, price, old_price?, min_price?}]"""
        body = {"prices": prices}
        data = await self._post("/v1/product/import/prices", body)
        return data.get("result", []) if isinstance(data, dict) else []

    # --- FBS postings (orders) ---

    async def list_unfulfilled_postings(
        self, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """Неотгруженные сборочные задания FBS / Unfulfilled FBS postings."""
        body = {
            "dir": "ASC",
            "filter": {"cutoff_from": "", "cutoff_to": "", "status": ""},
            "limit": limit,
            "offset": offset,
            "with": {"analytics_data": False, "financial_data": False},
        }
        return (await self._post("/v3/posting/fbs/unfulfilled/list", body)).get("result", {})

    async def list_postings(
        self,
        since: str,
        to: str,
        limit: int = 100,
        offset: int = 0,
        status: str = "",
    ) -> dict[str, Any]:
        """Сборочные задания за период (ISO-8601 datetime)."""
        body = {
            "dir": "ASC",
            "filter": {"since": since, "to": to, "status": status},
            "limit": limit,
            "offset": offset,
            "with": {"analytics_data": False, "financial_data": False},
        }
        return (await self._post("/v3/posting/fbs/list", body)).get("result", {})

    async def get_posting(self, posting_number: str) -> dict[str, Any]:
        """Получить сборочное задание по номеру."""
        body = {
            "posting_number": posting_number,
            "with": {"analytics_data": True, "financial_data": True, "products": True},
        }
        data = await self._post("/v3/posting/fbs/get", body)
        return data.get("result", {}) if isinstance(data, dict) else {}

    # --- Analytics + finance ---

    async def analytics_data(
        self,
        date_from: str,
        date_to: str,
        metrics: list[str],
        dimension: list[str] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Аналитические данные продавца."""
        body = {
            "date_from": date_from,
            "date_to": date_to,
            "metrics": metrics,
            "dimension": dimension or ["sku"],
            "limit": limit,
            "offset": 0,
        }
        data = await self._post("/v1/analytics/data", body)
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def list_transactions(
        self,
        since: str,
        to: str,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Финансовые операции за период."""
        body = {
            "filter": {"date": {"from": since, "to": to}},
            "page": page,
            "page_size": page_size,
        }
        data = await self._post("/v3/finance/transaction/list", body)
        return data.get("result", {}) if isinstance(data, dict) else {}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
