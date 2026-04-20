"""Moysklad MCP Server.

Exposes Moysklad operations as MCP tools for AI assistants.
Bearer token auth — configured via credential vault.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from yzel.core.types import MoyskladCredential
from yzel.core.vault import CredentialVault

from .client import MoyskladClient, MoyskladError

server = Server("yzel-moysklad")

# Runtime state
_client: MoyskladClient | None = None
_connection_id: str | None = None


async def _ensure_client() -> MoyskladClient:
    global _client, _connection_id

    if _client is not None:
        return _client

    vault = CredentialVault()
    connections = vault.list_connections()
    ms_connections = [c for c in connections if c["service"] == "moysklad"]

    if not ms_connections:
        raise RuntimeError(
            "Нет настроенных подключений к МойСклад. Используйте 'yzel config add-moysklad'"
        )

    _connection_id = ms_connections[0]["id"]
    cred = vault.get(_connection_id)

    if not isinstance(cred, MoyskladCredential):
        raise RuntimeError(f"Неверный тип учётных данных для {_connection_id}")

    _client = MoyskladClient(cred.bearer_token)
    return _client


_ENTITY_TYPES = {
    "counterparty": {
        "name_ru": "контрагент",
        "list_method": "get_counterparties",
        "get_method": "get_counterparty",
        "create_method": "create_counterparty",
        "update_method": "update_counterparty",
    },
    "product": {
        "name_ru": "товар",
        "list_method": "get_products",
        "get_method": "get_product",
        "create_method": "create_product",
        "update_method": "update_product",
    },
    "customerorder": {
        "name_ru": "заказ покупателя",
        "list_method": "get_customer_orders",
        "get_method": "get_customer_order",
        "create_method": "create_customer_order",
        "update_method": "update_customer_order",
    },
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Moysklad tools."""
    return [
        Tool(
            name="moysklad_list",
            description=(
                "Получить список сущностей из МойСклад (контрагенты, товары, заказы). "
                "Поддерживает фильтрацию, поиск и раскрытие вложенных объектов (expand)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["counterparty", "product", "customerorder"],
                        "description": "Тип сущности",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное количество записей (по умолчанию 25, макс 1000)",
                        "default": 25,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Смещение для пагинации",
                        "default": 0,
                    },
                    "filter": {
                        "type": "string",
                        "description": "Фильтр МойСклад (например, 'name=ООО Рога')",
                    },
                    "search": {
                        "type": "string",
                        "description": "Полнотекстовый поиск",
                    },
                    "expand": {
                        "type": "string",
                        "description": (
                            "Раскрыть вложенные объекты (например, 'agent,organization'). "
                            "Без expand вложенные объекты возвращаются как UUID-ссылки."
                        ),
                    },
                    "order": {
                        "type": "string",
                        "description": "Сортировка (например, 'name,asc')",
                    },
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="moysklad_get",
            description="Получить одну сущность из МойСклад по ID (UUID)",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["counterparty", "product", "customerorder"],
                        "description": "Тип сущности",
                    },
                    "id": {
                        "type": "string",
                        "description": "UUID сущности",
                    },
                    "expand": {
                        "type": "string",
                        "description": "Раскрыть вложенные объекты",
                    },
                },
                "required": ["entity", "id"],
            },
        ),
        Tool(
            name="moysklad_create",
            description="Создать сущность в МойСклад",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["counterparty", "product", "customerorder"],
                        "description": "Тип сущности",
                    },
                    "fields": {
                        "type": "object",
                        "description": "Поля для создания",
                    },
                },
                "required": ["entity", "fields"],
            },
        ),
        Tool(
            name="moysklad_update",
            description="Обновить сущность в МойСклад",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["counterparty", "product", "customerorder"],
                        "description": "Тип сущности",
                    },
                    "id": {
                        "type": "string",
                        "description": "UUID сущности",
                    },
                    "fields": {
                        "type": "object",
                        "description": "Поля для обновления",
                    },
                },
                "required": ["entity", "id", "fields"],
            },
        ),
        Tool(
            name="moysklad_stock",
            description="Получить остатки товаров из МойСклад (по всем складам или по каждому складу)",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["all", "bystore"],
                        "description": "Режим: 'all' — сводные остатки, 'bystore' — по складам",
                        "default": "all",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное количество записей",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Смещение для пагинации",
                    },
                    "groupBy": {
                        "type": "string",
                        "enum": ["product", "variant"],
                        "description": "Группировка (только для режима 'all')",
                    },
                },
            },
        ),
        Tool(
            name="moysklad_organizations",
            description="Получить список юрлиц из МойСклад",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


def _as_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        client = await _ensure_client()

        if name == "moysklad_list":
            entity_type = arguments["entity"]
            meta = _ENTITY_TYPES[entity_type]
            method = getattr(client, meta["list_method"])
            return _as_text(
                await method(
                    limit=arguments.get("limit"),
                    offset=arguments.get("offset"),
                    filter_expr=arguments.get("filter"),
                    search=arguments.get("search"),
                    expand=arguments.get("expand"),
                    **(
                        {}
                        if entity_type != "customerorder"
                        else {"order": arguments.get("order")}
                    ),
                )
            )

        if name == "moysklad_get":
            entity_type = arguments["entity"]
            meta = _ENTITY_TYPES[entity_type]
            method = getattr(client, meta["get_method"])
            return _as_text(await method(arguments["id"], expand=arguments.get("expand")))

        if name == "moysklad_create":
            entity_type = arguments["entity"]
            meta = _ENTITY_TYPES[entity_type]
            method = getattr(client, meta["create_method"])
            return _as_text(await method(arguments["fields"]))

        if name == "moysklad_update":
            entity_type = arguments["entity"]
            meta = _ENTITY_TYPES[entity_type]
            method = getattr(client, meta["update_method"])
            return _as_text(await method(arguments["id"], arguments["fields"]))

        if name == "moysklad_stock":
            mode = arguments.get("mode", "all")
            if mode == "bystore":
                return _as_text(
                    await client.get_stock_by_store(
                        limit=arguments.get("limit"),
                        offset=arguments.get("offset"),
                    )
                )
            return _as_text(
                await client.get_stock_all(
                    limit=arguments.get("limit"),
                    offset=arguments.get("offset"),
                    group_by=arguments.get("groupBy"),
                )
            )

        if name == "moysklad_organizations":
            return _as_text(await client.get_organizations())

        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]

    except MoyskladError as exc:
        return [TextContent(type="text", text=f"Ошибка МойСклад: {exc.message}")]


async def main() -> None:
    """Run the Moysklad MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
