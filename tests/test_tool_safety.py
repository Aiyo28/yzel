"""Every tool declares what it does to the data, and read-only mode enforces it.

Checked at the MCP boundary (`tools/list`, `tools/call`) over an in-memory session, so the
test survives however a server builds its tools. To cover another server, append one entry
to `SERVERS`.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession
from mcp.server import Server
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent, Tool

from yzel.connectors.amocrm import server as amocrm_server
from yzel.connectors.amocrm.client import AmoCRMClient
from yzel.connectors.bitrix24 import server as bitrix24_server
from yzel.connectors.iiko import server as iiko_server
from yzel.connectors.moysklad import server as moysklad_server
from yzel.connectors.moysklad.client import MoyskladClient
from yzel.connectors.onec import server as onec_server
from yzel.connectors.ozon import server as ozon_server
from yzel.connectors.telegram import server as telegram_server
from yzel.connectors.wildberries import client as wildberries_client
from yzel.connectors.wildberries import server as wildberries_server
from yzel.core import vault as vault_module
from yzel.core.tools import ToolKind, kind_of, make_tool
from yzel.core.types import (
    AmoCRMCredential,
    Bitrix24Credential,
    IikoCredential,
    MoyskladCredential,
    OzonCredential,
    ServiceCredential,
    TelegramCredential,
    WildberriesCredential,
)
from yzel.core.vault import CredentialVault

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ServerCase:
    """One connector server plus the kind each of its tools must have."""

    id: str
    server: Server[Any, Any]
    kinds: dict[str, ToolKind]
    # A read tool and arguments that reach the backend when read-only mode is on.
    read_call: tuple[str, dict[str, Any]]
    # Points the server at a backend we can watch (see `watch_backend`: `url` is the bare
    # `http://127.0.0.1:port`; `home` is a scratch directory) and resets any per-process
    # state it keeps, so every test starts from a cold server.
    point_at_backend: Callable[[pytest.MonkeyPatch, str, Path], None]


def _seed_vault(mp: pytest.MonkeyPatch, home: Path, credential: ServiceCredential) -> None:
    """Store `credential` in a scratch vault that the servers' `CredentialVault()` will open."""
    mp.delenv("YZEL_KEY", raising=False)
    mp.setattr(vault_module, "_DEFAULT_DB_PATH", home / "store.db")
    CredentialVault().store("test", credential)


def _point_onec(mp: pytest.MonkeyPatch, url: str, home: Path) -> None:
    mp.setattr(onec_server, "_client", None)
    mp.setenv("YZEL_1C_URL", f"{url}/odata/standard.odata")
    mp.setenv("YZEL_1C_USERNAME", "admin")
    mp.setenv("YZEL_1C_PASSWORD", "test")


def _point_amocrm(mp: pytest.MonkeyPatch, url: str, home: Path) -> None:
    _seed_vault(
        mp,
        home,
        AmoCRMCredential(
            name="t",
            subdomain="t",
            access_token="a",
            refresh_token="r",
            expires_at=time.time() + 3600,
            client_id="c",
            client_secret="s",
            redirect_uri="http://localhost",
        ),
    )

    def client_at_backend(**kwargs: Any) -> AmoCRMClient:
        client = AmoCRMClient(**kwargs)
        client.base_url = url
        return client

    mp.setattr(amocrm_server, "_client", None)
    mp.setattr(amocrm_server, "AmoCRMClient", client_at_backend)


def _point_bitrix24(mp: pytest.MonkeyPatch, url: str, home: Path) -> None:
    _seed_vault(mp, home, Bitrix24Credential(name="t", webhook_url=f"{url}/rest/1/secret/"))
    mp.setattr(bitrix24_server, "_client", None)


def _point_moysklad(mp: pytest.MonkeyPatch, url: str, home: Path) -> None:
    _seed_vault(mp, home, MoyskladCredential(name="t", bearer_token="t"))
    mp.setattr(moysklad_server, "_client", None)
    # The base URL is not part of the credential; rebind it where the server builds the client.
    mp.setattr(
        moysklad_server,
        "MoyskladClient",
        partial(MoyskladClient, base_url=f"{url}/api/remap/1.2"),
    )


def _point_iiko(mp: pytest.MonkeyPatch, url: str, home: Path) -> None:
    _seed_vault(mp, home, IikoCredential(name="t", api_login="t", base_url=url))
    mp.setattr(iiko_server, "_client", None)


def _point_ozon(mp: pytest.MonkeyPatch, url: str, home: Path) -> None:
    _seed_vault(mp, home, OzonCredential(name="t", client_id="1", api_key="t", base_url=url))
    mp.setattr(ozon_server, "_client", None)


