"""Tests for AmoCRM connector — client + mock server + token refresh."""

from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator

import httpx
import pytest
import uvicorn

from yzel.connectors.amocrm.client import AmoCRMClient, AmoCRMAuthError, AmoCRMError

from tests.mock_amocrm_server import (
    VALID_CLIENT_ID,
    VALID_CLIENT_SECRET,
    VALID_REDIRECT_URI,
    app,
    reset_state,
)

MOCK_PORT = 8180
MOCK_BASE = f"http://localhost:{MOCK_PORT}"

# Test-only placeholder tokens — not real credentials
_TEST_ACCESS = "test_access_value"  # noqa: S105
_TEST_REFRESH = "test_refresh_value"  # noqa: S105


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
                    await c.get(
                        f"http://127.0.0.1:{MOCK_PORT}/api/v4/account",
                        headers={"Authorization": f"Bearer {_TEST_ACCESS}"},
                    )
                return
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        raise RuntimeError("Mock AmoCRM server failed to start")

    async def stop(self) -> None:
        self._server.should_exit = True
        if self._task:
            await self._task


@pytest.fixture
async def mock_server() -> AsyncGenerator[str, None]:
    reset_state()  # Reset tokens between tests
    srv = _ServerThread(MOCK_PORT)
    await srv.start()
    yield MOCK_BASE
    await srv.stop()


@pytest.fixture
async def client(mock_server: str) -> AsyncGenerator[AmoCRMClient, None]:
    c = AmoCRMClient(
        subdomain="test",
        access_token=_TEST_ACCESS,
        refresh_token=_TEST_REFRESH,
        expires_at=time.time() + 1200,  # Valid for 20 min
        client_id=VALID_CLIENT_ID,
        client_secret=VALID_CLIENT_SECRET,
        redirect_uri=VALID_REDIRECT_URI,
    )
    c.base_url = mock_server  # Override to point at mock
    yield c
    await c.close()


# --- Lead Tests ---


async def test_get_leads(client: AmoCRMClient) -> None:
    """Fetch list of leads."""
    result = await client.get_leads()
    leads = result["_embedded"]["leads"]
    assert len(leads) == 3
    assert leads[0]["name"] == "Поставка офисного оборудования"


async def test_get_leads_with_query(client: AmoCRMClient) -> None:
    """Search leads by text query."""
    result = await client.get_leads(query="CRM")
    leads = result["_embedded"]["leads"]
    assert len(leads) == 1
    assert leads[0]["name"] == "Внедрение CRM-системы"


async def test_get_lead_by_id(client: AmoCRMClient) -> None:
    """Fetch single lead."""
    result = await client.get_lead(1)
    assert result["id"] == 1
    assert result["price"] == 250000


async def test_create_leads(client: AmoCRMClient) -> None:
    """Create leads (batch)."""
    result = await client.create_leads([
        {"name": "Тестовая сделка", "price": 100000},
    ])
    created = result["_embedded"]["leads"]
    assert len(created) == 1
    assert created[0]["id"] >= 100


async def test_update_lead(client: AmoCRMClient) -> None:
    """Update a lead."""
    result = await client.update_lead(1, {"price": 300000})
    assert result["price"] == 300000


# --- Contact Tests ---


async def test_get_contacts(client: AmoCRMClient) -> None:
    """Fetch contacts."""
    result = await client.get_contacts()
    contacts = result["_embedded"]["contacts"]
    assert len(contacts) == 2


async def test_get_contact_by_id(client: AmoCRMClient) -> None:
    """Fetch single contact."""
    result = await client.get_contact(1)
    assert result["name"] == "Алексей Смирнов"


# --- Company Tests ---


async def test_get_companies(client: AmoCRMClient) -> None:
    """Fetch companies."""
    result = await client.get_companies()
    companies = result["_embedded"]["companies"]
    assert len(companies) == 2
    assert companies[0]["name"] == "ООО Рога и Копыта"


async def test_get_company_by_id(client: AmoCRMClient) -> None:
    """Fetch single company."""
    result = await client.get_company(2)
    assert result["name"] == "ООО ТехСервис"


# --- Pipeline Tests ---


async def test_get_pipelines(client: AmoCRMClient) -> None:
    """Fetch all pipelines."""
    result = await client.get_pipelines()
    pipelines = result["_embedded"]["pipelines"]
    assert len(pipelines) == 2
    assert pipelines[0]["name"] == "Основная воронка"


async def test_get_pipeline_by_id(client: AmoCRMClient) -> None:
    """Fetch single pipeline."""
    result = await client.get_pipeline(1)
    assert result["name"] == "Основная воронка"
    assert result["is_main"] is True


# --- Account Tests ---


async def test_get_account(client: AmoCRMClient) -> None:
    """Fetch account info."""
    result = await client.get_account()
    assert result["name"] == "Тестовый аккаунт"
    assert result["currency"] == "RUB"


# --- Token Refresh Tests ---


async def test_auto_refresh_on_expired_token(mock_server: str) -> None:
    """Client auto-refreshes when token is about to expire."""
    refreshed_tokens: list[tuple[str, str, float]] = []

    def on_refresh(access: str, refresh: str, expires: float) -> None:
        refreshed_tokens.append((access, refresh, expires))

    c = AmoCRMClient(
        subdomain="test",
        access_token=_TEST_ACCESS,
        refresh_token=_TEST_REFRESH,
        expires_at=time.time() - 10,  # Already expired
        client_id=VALID_CLIENT_ID,
        client_secret=VALID_CLIENT_SECRET,
        redirect_uri=VALID_REDIRECT_URI,
        on_token_refresh=on_refresh,
    )
    c.base_url = mock_server

    # This should trigger a refresh before the actual request
    result = await c.get_account()
    assert result["name"] == "Тестовый аккаунт"

    # Verify refresh happened
    assert len(refreshed_tokens) == 1
    assert refreshed_tokens[0][0].startswith("refreshed_")

    await c.close()


