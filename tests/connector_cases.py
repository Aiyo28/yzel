"""Per-connector wiring shared by the tool-safety tests: one `ServerCase` per server.

To cover another connector, append one `ServerCase` to `SERVERS`.
"""

from __future__ import annotations

import asyncio
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

from yzel.connectors.amocrm import server as amocrm_server
from yzel.connectors.amocrm.client import AmoCRMClient
from yzel.connectors.bitrix24 import server as bitrix24_server
from yzel.connectors.iiko import server as iiko_server
from yzel.connectors.moysklad import server as moysklad_server
from yzel.connectors.moysklad.client import MoyskladClient
from yzel.connectors.onec import server as onec_server
from yzel.connectors.onec.odata import OneCODataClient
from yzel.connectors.ozon import server as ozon_server
from yzel.connectors.telegram import server as telegram_server
from yzel.connectors.wildberries import client as wildberries_client
from yzel.connectors.wildberries import server as wildberries_server
from yzel.core import vault as vault_module
from yzel.core.tools import ToolKind
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
    # Minimal valid arguments for every non-READ tool, enough to put a request on the wire.
    write_calls: dict[str, dict[str, Any]]


def _seed_vault(mp: pytest.MonkeyPatch, home: Path, credential: ServiceCredential) -> None:
    """Store `credential` in a scratch vault that the servers' `CredentialVault()` will open."""
    mp.delenv("YZEL_KEY", raising=False)
    mp.setattr(vault_module, "_DEFAULT_DB_PATH", home / "store.db")
    CredentialVault().store("test", credential)


def _point_onec(mp: pytest.MonkeyPatch, url: str, home: Path) -> None:
    # Hand the server a ready client: a cold start runs schema discovery first, and a failing
    # `$metadata` would end the call before the tool under test is reached.
    mp.setattr(
        onec_server, "_client", OneCODataClient(f"{url}/odata/standard.odata", "admin", "test")
    )
    mp.setattr(onec_server, "_schema", [])


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
        write_calls={
            "onec_create": {"entity": "Catalog_Контрагенты", "data": {"Description": "A"}},
            "onec_update": {"entity": "Catalog_Контрагенты", "key": "k", "data": {}},
            "onec_delete": {"entity": "Catalog_Контрагенты", "key": "k"},
        },
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
        write_calls={
            "amocrm_create": {"entity": "lead", "items": [{"name": "A"}]},
            "amocrm_update": {"entity": "lead", "id": 1, "fields": {"name": "B"}},
        },
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
        write_calls={
            "bitrix24_crm_create": {"entity": "lead", "fields": {"TITLE": "A"}},
            "bitrix24_crm_update": {"entity": "lead", "id": 1, "fields": {"TITLE": "B"}},
        },
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
        write_calls={
            "moysklad_create": {"entity": "counterparty", "fields": {"name": "A"}},
            "moysklad_update": {"entity": "counterparty", "id": "i", "fields": {"name": "B"}},
        },
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
        write_calls={
            "iiko_create_delivery": {
                "organization_id": "o",
                "terminal_group_id": "g",
                "order": {"phone": "+77001112233"},
            },
        },
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
        write_calls={
            "ozon_update_stocks": {"stocks": [{"offer_id": "A", "stock": 1, "warehouse_id": 1}]},
            "ozon_update_prices": {"prices": [{"offer_id": "A", "price": "100"}]},
        },
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
        write_calls={
            "wb_update_stocks": {"warehouse_id": 1, "stocks": [{"sku": "1", "amount": 1}]},
        },
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
        write_calls={
            "tg_send_message": {"chat_id": 1, "text": "hi"},
            "tg_send_photo": {"chat_id": 1, "photo": "https://example.com/a.png"},
            "tg_send_document": {"chat_id": 1, "document": "https://example.com/a.pdf"},
            "tg_answer_callback": {"callback_query_id": "c"},
            "tg_edit_message": {"chat_id": 1, "message_id": 2, "text": "hi"},
            "tg_set_webhook": {"url": "https://example.com/hook"},
            "tg_get_updates": {},
            "tg_delete_message": {"chat_id": 1, "message_id": 2},
            "tg_delete_webhook": {},
        },
    ),
]


_BAD_REQUEST_BODY = b'{"message": "boom!!!"}'
# Raw HTTP reply for `watch_backend`: every connector turns a 400 into its typed error.
BAD_REQUEST = (
    b"HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\n"
    + b"Content-Length: %d\r\nConnection: close\r\n\r\n" % len(_BAD_REQUEST_BODY)
    + _BAD_REQUEST_BODY
)


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
