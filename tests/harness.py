"""Shared plumbing for the write tests: a real HTTP backend, a stalling route, a body reader."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from mcp.types import CallToolResult, TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

STALL_SECONDS = 0.8
CLIENT_TIMEOUT = 0.2


@asynccontextmanager
async def serving(app: Starlette) -> AsyncIterator[str]:
    """Run `app` on a free port; yield its bare `http://127.0.0.1:port`."""
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


def committing_then_stalling(committed: list[dict[str, Any]], reply: Any = None) -> Any:
    """A route that records the request body (the write is committed), then answers too late."""

    async def route(request: Request) -> JSONResponse:
        committed.append(await request.json())
        await asyncio.sleep(STALL_SECONDS)
        return JSONResponse({"ok": True, "result": {}} if reply is None else reply)

    return route


def body(result: CallToolResult) -> dict[str, Any]:
    """The JSON object a write tool answered with."""
    block = result.content[0]
    assert isinstance(block, TextContent)
    parsed: dict[str, Any] = json.loads(block.text)
    return parsed
