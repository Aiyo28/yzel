"""Telegram Bot API client.

All requests go to `{base_url}/bot{token}/{method}` — the token lives in
the URL path, not a header. Responses are always wrapped in `{ok, result}`
on success or `{ok: false, error_code, description, parameters?}` on
error; 429 responses include `parameters.retry_after` (seconds).

Rate limit: ~30 messages/second total, 1 msg/sec per individual chat,
20 msg/min to groups. We throttle globally at 25/sec to stay safely
under the per-bot ceiling; per-chat pacing is the caller's responsibility.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


class RateLimiter:
    def __init__(self, max_per_second: float) -> None:
        self._min_interval = 1.0 / max_per_second
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request = time.monotonic()


class TelegramError(Exception):
    """Telegram Bot API error.

    retry_after is populated on 429 responses so callers can back off
    without parsing the raw payload themselves.
    """

    def __init__(
        self,
        status_code: int,
        error_code: int,
        description: str,
        retry_after: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.description = description
        self.retry_after = retry_after
        suffix = f" (retry_after={retry_after}s)" if retry_after else ""
        super().__init__(f"Telegram error [{status_code}/{error_code}]: {description}{suffix}")


def _parse_tg_error(response: httpx.Response) -> TelegramError:
    try:
        data = response.json()
    except ValueError:
        return TelegramError(
            response.status_code,
            response.status_code,
            response.text[:200] or response.reason_phrase,
        )
    if isinstance(data, dict):
        return TelegramError(
            response.status_code,
            int(data.get("error_code") or response.status_code),
            str(data.get("description", "")),
            retry_after=(data.get("parameters") or {}).get("retry_after"),
        )
    return TelegramError(response.status_code, response.status_code, str(data)[:200])


class TelegramClient:
    """Async Telegram Bot API client."""

    def __init__(
        self,
        bot_token: str,
        base_url: str = "https://api.telegram.org",
        max_per_second: float = 25.0,
    ) -> None:
        self._token = bot_token
        self._base = f"{base_url.rstrip('/')}/bot{bot_token}"
        self._client: httpx.AsyncClient | None = None
        self._limiter = RateLimiter(max_per_second=max_per_second)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,  # long enough for long-polling getUpdates
                headers={"Accept": "application/json"},
            )
        return self._client

    async def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        await self._limiter.acquire()
        url = f"{self._base}/{method}"
        client = await self._get_client()
        response = await client.post(url, json=params or {})

        if response.status_code >= 400:
            raise _parse_tg_error(response)

        data = response.json()
        if not data.get("ok"):
            # Telegram occasionally 200s with ok=false (rare but documented)
            raise TelegramError(
                response.status_code,
                int(data.get("error_code") or response.status_code),
                str(data.get("description", "")),
                retry_after=(data.get("parameters") or {}).get("retry_after"),
            )
        return data.get("result")

    # --- Identity ---

    async def get_me(self) -> dict[str, Any]:
        """Данные бота / Bot identity."""
        return await self._call("getMe")

    # --- Sending ---

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str | None = None,
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
        disable_web_page_preview: bool | None = None,
    ) -> dict[str, Any]:
        """Отправить текстовое сообщение / Send a text message."""
        params: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        if reply_to_message_id is not None:
            params["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        if disable_web_page_preview is not None:
            params["disable_web_page_preview"] = disable_web_page_preview
        return await self._call("sendMessage", params)

    async def send_photo(
        self,
        chat_id: int | str,
        photo: str,
        caption: str | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        """Отправить фото (URL или file_id) / Send photo by URL or file_id."""
        params: dict[str, Any] = {"chat_id": chat_id, "photo": photo}
        if caption:
            params["caption"] = caption
        if parse_mode:
            params["parse_mode"] = parse_mode
        return await self._call("sendPhoto", params)

    async def send_document(
        self,
        chat_id: int | str,
        document: str,
        caption: str | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        """Отправить документ (URL или file_id) / Send document."""
        params: dict[str, Any] = {"chat_id": chat_id, "document": document}
        if caption:
            params["caption"] = caption
        if parse_mode:
            params["parse_mode"] = parse_mode
        return await self._call("sendDocument", params)

    # --- Editing / deleting outgoing messages ---

    async def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        parse_mode: str | None = None,
    ) -> dict[str, Any] | bool:
        """Отредактировать текст сообщения / Edit outgoing text message."""
        params: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
        if parse_mode:
            params["parse_mode"] = parse_mode
        return await self._call("editMessageText", params)

    async def delete_message(self, chat_id: int | str, message_id: int) -> bool:
        """Удалить сообщение / Delete a message."""
        return bool(
            await self._call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
        )

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> bool:
        """Ответить на нажатие inline-кнопки / Answer callback query."""
        params: dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            params["text"] = text
        return bool(await self._call("answerCallbackQuery", params))

    # --- Updates / webhook ---

    async def get_updates(
        self,
        offset: int | None = None,
        limit: int = 100,
        timeout: int = 0,
        allowed_updates: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Получить обновления (long-polling) / Fetch updates."""
        params: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        if allowed_updates is not None:
            params["allowed_updates"] = allowed_updates
        return await self._call("getUpdates", params) or []

    async def set_webhook(
        self,
        url: str,
        secret_token: str | None = None,
        allowed_updates: list[str] | None = None,
        drop_pending_updates: bool = False,
    ) -> bool:
        """Установить webhook / Register webhook URL."""
        params: dict[str, Any] = {"url": url, "drop_pending_updates": drop_pending_updates}
        if secret_token:
            params["secret_token"] = secret_token
        if allowed_updates is not None:
            params["allowed_updates"] = allowed_updates
        return bool(await self._call("setWebhook", params))

    async def delete_webhook(self, drop_pending_updates: bool = False) -> bool:
        """Удалить webhook / Remove webhook."""
        return bool(
            await self._call("deleteWebhook", {"drop_pending_updates": drop_pending_updates})
        )

    async def get_webhook_info(self) -> dict[str, Any]:
        """Информация о текущем webhook / Current webhook info."""
        return await self._call("getWebhookInfo")

    # --- Chats ---

    async def get_chat(self, chat_id: int | str) -> dict[str, Any]:
        """Данные чата / Chat info."""
        return await self._call("getChat", {"chat_id": chat_id})

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
