"""1C write tools end to end: real httpx client, real timeout, mock 1C that commits then stalls."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from yzel.connectors.onec import server as onec
from yzel.connectors.onec.odata import OneCODataClient
from yzel.core import writes

PORT = 8184
BASE = f"http://127.0.0.1:{PORT}/odata"
STALL_SECONDS = 0.8
CLIENT_TIMEOUT = 0.2

created: list[dict[str, Any]] = []


async def _create_slow(request: Request) -> JSONResponse:
    """Commits the record, then answers after the client has given up."""
    created.append(await request.json())
    await asyncio.sleep(STALL_SECONDS)
    return JSONResponse({"Ref_Key": "new"}, status_code=201)


async def _bad_request(request: Request) -> JSONResponse:
    return JSONResponse(
        {"odata.error": {"code": "400", "message": {"lang": "ru", "value": "Не заполнено ИНН"}}},
        status_code=400,
    )


mock = Starlette(
    routes=[
        Route("/odata/Catalog_Slow", _create_slow, methods=["POST"]),
        Route("/odata/Catalog_Bad", _bad_request, methods=["POST", "GET"]),
    ]
)


@pytest.fixture
async def one_c() -> AsyncGenerator[None, None]:
    server = uvicorn.Server(uvicorn.Config(mock, host="127.0.0.1", port=PORT, log_level="error"))
    task = asyncio.create_task(server.serve())
    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.05)
    created.clear()
    writes.reset_guard()
    onec._client = OneCODataClient(BASE, "admin", "test", timeout=CLIENT_TIMEOUT)
    onec._schema = []
    yield
    onec._client = None
    server.should_exit = True
    await task


def body(result: Any) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(result.content[0].text)
    return parsed


async def test_timeout_after_commit_blocks_the_identical_resend(one_c: None) -> None:
    args = {"entity": "Catalog_Slow", "data": {"Description": "ООО Ромашка"}}

    first = await onec.call_tool("onec_create", dict(args))
    assert first.isError is True
    assert body(first)["outcome"] == "may_have_applied"
    assert body(first)["resend_safe"] is False
    assert "onec_query" in body(first)["message"]
    assert len(created) == 1  # 1C committed it

    second = await onec.call_tool("onec_create", dict(args))
    assert body(second)["outcome"] == "duplicate_refused"
    assert len(created) == 1  # the mock never saw a second request

    third = await onec.call_tool("onec_create", {**args, "again": True})
    assert body(third)["outcome"] == "may_have_applied"
    assert len(created) == 2


async def test_1c_400_on_create_is_rejected_with_the_reason(one_c: None) -> None:
    result = await onec.call_tool("onec_create", {"entity": "Catalog_Bad", "data": {}})
    assert result.isError is True
    assert body(result)["outcome"] == "rejected"
    assert "Не заполнено ИНН" in body(result)["message"]


async def test_connection_refused_is_not_sent(one_c: None) -> None:
    onec._client = OneCODataClient("http://127.0.0.1:1/odata", "a", "b", timeout=CLIENT_TIMEOUT)
    result = await onec.call_tool("onec_create", {"entity": "Catalog_X", "data": {}})
    assert body(result)["outcome"] == "not_sent"


async def test_read_tool_1c_error_is_an_error_result(one_c: None) -> None:
    result = await onec.call_tool("onec_query", {"entity": "Catalog_Bad"})
    assert result.isError is True
    assert "Не заполнено ИНН" in result.content[0].text
