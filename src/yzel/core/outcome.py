"""Result envelope shared by every connector's tools.

A write tool answers with one of the `Outcome` values so the agent can tell "nothing was
sent" from "sent, answer lost" and not retry blindly. Read tools use `error_result` for
typed errors.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from mcp.types import CallToolResult, TextContent


class Outcome(StrEnum):
    APPLIED = "applied"
    REJECTED = "rejected"
    NOT_SENT = "not_sent"
    MAY_HAVE_APPLIED = "may_have_applied"
    DUPLICATE_REFUSED = "duplicate_refused"
    REFUSED = "refused"


def _text_result(text: str, *, is_error: bool) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)], isError=is_error)


def outcome_result(outcome: Outcome, message: str, **fields: Any) -> CallToolResult:
    """One JSON object `{outcome, message, **fields}`; anything but APPLIED is an error."""
    body = {"outcome": outcome.value, "message": message, **fields}
    text = json.dumps(body, ensure_ascii=False, indent=2)
    return _text_result(text, is_error=outcome is not Outcome.APPLIED)


def error_result(text: str) -> CallToolResult:
    """Plain-text error for read tools."""
    return _text_result(text, is_error=True)


def json_text(payload: Any) -> list[TextContent]:
    """A successful read result: `payload` as pretty JSON in one text block."""
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]
