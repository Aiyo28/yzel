"""Tool registry: every tool is built with a `ToolKind`, and the kind drives safety.

`make_tool` is the only way servers build a `Tool`, and it requires a kind, so a tool cannot
ship without MCP annotations. The kind is stored in the tool's `_meta` (`kind_of` reads only
that); the annotations are derived from it for clients. Read-only mode (`YZEL_READ_ONLY`)
hides non-READ tools from the list and fails closed in the handler: only listed READ tools
may run, because a client may hold a cached list or guess a name.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from mcp.types import CallToolResult, Tool, ToolAnnotations

from .outcome import Outcome, outcome_result

READ_ONLY_ENV = "YZEL_READ_ONLY"
_KIND_META = "yzel/kind"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

_AGAIN_PROPERTY = {
    "type": "boolean",
    "description": (
        "Отправить повторно, даже если такой же запрос уже был за последние 10 минут. "
        "Только после проверки, что первого нет."
    ),
}


class ToolKind(StrEnum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


# MCP spec: destructiveHint true = may overwrite or remove, false = only adds.
_ANNOTATIONS: dict[ToolKind, ToolAnnotations] = {
    ToolKind.READ: ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    ToolKind.CREATE: ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
    ),
    ToolKind.UPDATE: ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True
    ),
    ToolKind.DELETE: ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=True
    ),
}


def make_tool(name: str, description: str, input_schema: dict[str, Any], kind: ToolKind) -> Tool:
    """Build a `Tool` annotated for `kind`. CREATE tools also get an optional `again` flag."""
    schema = input_schema
    if kind is ToolKind.CREATE:
        properties = {**input_schema.get("properties", {}), "again": dict(_AGAIN_PROPERTY)}
        schema = {**input_schema, "properties": properties}
    return Tool(
        name=name,
        description=description,
        inputSchema=schema,
        annotations=_ANNOTATIONS[kind].model_copy(),
        _meta={_KIND_META: kind.value},
    )


def kind_of(tool: Tool) -> ToolKind:
    """The kind `make_tool` stamped on the tool; raises if it was built another way."""
    raw = str((tool.meta or {}).get(_KIND_META))
    try:
        return ToolKind(raw)
    except ValueError:
        raise ValueError(f"У инструмента {tool.name} нет известного вида ({_KIND_META})") from None


def read_only_enabled() -> bool:
    return os.environ.get(READ_ONLY_ENV, "").strip().lower() in _TRUE_VALUES


def visible_tools(tools: Sequence[Tool]) -> list[Tool]:
    """All tools, or only READ tools when read-only mode is on."""
    if not read_only_enabled():
        return list(tools)
    return [t for t in tools if kind_of(t) is ToolKind.READ]


def refuse_if_read_only(tools: Sequence[Tool], name: str) -> CallToolResult | None:
    """None if the call may run; read-only: `refused` unless `name` is a listed READ tool."""
    if not read_only_enabled():
        return None
    if any(t.name == name and kind_of(t) is ToolKind.READ for t in tools):
        return None
    return outcome_result(
        Outcome.REFUSED,
        f"Инструмент недоступен в режиме «только чтение» ({READ_ONLY_ENV}). Запрос не отправлен.",
    )