def _point_wildberries(mp: pytest.MonkeyPatch, url: str, home: Path) -> None:
    _seed_vault(mp, home, WildberriesCredential(name="t", api_key="t"))
    mp.setattr(wildberries_server, "_client", None)
    for host in wildberries_client._HOSTS:
        mp.setitem(wildberries_client._HOSTS, host, url)


def _point_telegram(mp: pytest.MonkeyPatch, url: str, home: Path) -> None:
    _seed_vault(mp, home, TelegramCredential(name="t", bot_token="1:t", base_url=url))
    mp.setattr(telegram_server, "_client", None)


SERVERS = [
    ServerCase(
        id="onec",
        server=onec_server.server,
        kinds={
            "onec_list_entities": ToolKind.READ,
            "onec_query": ToolKind.READ,
            "onec_get": ToolKind.READ,
            "onec_schema": ToolKind.READ,
            "onec_count": ToolKind.READ,
            "onec_create": ToolKind.CREATE,
            "onec_update": ToolKind.UPDATE,
            "onec_delete": ToolKind.DELETE,
        },
        read_call=("onec_count", {"entity": "Catalog_Контрагенты"}),
        point_at_backend=_point_onec,
    ),
    ServerCase(
        id="amocrm",
        server=amocrm_server.server,
        kinds={
            "amocrm_list": ToolKind.READ,
            "amocrm_get": ToolKind.READ,
            "amocrm_pipelines": ToolKind.READ,
            "amocrm_account": ToolKind.READ,
            "amocrm_create": ToolKind.CREATE,
            "amocrm_update": ToolKind.UPDATE,
        },
        read_call=("amocrm_account", {}),
        point_at_backend=_point_amocrm,
    ),
    ServerCase(
        id="bitrix24",
        server=bitrix24_server.server,
        kinds={
            "bitrix24_crm_list": ToolKind.READ,
            "bitrix24_crm_get": ToolKind.READ,
            "bitrix24_tasks_list": ToolKind.READ,
            "bitrix24_task_get": ToolKind.READ,
            "bitrix24_crm_create": ToolKind.CREATE,
            "bitrix24_crm_update": ToolKind.UPDATE,
        },
        read_call=("bitrix24_tasks_list", {}),
        point_at_backend=_point_bitrix24,
    ),
    ServerCase(
        id="moysklad",
        server=moysklad_server.server,
        kinds={
            "moysklad_list": ToolKind.READ,
            "moysklad_get": ToolKind.READ,
            "moysklad_stock": ToolKind.READ,
            "moysklad_organizations": ToolKind.READ,
            "moysklad_create": ToolKind.CREATE,
            "moysklad_update": ToolKind.UPDATE,
        },
        read_call=("moysklad_organizations", {}),
        point_at_backend=_point_moysklad,
    ),
    ServerCase(
        id="iiko",
        server=iiko_server.server,
        kinds={
            "iiko_organizations": ToolKind.READ,
            "iiko_terminal_groups": ToolKind.READ,
            "iiko_nomenclature": ToolKind.READ,
            "iiko_stop_list": ToolKind.READ,
            "iiko_deliveries_by_phone": ToolKind.READ,
            "iiko_order_types": ToolKind.READ,
            "iiko_payment_types": ToolKind.READ,
            "iiko_employees": ToolKind.READ,
            "iiko_create_delivery": ToolKind.CREATE,
        },
        read_call=("iiko_organizations", {}),
        point_at_backend=_point_iiko,
    ),
    ServerCase(
        id="ozon",
        server=ozon_server.server,
        kinds={
            "ozon_list_warehouses": ToolKind.READ,
            "ozon_list_products": ToolKind.READ,
            "ozon_product_info": ToolKind.READ,
            "ozon_get_stocks": ToolKind.READ,
            "ozon_unfulfilled": ToolKind.READ,
            "ozon_list_postings": ToolKind.READ,
            "ozon_get_posting": ToolKind.READ,
            "ozon_analytics": ToolKind.READ,
            "ozon_transactions": ToolKind.READ,
            "ozon_update_stocks": ToolKind.UPDATE,
            "ozon_update_prices": ToolKind.UPDATE,
        },
        read_call=("ozon_list_warehouses", {}),
        point_at_backend=_point_ozon,
    ),
    ServerCase(
        id="wildberries",
        server=wildberries_server.server,
        kinds={
            "wb_seller_info": ToolKind.READ,
            "wb_list_warehouses": ToolKind.READ,
            "wb_new_orders": ToolKind.READ,
            "wb_get_orders": ToolKind.READ,
            "wb_get_stocks": ToolKind.READ,
            "wb_sales": ToolKind.READ,
            "wb_order_stats": ToolKind.READ,
            "wb_list_cards": ToolKind.READ,
            "wb_get_prices": ToolKind.READ,
            "wb_update_stocks": ToolKind.UPDATE,
        },
        read_call=("wb_seller_info", {}),
        point_at_backend=_point_wildberries,
    ),
    ServerCase(
        id="telegram",
        server=telegram_server.server,
        kinds={
            "tg_get_me": ToolKind.READ,
            "tg_get_webhook_info": ToolKind.READ,
            "tg_get_chat": ToolKind.READ,
            "tg_send_message": ToolKind.CREATE,
            "tg_send_photo": ToolKind.CREATE,
            "tg_send_document": ToolKind.CREATE,
            "tg_answer_callback": ToolKind.CREATE,
            "tg_edit_message": ToolKind.UPDATE,
            "tg_set_webhook": ToolKind.UPDATE,
            "tg_get_updates": ToolKind.UPDATE,
            "tg_delete_message": ToolKind.DELETE,
            "tg_delete_webhook": ToolKind.DELETE,
        },
        read_call=("tg_get_me", {}),
        point_at_backend=_point_telegram,
    ),
]

