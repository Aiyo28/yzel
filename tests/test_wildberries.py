"""Tests for the Wildberries Seller API client.

Mock is a single Starlette app; the client points all five WB hosts at it
via the `hosts` override. Per-host rate limiters are bypassed in tests by
setting max_per_second very high.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import httpx
import pytest
import uvicorn

from yzel.connectors.wildberries.client import (
    RateLimiter,
    WildberriesClient,
    WildberriesError,
)
from tests.mock_wildberries_server import app

MOCK_PORT = 8179
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}"
TOKEN = "test-wb-token"  # noqa: S105 — mock

# Point every WB host at the mock.
_HOSTS_OVERRIDE = {
    key: MOCK_URL for key in ("common", "content", "marketplace", "statistics", "prices")
}


class _ServerThread:
    def __init__(self, port: int) -> None:
        self._config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        self._server = uvicorn.Server(self._config)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._server.serve())
        for _ in range(50):
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.get(
                        f"{MOCK_URL}/api/v3/warehouses",
                        headers={"Authorization": TOKEN},
                        timeout=1.0,
                    )
                    if r.status_code == 200:
                        return
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        raise RuntimeError("Mock WB server failed to start")

    async def stop(self) -> None:
        self._server.should_exit = True
        if self._task:
            await self._task


@pytest.fixture
async def mock_server() -> AsyncGenerator[str, None]:
    srv = _ServerThread(MOCK_PORT)
    await srv.start()
    yield MOCK_URL
    await srv.stop()


@pytest.fixture
async def client(mock_server: str) -> AsyncGenerator[WildberriesClient, None]:
    c = WildberriesClient(TOKEN, hosts=_HOSTS_OVERRIDE)
    # Disable throttling in tests — real host rates would serialize the suite.
    for host, limiter in list(c._limiters.items()):
        c._limiters[host] = RateLimiter(max_per_second=1000.0)
    yield c
    await c.close()


# --- Seller + warehouses ---


async def test_seller_info(client: WildberriesClient) -> None:
    info = await client.get_seller_info()
    assert info["name"] == "ИП Тестовый Продавец"


async def test_list_warehouses(client: WildberriesClient) -> None:
    wh = await client.list_warehouses()
    assert len(wh) == 2
    assert {w["id"] for w in wh} == {507, 686}


# --- Orders ---


async def test_new_orders(client: WildberriesClient) -> None:
    res = await client.get_new_orders()
    assert len(res["orders"]) == 2
    assert res["orders"][0]["article"] == "BUM-A4-500"


async def test_get_orders_forwards_pagination(client: WildberriesClient) -> None:
    res = await client.get_orders(date_from=1_700_000_000, limit=50)
    # Mock echoes the params it received
    assert res["limit"] == 50
    assert res["dateFrom"] == "1700000000"
    assert len(res["orders"]) == 1


# --- Stocks ---


async def test_get_stocks(client: WildberriesClient) -> None:
    res = await client.get_stocks(507, ["2000000000017", "2000000000024", "missing"])
    by_sku = {s["sku"]: s["amount"] for s in res["stocks"]}
    assert by_sku["2000000000017"] == 120
    assert by_sku["2000000000024"] == 45
    assert by_sku["missing"] == 0


async def test_update_stocks_round_trip(client: WildberriesClient) -> None:
    await client.update_stocks(507, [{"sku": "2000000000017", "amount": 999}])
    res = await client.get_stocks(507, ["2000000000017"])
    assert res["stocks"][0]["amount"] == 999


# --- Statistics ---


async def test_sales(client: WildberriesClient) -> None:
    sales = await client.get_sales("2026-04-19T00:00:00")
    assert len(sales) == 1
    assert sales[0]["saleID"] == "S123"


async def test_order_stats(client: WildberriesClient) -> None:
    stats = await client.get_order_stats("2026-04-19T00:00:00")
    assert stats[0]["supplierArticle"] == "BUM-A4-500"


# --- Content + prices ---


async def test_list_cards(client: WildberriesClient) -> None:
    res = await client.list_cards(limit=100)
    assert len(res["cards"]) == 2
    assert res["cursor"]["total"] == 2


async def test_get_prices(client: WildberriesClient) -> None:
    res = await client.get_prices()
    goods = res["data"]["listGoods"]
    assert len(goods) == 2
    assert goods[0]["vendorCode"] == "BUM-A4-500"


# --- Auth ---


async def test_wrong_token_raises_unauthorized(mock_server: str) -> None:
    bad = WildberriesClient("wrong-token", hosts=_HOSTS_OVERRIDE)
    for host, _ in list(bad._limiters.items()):
        bad._limiters[host] = RateLimiter(max_per_second=1000.0)
    try:
        with pytest.raises(WildberriesError) as exc:
            await bad.get_seller_info()
        assert exc.value.status_code == 401
        assert "Неверный токен" in exc.value.message
    finally:
        await bad.close()


# --- Rate limiter ---


async def test_rate_limiter_enforces_interval() -> None:
    import time as t

    limiter = RateLimiter(max_per_second=20.0)  # 50ms
    start = t.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = t.monotonic() - start
    assert elapsed >= 0.09  # 2 intervals with slack
