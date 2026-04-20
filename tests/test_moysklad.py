"""Tests for Moysklad connector — client + mock server."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import httpx
import pytest
import uvicorn

from yzel.connectors.moysklad.client import MoyskladClient, MoyskladError, RateLimiter

from tests.mock_moysklad_server import VALID_TOKEN, app

MOCK_PORT = 8179
MOCK_BASE = f"http://localhost:{MOCK_PORT}/api/remap/1.2"


class _ServerThread:
    """Runs uvicorn in a background task for testing."""

    def __init__(self, port: int) -> None:
        self._config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        self._server = uvicorn.Server(self._config)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._server.serve())
        for _ in range(50):
            try:
                async with httpx.AsyncClient() as c:
                    await c.get(
                        f"http://127.0.0.1:{MOCK_PORT}/api/remap/1.2/entity/counterparty",
                        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
                    )
                return
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        raise RuntimeError("Mock Moysklad server failed to start")

    async def stop(self) -> None:
        self._server.should_exit = True
        if self._task:
            await self._task


@pytest.fixture
async def mock_server() -> AsyncGenerator[str, None]:
    """Start mock Moysklad server and return base URL."""
    srv = _ServerThread(MOCK_PORT)
    await srv.start()
    yield MOCK_BASE
    await srv.stop()


@pytest.fixture
async def client(mock_server: str) -> AsyncGenerator[MoyskladClient, None]:
    """Create a Moysklad client connected to mock server."""
    c = MoyskladClient(bearer_token=VALID_TOKEN, base_url=mock_server)
    yield c
    await c.close()


# --- Counterparty Tests ---


async def test_get_counterparties(client: MoyskladClient) -> None:
    """Fetch list of counterparties."""
    result = await client.get_counterparties()
    assert "rows" in result
    assert len(result["rows"]) == 3
    assert result["rows"][0]["name"] == "ООО Рога и Копыта"


async def test_get_counterparty_by_id(client: MoyskladClient) -> None:
    """Fetch single counterparty."""
    result = await client.get_counterparty("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    assert result["name"] == "ООО Рога и Копыта"
    assert result["inn"] == "7701234567"


async def test_search_counterparties(client: MoyskladClient) -> None:
    """Search counterparties by name."""
    result = await client.get_counterparties(search="Петров")
    assert len(result["rows"]) == 1
    assert result["rows"][0]["name"] == "ИП Петров П.П."


async def test_create_counterparty(client: MoyskladClient) -> None:
    """Create a new counterparty."""
    result = await client.create_counterparty({"name": "ООО Тест", "companyType": "legal"})
    assert "id" in result
    assert result["name"] == "ООО Тест"


async def test_update_counterparty(client: MoyskladClient) -> None:
    """Update counterparty."""
    result = await client.update_counterparty(
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        {"phone": "+7 (495) 999-99-99"},
    )
    assert result["phone"] == "+7 (495) 999-99-99"


# --- Product Tests ---


async def test_get_products(client: MoyskladClient) -> None:
    """Fetch list of products."""
    result = await client.get_products()
    assert len(result["rows"]) == 2
    assert result["rows"][0]["name"] == "Бумага А4 офисная"


async def test_get_product_by_id(client: MoyskladClient) -> None:
    """Fetch single product."""
    result = await client.get_product("d4e5f6a7-b8c9-0123-defa-345678901234")
    assert result["code"] == "BUM-A4-500"


# --- Customer Order Tests ---


async def test_get_customer_orders(client: MoyskladClient) -> None:
    """Fetch list of orders."""
    result = await client.get_customer_orders()
    assert len(result["rows"]) == 2


async def test_get_order_without_expand(client: MoyskladClient) -> None:
    """Without expand, agent is just a meta reference."""
    result = await client.get_customer_order("11111111-1111-1111-1111-111111111111")
    agent = result["agent"]
    # Without expand, agent should only have meta (reference)
    assert "meta" in agent
    assert "name" not in agent


async def test_get_order_with_expand(client: MoyskladClient) -> None:
    """With expand=agent, nested counterparty is fully resolved."""
    result = await client.get_customer_order(
        "11111111-1111-1111-1111-111111111111",
        expand="agent",
    )
    agent = result["agent"]
    # With expand, agent should be the full counterparty object
    assert agent["name"] == "ООО Рога и Копыта"
    assert agent["inn"] == "7701234567"


async def test_list_orders_with_expand(client: MoyskladClient) -> None:
    """Expand works on list endpoints too."""
    result = await client.get_customer_orders(expand="agent,organization")
    first_order = result["rows"][0]
    # Agent should be expanded
    assert first_order["agent"]["name"] == "ООО Рога и Копыта"
    # Organization should be expanded
    assert first_order["organization"]["name"] == "ООО Моя Компания"


# --- Stock Tests ---


async def test_stock_all(client: MoyskladClient) -> None:
    """Fetch stock across all warehouses."""
    result = await client.get_stock_all()
    assert len(result["rows"]) == 2
    assert result["rows"][0]["stock"] == 150


async def test_stock_by_store(client: MoyskladClient) -> None:
    """Fetch stock broken down by warehouse."""
    result = await client.get_stock_by_store()
    assert len(result["rows"]) == 2
    assert "stockByStore" in result["rows"][0]


# --- Organization Tests ---


async def test_get_organizations(client: MoyskladClient) -> None:
    """Fetch list of organizations."""
    result = await client.get_organizations()
    assert len(result["rows"]) == 1
    assert result["rows"][0]["name"] == "ООО Моя Компания"


# --- Error Handling ---


async def test_auth_error(mock_server: str) -> None:
    """Invalid token returns auth error."""
    bad_client = MoyskladClient(
        bearer_token="x" * 20,  # Obviously fake — not a real credential  # noqa: S106
        base_url=mock_server,
    )
    with pytest.raises(MoyskladError, match="аутентификации"):
        await bad_client.get_counterparties()
    await bad_client.close()


async def test_not_found_entity(client: MoyskladClient) -> None:
    """Getting non-existent entity returns error."""
    with pytest.raises(MoyskladError, match="не найден"):
        await client.get_counterparty("00000000-0000-0000-0000-000000000000")


async def test_error_carries_status_code(mock_server: str) -> None:
    """MoyskladError records the HTTP status code (for monitoring/dashboards)."""
    bad = MoyskladClient(bearer_token="x" * 20, base_url=mock_server)  # noqa: S106
    try:
        with pytest.raises(MoyskladError) as exc:
            await bad.get_counterparties()
        assert exc.value.status_code in (401, 403)
    finally:
        await bad.close()


async def test_error_wraps_non_errors_body(mock_server: str, monkeypatch) -> None:
    """A 4xx response without an `errors[]` envelope still surfaces as MoyskladError."""
    import httpx

    # Swap in a transport that returns a bare 500 with no body
    async def fake_request(self, method, url, **kwargs):
        return httpx.Response(500, request=httpx.Request(method, url))

    client = MoyskladClient(bearer_token="test", base_url=mock_server)
    try:
        monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
        with pytest.raises(MoyskladError) as exc:
            await client.get_counterparties()
        assert exc.value.status_code == 500
    finally:
        await client.close()


async def test_rate_limiter_enforces_interval() -> None:
    """Moysklad RateLimiter ensures the configured minimum interval."""
    import time

    limiter = RateLimiter(max_per_second=20.0)  # 50ms
    start = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    assert time.monotonic() - start >= 0.09
