"""1C Enterprise MCP Server.

Exposes 1C OData operations as MCP tools for AI assistants.
Handles dynamic schema discovery and Cyrillic entity names.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from yzel import __version__
from yzel.core.discovery import discover_schema
from yzel.core.outcome import error_result
from yzel.core.tools import ToolKind, make_tool, refuse_if_read_only, visible_tools
from yzel.core.types import OneCCredential, SchemaEntity
from yzel.core.vault import CredentialVault
from yzel.core.writes import run_write

from .odata import OneCError, OneCODataClient, detect_deployment

server = Server("yzel-1c", version=__version__)

# Runtime state
_client: OneCODataClient | None = None
_schema: list[SchemaEntity] = []
_connection_id: str | None = None


def _credential_from_env() -> OneCCredential | None:
    """Read a 1C connection from YZEL_1C_URL / _USERNAME / _PASSWORD, or None if unset.

    This is how the Claude Desktop extension (.mcpb) passes its settings form. When set,
    it takes precedence over the vault. An empty password is valid — many 1C users have none.
    """
    url = os.environ.get("YZEL_1C_URL")
    if not url:
        return None

    username = os.environ.get("YZEL_1C_USERNAME")
    if not username:
        raise RuntimeError("Задан YZEL_1C_URL, но не задан YZEL_1C_USERNAME")

    return OneCCredential(
        name="env",
        host=url,
        username=username,
        password=os.environ.get("YZEL_1C_PASSWORD", ""),
        is_fresh=detect_deployment(url) == "fresh",
    )


def _credential_from_vault() -> OneCCredential:
    global _connection_id

    vault = CredentialVault()
    connections = vault.list_connections()
    onec_connections = [c for c in connections if c["service"] == "1c"]

    if not onec_connections:
        raise RuntimeError("Нет настроенных подключений к 1С. Используйте 'yzel config add-1c'")

    _connection_id = onec_connections[0]["id"]
    cred = vault.get(_connection_id)

    if not isinstance(cred, OneCCredential):
        raise RuntimeError(f"Неверный тип учётных данных для {_connection_id}")
    return cred


async def _ensure_client() -> OneCODataClient:
    global _client, _schema

    if _client is not None:
        return _client

    cred = _credential_from_env() or _credential_from_vault()

    _client = OneCODataClient(cred.host, cred.username, cred.password)
    _schema = await discover_schema(cred.host, cred.username, cred.password)

    return _client


TOOLS: list[Tool] = [
    make_tool(
        "onec_list_entities",
        "Показать доступные объекты в 1С (справочники, документы, регистры)",
        {"type": "object", "properties": {}},
        ToolKind.READ,
    ),
    make_tool(
        "onec_query",
        (
            "Запросить данные из 1С по имени объекта. "
            "Примеры: Catalog_Контрагенты, Document_РеализацияТоваровУслуг"
        ),
        {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Имя объекта OData (например, Catalog_Контрагенты)",
                },
                "top": {
                    "type": "integer",
                    "description": "Максимальное количество записей",
                    "default": 20,
                },
                "filter": {"type": "string", "description": "OData $filter выражение"},
                "select": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Поля для выборки",
                },
            },
            "required": ["entity"],
        },
        ToolKind.READ,
    ),
    make_tool(
        "onec_get",
        "Получить одну запись из 1С по GUID",
        {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Имя объекта OData"},
                "key": {"type": "string", "description": "GUID записи"},
            },
            "required": ["entity", "key"],
        },
        ToolKind.READ,
    ),
    make_tool(
        "onec_schema",
        "Показать поля конкретного объекта 1С",
        {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Имя объекта OData"},
            },
            "required": ["entity"],
        },
        ToolKind.READ,
    ),
    make_tool(
        "onec_count",
        "Подсчитать количество записей в объекте 1С",
        {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Имя объекта OData"},
                "filter": {"type": "string", "description": "OData $filter выражение"},
            },
            "required": ["entity"],
        },
        ToolKind.READ,
    ),
    make_tool(
        "onec_create",
        "Создать новую запись в 1С",
        {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Имя объекта OData"},
                "data": {"type": "object", "description": "Поля новой записи"},
            },
            "required": ["entity", "data"],
        },
        ToolKind.CREATE,
    ),
    make_tool(
        "onec_update",
        "Обновить существующую запись в 1С (PATCH)",
        {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Имя объекта OData"},
                "key": {"type": "string", "description": "GUID записи"},
                "data": {"type": "object", "description": "Изменяемые поля"},
            },
            "required": ["entity", "key", "data"],
        },
        ToolKind.UPDATE,
    ),
    make_tool(
        "onec_delete",
        "Пометить запись на удаление в 1С (устанавливает DeletionMark)",
        {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Имя объекта OData"},
                "key": {"type": "string", "description": "GUID записи"},
            },
            "required": ["entity", "key"],
        },
        ToolKind.DELETE,
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available 1C tools (only the read ones in read-only mode)."""
    return visible_tools(TOOLS)


def _as_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


_TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def _write(
    name: str, arguments: dict[str, Any], call: Callable[[], Awaitable[Any]]
) -> Awaitable[CallToolResult]:
    """Run one 1C write through the write runner."""
    return run_write(
        _TOOLS_BY_NAME[name],
        arguments,
        call,
        error_types=(OneCError,),
        check_tool="onec_query",
    )


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent] | CallToolResult:
    """Handle tool calls."""
    # First, before any client or credential is touched: hiding tools in list_tools is not enough.
    if (refused := refuse_if_read_only(TOOLS, name)) is not None:
        return refused
    try:
        client = await _ensure_client()

        if name == "onec_list_entities":
            return _as_text([e.entity_name for e in _schema])

        if name == "onec_query":
            results = await client.get_entity_list(
                entity=arguments["entity"],
                top=arguments.get("top", 20),
                filter_expr=arguments.get("filter"),
                select=arguments.get("select"),
            )
            return _as_text(results)

        if name == "onec_get":
            result = await client.get_entity(arguments["entity"], arguments["key"])
            if result is None:
                return [TextContent(type="text", text="Запись не найдена")]
            return _as_text(result)

        if name == "onec_schema":
            entity_name = arguments["entity"]
            matching = [e for e in _schema if e.entity_name == entity_name]
            if not matching:
                return [
                    TextContent(type="text", text=f"Объект '{entity_name}' не найден в метаданных")
                ]
            schema = matching[0]
            return _as_text(
                [
                    {"name": f.name, "type": f.field_type, "nullable": f.nullable}
                    for f in schema.fields
                ]
            )

        if name == "onec_count":
            total = await client.count_entities(
                arguments["entity"], filter_expr=arguments.get("filter")
            )
            return [TextContent(type="text", text=str(total))]

        if name == "onec_create":
            return await _write(
                name,
                arguments,
                lambda: client.create_entity(arguments["entity"], arguments["data"]),
            )

        if name == "onec_update":
            return await _write(
                name,
                arguments,
                lambda: client.update_entity(
                    arguments["entity"], arguments["key"], arguments["data"]
                ),
            )

        if name == "onec_delete":

            async def delete() -> str:
                await client.delete_entity(arguments["entity"], arguments["key"])
                return "Запись помечена на удаление"

            return await _write(name, arguments, delete)

        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]

    except OneCError as exc:
        return error_result(f"Ошибка 1С: {exc.message}")


async def main() -> None:
    """Run the 1C MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    """Console-script entry point (see [project.scripts]). Sync wrapper for main()."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
