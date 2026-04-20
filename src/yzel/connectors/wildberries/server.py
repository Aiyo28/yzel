"""Wildberries Seller API MCP Server.

Exposes WB Seller operations as MCP tools. Tool descriptions are Russian first,
matching the RU-first docs rule in CLAUDE.md. Errors surface as WB error text
rather than raw httpx exceptions.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from yzel.core.types import WildberriesCredential
from yzel.core.vault import CredentialVault

from .client import WildberriesClient, WildberriesError

server = Server("yzel-wildberries")

_client: WildberriesClient | None = None
_connection_id: str | None = None


async def _ensure_client() -> WildberriesClient:
    global _client, _connection_id

    if _client is not None:
        return _client

    vault = CredentialVault()
    connections = vault.list_connections()
    wb_connections = [c for c in connections if c["service"] == "wildberries"]

    if not wb_connections:
        raise RuntimeError(
            "Нет настроенных подключений к Wildberries. Используйте 'yzel config add-wb'"
        )

    _connection_id = wb_connections[0]["id"]
    cred = vault.get(_connection_id)

    if not isinstance(cred, WildberriesCredential):
        raise RuntimeError(f"Неверный тип учётных данных для {_connection_id}")

    _client = WildberriesClient(cred.api_key)
    return _client


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List Wildberries Seller tools."""
    return [
        Tool(
            name="wb_seller_info",
            description="Показать информацию о продавце Wildberries",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="wb_list_warehouses",
            description="Список складов FBS продавца",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="wb_new_orders",
            description="Новые сборочные задания (очередь FBS)",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="wb_get_orders",
            description="Сборочные задания за период (FBS)",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_from": {"type": "integer", "description": "Unix timestamp начала периода"},
                    "date_to": {"type": "integer", "description": "Unix timestamp конца периода (опционально)"},
                    "limit": {"type": "integer", "default": 1000},
                    "next_cursor": {"type": "integer", "default": 0},
                },
                "required": ["date_from"],
            },
        ),
        Tool(
            name="wb_get_stocks",
            description="Остатки по SKU на указанном складе",
            inputSchema={
                "type": "object",
                "properties": {
                    "warehouse_id": {"type": "integer"},
                    "skus": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список штрихкодов (SKU)",
                    },
                },
                "required": ["warehouse_id", "skus"],
            },
        ),
        Tool(
            name="wb_update_stocks",
            description="Обновить остатки на складе. stocks = [{sku, amount}]",
            inputSchema={
                "type": "object",
                "properties": {
                    "warehouse_id": {"type": "integer"},
                    "stocks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sku": {"type": "string"},
                                "amount": {"type": "integer"},
                            },
                            "required": ["sku", "amount"],
                        },
                    },
                },
                "required": ["warehouse_id", "stocks"],
            },
        ),
        Tool(
            name="wb_sales",
            description="Продажи с указанной даты (RFC3339). flag=1 — все продажи за день",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "RFC3339 datetime"},
                    "flag": {"type": "integer", "default": 0},
                },
                "required": ["date_from"],
            },
        ),
        Tool(
            name="wb_order_stats",
            description="Статистика заказов с указанной даты (RFC3339)",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_from": {"type": "string"},
                    "flag": {"type": "integer", "default": 0},
                },
                "required": ["date_from"],
            },
        ),
        Tool(
            name="wb_list_cards",
            description="Список карточек товаров (пагинация через cursor)",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 100},
                    "cursor": {"type": "object", "description": "Курсор продолжения с предыдущего вызова"},
                },
            },
        ),
        Tool(
            name="wb_get_prices",
            description="Текущие цены и скидки по товарам",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 1000},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
    ]


def _as_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        client = await _ensure_client()

        if name == "wb_seller_info":
            return _as_text(await client.get_seller_info())

        if name == "wb_list_warehouses":
            return _as_text(await client.list_warehouses())

        if name == "wb_new_orders":
            return _as_text(await client.get_new_orders())

        if name == "wb_get_orders":
            return _as_text(
                await client.get_orders(
                    date_from=arguments["date_from"],
                    date_to=arguments.get("date_to"),
                    limit=arguments.get("limit", 1000),
                    next_cursor=arguments.get("next_cursor", 0),
                )
            )

        if name == "wb_get_stocks":
            return _as_text(
                await client.get_stocks(arguments["warehouse_id"], arguments["skus"])
            )

        if name == "wb_update_stocks":
            await client.update_stocks(arguments["warehouse_id"], arguments["stocks"])
            return [TextContent(type="text", text="Остатки обновлены")]

        if name == "wb_sales":
            return _as_text(
                await client.get_sales(arguments["date_from"], arguments.get("flag", 0))
            )

        if name == "wb_order_stats":
            return _as_text(
                await client.get_order_stats(arguments["date_from"], arguments.get("flag", 0))
            )

        if name == "wb_list_cards":
            return _as_text(
                await client.list_cards(
                    limit=arguments.get("limit", 100), cursor=arguments.get("cursor")
                )
            )

        if name == "wb_get_prices":
            return _as_text(
                await client.get_prices(
                    limit=arguments.get("limit", 1000), offset=arguments.get("offset", 0)
                )
            )

        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]

    except WildberriesError as exc:
        return [TextContent(type="text", text=f"Ошибка Wildberries: {exc.message}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
