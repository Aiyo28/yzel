"""Outcome table of the write runner, exercised directly (no server, no network)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from mcp.types import CallToolResult, Tool

from yzel.core import writes
from yzel.core.tools import ToolKind, make_tool
from yzel.core.writes import run_write

SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}
CREATE = make_tool("thing_create", "create", SCHEMA, ToolKind.CREATE)
UPDATE = make_tool("thing_update", "update", SCHEMA, ToolKind.UPDATE)
DELETE = make_tool("thing_delete", "delete", SCHEMA, ToolKind.DELETE)
OTHER = make_tool("other_create", "create", SCHEMA, ToolKind.CREATE)
TOOLS = [CREATE, UPDATE, DELETE, OTHER]


class ThingError(Exception):
    def __init__(self, status_code: int | None, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class StatusError(Exception):
    """AmoCRM style: the HTTP status lives in `.status`."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__("amo")


@pytest.fixture(autouse=True)
def _fresh_guard() -> Iterator[None]:
    writes.reset_guard()
    yield
    writes.reset_guard()


def body(result: CallToolResult) -> dict[str, Any]:
    first = result.content[0]
    assert first.type == "text"
    parsed: dict[str, Any] = json.loads(first.text)
    return parsed


class Spy:
    """A `call` that counts invocations and then returns or raises."""

    def __init__(self, *, returns: Any = None, raises: Exception | None = None) -> None:
        self.calls = 0
        self._returns = returns
        self._raises = raises

    async def __call__(self) -> Any:
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._returns


async def run(
    tool: Tool,
    spy: Spy,
    arguments: dict[str, Any] | None = None,
    check_tool: str | None = "thing_query",
) -> CallToolResult:
    return await run_write(
        TOOLS,
        tool.name,
        arguments or {},
        spy,
        error_types=(ThingError, StatusError),
        check_tool=check_tool,
    )


async def test_applied_returns_payload() -> None:
    result = await run(CREATE, Spy(returns={"Ref_Key": "abc"}))
    assert result.isError is False
    assert body(result)["outcome"] == "applied"
    assert body(result)["result"] == {"Ref_Key": "abc"}


@pytest.mark.parametrize("status", [400, 404, 409, None])
@pytest.mark.parametrize("tool", [CREATE, UPDATE, DELETE])
async def test_typed_error_below_500_is_rejected(tool: Tool, status: int | None) -> None:
    result = await run(tool, Spy(raises=ThingError(status, "Не заполнено поле")))
    assert result.isError is True
    assert body(result)["outcome"] == "rejected"
    assert "Не заполнено поле" in body(result)["message"]


async def test_amocrm_style_status_attribute_is_read() -> None:
    assert body(await run(CREATE, Spy(raises=StatusError(400))))["outcome"] == "rejected"
    assert body(await run(CREATE, Spy(raises=StatusError(502))))["outcome"] == "may_have_applied"


@pytest.mark.parametrize(
    "exc",
    [httpx.ConnectError("x"), httpx.ConnectTimeout("x"), httpx.PoolTimeout("x")],
)
@pytest.mark.parametrize("tool", [CREATE, UPDATE, DELETE])
async def test_request_never_left_is_not_sent(tool: Tool, exc: Exception) -> None:
    result = await run(tool, Spy(raises=exc))
    assert result.isError is True
    assert body(result)["outcome"] == "not_sent"
    assert body(result)["resend_safe"] is True


MAYBE: list[Exception] = [
    httpx.ReadTimeout(""),
    httpx.WriteTimeout("x"),
    httpx.RemoteProtocolError("x"),
    httpx.ReadError("x"),
    ThingError(500, "boom"),
    ThingError(503, "boom"),
]


@pytest.mark.parametrize("exc", MAYBE)
async def test_create_that_may_have_applied_says_do_not_resend(exc: Exception) -> None:
    result = await run(CREATE, Spy(raises=exc))
    assert result.isError is True
    out = body(result)
    assert out["outcome"] == "may_have_applied"
    assert out["resend_safe"] is False
    assert out["check_tool"] == "thing_query"
    assert "thing_query" in out["message"]


