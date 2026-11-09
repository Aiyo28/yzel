"""Ozon Seller API MCP Server.

Exposes Ozon Seller operations as MCP tools with RU-first descriptions.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from yzel import __version__
from yzel.core.outcome import error_result
from yzel.core.tools import ToolKind, make_tool, refuse_if_read_only, visible_tools
from yzel.core.types import OzonCredential
from yzel.core.vault import CredentialVault
from yzel.core.writes import run_write

from .client import OzonClient, OzonError

server = Server("yzel-ozon", version=__version__)

_client: OzonClient | None = None
_connection_id: str | None = None


async def _ensure_client() -> OzonClient:
    global _client, _connection_id

    if _client is not None:
        return _client

    vault = CredentialVault()
    connections = vault.list_connections()
    ozon_connections = [c for c in connections if c["service"] == "ozon"]

    if not ozon_connections:
        raise RuntimeError("Нет настроенных подключений к Ozon. Используйте 'yzel config add-ozon'")

    _connection_id = ozon_connections[0]["id"]
    cred = vault.get(_connection_id)

    if not isinstance(cred, OzonCredential):
        raise RuntimeError(f"Неверный тип учётных данных для {_connection_id}")

    _client = OzonClient(cred.client_id, cred.api_key, base_url=cred.base_url)
    return _client


TOOLS: list[Tool] = [
    make_tool(
        name="ozon_list_warehouses",
        description="Список складов продавца Ozon",
        input_schema={"type": "object", "properties": {}},
        kind=ToolKind.READ,
    ),
    make_tool(
        name="ozon_list_products",
        description="Список товаров (пагинация через last_id)",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 100},
                "last_id": {"type": "string", "default": ""},
                "visibility": {
                    "type": "string",
                    "default": "ALL",
                    "description": "ALL, VISIBLE, INVISIBLE, EMPTY_STOCK, NOT_MODERATED, ...",
                },
            },
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="ozon_product_info",
        description="Детали товаров по offer_id / product_id / sku",
        input_schema={
            "type": "object",
            "properties": {
                "offer_ids": {"type": "array", "items": {"type": "string"}},
                "product_ids": {"type": "array", "items": {"type": "integer"}},
                "skus": {"type": "array", "items": {"type": "integer"}},
            },
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="ozon_get_stocks",
        description="Остатки по SKU",
        input_schema={
            "type": "object",
            "properties": {
                "skus": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["skus"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="ozon_update_stocks",
        description="Обновить остатки. stocks = [{offer_id, stock, warehouse_id}]",
        input_schema={
            "type": "object",
            "properties": {
                "stocks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "offer_id": {"type": "string"},
                            "stock": {"type": "integer"},
                            "warehouse_id": {"type": "integer"},
                        },
                        "required": ["offer_id", "stock", "warehouse_id"],
                    },
                }
            },
            "required": ["stocks"],
        },
        kind=ToolKind.UPDATE,
    ),
    make_tool(
        name="ozon_update_prices",
        description="Обновить цены. prices = [{offer_id, price, min_price?, old_price?}]",
        input_schema={
            "type": "object",
            "properties": {
                "prices": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["prices"],
        },
        kind=ToolKind.UPDATE,
    ),
    make_tool(
        name="ozon_unfulfilled",
        description="Неотгруженные сборочные задания FBS",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 100},
                "offset": {"type": "integer", "default": 0},
            },
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="ozon_list_postings",
        description="Сборочные задания FBS за период (ISO-8601)",
        input_schema={
            "type": "object",
            "properties": {
                "since": {"type": "string"},
                "to": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
                "offset": {"type": "integer", "default": 0},
                "status": {"type": "string", "default": ""},
            },
            "required": ["since", "to"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="ozon_get_posting",
        description="Детали сборочного задания по номеру",
        input_schema={
            "type": "object",
            "properties": {"posting_number": {"type": "string"}},
            "required": ["posting_number"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="ozon_analytics",
        description="Аналитические данные продавца за период",
        input_schema={
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "metrics": {"type": "array", "items": {"type": "string"}},
                "dimension": {"type": "array", "items": {"type": "string"}},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["date_from", "date_to", "metrics"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="ozon_transactions",
        description="Финансовые операции за период",
        input_schema={
            "type": "object",
            "properties": {
                "since": {"type": "string"},
                "to": {"type": "string"},
                "page": {"type": "integer", "default": 1},
                "page_size": {"type": "integer", "default": 100},
            },
            "required": ["since", "to"],
        },
        kind=ToolKind.READ,
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools (only the read ones in read-only mode)."""
    return visible_tools(TOOLS)


def _as_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


_TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def _write(
    name: str, arguments: dict[str, Any], call: Callable[[], Awaitable[Any]]
) -> Awaitable[CallToolResult]:
    """Run one Ozon write through the write runner."""
    return run_write(
        _TOOLS_BY_NAME[name],
        arguments,
        call,
        error_types=(OzonError,),
        check_tool=None,
    )


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent] | CallToolResult:
    # First, before any client or credential is touched: hiding tools in list_tools is not enough.
    if (refused := refuse_if_read_only(TOOLS, name)) is not None:
        return refused
    try:
        client = await _ensure_client()

        if name == "ozon_list_warehouses":
            return _as_text(await client.list_warehouses())

        if name == "ozon_list_products":
            return _as_text(
                await client.list_products(
                    limit=arguments.get("limit", 100),
                    last_id=arguments.get("last_id", ""),
                    filter_visibility=arguments.get("visibility", "ALL"),
                )
            )

        if name == "ozon_product_info":
            return _as_text(
                await client.get_product_info(
                    offer_ids=arguments.get("offer_ids"),
                    product_ids=arguments.get("product_ids"),
                    skus=arguments.get("skus"),
                )
            )

        if name == "ozon_get_stocks":
            return _as_text(await client.get_stocks(arguments["skus"]))

        if name == "ozon_update_stocks":
            return await _write(name, arguments, lambda: client.update_stocks(arguments["stocks"]))

        if name == "ozon_update_prices":
            return await _write(name, arguments, lambda: client.update_prices(arguments["prices"]))

        if name == "ozon_unfulfilled":
            return _as_text(
                await client.list_unfulfilled_postings(
                    limit=arguments.get("limit", 100),
                    offset=arguments.get("offset", 0),
                )
            )

        if name == "ozon_list_postings":
            return _as_text(
                await client.list_postings(
                    since=arguments["since"],
                    to=arguments["to"],
                    limit=arguments.get("limit", 100),
                    offset=arguments.get("offset", 0),
                    status=arguments.get("status", ""),
                )
            )

        if name == "ozon_get_posting":
            return _as_text(await client.get_posting(arguments["posting_number"]))

        if name == "ozon_analytics":
            return _as_text(
                await client.analytics_data(
                    date_from=arguments["date_from"],
                    date_to=arguments["date_to"],
                    metrics=arguments["metrics"],
                    dimension=arguments.get("dimension"),
                    limit=arguments.get("limit", 100),
                )
            )

        if name == "ozon_transactions":
            return _as_text(
                await client.list_transactions(
                    since=arguments["since"],
                    to=arguments["to"],
                    page=arguments.get("page", 1),
                    page_size=arguments.get("page_size", 100),
                )
            )

        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]

    except OzonError as exc:
        return error_result(f"Ошибка Ozon: {exc.message}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    """Console-script entry point (see [project.scripts]). Sync wrapper for main()."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
