"""Mock iiko Cloud API server.

Emulates apiLogin → access_token exchange and the MVP set of POST endpoints.
Issues short-lived tokens (`token-v{N}`) so the 401-then-refresh path can be
exercised deterministically without sleeping.
"""

from __future__ import annotations

import time

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

VALID_API_LOGIN = "test-api-login"

# Server state — the "current" token the server will accept
_current_token_version = 0
_current_token: str | None = None


def _mint_token() -> str:
    global _current_token_version, _current_token
    _current_token_version += 1
    _current_token = f"iiko-token-v{_current_token_version}"
    return _current_token


def invalidate_current_token() -> None:
    """Helper for tests — forces the next request to 401 before refresh."""
    global _current_token
    _current_token = None


def _auth(request: Request) -> JSONResponse | None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(
            {"errorDescription": "Отсутствует токен"}, status_code=401
        )
    token = auth[len("Bearer ") :]
    if _current_token is None or token != _current_token:
        return JSONResponse(
            {"errorDescription": "Токен недействителен"}, status_code=401
        )
    return None


async def access_token(request: Request) -> JSONResponse:
    body = await request.json()
    if body.get("apiLogin") != VALID_API_LOGIN:
        return JSONResponse(
            {"errorDescription": "apiLogin не найден"}, status_code=401
        )
    return JSONResponse({"token": _mint_token()})


ORGANIZATIONS = [
    {"id": "org-1", "name": "Кафе Уют", "country": "Kazakhstan"},
    {"id": "org-2", "name": "Ресторан Арбат", "country": "Russia"},
]

TERMINAL_GROUPS_BY_ORG = {
    "org-1": [{"id": "tg-1", "organizationId": "org-1", "name": "Касса 1"}],
    "org-2": [
        {"id": "tg-2", "organizationId": "org-2", "name": "Касса главная"},
        {"id": "tg-3", "organizationId": "org-2", "name": "Касса терраса"},
    ],
}

NOMENCLATURE = {
    "org-1": {
        "groups": [{"id": "grp-1", "name": "Напитки"}],
        "products": [
            {"id": "p-1", "name": "Капучино", "price": 1500, "groupId": "grp-1"},
            {"id": "p-2", "name": "Американо", "price": 1200, "groupId": "grp-1"},
        ],
    }
}

STOP_LISTS = {
    "org-1": [
        {
            "terminalGroupId": "tg-1",
            "items": [{"productId": "p-2", "balance": 0}],
        }
    ]
}

ORDER_TYPES = {
    "org-1": [
        {"id": "ot-dine-in", "name": "В зале"},
        {"id": "ot-delivery", "name": "Доставка"},
    ]
}

PAYMENT_TYPES = {
    "org-1": [
        {"id": "pt-cash", "name": "Наличные"},
        {"id": "pt-card", "name": "Карта"},
    ]
}

EMPLOYEES = {
    "org-1": [{"id": "emp-1", "firstName": "Иван", "lastName": "Петров"}]
}

DELIVERIES_BY_PHONE: dict[tuple[str, str], list[dict]] = {
    ("org-1", "+77011234567"): [
        {"id": "ord-1", "phone": "+77011234567", "total": 3200}
    ]
}

CREATED_ORDERS: list[dict] = []


async def organizations(request: Request) -> JSONResponse:
    if err := _auth(request):
        return err
    body = await request.json()
    wanted = body.get("organizationIds")
    orgs = (
        [o for o in ORGANIZATIONS if o["id"] in set(wanted)]
        if wanted
        else ORGANIZATIONS
    )
    return JSONResponse({"organizations": orgs})


async def terminal_groups(request: Request) -> JSONResponse:
    if err := _auth(request):
        return err
    body = await request.json()
    groups: list[dict] = []
    for org_id in body.get("organizationIds", []):
        groups.extend(TERMINAL_GROUPS_BY_ORG.get(org_id, []))
    return JSONResponse({"terminalGroups": groups})


async def nomenclature(request: Request) -> JSONResponse:
    if err := _auth(request):
        return err
    body = await request.json()
    org_id = body.get("organizationId")
    if org_id not in NOMENCLATURE:
        return JSONResponse(
            {"errorDescription": f"Организация {org_id} не найдена"},
            status_code=400,
        )
    return JSONResponse(NOMENCLATURE[org_id])


async def stop_lists(request: Request) -> JSONResponse:
    if err := _auth(request):
        return err
    body = await request.json()
    result = []
    for org_id in body.get("organizationIds", []):
        result.extend(STOP_LISTS.get(org_id, []))
    return JSONResponse({"terminalGroupStopLists": result})


async def deliveries_by_phone(request: Request) -> JSONResponse:
    if err := _auth(request):
        return err
    body = await request.json()
    phone = body.get("phone")
    result = []
    for org_id in body.get("organizationIds", []):
        for order in DELIVERIES_BY_PHONE.get((org_id, phone), []):
            result.append({"organizationId": org_id, "orders": [order]})
    return JSONResponse({"ordersByOrganizations": result})


async def create_delivery(request: Request) -> JSONResponse:
    if err := _auth(request):
        return err
    body = await request.json()
    order = {
        "id": f"new-ord-{len(CREATED_ORDERS) + 1}",
        "organizationId": body.get("organizationId"),
        "terminalGroupId": body.get("terminalGroupId"),
        "created_at": int(time.time()),
        "submitted": body.get("order"),
    }
    CREATED_ORDERS.append(order)
    return JSONResponse({"orderInfo": order})


async def order_types(request: Request) -> JSONResponse:
    if err := _auth(request):
        return err
    body = await request.json()
    result = []
    for org_id in body.get("organizationIds", []):
        result.append(
            {"organizationId": org_id, "items": ORDER_TYPES.get(org_id, [])}
        )
    return JSONResponse({"orderTypes": result})


async def payment_types(request: Request) -> JSONResponse:
    if err := _auth(request):
        return err
    body = await request.json()
    result = []
    for org_id in body.get("organizationIds", []):
        for pt in PAYMENT_TYPES.get(org_id, []):
            result.append({**pt, "organizationId": org_id})
    return JSONResponse({"paymentTypes": result})


async def employees(request: Request) -> JSONResponse:
    if err := _auth(request):
        return err
    body = await request.json()
    result = []
    for org_id in body.get("organizationIds", []):
        for emp in EMPLOYEES.get(org_id, []):
            result.append({**emp, "organizationId": org_id})
    return JSONResponse({"employees": result})


app = Starlette(
    routes=[
        Route("/api/1/access_token", access_token, methods=["POST"]),
        Route("/api/1/organizations", organizations, methods=["POST"]),
        Route("/api/1/terminal_groups", terminal_groups, methods=["POST"]),
        Route("/api/1/nomenclature", nomenclature, methods=["POST"]),
        Route("/api/1/stop_lists", stop_lists, methods=["POST"]),
        Route(
            "/api/1/deliveries/by_delivery_date_and_phone",
            deliveries_by_phone,
            methods=["POST"],
        ),
        Route("/api/1/deliveries/create", create_delivery, methods=["POST"]),
        Route("/api/1/deliveries/order_types", order_types, methods=["POST"]),
        Route("/api/1/payment_types", payment_types, methods=["POST"]),
        Route("/api/1/employees", employees, methods=["POST"]),
    ],
)


if __name__ == "__main__":
    import uvicorn

    print("🍲 Mock iiko Cloud API — http://localhost:8082 — apiLogin: test-api-login")
    uvicorn.run(app, host="0.0.0.0", port=8082)
