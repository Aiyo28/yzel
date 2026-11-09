"""Write runner: one place that turns a write call's fate into an `Outcome`.

The failure this prevents: a create times out after the server already committed, the agent
sees an empty error and calls again, and the document exists twice. `run_write` classifies
what happened, tells the agent whether a resend is safe, and refuses an identical CREATE for
10 minutes after one that applied or may have. Outcomes: 2xx applied; a typed error below 500
rejected (nothing written); a failure before the request left not_sent (resend safe); a timeout,
a dropped connection, a 5xx or an unreadable 2xx body may_have_applied (resend safe except for
creates); a guarded repeat duplicate_refused. The guard lives in this process only; a restart
forgets it.
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from mcp.types import CallToolResult, Tool

from .outcome import Outcome, outcome_result
from .tools import ToolKind, kind_of

GUARD_WINDOW_SECONDS = 600.0

# The request never left this machine, so nothing was written. Checked before the generic
# TransportError fallback: httpx's exception tree overlaps (ConnectTimeout is a timeout too).
_NOT_SENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)

_now: Callable[[], float] = time.monotonic
# shortcut: entries are never evicted. Fine at one user per process; prune on insert if that
# changes.
_recent: dict[tuple[str, str], float] = {}


def reset_guard() -> None:
    """Forget every recorded create (tests)."""
    _recent.clear()


def status_of(exc: Exception) -> int | None:
    """HTTP status of a typed connector error (`status_code`, else `status`) or HTTPStatusError."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _guard_key(tool: Tool, arguments: dict[str, Any]) -> tuple[str, str]:
    """Tool name plus sorted-JSON arguments without `again`: key order and spacing don't matter."""
    args = {k: v for k, v in arguments.items() if k != "again"}
    return tool.name, json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)


def _recently_made(key: tuple[str, str]) -> bool:
    made_at = _recent.get(key)
    return made_at is not None and _now() - made_at < GUARD_WINDOW_SECONDS


def _reason(exc: Exception) -> str:
    """Readable text of a connector error: its `message`, `detail` or `description` field.

    A bare `HTTPStatusError` gets a Russian line with the status only: httpx's own text holds
    the request URL, and Telegram's URL holds the bot token.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Сервер ответил {exc.response.status_code}"
    for attr in ("message", "detail", "description"):
        value = getattr(exc, attr, None)
        if isinstance(value, str) and value:
            return value
    return str(exc) or type(exc).__name__


def _may_have_applied(is_create: bool, check_tool: str | None) -> CallToolResult:
    if is_create:
        look = f" — проверьте через {check_tool}" if check_tool else ""
        return outcome_result(
            Outcome.MAY_HAVE_APPLIED,
            f"Запись могла быть создана. Не отправляйте этот запрос повторно{look}. "
            "Такой же запрос будет отклонён.",
            resend_safe=False,
            check_tool=check_tool,
        )
    return outcome_result(
        Outcome.MAY_HAVE_APPLIED,
        "Ответ не получен, изменение могло быть применено. "
        "Повтор с теми же данными безопасен: результат будет тот же.",
        resend_safe=True,
    )


async def run_write(
    tool: Tool,
    arguments: dict[str, Any],
    call: Callable[[], Awaitable[Any]],
    *,
    error_types: tuple[type[Exception], ...],
    check_tool: str | None = None,
) -> CallToolResult:
    """Run one write call and report its outcome. Other exceptions propagate unchanged."""
    is_create = kind_of(tool) is ToolKind.CREATE
    key = _guard_key(tool, arguments)
    typed_errors: tuple[type[Exception], ...] = (*error_types, httpx.HTTPStatusError)

    # shortcut: check-then-act across an await, so identical creates sent in one parallel tool
    # batch can both pass. Sequential retries (the case this guards) are caught. Upgrade: record
    # a pending marker before sending if parallel duplicates are ever seen.
    if is_create and arguments.get("again") is not True and _recently_made(key):
        look = f"Сначала проверьте через {check_tool}. " if check_tool else "Сначала проверьте. "
        return outcome_result(
            Outcome.DUPLICATE_REFUSED,
            "Такой же запрос уже выполнялся за последние 10 минут, повтор не отправлен. "
            f"{look}Если записи нет, повторите с again: true.",
        )

    try:
        payload = await call()
    except _NOT_SENT:
        return outcome_result(
            Outcome.NOT_SENT,
            "Запрос не ушёл (нет соединения), ничего не записано. Можно отправить повторно.",
            resend_safe=True,
        )
    except (httpx.TransportError, json.JSONDecodeError):
        # Sent, but no usable answer (a 2xx body that is not JSON counts: the write happened).
        result = _may_have_applied(is_create, check_tool)
    except typed_errors as exc:
        status = status_of(exc)
        if status is None or status < 500:
            return outcome_result(
                Outcome.REJECTED,
                f"{_reason(exc)}. Ничего не записано: исправьте запрос и отправьте заново.",
            )
        result = _may_have_applied(is_create, check_tool)
    else:
        result = outcome_result(Outcome.APPLIED, "Выполнено.", result=payload)

    if is_create:
        _recent[key] = _now()
    return result
