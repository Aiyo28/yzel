"""Tool registry: every tool is built with a `ToolKind`, and the kind drives safety.

`make_tool` is the only way servers build a `Tool`, and it requires a kind, so a tool cannot
ship without MCP annotations. The annotations are the single source of truth: `kind_of` reads
the kind back from them. Read-only mode (`YZEL_READ_ONLY`) hides non-READ tools from the
list and, because a client may hold a cached list or guess a name, refuses their calls too.
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
        properties = {**input_schema.get("properties", {}), "again": _AGAIN_PROPERTY}
        schema = {**input_schema, "properties": properties}
    return Tool(
        name=name,
        description=description,
        inputSchema=schema,
        annotations=_ANNOTATIONS[kind].model_copy(),
        # The spec's hint table gives UPDATE and DELETE identical annotations, so DELETE is
        # marked in `_meta` to let `kind_of` tell them apart. Safety never depends on it.
        _meta={_KIND_META: kind.value} if kind is ToolKind.DELETE else None,
    )


def kind_of(tool: Tool) -> ToolKind:
    """Recover a tool's kind from its annotations."""
    ann = tool.annotations
    if ann is None:
        raise ValueError(f"У инструмента {tool.name} нет аннотаций")
    if ann.readOnlyHint:
        return ToolKind.READ
    if ann.destructiveHint is False:
        return ToolKind.CREATE
    if tool.meta and tool.meta.get(_KIND_META) == ToolKind.DELETE:
        return ToolKind.DELETE
    return ToolKind.UPDATE


def read_only_enabled() -> bool:
    return os.environ.get(READ_ONLY_ENV, "").strip().lower() in _TRUE_VALUES


def visible_tools(tools: Sequence[Tool]) -> list[Tool]:
    """All tools, or only READ tools when read-only mode is on."""
    if not read_only_enabled():
        return list(tools)
    return [t for t in tools if kind_of(t) is ToolKind.READ]


def refuse_if_read_only(tools: Sequence[Tool], name: str) -> CallToolResult | None:
    """A `refused` result when read-only mode is on and `name` is a write tool, else None."""
    if not read_only_enabled():
        return None
    for tool in tools:
        if tool.name == name and kind_of(tool) is not ToolKind.READ:
            return outcome_result(
                Outcome.REFUSED,
                f"Включён режим «только чтение» ({READ_ONLY_ENV}). Запрос не отправлен.",
            )
    return None
