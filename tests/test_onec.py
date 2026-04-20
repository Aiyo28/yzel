"""Tests for 1C OData connector — client against mock_odata_server.

Covers:
- Cyrillic entity names round-trip through URL encoding
- $format=json is always appended (never XML)
- Basic Auth per-request (no token/session)
- $top / $filter / $select pass-through
- GUID-keyed single-entity fetch
- 404 → None (get_entity) and OneCError (others)
- 401 raised as OneCError
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import httpx
import pytest
import uvicorn

from yzel.connectors.onec.odata import OneCError, OneCODataClient
from tests.mock_odata_server import app

MOCK_PORT = 8078
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}/odata/standard.odata"
USER = "admin"
PASS = "test"  # noqa: S105 — mock credentials


class _ServerThread:
    """Runs uvicorn in-process for test fixtures."""

    def __init__(self, port: int) -> None:
        self._config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        self._server = uvicorn.Server(self._config)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._server.serve())
        for _ in range(50):
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.get(
                        f"{MOCK_URL}/$metadata",
                        auth=(USER, PASS),
                        timeout=1.0,
                    )
                    if r.status_code == 200:
                        return
            except httpx.ConnectError:
                await asyncio.sleep(0.1)
        raise RuntimeError("Mock 1C OData server failed to start")

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
async def client(mock_server: str) -> AsyncGenerator[OneCODataClient, None]:
    c = OneCODataClient(mock_server, USER, PASS)
    yield c
    await c.close()


# --- Cyrillic + URL encoding ---


async def test_get_cyrillic_entity_list(client: OneCODataClient) -> None:
    """Cyrillic entity names round-trip through URL encoding."""
    results = await client.get_entity_list("Catalog_Контрагенты")
    assert len(results) == 5
    assert any(r["Description"] == "ООО Рога и Копыта" for r in results)


async def test_cyrillic_in_response_preserved(client: OneCODataClient) -> None:
    """Cyrillic field values come back unmangled."""
    results = await client.get_entity_list("Catalog_Номенклатура")
    names = [r["Description"] for r in results]
    assert "Бумага А4 офисная" in names
    assert "Консультационные услуги" in names


# --- OData query params ---


async def test_top_limits_results(client: OneCODataClient) -> None:
    results = await client.get_entity_list("Catalog_Контрагенты", top=2)
    assert len(results) == 2


async def test_select_projects_fields(client: OneCODataClient) -> None:
    results = await client.get_entity_list(
        "Catalog_Контрагенты", top=1, select=["Ref_Key", "Description"]
    )
    assert len(results) == 1
    assert set(results[0].keys()) == {"Ref_Key", "Description"}


async def test_filter_by_string_eq(client: OneCODataClient) -> None:
    results = await client.get_entity_list(
        "Catalog_Контрагенты", filter_expr="ЮридическоеФизическоеЛицо eq 'ФизическоеЛицо'"
    )
    assert len(results) == 2
    assert all(r["ЮридическоеФизическоеЛицо"] == "ФизическоеЛицо" for r in results)


async def test_filter_by_boolean(client: OneCODataClient) -> None:
    results = await client.get_entity_list(
        "Catalog_Контрагенты", filter_expr="DeletionMark eq true"
    )
    assert len(results) == 1


# --- Single-entity fetch ---


async def test_get_entity_by_guid(client: OneCODataClient) -> None:
    record = await client.get_entity(
        "Catalog_Контрагенты", "b1c2d3e4-f5a6-7890-abcd-ef1234567890"
    )
    assert record is not None
    assert record["Description"] == "ООО Рога и Копыта"
    assert record["ИНН"] == "7701234567"


async def test_get_entity_not_found_returns_none(client: OneCODataClient) -> None:
    record = await client.get_entity("Catalog_Контрагенты", "00000000-0000-0000-0000-000000000000")
    assert record is None


# --- JSON format enforcement ---


async def test_response_is_json_not_xml(client: OneCODataClient) -> None:
    """Client must always request $format=json. Mock returns XML when format differs."""
    results = await client.get_entity_list("Catalog_Контрагенты", top=1)
    assert isinstance(results, list)
    assert isinstance(results[0], dict)


# --- Auth ---


async def test_wrong_password_raises(mock_server: str) -> None:
    bad = OneCODataClient(mock_server, USER, "wrong")
    try:
        with pytest.raises(OneCError) as exc:
            await bad.get_entity_list("Catalog_Контрагенты")
        assert exc.value.status_code == 401
    finally:
        await bad.close()


# --- Error wrapping ---


async def test_unknown_entity_raises_onec_error(client: OneCODataClient) -> None:
    with pytest.raises(OneCError) as exc:
        await client.get_entity_list("Catalog_НеСуществует")
    assert exc.value.status_code == 404
    # Mock returns odata.error payload in Russian
    assert "Сущность" in str(exc.value) or "не найдена" in str(exc.value)


# --- Count ---


async def test_count_entities(client: OneCODataClient) -> None:
    total = await client.count_entities("Catalog_Контрагенты")
    assert total == 5


# --- Deployment detection ---


def test_detect_deployment_fresh() -> None:
    from yzel.connectors.onec.odata import detect_deployment

    assert detect_deployment("https://1cfresh.com/a/sbm/12345/odata/standard.odata") == "fresh"


def test_detect_deployment_on_prem() -> None:
    from yzel.connectors.onec.odata import detect_deployment

    assert detect_deployment("https://erp.mycompany.ru/base/odata/standard.odata") == "on-prem"
