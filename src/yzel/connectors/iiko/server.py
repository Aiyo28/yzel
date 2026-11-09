"""iiko Cloud API MCP Server."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from yzel import __version__
from yzel.core.outcome import error_result, json_text
from yzel.core.tools import ToolKind, make_tool, refuse_if_read_only, visible_tools
from yzel.core.types import IikoCredential
from yzel.core.vault import CredentialVault
from yzel.core.writes import run_write

from .client import IikoClient, IikoError

server = Server("yzel-iiko", version=__version__)

_client: IikoClient | None = None
_connection_id: str | None = None


async def _ensure_client() -> IikoClient:
    global _client, _connection_id

    if _client is not None:
        return _client

    vault = CredentialVault()
    connections = vault.list_connections()
    iiko_connections = [c for c in connections if c["service"] == "iiko"]

    if not iiko_connections:
        raise RuntimeError("Нет настроенных подключений к iiko. Используйте 'yzel config add-iiko'")

    _connection_id = iiko_connections[0]["id"]
    cred = vault.get(_connection_id)

    if not isinstance(cred, IikoCredential):
        raise RuntimeError(f"Неверный тип учётных данных для {_connection_id}")

    _client = IikoClient(cred.api_login, base_url=cred.base_url)
    return _client


_ORG_IDS_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
    "description": "GUID организаций iiko",
}


TOOLS: list[Tool] = [
    make_tool(
        name="iiko_organizations",
        description="Список организаций (ресторанов) iiko",
        input_schema={
            "type": "object",
            "properties": {"organization_ids": _ORG_IDS_SCHEMA},
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="iiko_terminal_groups",
        description="Группы терминалов по организациям",
        input_schema={
            "type": "object",
            "properties": {"organization_ids": _ORG_IDS_SCHEMA},
            "required": ["organization_ids"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="iiko_nomenclature",
        description="Меню (номенклатура) одной организации",
        input_schema={
            "type": "object",
            "properties": {"organization_id": {"type": "string"}},
            "required": ["organization_id"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="iiko_stop_list",
        description="Стоп-лист (товары, которых сейчас нет)",
        input_schema={
            "type": "object",
            "properties": {"organization_ids": _ORG_IDS_SCHEMA},
            "required": ["organization_ids"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="iiko_deliveries_by_phone",
        description="Доставки клиента по номеру телефона",
        input_schema={
            "type": "object",
            "properties": {
                "organization_ids": _ORG_IDS_SCHEMA,
                "phone": {"type": "string"},
                "delivery_date_from": {"type": "string"},
                "delivery_date_to": {"type": "string"},
            },
            "required": ["organization_ids", "phone"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="iiko_create_delivery",
        description="Создать заказ на доставку",
        input_schema={
            "type": "object",
            "properties": {
                "organization_id": {"type": "string"},
                "terminal_group_id": {"type": "string"},
                "order": {"type": "object"},
            },
            "required": ["organization_id", "terminal_group_id", "order"],
        },
        kind=ToolKind.CREATE,
    ),
    make_tool(
        name="iiko_order_types",
        description="Типы заказов (в зале / на вынос / доставка)",
        input_schema={
            "type": "object",
            "properties": {"organization_ids": _ORG_IDS_SCHEMA},
            "required": ["organization_ids"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="iiko_payment_types",
        description="Типы оплаты",
        input_schema={
            "type": "object",
            "properties": {"organization_ids": _ORG_IDS_SCHEMA},
            "required": ["organization_ids"],
        },
        kind=ToolKind.READ,
    ),
    make_tool(
        name="iiko_employees",
        description="Сотрудники по организациям",
        input_schema={
            "type": "object",
            "properties": {"organization_ids": _ORG_IDS_SCHEMA},
            "required": ["organization_ids"],
        },
        kind=ToolKind.READ,
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools (only the read ones in read-only mode)."""
    return visible_tools(TOOLS)


_write = partial(run_write, TOOLS, error_types=(IikoError,), check_tool="iiko_deliveries_by_phone")


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent] | CallToolResult:
    # First, before any client or credential is touched: hiding tools in list_tools is not enough.
    if (refused := refuse_if_read_only(TOOLS, name)) is not None:
        return refused
    try:
        client = await _ensure_client()

        if name == "iiko_organizations":
            return json_text(await client.get_organizations(arguments.get("organization_ids")))

        if name == "iiko_terminal_groups":
            return json_text(await client.get_terminal_groups(arguments["organization_ids"]))

        if name == "iiko_nomenclature":
            return json_text(await client.get_nomenclature(arguments["organization_id"]))

        if name == "iiko_stop_list":
            return json_text(await client.get_stop_list(arguments["organization_ids"]))

        if name == "iiko_deliveries_by_phone":
            return json_text(
                await client.get_deliveries_by_phone(
                    organization_ids=arguments["organization_ids"],
                    phone=arguments["phone"],
                    delivery_date_from=arguments.get("delivery_date_from"),
                    delivery_date_to=arguments.get("delivery_date_to"),
                )
            )

        if name == "iiko_create_delivery":
            return await _write(
                name,
                arguments,
                lambda: client.create_delivery(
                    organization_id=arguments["organization_id"],
                    terminal_group_id=arguments["terminal_group_id"],
                    order=arguments["order"],
                ),
            )

        if name == "iiko_order_types":
            return json_text(await client.get_order_types(arguments["organization_ids"]))

        if name == "iiko_payment_types":
            return json_text(await client.get_payment_types(arguments["organization_ids"]))

        if name == "iiko_employees":
            return json_text(await client.get_employees(arguments["organization_ids"]))

        return error_result(f"Неизвестный инструмент: {name}")

    except IikoError as exc:
        return error_result(f"Ошибка iiko: {exc.message}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    """Console-script entry point (see [project.scripts]). Sync wrapper for main()."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
