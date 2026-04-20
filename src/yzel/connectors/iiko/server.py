"""iiko Cloud API MCP Server."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from yzel.core.types import IikoCredential
from yzel.core.vault import CredentialVault

from .client import IikoClient, IikoError

server = Server("yzel-iiko")

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
        raise RuntimeError(
            "Нет настроенных подключений к iiko. Используйте 'yzel config add-iiko'"
        )

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


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="iiko_organizations",
            description="Список организаций (ресторанов) iiko",
            inputSchema={
                "type": "object",
                "properties": {"organization_ids": _ORG_IDS_SCHEMA},
            },
        ),
        Tool(
            name="iiko_terminal_groups",
            description="Группы терминалов по организациям",
            inputSchema={
                "type": "object",
                "properties": {"organization_ids": _ORG_IDS_SCHEMA},
                "required": ["organization_ids"],
            },
        ),
        Tool(
            name="iiko_nomenclature",
            description="Меню (номенклатура) одной организации",
            inputSchema={
                "type": "object",
                "properties": {"organization_id": {"type": "string"}},
                "required": ["organization_id"],
            },
        ),
        Tool(
            name="iiko_stop_list",
            description="Стоп-лист (товары, которых сейчас нет)",
            inputSchema={
                "type": "object",
                "properties": {"organization_ids": _ORG_IDS_SCHEMA},
                "required": ["organization_ids"],
            },
        ),
        Tool(
            name="iiko_deliveries_by_phone",
            description="Доставки клиента по номеру телефона",
            inputSchema={
                "type": "object",
                "properties": {
                    "organization_ids": _ORG_IDS_SCHEMA,
                    "phone": {"type": "string"},
                    "delivery_date_from": {"type": "string"},
                    "delivery_date_to": {"type": "string"},
                },
                "required": ["organization_ids", "phone"],
            },
        ),
        Tool(
            name="iiko_create_delivery",
            description="Создать заказ на доставку",
            inputSchema={
                "type": "object",
                "properties": {
                    "organization_id": {"type": "string"},
                    "terminal_group_id": {"type": "string"},
                    "order": {"type": "object"},
                },
                "required": ["organization_id", "terminal_group_id", "order"],
            },
        ),
        Tool(
            name="iiko_order_types",
            description="Типы заказов (в зале / на вынос / доставка)",
            inputSchema={
                "type": "object",
                "properties": {"organization_ids": _ORG_IDS_SCHEMA},
                "required": ["organization_ids"],
            },
        ),
        Tool(
            name="iiko_payment_types",
            description="Типы оплаты",
            inputSchema={
                "type": "object",
                "properties": {"organization_ids": _ORG_IDS_SCHEMA},
                "required": ["organization_ids"],
            },
        ),
        Tool(
            name="iiko_employees",
            description="Сотрудники по организациям",
            inputSchema={
                "type": "object",
                "properties": {"organization_ids": _ORG_IDS_SCHEMA},
                "required": ["organization_ids"],
            },
        ),
    ]


def _as_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        client = await _ensure_client()

        if name == "iiko_organizations":
            return _as_text(
                await client.get_organizations(arguments.get("organization_ids"))
            )

        if name == "iiko_terminal_groups":
            return _as_text(
                await client.get_terminal_groups(arguments["organization_ids"])
            )

        if name == "iiko_nomenclature":
            return _as_text(await client.get_nomenclature(arguments["organization_id"]))

        if name == "iiko_stop_list":
            return _as_text(await client.get_stop_list(arguments["organization_ids"]))

        if name == "iiko_deliveries_by_phone":
            return _as_text(
                await client.get_deliveries_by_phone(
                    organization_ids=arguments["organization_ids"],
                    phone=arguments["phone"],
                    delivery_date_from=arguments.get("delivery_date_from"),
                    delivery_date_to=arguments.get("delivery_date_to"),
                )
            )

        if name == "iiko_create_delivery":
            return _as_text(
                await client.create_delivery(
                    organization_id=arguments["organization_id"],
                    terminal_group_id=arguments["terminal_group_id"],
                    order=arguments["order"],
                )
            )

        if name == "iiko_order_types":
            return _as_text(await client.get_order_types(arguments["organization_ids"]))

        if name == "iiko_payment_types":
            return _as_text(await client.get_payment_types(arguments["organization_ids"]))

        if name == "iiko_employees":
            return _as_text(await client.get_employees(arguments["organization_ids"]))

        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]

    except IikoError as exc:
        return [TextContent(type="text", text=f"Ошибка iiko: {exc.message}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
