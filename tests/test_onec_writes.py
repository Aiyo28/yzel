"""1C write tools end to end: real httpx client, real timeout, mock 1C that commits then stalls.

Servers start cold (`_client = None`, connection from env), like a fresh process: the first
write of a session must end in an outcome even when `$metadata` is down.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from mcp.types import TextContent
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from tests.connector_cases import CASES_BY_ID, call_tool
from tests.harness import CLIENT_TIMEOUT, STALL_SECONDS, body, serving
from yzel.connectors.onec import server as onec
from yzel.connectors.onec.odata import OneCODataClient
from yzel.core import writes

ONEC_CASE = CASES_BY_ID["onec"]
BASE = "/odata/standard.odata"
ARGS = {"entity": "Catalog_Slow", "data": {"Description": "ООО Ромашка"}}


@pytest.fixture(autouse=True)
def _fresh_guard() -> None:
    writes.reset_guard()


async def _metadata_down(request: Request) -> Response:
    return Response("Service Unavailable", status_code=503)


async def _bad_request(request: Request) -> JSONResponse:
    return JSONResponse(
        {"odata.error": {"code": "400", "message": {"lang": "ru", "value": "Не заполнено ИНН"}}},
        status_code=400,
    )


async def test_timeout_after_commit_blocks_the_identical_resend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    created: list[dict[str, Any]] = []

    async def create_slow(request: Request) -> JSONResponse:
        """Commits the record, then answers after the client has given up."""
        created.append(await request.json())
        await asyncio.sleep(STALL_SECONDS)
        return JSONResponse({"Ref_Key": "new"}, status_code=201)

    app = Starlette(routes=[Route(f"{BASE}/Catalog_Slow", create_slow, methods=["POST"])])
    async with serving(app) as url:
        ONEC_CASE.point_at_backend(monkeypatch, url, tmp_path)
        # The server builds its own client from env; inject a short timeout to provoke the stall.
        monkeypatch.setattr(
            onec,
            "OneCODataClient",
            lambda *a, **k: OneCODataClient(*a, **k, timeout=CLIENT_TIMEOUT),
        )

        first = await call_tool(ONEC_CASE, "onec_create", dict(ARGS))
        assert first.isError is True
        assert body(first)["outcome"] == "may_have_applied"
        assert body(first)["resend_safe"] is False
        assert "onec_query" in body(first)["message"]
        assert len(created) == 1  # 1C committed it

        second = await call_tool(ONEC_CASE, "onec_create", dict(ARGS))
        assert body(second)["outcome"] == "duplicate_refused"
        assert len(created) == 1  # the mock never saw a second request

        third = await call_tool(ONEC_CASE, "onec_create", {**ARGS, "again": True})
        assert body(third)["outcome"] == "may_have_applied"
        assert len(created) == 2


async def test_1c_400_on_create_is_rejected_with_the_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = Starlette(routes=[Route(f"{BASE}/Catalog_Bad", _bad_request, methods=["POST"])])
    async with serving(app) as url:
        ONEC_CASE.point_at_backend(monkeypatch, url, tmp_path)
        result = await call_tool(ONEC_CASE, "onec_create", {"entity": "Catalog_Bad", "data": {}})

    assert result.isError is True
    assert body(result)["outcome"] == "rejected"
    assert "Не заполнено ИНН" in body(result)["message"]


@pytest.mark.parametrize("entity_route", [_bad_request, None], ids=["400", "created"])
async def test_first_write_of_a_session_ends_in_an_outcome_when_metadata_is_down(
    entity_route: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def created(request: Request) -> JSONResponse:
        return JSONResponse({"Ref_Key": "new"}, status_code=201)

    app = Starlette(
        routes=[
            Route(f"{BASE}/$metadata", _metadata_down, methods=["GET"]),
            Route(f"{BASE}/Catalog_X", entity_route or created, methods=["POST"]),
        ]
    )
    async with serving(app) as url:
        ONEC_CASE.point_at_backend(monkeypatch, url, tmp_path)
        result = await call_tool(ONEC_CASE, "onec_create", {"entity": "Catalog_X", "data": {}})

    assert body(result)["outcome"] == ("rejected" if entity_route else "applied")


async def test_cold_server_with_refused_connection_is_not_sent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ONEC_CASE.point_at_backend(monkeypatch, "http://127.0.0.1:1", tmp_path)
    result = await call_tool(ONEC_CASE, "onec_create", {"entity": "Catalog_X", "data": {}})
    assert body(result)["outcome"] == "not_sent"


async def test_failed_discovery_is_not_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`onec_list_entities` needs `$metadata`; a 503 now must not poison the next call."""
    metadata = (
        '<edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">'
        '<Schema xmlns="http://schemas.microsoft.com/ado/2009/11/edm">'
        '<EntityType Name="Catalog_Контрагенты"><Property Name="Ref_Key" Type="Edm.Guid"/>'
        "</EntityType></Schema></edmx:Edmx>"
    )
    up = False

    async def flaky_metadata(request: Request) -> Response:
        return Response(metadata if up else "down", status_code=200 if up else 503)

    app = Starlette(routes=[Route(f"{BASE}/$metadata", flaky_metadata, methods=["GET"])])
    async with serving(app) as url:
        ONEC_CASE.point_at_backend(monkeypatch, url, tmp_path)
        first = await call_tool(ONEC_CASE, "onec_list_entities", {})
        assert first.isError is True
        up = True
        second = await call_tool(ONEC_CASE, "onec_list_entities", {})

    assert second.isError is False
    block = second.content[0]
    assert isinstance(block, TextContent)
    assert "Catalog_Контрагенты" in block.text
