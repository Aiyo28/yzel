"""Every tool declares what it does to the data, and read-only mode enforces it.

Checked at the MCP boundary (`tools/list`, `tools/call`) over an in-memory session, so the
test survives however a server builds its tools. To cover another server, append one entry
to `SERVERS`.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession
from mcp.server import Server
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, Tool

from yzel.connectors.onec import server as onec_server
from yzel.core.tools import ToolKind, kind_of, make_tool

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ServerCase:
    """One connector server plus the kind each of its tools must have."""

    id: str
    server: Server[Any, Any]
    kinds: dict[str, ToolKind]
    # A write tool and arguments that would reach the backend if it were not refused.
    write_call: tuple[str, dict[str, Any]]
    # Env vars that point the server at a backend we can watch (set by `watch_backend`).
    point_at_backend: Callable[[pytest.MonkeyPatch, str], None]


def _point_onec(mp: pytest.MonkeyPatch, url: str) -> None:
    mp.setenv("YZEL_1C_URL", url)
    mp.setenv("YZEL_1C_USERNAME", "admin")
    mp.setenv("YZEL_1C_PASSWORD", "test")


SERVERS = [
    ServerCase(
        id="onec",
        server=onec_server.server,
        kinds={
            "onec_list_entities": ToolKind.READ,
            "onec_query": ToolKind.READ,
            "onec_get": ToolKind.READ,
            "onec_schema": ToolKind.READ,
            "onec_count": ToolKind.READ,
            "onec_create": ToolKind.CREATE,
            "onec_update": ToolKind.UPDATE,
            "onec_delete": ToolKind.DELETE,
        },
        write_call=("onec_delete", {"entity": "Catalog_Контрагенты", "key": "x"}),
        point_at_backend=_point_onec,
    ),
]

ANNOTATIONS = {
    ToolKind.READ: dict(readOnlyHint=True, destructiveHint=None, idempotentHint=None),
    ToolKind.CREATE: dict(readOnlyHint=False, destructiveHint=False, idempotentHint=False),
    ToolKind.UPDATE: dict(readOnlyHint=False, destructiveHint=True, idempotentHint=True),
    ToolKind.DELETE: dict(readOnlyHint=False, destructiveHint=True, idempotentHint=True),
}


@asynccontextmanager
async def connected(case: ServerCase) -> AsyncIterator[ClientSession]:
    async with create_connected_server_and_client_session(case.server) as session:
        yield session


@asynccontextmanager
async def watch_backend() -> AsyncIterator[tuple[str, list[bytes]]]:
    """A listener that records every connection made to it: proof a request was (not) sent."""
    connections: list[bytes] = []

    async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        connections.append(await reader.read(1))
        writer.close()

    srv = await asyncio.start_server(on_connect, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/odata/standard.odata", connections
    finally:
        srv.close()
        await srv.wait_closed()


def _payload(result: CallToolResult) -> dict[str, Any]:
    text = result.content[0].text  # type: ignore[union-attr]
    loaded: dict[str, Any] = json.loads(text)
    return loaded


@pytest.fixture(autouse=True)
def _reset_onec_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(onec_server, "_client", None)
    monkeypatch.delenv("YZEL_READ_ONLY", raising=False)


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_every_listed_tool_carries_annotations_matching_its_kind(case: ServerCase) -> None:
    async with connected(case) as session:
        tools = (await session.list_tools()).tools

    assert {t.name for t in tools} == set(case.kinds)
    for tool in tools:
        assert tool.annotations is not None, f"{tool.name} has no annotations"
        want = ANNOTATIONS[case.kinds[tool.name]]
        got = tool.annotations
        assert (got.readOnlyHint, got.destructiveHint, got.idempotentHint) == (
            want["readOnlyHint"],
            want["destructiveHint"],
            want["idempotentHint"],
        ), tool.name
        assert got.openWorldHint is True, tool.name
        assert kind_of(tool) is case.kinds[tool.name]


@pytest.mark.parametrize("flag", ["1", "true", "TRUE", "yes", "on"])
@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_read_only_mode_lists_exactly_the_read_tools(
    case: ServerCase, flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YZEL_READ_ONLY", flag)
    async with connected(case) as session:
        listed = {t.name for t in (await session.list_tools()).tools}

    assert listed == {n for n, k in case.kinds.items() if k is ToolKind.READ}


@pytest.mark.parametrize("flag", ["", "0", "false", "no", "off"])
@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_other_values_leave_every_tool_listed(
    case: ServerCase, flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YZEL_READ_ONLY", flag)
    async with connected(case) as session:
        listed = {t.name for t in (await session.list_tools()).tools}

    assert listed == set(case.kinds)


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_read_only_mode_refuses_a_hidden_write_tool_without_touching_the_backend(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A client with a cached tool list, or an agent guessing the name, still calls it."""
    monkeypatch.setenv("YZEL_READ_ONLY", "1")
    tool, arguments = case.write_call
    vault_lookups: list[str] = []
    monkeypatch.setattr(
        onec_server, "_credential_from_vault", lambda: vault_lookups.append("vault") or 1 / 0
    )
    async with watch_backend() as (url, connections):
        case.point_at_backend(monkeypatch, url)
        async with connected(case) as session:
            result = await session.call_tool(tool, arguments)

    assert result.isError is True
    body = _payload(result)
    assert body["outcome"] == "refused"
    assert "YZEL_READ_ONLY" in body["message"]
    assert connections == []
    assert vault_lookups == []
    assert onec_server._client is None


async def test_read_only_mode_still_serves_read_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal is for writes only: a read call gets past it to the backend."""
    monkeypatch.setenv("YZEL_READ_ONLY", "1")
    async with watch_backend() as (url, connections):
        _point_onec(monkeypatch, url)
        async with connected(SERVERS[0]) as session:
            await session.call_tool("onec_count", {"entity": "Catalog_Контрагенты"})

    assert connections, "the read call never reached the backend"


def test_a_tool_cannot_be_built_without_a_kind() -> None:
    with pytest.raises(TypeError):
        make_tool("t", "d", {"type": "object"})  # type: ignore[call-arg]


@pytest.mark.parametrize("kind", list(ToolKind))
def test_make_tool_round_trips_kind_and_keeps_callers_schema_intact(kind: ToolKind) -> None:
    schema: dict[str, Any] = {"type": "object", "properties": {"a": {"type": "string"}}}
    tool = make_tool("t", "d", schema, kind)

    assert kind_of(tool) is kind
    assert schema == {"type": "object", "properties": {"a": {"type": "string"}}}
    has_again = "again" in tool.inputSchema["properties"]
    assert has_again is (kind is ToolKind.CREATE)
    if has_again:
        assert tool.inputSchema["properties"]["again"]["type"] == "boolean"
        assert "again" not in tool.inputSchema.get("required", [])


def test_kind_of_rejects_a_tool_built_without_annotations() -> None:
    with pytest.raises(ValueError):
        kind_of(Tool(name="bare", inputSchema={"type": "object"}))


def test_onec_extension_checkbox_defaults_to_read_only_and_reaches_the_server() -> None:
    """The .mcpb host passes the checkbox as the env var the server reads."""
    manifest = json.loads((ROOT / "extensions" / "1c" / "manifest.json").read_text("utf-8"))

    assert manifest["user_config"]["read_only"]["type"] == "boolean"
    assert manifest["user_config"]["read_only"]["default"] is True
    env = manifest["server"]["mcp_config"]["env"]
    assert env["YZEL_READ_ONLY"] == "${user_config.read_only}"