async def test_refresh_with_bad_secret(mock_server: str) -> None:
    """Bad client_secret during refresh raises AmoCRMAuthError."""
    c = AmoCRMClient(
        subdomain="test",
        access_token=_TEST_ACCESS,
        refresh_token=_TEST_REFRESH,
        expires_at=time.time() - 10,
        client_id=VALID_CLIENT_ID,
        client_secret="wrong",
        redirect_uri=VALID_REDIRECT_URI,
    )
    c.base_url = mock_server

    with pytest.raises(AmoCRMAuthError, match="Ошибка обновления токена"):
        await c.get_account()

    await c.close()


# --- Error Handling ---


async def test_not_found_entity(client: AmoCRMClient) -> None:
    """Getting non-existent entity returns error."""
    with pytest.raises(AmoCRMError, match="не найден"):
        await client.get_lead(99999)


# --- Refresh-health guard (3-month silent-death) ---


async def test_days_since_refresh_defaults_to_zero_for_fresh_client(mock_server: str) -> None:
    """A client instantiated without an explicit timestamp is treated as just-refreshed."""
    c = AmoCRMClient(
        subdomain="test",
        access_token=_TEST_ACCESS,
        refresh_token=_TEST_REFRESH,
        expires_at=time.time() + 1200,
        client_id=VALID_CLIENT_ID,
        client_secret=VALID_CLIENT_SECRET,
        redirect_uri=VALID_REDIRECT_URI,
    )
    try:
        assert c.days_since_refresh() < 1.0
        assert c.days_until_refresh_expiry() > 80.0
    finally:
        await c.close()


async def test_days_until_refresh_expiry_reflects_stored_timestamp(mock_server: str) -> None:
    """An older refresh_token_updated_at produces a smaller remaining-window."""
    forty_days_ago = time.time() - 40 * 86400
    c = AmoCRMClient(
        subdomain="test",
        access_token=_TEST_ACCESS,
        refresh_token=_TEST_REFRESH,
        expires_at=time.time() + 1200,
        client_id=VALID_CLIENT_ID,
        client_secret=VALID_CLIENT_SECRET,
        redirect_uri=VALID_REDIRECT_URI,
        refresh_token_updated_at=forty_days_ago,
    )
    try:
        assert 39.0 < c.days_since_refresh() < 41.0
        assert 48.0 < c.days_until_refresh_expiry() < 52.0
    finally:
        await c.close()


async def test_ensure_refresh_fresh_no_op_when_recent(mock_server: str) -> None:
    """Recent refresh → ensure_refresh_fresh skips the network call."""
    c = AmoCRMClient(
        subdomain="test",
        access_token=_TEST_ACCESS,
        refresh_token=_TEST_REFRESH,
        expires_at=time.time() + 1200,
        client_id=VALID_CLIENT_ID,
        client_secret=VALID_CLIENT_SECRET,
        redirect_uri=VALID_REDIRECT_URI,
    )
    c.base_url = mock_server
    try:
        refreshed = await c.ensure_refresh_fresh(min_remaining_days=14.0)
        assert refreshed is False
    finally:
        await c.close()


async def test_ensure_refresh_fresh_forces_refresh_when_stale(mock_server: str) -> None:
    """Stale refresh → ensure_refresh_fresh triggers a refresh and updates the timestamp."""
    eighty_days_ago = time.time() - 80 * 86400
    c = AmoCRMClient(
        subdomain="test",
        access_token=_TEST_ACCESS,
        refresh_token=_TEST_REFRESH,
        expires_at=time.time() + 1200,  # Access token still valid
        client_id=VALID_CLIENT_ID,
        client_secret=VALID_CLIENT_SECRET,
        redirect_uri=VALID_REDIRECT_URI,
        refresh_token_updated_at=eighty_days_ago,
    )
    c.base_url = mock_server
    try:
        assert c.days_until_refresh_expiry() < 14.0
        refreshed = await c.ensure_refresh_fresh(min_remaining_days=14.0)
        assert refreshed is True
        # Timestamp reset to "now" — plenty of runway again
        assert c.days_since_refresh() < 1.0
        assert c.days_until_refresh_expiry() > 80.0
    finally:
        await c.close()


async def test_refresh_updates_timestamp_on_normal_auto_refresh(mock_server: str) -> None:
    """The auto-refresh path (expired access token) also bumps refresh_token_updated_at."""
    old_ts = time.time() - 60 * 86400
    c = AmoCRMClient(
        subdomain="test",
        access_token=_TEST_ACCESS,
        refresh_token=_TEST_REFRESH,
        expires_at=time.time() - 10,  # Forces refresh on next call
        client_id=VALID_CLIENT_ID,
        client_secret=VALID_CLIENT_SECRET,
        redirect_uri=VALID_REDIRECT_URI,
        refresh_token_updated_at=old_ts,
    )
    c.base_url = mock_server
    try:
        await c.get_account()
        assert c.days_since_refresh() < 1.0
    finally:
        await c.close()
