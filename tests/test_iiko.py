"""Tests for the iiko Cloud API client."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import httpx
import pytest
import uvicorn

from yzel.connectors.iiko.client import IikoClient, IikoError, RateLimiter
from tests import mock_iiko_server
from tests.mock_iiko_server import VALID_API_LOGIN, app

MOCK_PORT = 8183
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}"


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
                        f"{MOCK_URL}/api/1/access_token",
                        json={"apiLogin": VALID_API_LOGIN},
                        timeout=1.0,
                    )
                    if r.status_code == 200:
                        return
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        raise RuntimeError("Mock iiko server failed to start")

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
async def client(mock_server: str) -> AsyncGenerator[IikoClient, None]:
    c = IikoClient(VALID_API_LOGIN, base_url=mock_server, max_per_second=1000.0)
    yield c
    await c.close()


# --- Auth + token lifecycle ---


async def test_bad_api_login_raises(mock_server: str) -> None:
    bad = IikoClient("not-real", base_url=mock_server, max_per_second=1000.0)
    try:
        with pytest.raises(IikoError) as exc:
            await bad.get_organizations()
        assert exc.value.status_code == 401
        assert "apiLogin" in exc.value.message
    finally:
        await bad.close()


async def test_first_call_triggers_token_exchange(client: IikoClient) -> None:
    assert client._access_token is None
    orgs = await client.get_organizations()
    assert client._access_token is not None
    assert len(orgs) == 2


async def test_auto_refresh_on_401(client: IikoClient) -> None:
    # Warm up — mint a token
    await client.get_organizations()
    first_token = client._access_token

    # Server-side invalidation — next request gets 401, client should refresh+retry
    mock_iiko_server.invalidate_current_token()
    # Invalidating on the server means the client's cached token is no longer
    # valid; the retry path mints a new one and the call succeeds.
    orgs = await client.get_organizations()
    assert len(orgs) == 2
    assert client._access_token is not None
    assert client._access_token != first_token


# --- Organizations + topology ---


async def test_get_organizations_all(client: IikoClient) -> None:
    orgs = await client.get_organizations()
    assert {o["id"] for o in orgs} == {"org-1", "org-2"}


async def test_get_organizations_filtered(client: IikoClient) -> None:
    orgs = await client.get_organizations(organization_ids=["org-2"])
    assert len(orgs) == 1
    assert orgs[0]["name"] == "Ресторан Арбат"


async def test_get_terminal_groups(client: IikoClient) -> None:
    groups = await client.get_terminal_groups(organization_ids=["org-2"])
    assert len(groups) == 2
    assert {g["id"] for g in groups} == {"tg-2", "tg-3"}


# --- Menu + stocks ---


async def test_get_nomenclature(client: IikoClient) -> None:
    menu = await client.get_nomenclature("org-1")
    assert len(menu["products"]) == 2
    assert menu["products"][0]["name"] == "Капучино"


async def test_get_nomenclature_unknown_org_raises(client: IikoClient) -> None:
    with pytest.raises(IikoError) as exc:
        await client.get_nomenclature("unknown")
    assert exc.value.status_code == 400
    assert "не найдена" in exc.value.message


async def test_get_stop_list(client: IikoClient) -> None:
    stops = await client.get_stop_list(["org-1"])
    assert len(stops) == 1
    assert stops[0]["items"][0]["productId"] == "p-2"


# --- Deliveries ---


async def test_deliveries_by_phone(client: IikoClient) -> None:
    deliveries = await client.get_deliveries_by_phone(
        organization_ids=["org-1"], phone="+77011234567"
    )
    assert len(deliveries) == 1
    assert deliveries[0]["orders"][0]["total"] == 3200


async def test_create_delivery_round_trip(client: IikoClient) -> None:
    res = await client.create_delivery(
        organization_id="org-1",
        terminal_group_id="tg-1",
        order={
            "phone": "+77019998877",
            "items": [{"productId": "p-1", "amount": 2}],
        },
    )
    assert res["orderInfo"]["organizationId"] == "org-1"
    assert res["orderInfo"]["submitted"]["phone"] == "+77019998877"


# --- Reference data ---


async def test_get_order_types(client: IikoClient) -> None:
    types = await client.get_order_types(["org-1"])
    assert len(types) == 1
    assert {t["id"] for t in types[0]["items"]} == {"ot-dine-in", "ot-delivery"}


async def test_get_payment_types(client: IikoClient) -> None:
    pts = await client.get_payment_types(["org-1"])
    assert {p["id"] for p in pts} == {"pt-cash", "pt-card"}


async def test_get_employees(client: IikoClient) -> None:
    emps = await client.get_employees(["org-1"])
    assert len(emps) == 1
    assert emps[0]["lastName"] == "Петров"


# --- Rate limiter ---


async def test_rate_limiter_enforces_interval() -> None:
    import time as t

    limiter = RateLimiter(max_per_second=20.0)
    start = t.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    assert t.monotonic() - start >= 0.09
