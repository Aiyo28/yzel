"""Mock Moysklad JSON API 1.2 server for testing.

Simulates a Moysklad account with:
- Counterparties (контрагенты)
- Products (товары)
- Customer orders (заказы покупателей) with nested entity expansion
- Stock reports (остатки)
- Organizations (юрлица)
- Bearer token auth

Usage:
    python -m tests.mock_moysklad_server
    # Runs on http://localhost:8079/api/remap/1.2/
    # Token: test_bearer_token_value
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

# --- Auth ---
VALID_TOKEN = "test_bearer_token_value"  # noqa: S105


def _check_auth(request: Request) -> Response | None:
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {VALID_TOKEN}":
        return JSONResponse(
            {"errors": [{"error": "Ошибка аутентификации", "code": 1056}]},
            status_code=401,
        )
    return None


# --- Demo Data ---

COUNTERPARTIES = [
    {
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "type": "counterparty",
        },
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "ООО Рога и Копыта",
        "inn": "7701234567",
        "kpp": "770101001",
        "companyType": "legal",
        "legalTitle": "Общество с ограниченной ответственностью «Рога и Копыта»",
        "phone": "+7 (495) 100-00-01",
        "email": "info@rogakopyta.ru",
    },
    {
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "type": "counterparty",
        },
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "name": "ИП Петров П.П.",
        "inn": "771234567890",
        "companyType": "individual",
        "phone": "+7 (495) 200-00-02",
    },
    {
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/c3d4e5f6-a7b8-9012-cdef-234567890123",
            "type": "counterparty",
        },
        "id": "c3d4e5f6-a7b8-9012-cdef-234567890123",
        "name": "ТОО КазМунайГаз",
        "inn": "040240003505",
        "companyType": "legal",
        "legalTitle": "Товарищество с ограниченной ответственностью «КазМунайГаз»",
    },
]

PRODUCTS = [
    {
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/product/d4e5f6a7-b8c9-0123-defa-345678901234",
            "type": "product",
        },
        "id": "d4e5f6a7-b8c9-0123-defa-345678901234",
        "name": "Бумага А4 офисная",
        "code": "BUM-A4-500",
        "article": "BUM-A4-500",
        "salePrices": [{"value": 35000, "currency": {"name": "руб"}}],
        "buyPrice": {"value": 25000, "currency": {"name": "руб"}},
        "uom": {"name": "упак"},
    },
    {
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/product/e5f6a7b8-c9d0-1234-efab-456789012345",
            "type": "product",
        },
        "id": "e5f6a7b8-c9d0-1234-efab-456789012345",
        "name": "Дизельное топливо ДТ-Л",
        "code": "DT-L-001",
        "article": "DT-L-001",
        "salePrices": [{"value": 6500, "currency": {"name": "руб"}}],
        "buyPrice": {"value": 5800, "currency": {"name": "руб"}},
        "uom": {"name": "л"},
    },
]

ORGANIZATIONS = [
    {
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/organization/f6a7b8c9-d0e1-2345-fabc-567890123456",
            "type": "organization",
        },
        "id": "f6a7b8c9-d0e1-2345-fabc-567890123456",
        "name": "ООО Моя Компания",
        "inn": "7707654321",
        "kpp": "770701001",
    },
]

# Orders reference counterparties and org — nested expansion test
CUSTOMER_ORDERS = [
    {
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/customerorder/11111111-1111-1111-1111-111111111111",
            "type": "customerorder",
        },
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "00001",
        "moment": "2026-04-01 10:30:00",
        "sum": 4500000,  # in kopeks (45,000 RUB)
        "agent": {
            "meta": {
                "href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "type": "counterparty",
            },
        },
        "organization": {
            "meta": {
                "href": "https://api.moysklad.ru/api/remap/1.2/entity/organization/f6a7b8c9-d0e1-2345-fabc-567890123456",
                "type": "organization",
            },
        },
        "state": {"name": "Новый"},
    },
    {
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/customerorder/22222222-2222-2222-2222-222222222222",
            "type": "customerorder",
        },
        "id": "22222222-2222-2222-2222-222222222222",
        "name": "00002",
        "moment": "2026-04-05 14:00:00",
        "sum": 12850050,
        "agent": {
            "meta": {
                "href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/c3d4e5f6-a7b8-9012-cdef-234567890123",
                "type": "counterparty",
            },
        },
        "organization": {
            "meta": {
                "href": "https://api.moysklad.ru/api/remap/1.2/entity/organization/f6a7b8c9-d0e1-2345-fabc-567890123456",
                "type": "organization",
            },
        },
        "state": {"name": "Подтверждён"},
    },
]

STOCK_ALL = [
    {"name": "Бумага А4 офисная", "code": "BUM-A4-500", "stock": 150, "reserve": 20, "inTransit": 0, "quantity": 150},
    {"name": "Дизельное топливо ДТ-Л", "code": "DT-L-001", "stock": 5000, "reserve": 0, "inTransit": 200, "quantity": 5000},
]

STOCK_BYSTORE = [
    {"name": "Бумага А4 офисная", "stockByStore": [
        {"store": {"name": "Основной склад"}, "stock": 100, "reserve": 20},
        {"store": {"name": "Склад №2"}, "stock": 50, "reserve": 0},
    ]},
    {"name": "Дизельное топливо ДТ-Л", "stockByStore": [
        {"store": {"name": "ГСМ Склад"}, "stock": 5000, "reserve": 0},
    ]},
]

# Entity registries
ENTITIES: dict[str, list[dict[str, Any]]] = {
    "counterparty": COUNTERPARTIES,
    "product": PRODUCTS,
    "customerorder": CUSTOMER_ORDERS,
    "organization": ORGANIZATIONS,
}

_next_id_counter = 0


def _expand_nested(item: dict[str, Any], expand_fields: list[str]) -> dict[str, Any]:
    """Expand nested entity references to full objects (simulates Moysklad expand)."""
    result = dict(item)
    for field in expand_fields:
        field = field.strip()
        if field not in result:
            continue
        nested = result[field]
        if not isinstance(nested, dict) or "meta" not in nested:
            continue
        # Resolve the reference
        href = nested["meta"].get("href", "")
        entity_type = nested["meta"].get("type", "")
        if entity_type in ENTITIES:
            # Find by matching href suffix (the UUID)
            for candidate in ENTITIES[entity_type]:
                if candidate["id"] in href:
                    result[field] = candidate
                    break
    return result


# --- Handlers ---

async def entity_list(request: Request) -> Response:
    if err := _check_auth(request):
        return err

    entity_type = request.path_params["entity_type"]
    if entity_type not in ENTITIES:
        return JSONResponse(
            {"errors": [{"error": f"Неизвестный тип сущности: {entity_type}", "code": 1005}]},
            status_code=404,
        )

    items = list(ENTITIES[entity_type])

    # Search
    search = request.query_params.get("search")
    if search:
        search_lower = search.lower()
        items = [i for i in items if search_lower in i.get("name", "").lower()]

    # Filter (basic: name=value)
    filter_expr = request.query_params.get("filter")
    if filter_expr:
        for part in filter_expr.split(";"):
            if "=" in part:
                key, _, val = part.partition("=")
                items = [i for i in items if str(i.get(key.strip(), "")) == val.strip()]

    total = len(items)

    # Pagination
    offset = int(request.query_params.get("offset", 0))
    limit = int(request.query_params.get("limit", 25))
    items = items[offset : offset + limit]

    # Expand
    expand = request.query_params.get("expand")
    if expand:
        expand_fields = expand.split(",")
        items = [_expand_nested(i, expand_fields) for i in items]

    return JSONResponse({
        "meta": {"href": str(request.url), "type": entity_type, "size": total, "limit": limit, "offset": offset},
        "rows": items,
    })


async def entity_get(request: Request) -> Response:
    if err := _check_auth(request):
        return err

    entity_type = request.path_params["entity_type"]
    entity_id = request.path_params["entity_id"]

    if entity_type not in ENTITIES:
        return JSONResponse(
            {"errors": [{"error": f"Неизвестный тип сущности: {entity_type}", "code": 1005}]},
            status_code=404,
        )

    for item in ENTITIES[entity_type]:
        if item["id"] == entity_id:
            expand = request.query_params.get("expand")
            if expand:
                return JSONResponse(_expand_nested(item, expand.split(",")))
            return JSONResponse(item)

    return JSONResponse(
        {"errors": [{"error": f"Объект не найден: {entity_id}", "code": 1056}]},
        status_code=404,
    )


async def entity_create(request: Request) -> Response:
    if err := _check_auth(request):
        return err

    entity_type = request.path_params["entity_type"]
    if entity_type not in ENTITIES:
        return JSONResponse(
            {"errors": [{"error": f"Неизвестный тип сущности: {entity_type}", "code": 1005}]},
            status_code=404,
        )

    body = await request.json()
    global _next_id_counter
    _next_id_counter += 1
    new_id = str(uuid.uuid4())
    body["id"] = new_id
    body["meta"] = {
        "href": f"https://api.moysklad.ru/api/remap/1.2/entity/{entity_type}/{new_id}",
        "type": entity_type,
    }
    ENTITIES[entity_type].append(body)
    return JSONResponse(body, status_code=200)


async def entity_update(request: Request) -> Response:
    if err := _check_auth(request):
        return err

    entity_type = request.path_params["entity_type"]
    entity_id = request.path_params["entity_id"]

    if entity_type not in ENTITIES:
        return JSONResponse(
            {"errors": [{"error": f"Неизвестный тип сущности: {entity_type}", "code": 1005}]},
            status_code=404,
        )

    body = await request.json()
    for item in ENTITIES[entity_type]:
        if item["id"] == entity_id:
            item.update(body)
            return JSONResponse(item)

    return JSONResponse(
        {"errors": [{"error": f"Объект не найден: {entity_id}", "code": 1056}]},
        status_code=404,
    )


async def stock_all(request: Request) -> Response:
    if err := _check_auth(request):
        return err
    return JSONResponse({
        "meta": {"href": str(request.url), "size": len(STOCK_ALL)},
        "rows": STOCK_ALL,
    })


async def stock_bystore(request: Request) -> Response:
    if err := _check_auth(request):
        return err
    return JSONResponse({
        "meta": {"href": str(request.url), "size": len(STOCK_BYSTORE)},
        "rows": STOCK_BYSTORE,
    })


# --- App ---

app = Starlette(
    routes=[
        Route("/api/remap/1.2/entity/{entity_type}/{entity_id}", entity_get, methods=["GET"]),
        Route("/api/remap/1.2/entity/{entity_type}/{entity_id}", entity_update, methods=["PUT"]),
        Route("/api/remap/1.2/entity/{entity_type}", entity_list, methods=["GET"]),
        Route("/api/remap/1.2/entity/{entity_type}", entity_create, methods=["POST"]),
        Route("/api/remap/1.2/report/stock/all", stock_all, methods=["GET"]),
        Route("/api/remap/1.2/report/stock/bystore", stock_bystore, methods=["GET"]),
    ],
)

if __name__ == "__main__":
    import uvicorn

    print("🔧 Mock Moysklad JSON API 1.2 Server")
    print("   URL:   http://localhost:8079/api/remap/1.2/")
    print("   Token: test_bearer_token_value")
    print("   Entities: counterparty, product, customerorder, organization")
    uvicorn.run(app, host="0.0.0.0", port=8079)
