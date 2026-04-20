"""Bitrix24 MCP Server.

Exposes Bitrix24 CRM and task operations as MCP tools for AI assistants.
Webhook-based auth — no token management needed.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from yzel.core.types import Bitrix24Credential
from yzel.core.vault import CredentialVault

from .client import Bitrix24Client, Bitrix24Error

server = Server("yzel-bitrix24")

# Runtime state
_client: Bitrix24Client | None = None
_connection_id: str | None = None


async def _ensure_client() -> Bitrix24Client:
    global _client, _connection_id

    if _client is not None:
        return _client

    vault = CredentialVault()
    connections = vault.list_connections()
    bitrix_connections = [c for c in connections if c["service"] == "bitrix24"]

    if not bitrix_connections:
        raise RuntimeError(
            "Нет настроенных подключений к Bitrix24. Используйте 'yzel config add-bitrix'"
        )

    _connection_id = bitrix_connections[0]["id"]
    cred = vault.get(_connection_id)

    if not isinstance(cred, Bitrix24Credential):
        raise RuntimeError(f"Неверный тип учётных данных для {_connection_id}")

    _client = Bitrix24Client(cred.webhook_url)
    return _client


# --- Tool Definitions ---

_CRM_ENTITIES = {
    "lead": {
        "name_ru": "лид",
        "name_ru_plural": "лиды",
        "list_method": "get_leads",
        "get_method": "get_lead",
        "create_method": "create_lead",
        "update_method": "update_lead",
    },
    "contact": {
        "name_ru": "контакт",
        "name_ru_plural": "контакты",
        "list_method": "get_contacts",
        "get_method": "get_contact",
        "create_method": "create_contact",
        "update_method": "update_contact",
    },
    "deal": {
        "name_ru": "сделка",
        "name_ru_plural": "сделки",
        "list_method": "get_deals",
        "get_method": "get_deal",
        "create_method": "create_deal",
        "update_method": "update_deal",
    },
    "company": {
        "name_ru": "компания",
        "name_ru_plural": "компании",
        "list_method": "get_companies",
        "get_method": "get_company",
        "create_method": "create_company",
        "update_method": "update_company",
    },
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Bitrix24 tools."""
    return [
        Tool(
            name="bitrix24_crm_list",
            description=(
                "Получить список CRM-сущностей из Bitrix24 (лиды, контакты, сделки, компании). "
                "Поддерживает фильтрацию, сортировку и выбор полей."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["lead", "contact", "deal", "company"],
                        "description": "Тип сущности CRM",
                    },
                    "select": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Поля для выборки (например, ['ID', 'TITLE', 'STATUS_ID'])",
                    },
                    "filter": {
                        "type": "object",
                        "description": (
                            "Фильтр в формате Bitrix24 "
                            "(например, {'>DATE_CREATE': '2026-01-01', 'STATUS_ID': 'NEW'})"
                        ),
                    },
                    "order": {
                        "type": "object",
                        "description": "Сортировка (например, {'DATE_CREATE': 'DESC'})",
                    },
                    "start": {
                        "type": "integer",
                        "description": "Смещение для пагинации (по умолчанию 0)",
                        "default": 0,
                    },
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="bitrix24_crm_get",
            description="Получить одну CRM-сущность из Bitrix24 по ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["lead", "contact", "deal", "company"],
                        "description": "Тип сущности CRM",
                    },
                    "id": {
                        "type": "integer",
                        "description": "ID записи",
                    },
                },
                "required": ["entity", "id"],
            },
        ),
        Tool(
            name="bitrix24_crm_create",
            description="Создать CRM-сущность в Bitrix24 (лид, контакт, сделку или компанию)",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["lead", "contact", "deal", "company"],
                        "description": "Тип сущности CRM",
                    },
                    "fields": {
                        "type": "object",
                        "description": "Поля для создания (например, {'TITLE': 'Новый лид', 'NAME': 'Иван'})",
                    },
                },
                "required": ["entity", "fields"],
            },
        ),
        Tool(
            name="bitrix24_crm_update",
            description="Обновить CRM-сущность в Bitrix24",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["lead", "contact", "deal", "company"],
                        "description": "Тип сущности CRM",
                    },
                    "id": {
                        "type": "integer",
                        "description": "ID записи",
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
            name="bitrix24_tasks_list",
            description="Получить список задач из Bitrix24",
            inputSchema={
                "type": "object",
                "properties": {
                    "select": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Поля для выборки",
                    },
                    "filter": {
                        "type": "object",
                        "description": "Фильтр задач",
                    },
                    "order": {
                        "type": "object",
                        "description": "Сортировка",
                    },
                    "start": {
                        "type": "integer",
                        "description": "Смещение для пагинации",
                        "default": 0,
                    },
                },
            },
        ),
        Tool(
            name="bitrix24_task_get",
            description="Получить задачу из Bitrix24 по ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "ID задачи",
                    },
                },
                "required": ["id"],
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

        if name == "bitrix24_crm_list":
            entity_type = arguments["entity"]
            meta = _CRM_ENTITIES[entity_type]
            method = getattr(client, meta["list_method"])
            return _as_text(
                await method(
                    select=arguments.get("select"),
                    filter_params=arguments.get("filter"),
                    order=arguments.get("order"),
                    start=arguments.get("start", 0),
                )
            )

        if name == "bitrix24_crm_get":
            entity_type = arguments["entity"]
            meta = _CRM_ENTITIES[entity_type]
            method = getattr(client, meta["get_method"])
            return _as_text(await method(arguments["id"]))

        if name == "bitrix24_crm_create":
            entity_type = arguments["entity"]
            meta = _CRM_ENTITIES[entity_type]
            method = getattr(client, meta["create_method"])
            return _as_text(await method(arguments["fields"]))

        if name == "bitrix24_crm_update":
            entity_type = arguments["entity"]
            meta = _CRM_ENTITIES[entity_type]
            method = getattr(client, meta["update_method"])
            return _as_text(await method(arguments["id"], arguments["fields"]))

        if name == "bitrix24_tasks_list":
            return _as_text(
                await client.get_tasks(
                    select=arguments.get("select"),
                    filter_params=arguments.get("filter"),
                    order=arguments.get("order"),
                    start=arguments.get("start", 0),
                )
            )

        if name == "bitrix24_task_get":
            return _as_text(await client.get_task(arguments["id"]))

        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]

    except Bitrix24Error as exc:
        return [TextContent(type="text", text=f"Ошибка Bitrix24: {exc.description}")]


async def main() -> None:
    """Run the Bitrix24 MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