# (readOnlyHint, destructiveHint, idempotentHint) per kind, from the spec.
ANNOTATIONS: dict[ToolKind, tuple[bool | None, bool | None, bool | None]] = {
    ToolKind.READ: (True, None, None),
    ToolKind.CREATE: (False, False, False),
    ToolKind.UPDATE: (False, True, True),
    ToolKind.DELETE: (False, True, True),
}

WRITE_TOOLS = [(c, n) for c in SERVERS for n, k in c.kinds.items() if k is not ToolKind.READ]


@asynccontextmanager
async def connected(case: ServerCase) -> AsyncIterator[ClientSession]:
    async with create_connected_server_and_client_session(case.server) as session:
        yield session


@asynccontextmanager
async def watch_backend(
    reply: bytes | None = None,
) -> AsyncIterator[tuple[str, list[bytes]]]:
    """A listener that records every connection made to it: proof a request was (not) sent.

    Yields the bare `http://127.0.0.1:port`. With `reply` it answers each request with those
    raw HTTP bytes (to provoke a connector's typed error); otherwise it just hangs up.
    """
    connections: list[bytes] = []

    async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if reply is None:
            connections.append(await reader.read(1))
        else:
            head = await reader.readuntil(b"\r\n\r\n")
            connections.append(head)
            length = next(
                (
                    int(line.split(b":", 1)[1])
                    for line in head.lower().split(b"\r\n")
                    if line.startswith(b"content-length:")
                ),
                0,
            )
            await reader.readexactly(length)
            writer.write(reply)
            await writer.drain()
        writer.close()

    srv = await asyncio.start_server(on_connect, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}", connections
    finally:
        srv.close()
        await srv.wait_closed()


def _payload(result: CallToolResult) -> dict[str, Any]:
    block = result.content[0]
    assert isinstance(block, TextContent)
    loaded: dict[str, Any] = json.loads(block.text)
    return loaded


@pytest.fixture(autouse=True)
def _read_only_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YZEL_READ_ONLY", raising=False)


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_every_listed_tool_carries_annotations_matching_its_kind(case: ServerCase) -> None:
    async with connected(case) as session:
        tools = (await session.list_tools()).tools

    assert {t.name for t in tools} == set(case.kinds)
    for tool in tools:
        assert tool.annotations is not None, f"{tool.name} has no annotations"
        got = tool.annotations
        assert (got.readOnlyHint, got.destructiveHint, got.idempotentHint) == ANNOTATIONS[
            case.kinds[tool.name]
        ], tool.name
        assert got.openWorldHint is True, tool.name
        assert kind_of(tool) is case.kinds[tool.name]


