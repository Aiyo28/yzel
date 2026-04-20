"""1C Enterprise MCP Server.

Exposes 1C OData operations as MCP tools for AI assistants.
Handles dynamic schema discovery and Cyrillic entity names.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from yzel.core.discovery import discover_schema
from yzel.core.types import OneCCredential, SchemaEntity
from yzel.core.vault import CredentialVault

from .odata import OneCError, OneCODataClient

server = Server("yzel-1c")

# Runtime state
_client: OneCODataClient | None = None
_schema: list[SchemaEntity] = []
_connection_id: str | None = None


async def _ensure_client() -> OneCODataClient:
    global _client, _schema, _connection_id

    if _client is not None:
        return _client

    vault = CredentialVault()
    connections = vault.list_connections()
    onec_connections = [c for c in connections if c["service"] == "1c"]

    if not onec_connections:
        raise RuntimeError("Нет настроенных подключений к 1С. Используйте 'yzel config add-1c'")

    _connection_id = onec_connections[0]["id"]
    cred = vault.get(_connection_id)

    if not isinstance(cred, OneCCredential):
        raise RuntimeError(f"Неверный тип учётных данных для {_connection_id}")

    _client = OneCODataClient(cred.host, cred.username, cred.password)
    _schema = await discover_schema(cred.host, cred.username, cred.password)

    return _client


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available 1C tools."""
    return [
        Tool(
            name="onec_list_entities",
            description="Показать доступные объекты в 1С (справочники, документы, регистры)",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="onec_query",
            description="Запросить данные из 1С по имени объекта. Примеры: Catalog_Контрагенты, Document_РеализацияТоваровУслуг",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Имя объекта OData (например, Catalog_Контрагенты)"},
                    "top": {"type": "integer", "description": "Максимальное количество записей", "default": 20},
                    "filter": {"type": "string", "description": "OData $filter выражение"},
                    "select": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Поля для выборки",
                    },
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="onec_get",
            description="Получить одну запись из 1С по GUID",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Имя объекта OData"},
                    "key": {"type": "string", "description": "GUID записи"},
                },
                "required": ["entity", "key"],
            },
        ),
        Tool(
            name="onec_schema",
            description="Показать поля конкретного объекта 1С",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Имя объекта OData"},
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="onec_count",
            description="Подсчитать количество записей в объекте 1С",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Имя объекта OData"},
                    "filter": {"type": "string", "description": "OData $filter выражение"},
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="onec_create",
            description="Создать новую запись в 1С",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Имя объекта OData"},
                    "data": {"type": "object", "description": "Поля новой записи"},
                },
                "required": ["entity", "data"],
            },
        ),
        Tool(
            name="onec_update",
            description="Обновить существующую запись в 1С (PATCH)",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Имя объекта OData"},
                    "key": {"type": "string", "description": "GUID записи"},
                    "data": {"type": "object", "description": "Изменяемые поля"},
                },
                "required": ["entity", "key", "data"],
            },
        ),
        Tool(
            name="onec_delete",
            description="Пометить запись на удаление в 1С (устанавливает DeletionMark)",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Имя объекта OData"},
                    "key": {"type": "string", "description": "GUID записи"},
                },
                "required": ["entity", "key"],
            },
        ),
    ]


def _as_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
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
                [{"name": f.name, "type": f.field_type, "nullable": f.nullable} for f in schema.fields]
            )

        if name == "onec_count":
            total = await client.count_entities(
                arguments["entity"], filter_expr=arguments.get("filter")
            )
            return [TextContent(type="text", text=str(total))]

        if name == "onec_create":
            created = await client.create_entity(arguments["entity"], arguments["data"])
            return _as_text(created)

        if name == "onec_update":
            updated = await client.update_entity(
                arguments["entity"], arguments["key"], arguments["data"]
            )
            return _as_text(updated)

        if name == "onec_delete":
            await client.delete_entity(arguments["entity"], arguments["key"])
            return [TextContent(type="text", text="Запись помечена на удаление")]

        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]

    except OneCError as exc:
        return [TextContent(type="text", text=f"Ошибка 1С: {exc.message}")]


async def main() -> None:
    """Run the 1C MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
