"""Write tools of the other connectors end to end: real httpx client, real timeout, and a mock
backend that commits the write, then stalls past the client's timeout."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from mcp.types import TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from tests.connector_cases import BAD_REQUEST, SERVERS, ServerCase, connected, watch_backend
from yzel.connectors.iiko import server as iiko
from yzel.connectors.iiko.client import IikoClient
from yzel.connectors.ozon import server as ozon
from yzel.connectors.ozon.client import OzonClient
from yzel.connectors.telegram import server as telegram
from yzel.connectors.telegram.client import TelegramClient
from yzel.core import writes
from yzel.core.tools import ToolKind

STALL_SECONDS = 0.8
CLIENT_TIMEOUT = 0.2


@pytest.fixture(autouse=True)
def _fresh_guard() -> None:
    writes.reset_guard()


@asynccontextmanager
async def serving(app: Starlette) -> AsyncIterator[str]:
    """Run `app` on a free port; yield its base URL."""
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task


def committing_then_stalling(committed: list[dict[str, Any]]) -> Any:
    """A route that records the request body (the write is committed), then answers too late."""

    async def route(request: Request) -> JSONResponse:
        committed.append(await request.json())
        await asyncio.sleep(STALL_SECONDS)
        return JSONResponse({"ok": True, "result": {}})

    return route


def body(result: Any) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(result.content[0].text)
    return parsed


async def test_iiko_timeout_after_commit_blocks_the_identical_resend() -> None:
    orders: list[dict[str, Any]] = []

    async def token(request: Request) -> JSONResponse:
        return JSONResponse({"token": "t"})

    app = Starlette(
        routes=[
            Route("/api/1/access_token", token, methods=["POST"]),
            Route("/api/1/deliveries/create", committing_then_stalling(orders), methods=["POST"]),
        ]
    )
    args = {"organization_id": "o", "terminal_group_id": "g", "order": {"phone": "+77001112233"}}
    async with serving(app) as url:
        iiko._client = IikoClient("k", base_url=url, timeout=CLIENT_TIMEOUT, max_per_second=100)
        try:
            first = await iiko.call_tool("iiko_create_delivery", dict(args))
            assert first.isError is True
            assert body(first)["outcome"] == "may_have_applied"
            assert body(first)["resend_safe"] is False
            assert body(first)["check_tool"] == "iiko_deliveries_by_phone"
            assert "iiko_deliveries_by_phone" in body(first)["message"]
            assert len(orders) == 1

            second = await iiko.call_tool("iiko_create_delivery", dict(args))
            assert body(second)["outcome"] == "duplicate_refused"
            assert len(orders) == 1  # the mock never saw the resend

            third = await iiko.call_tool("iiko_create_delivery", {**args, "again": True})
            assert body(third)["outcome"] == "may_have_applied"
            assert len(orders) == 2
        finally:
            iiko._client = None


async def test_telegram_timeout_after_send_blocks_the_identical_resend_and_names_no_check() -> None:
    sent: list[dict[str, Any]] = []
    app = Starlette(
        routes=[Route("/bot1:t/sendMessage", committing_then_stalling(sent), methods=["POST"])]
    )
    args = {"chat_id": 42, "text": "Заказ готов"}
    async with serving(app) as url:
        telegram._client = TelegramClient("1:t", base_url=url, timeout=CLIENT_TIMEOUT)
        try:
            first = await telegram.call_tool("tg_send_message", dict(args))
            assert first.isError is True
            assert body(first)["outcome"] == "may_have_applied"
            assert body(first)["resend_safe"] is False
            assert body(first)["check_tool"] is None
            assert "tg_" not in body(first)["message"]
            assert len(sent) == 1

            second = await telegram.call_tool("tg_send_message", dict(args))
            assert body(second)["outcome"] == "duplicate_refused"
            assert "tg_" not in body(second)["message"]
            assert len(sent) == 1  # the chat gets one message, not two
        finally:
            telegram._client = None


async def test_ozon_update_prices_timeout_says_resend_is_safe_and_does_not_guard() -> None:
    received: list[dict[str, Any]] = []
    app = Starlette(
        routes=[
            Route("/v1/product/import/prices", committing_then_stalling(received), methods=["POST"])
        ]
    )
    args = {"prices": [{"offer_id": "A-1", "price": "990"}]}
    async with serving(app) as url:
        ozon._client = OzonClient("1", "k", base_url=url, timeout=CLIENT_TIMEOUT)
        try:
            first = await ozon.call_tool("ozon_update_prices", dict(args))
            assert first.isError is True
            assert body(first)["outcome"] == "may_have_applied"
            assert body(first)["resend_safe"] is True
            assert len(received) == 1

            second = await ozon.call_tool("ozon_update_prices", dict(args))
            assert body(second)["outcome"] == "may_have_applied"
            assert len(received) == 2  # updates are idempotent: the resend goes through
        finally:
            ozon._client = None


WRITE_CASES = [(c, n) for c in SERVERS for n, k in c.kinds.items() if k is not ToolKind.READ]


def test_every_write_tool_has_minimal_arguments() -> None:
    declared = {n for c in SERVERS for n in c.write_calls}
    assert declared == {n for _, n in WRITE_CASES}


@pytest.mark.parametrize(("case", "tool"), WRITE_CASES, ids=lambda v: getattr(v, "id", v))
async def test_every_write_tool_goes_through_the_runner(
    case: ServerCase, tool: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A 400 from the backend on a write is `rejected`: only the runner produces that outcome."""
    monkeypatch.delenv("YZEL_READ_ONLY", raising=False)
    async with watch_backend(BAD_REQUEST) as (url, connections):
        case.point_at_backend(monkeypatch, url, tmp_path)
        async with connected(case) as session:
            result = await session.call_tool(tool, case.write_calls[tool])

    assert connections, "the write never reached the backend"
    assert result.isError is True
    block = result.content[0]
    assert isinstance(block, TextContent)
    assert json.loads(block.text)["outcome"] == "rejected"
