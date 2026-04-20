"""Mock Telegram Bot API server.

Serves the `/bot{token}/{method}` URL pattern and returns the `{ok, result}`
envelope production Telegram uses. Token validation is strict — wrong token
returns a 401 with an `ok:false` body, matching real behavior.
"""

from __future__ import annotations

import time

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

VALID_TOKEN = "123456:test-bot-token"  # noqa: S105 — mock

_BOT_IDENTITY = {
    "id": 123456,
    "is_bot": True,
    "first_name": "YzelTestBot",
    "username": "yzeltestbot",
    "can_join_groups": True,
    "can_read_all_group_messages": False,
    "supports_inline_queries": False,
}

# Mutable per-chat outgoing log so edit/delete can round-trip
_SENT: dict[int, dict[int, dict]] = {}
_NEXT_MSG_ID = 1000

# Sequence of updates served to long-poll getUpdates
_UPDATES_QUEUE: list[dict] = [
    {
        "update_id": 100001,
        "message": {
            "message_id": 1,
            "from": {"id": 999, "is_bot": False, "first_name": "Тест"},
            "chat": {"id": -100123, "type": "group", "title": "Склад"},
            "date": int(time.time()),
            "text": "привет",
        },
    }
]

_WEBHOOK: dict[str, object] = {
    "url": "",
    "has_custom_certificate": False,
    "pending_update_count": 0,
    "allowed_updates": [],
}


def _wrong_token_response() -> JSONResponse:
    return JSONResponse(
        {"ok": False, "error_code": 401, "description": "Unauthorized"},
        status_code=401,
    )


async def bot_endpoint(request: Request) -> JSONResponse:
    global _NEXT_MSG_ID
    token = request.path_params["token"]
    method = request.path_params["method"]

    if token != VALID_TOKEN:
        return _wrong_token_response()

    try:
        body = await request.json() if (await request.body()) else {}
    except ValueError:
        body = {}

    if method == "getMe":
        return JSONResponse({"ok": True, "result": _BOT_IDENTITY})

    if method == "sendMessage":
        chat_id = body["chat_id"]
        _NEXT_MSG_ID += 1
        message = {
            "message_id": _NEXT_MSG_ID,
            "chat": {"id": chat_id, "type": "private"},
            "date": int(time.time()),
            "text": body.get("text"),
        }
        _SENT.setdefault(chat_id, {})[_NEXT_MSG_ID] = message
        return JSONResponse({"ok": True, "result": message})

    if method in {"sendPhoto", "sendDocument"}:
        chat_id = body["chat_id"]
        _NEXT_MSG_ID += 1
        message = {
            "message_id": _NEXT_MSG_ID,
            "chat": {"id": chat_id, "type": "private"},
            "date": int(time.time()),
            "caption": body.get("caption"),
        }
        return JSONResponse({"ok": True, "result": message})

    if method == "editMessageText":
        chat_id = body["chat_id"]
        message_id = body["message_id"]
        stored = _SENT.get(chat_id, {}).get(message_id)
        if not stored:
            return JSONResponse(
                {
                    "ok": False,
                    "error_code": 400,
                    "description": "Bad Request: message to edit not found",
                },
                status_code=400,
            )
        stored["text"] = body["text"]
        return JSONResponse({"ok": True, "result": stored})

    if method == "deleteMessage":
        chat_id = body["chat_id"]
        message_id = body["message_id"]
        if message_id in _SENT.get(chat_id, {}):
            del _SENT[chat_id][message_id]
            return JSONResponse({"ok": True, "result": True})
        return JSONResponse(
            {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: message to delete not found",
            },
            status_code=400,
        )

    if method == "answerCallbackQuery":
        return JSONResponse({"ok": True, "result": True})

    if method == "getUpdates":
        offset = body.get("offset")
        updates = _UPDATES_QUEUE
        if offset is not None:
            updates = [u for u in updates if u["update_id"] >= offset]
        return JSONResponse({"ok": True, "result": updates})

    if method == "setWebhook":
        _WEBHOOK["url"] = body.get("url", "")
        _WEBHOOK["allowed_updates"] = body.get("allowed_updates") or []
        return JSONResponse({"ok": True, "result": True})

    if method == "deleteWebhook":
        _WEBHOOK["url"] = ""
        return JSONResponse({"ok": True, "result": True})

    if method == "getWebhookInfo":
        return JSONResponse({"ok": True, "result": _WEBHOOK})

    if method == "getChat":
        chat_id = body["chat_id"]
        return JSONResponse(
            {
                "ok": True,
                "result": {
                    "id": chat_id,
                    "type": "private" if isinstance(chat_id, int) and chat_id > 0 else "group",
                    "title": "Mock Chat" if not isinstance(chat_id, int) or chat_id < 0 else None,
                    "username": "mockuser" if isinstance(chat_id, int) and chat_id > 0 else None,
                },
            }
        )

    if method == "floodControlTest":
        # Used only by the rate-limit test to force a 429
        return JSONResponse(
            {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests: retry after 3",
                "parameters": {"retry_after": 3},
            },
            status_code=429,
        )

    return JSONResponse(
        {"ok": False, "error_code": 404, "description": f"method {method} not mocked"},
        status_code=404,
    )


app = Starlette(
    routes=[Route("/bot{token}/{method}", bot_endpoint, methods=["GET", "POST"])],
)


if __name__ == "__main__":
    import uvicorn

    print("✈️  Mock Telegram Bot API — http://localhost:8081 — token: 123456:test-bot-token")
    uvicorn.run(app, host="0.0.0.0", port=8081)
