"""Tests for the Ozon Seller API client against the mock server."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import httpx
import pytest
import uvicorn

from yzel.connectors.ozon.client import OzonClient, OzonError, RateLimiter
from tests.mock_ozon_server import app

MOCK_PORT = 8181
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}"
CLIENT_ID = "123456"
API_KEY = "test-ozon-key"  # noqa: S105


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
                    r = await c.post(
                        f"{MOCK_URL}/v1/warehouse/list",
                        headers={"Client-Id": CLIENT_ID, "Api-Key": API_KEY},
                        json={},
                        timeout=1.0,
                    )
                    if r.status_code == 200:
                        return
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        raise RuntimeError("Mock Ozon server failed to start")

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
async def client(mock_server: str) -> AsyncGenerator[OzonClient, None]:
    c = OzonClient(CLIENT_ID, API_KEY, base_url=mock_server, max_per_second=1000.0)
    yield c
    await c.close()


# --- Warehouses ---


async def test_list_warehouses(client: OzonClient) -> None:
    wh = await client.list_warehouses()
    assert len(wh) == 2
    assert {w["warehouse_id"] for w in wh} == {1001, 1002}


# --- Products ---


async def test_list_products(client: OzonClient) -> None:
    res = await client.list_products(limit=10)
    assert res["total"] == 2
    assert {item["offer_id"] for item in res["items"]} == {"BUM-A4-500", "DT-L-001"}


async def test_get_product_info_by_offer_id(client: OzonClient) -> None:
    items = await client.get_product_info(offer_ids=["BUM-A4-500"])
    assert len(items) == 1
    assert items[0]["name"] == "Бумага А4"


# --- Stocks ---


async def test_get_stocks(client: OzonClient) -> None:
    items = await client.get_stocks([9000001])
    assert len(items) == 1
    assert items[0]["stocks"][0]["present"] == 120


async def test_update_stocks_round_trip(client: OzonClient) -> None:
    result = await client.update_stocks(
        [{"offer_id": "BUM-A4-500", "stock": 999, "warehouse_id": 1001}]
    )
    assert result[0]["updated"] is True
    # Reflect in subsequent read
    items = await client.get_stocks([9000001])
    assert items[0]["stocks"][0]["present"] == 999


async def test_update_prices(client: OzonClient) -> None:
    result = await client.update_prices(
        [{"offer_id": "DT-L-001", "price": "90000", "min_price": "80000"}]
    )
    assert result[0]["offer_id"] == "DT-L-001"
    assert result[0]["updated"] is True


# --- Postings ---


async def test_unfulfilled_postings(client: OzonClient) -> None:
    res = await client.list_unfulfilled_postings(limit=10)
    assert res["count"] == 2
    assert res["postings"][0]["posting_number"] == "1234-5678-0001"


async def test_list_postings_forwards_date_filter(client: OzonClient) -> None:
    res = await client.list_postings(
        since="2026-04-01T00:00:00Z", to="2026-04-30T00:00:00Z"
    )
    assert res["since"] == "2026-04-01T00:00:00Z"
    assert res["to"] == "2026-04-30T00:00:00Z"


async def test_get_posting_by_number(client: OzonClient) -> None:
    res = await client.get_posting("1234-5678-0001")
    assert res["order_id"] == 77001


async def test_get_posting_not_found_raises(client: OzonClient) -> None:
    with pytest.raises(OzonError) as exc:
        await client.get_posting("nonexistent")
    assert exc.value.status_code == 404
    assert "не найдено" in exc.value.message


# --- Analytics + finance ---


async def test_analytics_data(client: OzonClient) -> None:
    res = await client.analytics_data(
        date_from="2026-04-01",
        date_to="2026-04-19",
        metrics=["revenue", "ordered_units"],
    )
    assert res["data"][0]["metrics"] == [100.0, 5.0]
    assert res["date_from"] == "2026-04-01"


async def test_list_transactions(client: OzonClient) -> None:
    res = await client.list_transactions(since="2026-04-01", to="2026-04-19")
    assert res["row_count"] == 2
    assert res["operations"][1]["amount"] == 3500


# --- Auth ---


async def test_missing_client_id_raises_403(mock_server: str) -> None:
    bad = OzonClient("wrong", API_KEY, base_url=mock_server, max_per_second=1000.0)
    try:
        with pytest.raises(OzonError) as exc:
            await bad.list_warehouses()
        assert exc.value.status_code == 403
    finally:
        await bad.close()


async def test_missing_api_key_raises_403(mock_server: str) -> None:
    bad = OzonClient(CLIENT_ID, "wrong", base_url=mock_server, max_per_second=1000.0)
    try:
        with pytest.raises(OzonError) as exc:
            await bad.list_warehouses()
        assert exc.value.status_code == 403
        assert "неверны" in exc.value.message
    finally:
        await bad.close()


# --- Rate limiter ---


async def test_rate_limiter_enforces_interval() -> None:
    import time as t

    limiter = RateLimiter(max_per_second=20.0)
    start = t.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    assert t.monotonic() - start >= 0.09
