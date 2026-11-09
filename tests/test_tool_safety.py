"""Every tool declares what it does to the data, and read-only mode enforces it.

Checked at the MCP boundary (`tools/list`, `tools/call`) over an in-memory session, so the
test survives however a server builds its tools. Per-connector wiring lives in
`connector_cases.py`.
"""

from __future__ import annotations

import json
import pkgutil
from pathlib import Path
from typing import Any

import pytest
from mcp.types import CallToolResult, TextContent, Tool

import yzel.connectors
from tests.connector_cases import (
    BAD_REQUEST,
    SERVERS,
    WRITE_CASES,
    ServerCase,
    connected,
    watch_backend,
)
from tests.harness import body
from yzel.core.tools import ToolKind, kind_of, make_tool

ROOT = Path(__file__).resolve().parent.parent


# (readOnlyHint, destructiveHint, idempotentHint) per kind, from the spec.
ANNOTATIONS: dict[ToolKind, tuple[bool | None, bool | None, bool | None]] = {
    ToolKind.READ: (True, None, None),
    ToolKind.CREATE: (False, False, False),
    ToolKind.UPDATE: (False, True, True),
    ToolKind.DELETE: (False, True, True),
}


@pytest.fixture(autouse=True)
def _read_only_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YZEL_READ_ONLY", raising=False)


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_every_listed_tool_carries_annotations_matching_its_kind(case: ServerCase) -> None:
    async with connected(case) as session:
        tools = (await session.list_tools()).tools

    assert {t.name for t in tools} == set(case.kinds)
    for tool in tools:
        assert tool.annotations is not None, f"{tool.name} has no annotations"
        got = tool.annotations
        assert (got.readOnlyHint, got.destructiveHint, got.idempotentHint) == ANNOTATIONS[
            case.kinds[tool.name]
        ], tool.name
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


async def _refused_call(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> tuple[CallToolResult, list[bytes]]:
    """Call `name` with no arguments in read-only mode; also return the backend's connections."""
    monkeypatch.setenv("YZEL_READ_ONLY", "1")
    async with watch_backend() as (url, connections):
        case.point_at_backend(monkeypatch, url, tmp_path)
        async with connected(case) as session:
            # Like a real client: list first (the server caches that list), then call by name.
            await session.list_tools()
            result = await session.call_tool(name, {})
    return result, connections


def _assert_refused(result: CallToolResult, connections: list[bytes]) -> None:
    assert result.isError is True
    out = body(result)
    assert out["outcome"] == "refused"
    assert "YZEL_READ_ONLY" in out["message"]
    assert connections == [], "a request reached the backend"


@pytest.mark.parametrize(("case", "tool"), WRITE_CASES, ids=lambda v: getattr(v, "id", v))
async def test_read_only_mode_refuses_a_hidden_write_tool_without_touching_the_backend(
    case: ServerCase, tool: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A client with a cached tool list, or an agent guessing the name, still calls it."""
    result, connections = await _refused_call(case, monkeypatch, tmp_path, tool)

    _assert_refused(result, connections)


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_read_only_mode_refuses_a_name_the_server_does_not_list(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fail closed: a write branch missing from the tool list must not run either."""
    result, connections = await _refused_call(case, monkeypatch, tmp_path, "no_such_tool")

    _assert_refused(result, connections)


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_read_only_mode_still_serves_read_tools(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The refusal is for everything but listed READ tools: a read call reaches the backend."""
    monkeypatch.setenv("YZEL_READ_ONLY", "1")
    tool, arguments = case.read_call
    async with watch_backend() as (url, connections):
        case.point_at_backend(monkeypatch, url, tmp_path)
        async with connected(case) as session:
            await session.call_tool(tool, arguments)

    assert connections, "the read call never reached the backend"


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_a_typed_backend_error_on_a_read_is_an_error_result(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The model must see `isError`, not a successful-looking result that says "Ошибка"."""
    tool, arguments = case.read_call
    async with watch_backend(BAD_REQUEST) as (url, connections):
        case.point_at_backend(monkeypatch, url, tmp_path)
        async with connected(case) as session:
            result = await session.call_tool(tool, arguments)

    assert connections, "the read call never reached the backend"
    assert result.isError is True
    block = result.content[0]
    assert isinstance(block, TextContent)
    # The server's own message, not the SDK's fallback text for an escaped exception.
    assert block.text.startswith("Ошибка "), block.text


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_an_unknown_tool_name_is_an_error_result(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async with watch_backend() as (url, _):
        case.point_at_backend(monkeypatch, url, tmp_path)
        async with connected(case) as session:
            result = await session.call_tool("no_such_tool", {})

    assert result.isError is True
    block = result.content[0]
    assert isinstance(block, TextContent)
    assert "Неизвестный инструмент" in block.text


def test_every_connector_package_has_a_server_case() -> None:
    packages = {m.name for m in pkgutil.iter_modules(yzel.connectors.__path__)}

    assert packages == {c.id for c in SERVERS}


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


def test_kind_of_rejects_a_tool_not_built_by_make_tool() -> None:
    with pytest.raises(ValueError):
        kind_of(Tool(name="bare", inputSchema={"type": "object"}))


def test_onec_extension_checkbox_defaults_to_read_only_and_reaches_the_server() -> None:
    """The .mcpb host passes the checkbox as the env var the server reads."""
    manifest = json.loads((ROOT / "extensions" / "1c" / "manifest.json").read_text("utf-8"))

    assert manifest["user_config"]["read_only"]["type"] == "boolean"
    assert manifest["user_config"]["read_only"]["default"] is True
    env = manifest["server"]["mcp_config"]["env"]
    assert env["YZEL_READ_ONLY"] == "${user_config.read_only}"
