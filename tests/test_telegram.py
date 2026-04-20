"""Tests for the Telegram Bot API client against the mock server."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import httpx
import pytest
import uvicorn

from yzel.connectors.telegram.client import RateLimiter, TelegramClient, TelegramError
from tests.mock_telegram_server import VALID_TOKEN, app

MOCK_PORT = 8182
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}"


class _ServerThread:
    def __init__(self, port: int) -> None:
        self._config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        self._server = uvicorn.Server(self._config)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._server.serve())
        for _ in range(50):
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.post(f"{MOCK_URL}/bot{VALID_TOKEN}/getMe", timeout=1.0)
                    if r.status_code == 200:
                        return
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        raise RuntimeError("Mock Telegram server failed to start")

    async def stop(self) -> None:
        self._server.should_exit = True
        if self._task:
            await self._task


@pytest.fixture
async def mock_server() -> AsyncGenerator[str, None]:
    srv = _ServerThread(MOCK_PORT)
    await srv.start()
    yield MOCK_URL
    await srv.stop()


@pytest.fixture
async def client(mock_server: str) -> AsyncGenerator[TelegramClient, None]:
    c = TelegramClient(VALID_TOKEN, base_url=mock_server, max_per_second=1000.0)
    yield c
    await c.close()


# --- Identity ---


async def test_get_me(client: TelegramClient) -> None:
    me = await client.get_me()
    assert me["username"] == "yzeltestbot"
    assert me["is_bot"] is True


# --- Messaging round-trip ---


async def test_send_and_edit_and_delete(client: TelegramClient) -> None:
    sent = await client.send_message(chat_id=555, text="Привет")
    mid = sent["message_id"]

    edited = await client.edit_message_text(chat_id=555, message_id=mid, text="Обновлено")
    assert edited["text"] == "Обновлено"

    ok = await client.delete_message(chat_id=555, message_id=mid)
    assert ok is True


async def test_edit_missing_message_raises(client: TelegramClient) -> None:
    with pytest.raises(TelegramError) as exc:
        await client.edit_message_text(chat_id=555, message_id=999999, text="x")
    assert exc.value.status_code == 400
    assert "message to edit not found" in exc.value.description


async def test_send_photo(client: TelegramClient) -> None:
    res = await client.send_photo(
        chat_id=555, photo="https://example.com/cat.jpg", caption="Кот"
    )
    assert res["caption"] == "Кот"


async def test_send_document(client: TelegramClient) -> None:
    res = await client.send_document(
        chat_id=555, document="https://example.com/report.pdf", caption="Отчёт"
    )
    assert res["caption"] == "Отчёт"


async def test_answer_callback_query(client: TelegramClient) -> None:
    assert await client.answer_callback_query("cb-1", text="готово") is True


# --- Updates / webhook ---


async def test_get_updates(client: TelegramClient) -> None:
    updates = await client.get_updates(timeout=0)
    assert len(updates) == 1
    assert updates[0]["message"]["text"] == "привет"


async def test_webhook_lifecycle(client: TelegramClient) -> None:
    assert await client.set_webhook("https://example.com/hook", secret_token="s") is True
    info = await client.get_webhook_info()
    assert info["url"] == "https://example.com/hook"
    assert await client.delete_webhook() is True
    info_after = await client.get_webhook_info()
    assert info_after["url"] == ""


# --- Chats ---


async def test_get_chat_private(client: TelegramClient) -> None:
    chat = await client.get_chat(555)
    assert chat["type"] == "private"


async def test_get_chat_group(client: TelegramClient) -> None:
    chat = await client.get_chat(-100123)
    assert chat["type"] == "group"


# --- Auth ---


async def test_wrong_token_raises_unauthorized(mock_server: str) -> None:
    bad = TelegramClient("wrong-token", base_url=mock_server, max_per_second=1000.0)
    try:
        with pytest.raises(TelegramError) as exc:
            await bad.get_me()
        assert exc.value.status_code == 401
    finally:
        await bad.close()


# --- Flood control (429 with retry_after parsing) ---


async def test_flood_429_parses_retry_after(client: TelegramClient) -> None:
    with pytest.raises(TelegramError) as exc:
        await client._call("floodControlTest")
    assert exc.value.status_code == 429
    assert exc.value.retry_after == 3


# --- Rate limiter ---


async def test_rate_limiter_enforces_interval() -> None:
    import time as t

    limiter = RateLimiter(max_per_second=20.0)
    start = t.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    assert t.monotonic() - start >= 0.09