@pytest.mark.parametrize("flag", ["1", "true", "TRUE", "yes", "on"])
@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_read_only_mode_lists_exactly_the_read_tools(
    case: ServerCase, flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YZEL_READ_ONLY", flag)
    async with connected(case) as session:
        listed = {t.name for t in (await session.list_tools()).tools}

    assert listed == {n for n, k in case.kinds.items() if k is ToolKind.READ}


@pytest.mark.parametrize("flag", ["", "0", "false", "no", "off"])
@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_other_values_leave_every_tool_listed(
    case: ServerCase, flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YZEL_READ_ONLY", flag)
    async with connected(case) as session:
        listed = {t.name for t in (await session.list_tools()).tools}

    assert listed == set(case.kinds)


async def _refused_call(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> tuple[CallToolResult, list[bytes]]:
    """Call `name` with no arguments in read-only mode; also return the backend's connections."""
    monkeypatch.setenv("YZEL_READ_ONLY", "1")
    async with watch_backend() as (url, connections):
        case.point_at_backend(monkeypatch, url, tmp_path)
        async with connected(case) as session:
            # Like a real client: list first (the server caches that list), then call by name.
            await session.list_tools()
            result = await session.call_tool(name, {})
    return result, connections


def _assert_refused(result: CallToolResult, connections: list[bytes]) -> None:
    assert result.isError is True
    body = _payload(result)
    assert body["outcome"] == "refused"
    assert "YZEL_READ_ONLY" in body["message"]
    assert connections == [], "a request reached the backend"


@pytest.mark.parametrize(("case", "tool"), WRITE_TOOLS, ids=lambda v: getattr(v, "id", v))
async def test_read_only_mode_refuses_a_hidden_write_tool_without_touching_the_backend(
    case: ServerCase, tool: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A client with a cached tool list, or an agent guessing the name, still calls it."""
    result, connections = await _refused_call(case, monkeypatch, tmp_path, tool)

    _assert_refused(result, connections)


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_read_only_mode_refuses_a_name_the_server_does_not_list(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fail closed: a write branch missing from the tool list must not run either."""
    result, connections = await _refused_call(case, monkeypatch, tmp_path, "no_such_tool")

    _assert_refused(result, connections)


@pytest.mark.parametrize("case", SERVERS, ids=lambda c: c.id)
async def test_read_only_mode_still_serves_read_tools(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The refusal is for everything but listed READ tools: a read call reaches the backend."""
    monkeypatch.setenv("YZEL_READ_ONLY", "1")
    tool, arguments = case.read_call
    async with watch_backend() as (url, connections):
        case.point_at_backend(monkeypatch, url, tmp_path)
        async with connected(case) as session:
            await session.call_tool(tool, arguments)

    assert connections, "the read call never reached the backend"


# 1C is covered by slice 2, which converts its own typed error.
TYPED_ERROR_CASES = [c for c in SERVERS if c.id != "onec"]
_BAD_REQUEST = (
    b"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\n"
    b'Content-Length: 21\r\nConnection: close\r\n\r\n{"message": "boom!!!"}'
)


@pytest.mark.parametrize("case", TYPED_ERROR_CASES, ids=lambda c: c.id)
async def test_a_typed_backend_error_on_a_read_is_an_error_result(
    case: ServerCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The model must see `isError`, not a successful-looking result that says "Ошибка"."""
    tool, arguments = case.read_call
    async with watch_backend(_BAD_REQUEST) as (url, connections):
        case.point_at_backend(monkeypatch, url, tmp_path)
        async with connected(case) as session:
            result = await session.call_tool(tool, arguments)

    assert connections, "the read call never reached the backend"
    assert result.isError is True
    assert isinstance(result.content[0], TextContent)
    assert result.content[0].text


@pytest.mark.parametrize("kind", list(ToolKind))
def test_make_tool_round_trips_kind_and_keeps_callers_schema_intact(kind: ToolKind) -> None:
    schema: dict[str, Any] = {"type": "object", "properties": {"a": {"type": "string"}}}
    tool = make_tool("t", "d", schema, kind)

    assert kind_of(tool) is kind
    assert schema == {"type": "object", "properties": {"a": {"type": "string"}}}
    has_again = "again" in tool.inputSchema["properties"]
    assert has_again is (kind is ToolKind.CREATE)
    if has_again:
        assert tool.inputSchema["properties"]["again"]["type"] == "boolean"
        assert "again" not in tool.inputSchema.get("required", [])


def test_kind_of_rejects_a_tool_not_built_by_make_tool() -> None:
    with pytest.raises(ValueError):
        kind_of(Tool(name="bare", inputSchema={"type": "object"}))


def test_onec_extension_checkbox_defaults_to_read_only_and_reaches_the_server() -> None:
    """The .mcpb host passes the checkbox as the env var the server reads."""
    manifest = json.loads((ROOT / "extensions" / "1c" / "manifest.json").read_text("utf-8"))

    assert manifest["user_config"]["read_only"]["type"] == "boolean"
    assert manifest["user_config"]["read_only"]["default"] is True
    env = manifest["server"]["mcp_config"]["env"]
    assert env["YZEL_READ_ONLY"] == "${user_config.read_only}"
