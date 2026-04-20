"""Tests for Bitrix24 connector — client + mock server."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
import pytest
import uvicorn

from yzel.connectors.bitrix24.client import Bitrix24Client, Bitrix24Error, RateLimiter

# Re-import to reset state each test run
from tests.mock_bitrix24_server import app

MOCK_PORT = 8178  # Different from dev port to avoid conflicts
MOCK_WEBHOOK = f"http://localhost:{MOCK_PORT}/rest/1/test_webhook_secret"


class _ServerThread:
    """Runs uvicorn in a background thread for testing."""

    def __init__(self, port: int) -> None:
        self._config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        self._server = uvicorn.Server(self._config)
        self._thread: asyncio.Task | None = None

    async def start(self) -> None:
        self._thread = asyncio.create_task(self._server.serve())
        # Wait for server to be ready
        for _ in range(50):
            try:
                async with httpx.AsyncClient() as c:
                    await c.get(f"http://127.0.0.1:{MOCK_PORT}/rest/1/test_webhook_secret/crm.lead.list.json")
                return
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        raise RuntimeError("Mock Bitrix24 server failed to start")

    async def stop(self) -> None:
        self._server.should_exit = True
        if self._thread:
            await self._thread


@pytest.fixture
async def mock_server() -> AsyncGenerator[str, None]:
    """Start mock Bitrix24 server and return webhook URL."""
    srv = _ServerThread(MOCK_PORT)
    await srv.start()
    yield MOCK_WEBHOOK
    await srv.stop()


@pytest.fixture
async def client(mock_server: str) -> AsyncGenerator[Bitrix24Client, None]:
    """Create a Bitrix24 client connected to mock server."""
    c = Bitrix24Client(mock_server)
    yield c
    await c.close()


# --- CRM Lead Tests ---


async def test_get_leads(client: Bitrix24Client) -> None:
    """Fetch list of leads."""
    result = await client.get_leads()
    assert "result" in result
    assert len(result["result"]) == 3
    assert result["result"][0]["TITLE"] == "Заявка с сайта — офисная мебель"


async def test_get_leads_with_select(client: Bitrix24Client) -> None:
    """Fetch leads with field selection."""
    result = await client.get_leads(select=["ID", "TITLE"])
    items = result["result"]
    assert len(items) == 3
    # Selected fields should be present
    assert "ID" in items[0]
    assert "TITLE" in items[0]


async def test_get_lead_by_id(client: Bitrix24Client) -> None:
    """Fetch a single lead by ID."""
    result = await client.get_lead(1)
    assert "result" in result
    assert result["result"]["ID"] == "1"
    assert result["result"]["NAME"] == "Алексей"


async def test_create_lead(client: Bitrix24Client) -> None:
    """Create a new lead."""
    result = await client.create_lead({"TITLE": "Тестовый лид", "NAME": "Тест"})
    assert "result" in result
    assert result["result"] >= 100  # Auto-increment starts at 100


async def test_update_lead(client: Bitrix24Client) -> None:
    """Update an existing lead."""
    result = await client.update_lead(1, {"STATUS_ID": "PROCESSED"})
    assert result["result"] is True


# --- CRM Contact Tests ---


async def test_get_contacts(client: Bitrix24Client) -> None:
    """Fetch list of contacts."""
    result = await client.get_contacts()
    assert len(result["result"]) == 2


async def test_get_contact_by_id(client: Bitrix24Client) -> None:
    """Fetch a single contact."""
    result = await client.get_contact(1)
    assert result["result"]["LAST_NAME"] == "Смирнов"


# --- CRM Deal Tests ---


async def test_get_deals(client: Bitrix24Client) -> None:
    """Fetch list of deals."""
    result = await client.get_deals()
    assert len(result["result"]) == 2


async def test_get_deal_by_id(client: Bitrix24Client) -> None:
    """Fetch a single deal."""
    result = await client.get_deal(1)
    assert result["result"]["STAGE_ID"] == "PREPARATION"


async def test_create_deal(client: Bitrix24Client) -> None:
    """Create a new deal."""
    result = await client.create_deal({
        "TITLE": "Тестовая сделка",
        "OPPORTUNITY": "999999",
    })
    assert result["result"] >= 100


# --- CRM Company Tests ---


async def test_get_companies(client: Bitrix24Client) -> None:
    """Fetch list of companies."""
    result = await client.get_companies()
    assert len(result["result"]) == 2
    assert result["result"][0]["TITLE"] == "ООО Рога и Копыта"


async def test_get_company_by_id(client: Bitrix24Client) -> None:
    """Fetch a single company."""
    result = await client.get_company(2)
    assert result["result"]["TITLE"] == "ООО ТехСервис"


# --- Task Tests ---


async def test_get_tasks(client: Bitrix24Client) -> None:
    """Fetch list of tasks."""
    result = await client.get_tasks()
    assert "result" in result
    tasks = result["result"]["tasks"]
    assert len(tasks) == 2


async def test_get_task_by_id(client: Bitrix24Client) -> None:
    """Fetch a single task."""
    result = await client.get_task(1)
    assert result["result"]["task"]["title"] == "Подготовить КП для Рога и Копыта"


# --- Error Handling ---


async def test_bitrix24_error_on_invalid_method(client: Bitrix24Client) -> None:
    """Invalid method returns Bitrix24Error."""
    with pytest.raises(Bitrix24Error, match="ERROR_METHOD_NOT_FOUND"):
        await client._call("crm.nonexistent.method")


async def test_not_found_entity(client: Bitrix24Client) -> None:
    """Getting a non-existent entity returns error."""
    with pytest.raises(Bitrix24Error, match="NOT_FOUND"):
        await client.get_lead(99999)


async def test_bitrix24_error_carries_status_code(client: Bitrix24Client) -> None:
    """Bitrix24Error records the HTTP status — even for Bitrix's 200-with-error envelope."""
    with pytest.raises(Bitrix24Error) as exc:
        await client._call("crm.nonexistent.method")
    # Mock returns 200 + error body for invalid method (matches real Bitrix24)
    assert exc.value.status_code == 200
    assert exc.value.code == "ERROR_METHOD_NOT_FOUND"


# --- Rate Limiter Tests ---


async def test_rate_limiter_enforces_interval() -> None:
    """Rate limiter ensures minimum interval between acquires."""
    limiter = RateLimiter(max_per_second=10.0)  # 100ms interval

    start = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    # 3 acquires at 10/sec = at least 200ms gap (2 intervals)
    assert elapsed >= 0.18  # Allow small timing slack