async def test_create_without_check_tool_reports_null() -> None:
    result = await run(CREATE, Spy(raises=httpx.ReadTimeout("")), check_tool=None)
    assert body(result)["check_tool"] is None


@pytest.mark.parametrize("exc", MAYBE)
@pytest.mark.parametrize("tool", [UPDATE, DELETE])
async def test_update_and_delete_that_may_have_applied_are_resend_safe(
    tool: Tool, exc: Exception
) -> None:
    result = await run(tool, Spy(raises=exc))
    assert result.isError is True
    assert body(result)["outcome"] == "may_have_applied"
    assert body(result)["resend_safe"] is True


@pytest.mark.parametrize("first", [Spy(returns={"ok": 1}), Spy(raises=httpx.ReadTimeout(""))])
async def test_identical_create_is_refused_and_not_made(first: Spy) -> None:
    args = {"entity": "A", "data": {"x": 1, "y": 2}}
    await run(CREATE, first, args)
    second = Spy(returns={"ok": 2})
    # Same arguments, different key order.
    result = await run(CREATE, second, {"data": {"y": 2, "x": 1}, "entity": "A"})
    assert result.isError is True
    assert body(result)["outcome"] == "duplicate_refused"
    assert "thing_query" in body(result)["message"]
    assert second.calls == 0


async def test_again_true_bypasses_the_guard_and_still_records() -> None:
    args = {"entity": "A"}
    await run(CREATE, Spy(returns=1), args)
    third = Spy(returns=2)
    result = await run(CREATE, third, {**args, "again": True})
    assert body(result)["outcome"] == "applied"
    assert third.calls == 1
    # `again` is excluded from the key, so a plain repeat is still refused.
    assert body(await run(CREATE, Spy(returns=3), args))["outcome"] == "duplicate_refused"


async def test_guard_window_is_ten_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(writes, "_now", lambda: now[0])
    await run(CREATE, Spy(returns=1), {"entity": "A"})
    now[0] += 599
    assert body(await run(CREATE, Spy(returns=1), {"entity": "A"}))["outcome"] == (
        "duplicate_refused"
    )
    now[0] += 2
    assert body(await run(CREATE, Spy(returns=1), {"entity": "A"}))["outcome"] == "applied"


async def test_different_arguments_or_tool_are_not_duplicates() -> None:
    await run(CREATE, Spy(returns=1), {"entity": "A"})
    assert body(await run(CREATE, Spy(returns=1), {"entity": "B"}))["outcome"] == "applied"
    assert body(await run(OTHER, Spy(returns=1), {"entity": "A"}))["outcome"] == "applied"


async def test_rejected_and_not_sent_creates_are_not_recorded() -> None:
    args = {"entity": "A"}
    await run(CREATE, Spy(raises=ThingError(400, "bad")), args)
    await run(CREATE, Spy(raises=httpx.ConnectError("x")), args)
    retry = Spy(returns=1)
    assert body(await run(CREATE, retry, args))["outcome"] == "applied"
    assert retry.calls == 1


@pytest.mark.parametrize("tool", [UPDATE, DELETE])
async def test_update_and_delete_are_never_guarded(tool: Tool) -> None:
    await run(tool, Spy(returns=1), {"key": "k"})
    second = Spy(returns=1)
    assert body(await run(tool, second, {"key": "k"}))["outcome"] == "applied"
    assert second.calls == 1


async def test_unexpected_exception_propagates_and_is_not_recorded() -> None:
    with pytest.raises(KeyError):
        await run(CREATE, Spy(raises=KeyError("entity")), {"a": 1})
    assert body(await run(CREATE, Spy(returns=1), {"a": 1}))["outcome"] == "applied"


def http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://x")
    return httpx.HTTPStatusError(
        "bad gateway", request=request, response=httpx.Response(status, request=request)
    )


async def test_http_status_error_5xx_on_create_may_have_applied_and_is_guarded() -> None:
    args = {"entity": "A"}
    result = await run(CREATE, Spy(raises=http_status_error(502)), args)
    assert body(result)["outcome"] == "may_have_applied"
    second = Spy(returns=1)
    assert body(await run(CREATE, second, args))["outcome"] == "duplicate_refused"
    assert second.calls == 0


