"""Telegram Bot API MCP Server.

Exposes Telegram bot operations as MCP tools. Descriptions RU-first.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from yzel.core.types import TelegramCredential
from yzel.core.vault import CredentialVault

from .client import TelegramClient, TelegramError

server = Server("yzel-telegram")

_client: TelegramClient | None = None
_connection_id: str | None = None


async def _ensure_client() -> TelegramClient:
    global _client, _connection_id

    if _client is not None:
        return _client

    vault = CredentialVault()
    connections = vault.list_connections()
    tg_connections = [c for c in connections if c["service"] == "telegram"]

    if not tg_connections:
        raise RuntimeError(
            "Нет настроенных подключений к Telegram. Используйте 'yzel config add-telegram'"
        )

    _connection_id = tg_connections[0]["id"]
    cred = vault.get(_connection_id)

    if not isinstance(cred, TelegramCredential):
        raise RuntimeError(f"Неверный тип учётных данных для {_connection_id}")

    _client = TelegramClient(cred.bot_token, base_url=cred.base_url)
    return _client


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="tg_get_me",
            description="Данные бота Telegram",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="tg_send_message",
            description="Отправить текстовое сообщение в чат",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"]},
                    "text": {"type": "string"},
                    "parse_mode": {"type": "string", "description": "HTML | MarkdownV2"},
                    "reply_to_message_id": {"type": "integer"},
                    "reply_markup": {"type": "object"},
                    "disable_web_page_preview": {"type": "boolean"},
                },
                "required": ["chat_id", "text"],
            },
        ),
        Tool(
            name="tg_send_photo",
            description="Отправить фото (URL или file_id)",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"]},
                    "photo": {"type": "string"},
                    "caption": {"type": "string"},
                    "parse_mode": {"type": "string"},
                },
                "required": ["chat_id", "photo"],
            },
        ),
        Tool(
            name="tg_send_document",
            description="Отправить документ (URL или file_id)",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"]},
                    "document": {"type": "string"},
                    "caption": {"type": "string"},
                    "parse_mode": {"type": "string"},
                },
                "required": ["chat_id", "document"],
            },
        ),
        Tool(
            name="tg_edit_message",
            description="Отредактировать текст ранее отправленного сообщения",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"]},
                    "message_id": {"type": "integer"},
                    "text": {"type": "string"},
                    "parse_mode": {"type": "string"},
                },
                "required": ["chat_id", "message_id", "text"],
            },
        ),
        Tool(
            name="tg_delete_message",
            description="Удалить сообщение",
            inputSchema={
                "type": "object",
                "properties": {
                    "chat_id": {"type": ["integer", "string"]},
                    "message_id": {"type": "integer"},
                },
                "required": ["chat_id", "message_id"],
            },
        ),
        Tool(
            name="tg_answer_callback",
            description="Ответить на нажатие inline-кнопки",
            inputSchema={
                "type": "object",
                "properties": {
                    "callback_query_id": {"type": "string"},
                    "text": {"type": "string"},
                    "show_alert": {"type": "boolean", "default": False},
                },
                "required": ["callback_query_id"],
            },
        ),
        Tool(
            name="tg_get_updates",
            description="Получить обновления (long-polling). Не использовать одновременно с webhook",
            inputSchema={
                "type": "object",
                "properties": {
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer", "default": 100},
                    "timeout": {"type": "integer", "default": 0},
                    "allowed_updates": {"type": "array", "items": {"type": "string"}},
                },
            },
        ),
        Tool(
            name="tg_set_webhook",
            description="Установить webhook URL (отключает long-polling)",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "secret_token": {"type": "string"},
                    "allowed_updates": {"type": "array", "items": {"type": "string"}},
                    "drop_pending_updates": {"type": "boolean", "default": False},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="tg_delete_webhook",
            description="Удалить webhook",
            inputSchema={
                "type": "object",
                "properties": {"drop_pending_updates": {"type": "boolean", "default": False}},
            },
        ),
        Tool(
            name="tg_get_webhook_info",
            description="Информация о текущем webhook",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="tg_get_chat",
            description="Данные чата",
            inputSchema={
                "type": "object",
                "properties": {"chat_id": {"type": ["integer", "string"]}},
                "required": ["chat_id"],
            },
        ),
    ]


def _as_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        client = await _ensure_client()

        if name == "tg_get_me":
            return _as_text(await client.get_me())

        if name == "tg_send_message":
            return _as_text(
                await client.send_message(
                    chat_id=arguments["chat_id"],
                    text=arguments["text"],
                    parse_mode=arguments.get("parse_mode"),
                    reply_to_message_id=arguments.get("reply_to_message_id"),
                    reply_markup=arguments.get("reply_markup"),
                    disable_web_page_preview=arguments.get("disable_web_page_preview"),
                )
            )

        if name == "tg_send_photo":
            return _as_text(
                await client.send_photo(
                    chat_id=arguments["chat_id"],
                    photo=arguments["photo"],
                    caption=arguments.get("caption"),
                    parse_mode=arguments.get("parse_mode"),
                )
            )

        if name == "tg_send_document":
            return _as_text(
                await client.send_document(
                    chat_id=arguments["chat_id"],
                    document=arguments["document"],
                    caption=arguments.get("caption"),
                    parse_mode=arguments.get("parse_mode"),
                )
            )

        if name == "tg_edit_message":
            return _as_text(
                await client.edit_message_text(
                    chat_id=arguments["chat_id"],
                    message_id=arguments["message_id"],
                    text=arguments["text"],
                    parse_mode=arguments.get("parse_mode"),
                )
            )

        if name == "tg_delete_message":
            ok = await client.delete_message(arguments["chat_id"], arguments["message_id"])
            return [TextContent(type="text", text="Удалено" if ok else "Не удалось удалить")]

        if name == "tg_answer_callback":
            ok = await client.answer_callback_query(
                arguments["callback_query_id"],
                text=arguments.get("text"),
                show_alert=arguments.get("show_alert", False),
            )
            return [TextContent(type="text", text="OK" if ok else "Ошибка")]

        if name == "tg_get_updates":
            return _as_text(
                await client.get_updates(
                    offset=arguments.get("offset"),
                    limit=arguments.get("limit", 100),
                    timeout=arguments.get("timeout", 0),
                    allowed_updates=arguments.get("allowed_updates"),
                )
            )

        if name == "tg_set_webhook":
            ok = await client.set_webhook(
                url=arguments["url"],
                secret_token=arguments.get("secret_token"),
                allowed_updates=arguments.get("allowed_updates"),
                drop_pending_updates=arguments.get("drop_pending_updates", False),
            )
            return [TextContent(type="text", text="Webhook установлен" if ok else "Ошибка")]

        if name == "tg_delete_webhook":
            ok = await client.delete_webhook(arguments.get("drop_pending_updates", False))
            return [TextContent(type="text", text="Webhook удалён" if ok else "Ошибка")]

        if name == "tg_get_webhook_info":
            return _as_text(await client.get_webhook_info())

        if name == "tg_get_chat":
            return _as_text(await client.get_chat(arguments["chat_id"]))

        return [TextContent(type="text", text=f"Неизвестный инструмент: {name}")]

    except TelegramError as exc:
        hint = (
            f" — подождите {exc.retry_after}с"
            if exc.retry_after
            else ""
        )
        return [TextContent(type="text", text=f"Ошибка Telegram: {exc.description}{hint}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
