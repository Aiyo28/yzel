"""AmoCRM (Kommo) MCP Server.

Exposes AmoCRM CRM operations as MCP tools for AI assistants.
OAuth2 auth with automatic token refresh — credentials from vault.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from yzel.core.types import AmoCRMCredential
from yzel.core.vault import CredentialVault

from .client import AmoCRMClient

server = Server("yzel-amocrm")

# Runtime state
_client: AmoCRMClient | None = None
_connection_id: str | None = None
_vault: CredentialVault | None = None


def _on_token_refresh(access_token: str, refresh_token: str, expires_at: float) -> None:
    """Persist refreshed tokens back to the vault."""
    if _vault is None or _connection_id is None:
        return

    cred = _vault.get(_connection_id)
    if not isinstance(cred, AmoCRMCredential):
        return

    updated = cred.model_copy(update={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    })
    _vault.store(_connection_id, updated)


async def _ensure_client() -> AmoCRMClient:
    global _client, _connection_id, _vault

    if _client is not None:
        return _client

    _vault = CredentialVault()
    connections = _vault.list_connections()
    amo_connections = [c for c in connections if c["service"] == "amocrm"]

    if not amo_connections:
        raise RuntimeError(
            "Нет настроенных подключений к AmoCRM. Настройте OAuth2 через интеграцию."
        )

    _connection_id = amo_connections[0]["id"]
    cred = _vault.get(_connection_id)

    if not isinstance(cred, AmoCRMCredential):
        raise RuntimeError(f"Неверный тип учётных данных для {_connection_id}")

    _client = AmoCRMClient(
        subdomain=cred.subdomain,
        access_token=cred.access_token,
        refresh_token=cred.refresh_token,
        expires_at=cred.expires_at,
        client_id=cred.client_id,
        client_secret=cred.client_secret,
        redirect_uri=cred.redirect_uri,
        on_token_refresh=_on_token_refresh,
    )
    return _client


_ENTITY_TYPES = {
    "lead": {
        "list_method": "get_leads",
        "get_method": "get_lead",
        "create_method": "create_leads",
        "update_method": "update_lead",
    },
    "contact": {
        "list_method": "get_contacts",
        "get_method": "get_contact",
        "create_method": "create_contacts",
        "update_method": "update_contact",
    },
    "company": {
        "list_method": "get_companies",
        "get_method": "get_company",
        "create_method": "create_companies",
        "update_method": "update_company",
    },
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available AmoCRM tools."""
    return [
        Tool(
            name="amocrm_list",
            description=(
                "Получить список сущностей из AmoCRM (сделки, контакты, компании). "
                "Поддерживает поиск, фильтрацию и связанные данные (with)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["lead", "contact", "company"],
                        "description": "Тип сущности",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Записей на странице (макс 250)",
                        "default": 50,
                    },
                    "page": {
                        "type": "integer",
                        "description": "Номер страницы",
                        "default": 1,
                    },
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос",
                    },
                    "with": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Связанные данные (например, ['contacts', 'catalog_elements'])",
                    },
                },
                "required": ["entity"],
            },
        ),
        Tool(
            name="amocrm_get",
            description="Получить одну сущность из AmoCRM по ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["lead", "contact", "company"],
                        "description": "Тип сущности",
                    },
                    "id": {
                        "type": "integer",
                        "description": "ID записи",
                    },
                    "with": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Связанные данные",
                    },
                },
                "required": ["entity", "id"],
            },
        ),
        Tool(
            name="amocrm_create",
            description="Создать сущности в AmoCRM (batch — можно передать массив)",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["lead", "contact", "company"],
                        "description": "Тип сущности",
                    },
                    "items": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Массив объектов для создания",
                    },
                },
                "required": ["entity", "items"],
            },
        ),
        Tool(
            name="amocrm_update",
            description="Обновить сущность в AmoCRM",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["lead", "contact", "company"],
                        "description": "Тип сущности",
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
            name="amocrm_pipelines",
            description="Получить воронки продаж из AmoCRM (все или по ID)",
            inputSchema={
                "type": "object",
                "properties": {
                    "pipeline_id": {
                        "type": "integer",
                        "description": "ID воронки (если не указан — все воронки)",
                    },
                },
            },
        ),
        Tool(
            name="amocrm_account",
            description="Получить информацию об аккаунте AmoCRM",
            inputSchema={
                "type": "object",
                "properties": {
                    "with": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Доп. данные (например, ['amojo_id', 'users_groups'])",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    client = await _ensure_client()

    if name == "amocrm_list":
        entity_type = arguments["entity"]
        meta = _ENTITY_TYPES[entity_type]
        method = getattr(client, meta["list_method"])
        kwargs: dict[str, Any] = {
            "limit": arguments.get("limit", 50),
            "page": arguments.get("page", 1),
        }
        if arguments.get("query"):
            kwargs["query"] = arguments["query"]
        if arguments.get("with"):
            kwargs["with_params"] = arguments["with"]
        result = await method(**kwargs)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "amocrm_get":
        entity_type = arguments["entity"]
        meta = _ENTITY_TYPES[entity_type]
        method = getattr(client, meta["get_method"])
        kwargs = {}
        if arguments.get("with"):
            kwargs["with_params"] = arguments["with"]
        result = await method(arguments["id"], **kwargs)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "amocrm_create":
        entity_type = arguments["entity"]
        meta = _ENTITY_TYPES[entity_type]
        method = getattr(client, meta["create_method"])
        result = await method(arguments["items"])
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "amocrm_update":
        entity_type = arguments["entity"]
        meta = _ENTITY_TYPES[entity_type]
        method = getattr(client, meta["update_method"])
        result = await method(arguments["id"], arguments["fields"])
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "amocrm_pipelines":
        pipeline_id = arguments.get("pipeline_id")
        if pipeline_id:
            result = await client.get_pipeline(pipeline_id)
        else:
            result = await client.get_pipelines()
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "amocrm_account":
        result = await client.get_account(with_params=arguments.get("with"))
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]


async def main() -> None:
    """Run the AmoCRM MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