async def test_http_status_error_4xx_is_rejected() -> None:
    result = await run(CREATE, Spy(raises=http_status_error(400)))
    assert body(result)["outcome"] == "rejected"
    # The English text of httpx carries the request URL (Telegram's holds the bot token).
    assert "http" not in body(result)["message"]
    assert "400" in body(result)["message"]


async def test_unreadable_2xx_body_on_create_may_have_applied_and_is_guarded() -> None:
    args = {"entity": "A"}
    result = await run(CREATE, Spy(raises=json.JSONDecodeError("x", "", 0)), args)
    assert body(result)["outcome"] == "may_have_applied"
    assert body(await run(CREATE, Spy(returns=1), args))["outcome"] == "duplicate_refused"


class DetailError(Exception):
    def __init__(self) -> None:
        self.detail = "Неверный pipeline"
        super().__init__("AmoCRM error")


class DescriptionError(Exception):
    def __init__(self) -> None:
        self.description = "Чат не найден"
        super().__init__("Telegram error")


@pytest.mark.parametrize(
    ("exc", "text"), [(DetailError(), "Неверный pipeline"), (DescriptionError(), "Чат не найден")]
)
async def test_reason_reads_detail_and_description(exc: Exception, text: str) -> None:
    result = await run_write(TOOLS, CREATE.name, {}, Spy(raises=exc), error_types=(type(exc),))
    assert body(result)["outcome"] == "rejected"
    assert text in body(result)["message"]
    assert "error" not in body(result)["message"]


async def test_unknown_tool_name_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="no_such_tool"):
        await run_write(TOOLS, "no_such_tool", {}, Spy(), error_types=(ThingError,))


async def test_rejected_message_does_not_double_the_full_stop() -> None:
    result = await run(CREATE, Spy(raises=ThingError(400, "Не заполнено поле.")))
    assert "Не заполнено поле. Ничего" in body(result)["message"]
    assert ".." not in body(result)["message"]


class RetryAfterError(Exception):
    """Telegram style: `retry_after` seconds on a 429."""

    def __init__(self, retry_after: int | None) -> None:
        self.status_code = 429
        self.retry_after = retry_after
        self.description = "Too Many Requests"
        super().__init__("Telegram error")


class EmptyDetailError(Exception):
    """AmoCRM style: status in `.status`, nothing readable in `.detail`."""

    def __init__(self) -> None:
        self.status = 429
        self.detail = ""
        super().__init__("AmoCRM error [429]: ")


@pytest.mark.parametrize("tool", [CREATE, UPDATE, DELETE])
async def test_429_says_wait_and_names_the_retry_after_seconds(tool: Tool) -> None:
    result = await run_write(
        TOOLS, tool.name, {}, Spy(raises=RetryAfterError(7)), error_types=(RetryAfterError,)
    )
    out = body(result)
    assert out["outcome"] == "rejected"
    assert out["message"] == (
        "Слишком много запросов, ничего не записано. Подождите 7 с и отправьте заново."
    )


async def test_429_without_a_usable_retry_after_still_says_wait() -> None:
    for exc in (RetryAfterError(None), EmptyDetailError()):
        result = await run_write(TOOLS, CREATE.name, {}, Spy(raises=exc), error_types=(type(exc),))
        assert body(result)["message"] == (
            "Слишком много запросов, ничего не записано. Подождите и отправьте заново."
        )


async def test_create_without_check_tool_points_the_agent_to_look_by_hand() -> None:
    args = {"chat_id": 1}
    first = await run(CREATE, Spy(raises=httpx.ReadTimeout("")), args, check_tool=None)
    assert "Запрос мог быть выполнен" in body(first)["message"]
    assert "вручную" in body(first)["message"]
    second = await run(CREATE, Spy(returns=1), args, check_tool=None)
    assert body(second)["outcome"] == "duplicate_refused"
    assert "убедитесь вручную" in body(second)["message"]
