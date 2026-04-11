"""Mock AmoCRM (Kommo) API v4 server for testing.

Simulates an AmoCRM portal with:
- OAuth2 token exchange and refresh
- Leads (сделки), contacts (контакты), companies (компании)
- Pipelines (воронки)
- Account info
- Bearer token auth on all API endpoints

Usage:
    python -m tests.mock_amocrm_server
    # Runs on http://localhost:8080/
    # Initial access token: test_access_value
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

# --- Auth State ---
# These are test-only placeholder values, not real credentials
_current_access = "test_access_value"  # noqa: S105
_current_refresh = "test_refresh_value"  # noqa: S105
_token_expires_in = 1200  # 20 minutes (AmoCRM default)

VALID_CLIENT_ID = "test_client_id"
VALID_CLIENT_SECRET = "test_client_secret_val"  # noqa: S105
VALID_REDIRECT_URI = "https://example.com/oauth/callback"


def reset_state() -> None:
    """Reset mutable server state between tests."""
    global _current_access, _current_refresh
    _current_access = "test_access_value"  # noqa: S105
    _current_refresh = "test_refresh_value"  # noqa: S105


def _check_auth(request: Request) -> Response | None:
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {_current_access}":
        return JSONResponse(
            {"title": "Unauthorized", "status": 401, "detail": "Неверный токен доступа"},
            status_code=401,
        )
    return None


# --- Token endpoint ---

async def oauth_token(request: Request) -> Response:
    """Handle OAuth2 token exchange and refresh."""
    global _current_access, _current_refresh

    body = await request.json()
    grant_type = body.get("grant_type")

    if body.get("client_id") != VALID_CLIENT_ID or body.get("client_secret") != VALID_CLIENT_SECRET:
        return JSONResponse(
            {"hint": "Неверные client_id или client_secret", "message": "Ошибка авторизации"},
            status_code=401,
        )

    if grant_type == "refresh_token":
        if body.get("refresh_token") != _current_refresh:
            return JSONResponse(
                {"hint": "Неверный refresh_token", "message": "Токен обновления недействителен"},
                status_code=401,
            )
        # Issue new tokens
        _current_access = f"refreshed_{uuid.uuid4().hex[:8]}"
        _current_refresh = f"refresh_{uuid.uuid4().hex[:8]}"
        return JSONResponse({
            "token_type": "Bearer",
            "expires_in": _token_expires_in,
            "access_token": _current_access,
            "refresh_token": _current_refresh,
        })

    elif grant_type == "authorization_code":
        _current_access = f"auth_{uuid.uuid4().hex[:8]}"
        _current_refresh = f"refresh_{uuid.uuid4().hex[:8]}"
        return JSONResponse({
            "token_type": "Bearer",
            "expires_in": _token_expires_in,
            "access_token": _current_access,
            "refresh_token": _current_refresh,
        })

    return JSONResponse(
        {"hint": f"Неизвестный grant_type: {grant_type}", "message": "Ошибка"},
        status_code=400,
    )


# --- Demo Data ---

LEADS = [
    {
        "id": 1,
        "name": "Поставка офисного оборудования",
        "price": 250000,
        "status_id": 142,
        "pipeline_id": 1,
        "responsible_user_id": 1,
        "created_at": 1711958400,
        "updated_at": 1712044800,
        "_embedded": {"contacts": [{"id": 1}], "companies": [{"id": 1}]},
    },
    {
        "id": 2,
        "name": "Внедрение CRM-системы",
        "price": 800000,
        "status_id": 143,
        "pipeline_id": 1,
        "responsible_user_id": 1,
        "created_at": 1712131200,
        "updated_at": 1712217600,
        "_embedded": {"contacts": [{"id": 2}]},
    },
    {
        "id": 3,
        "name": "Дизайн-проект интерьера",
        "price": 150000,
        "status_id": 142,
        "pipeline_id": 2,
        "responsible_user_id": 2,
        "created_at": 1712304000,
        "updated_at": 1712390400,
        "_embedded": {},
    },
]

CONTACTS = [
    {
        "id": 1,
        "name": "Алексей Смирнов",
        "first_name": "Алексей",
        "last_name": "Смирнов",
        "responsible_user_id": 1,
        "custom_fields_values": [
            {"field_name": "Телефон", "values": [{"value": "+7 (495) 123-45-67"}]},
            {"field_name": "Email", "values": [{"value": "smirnov@rogakopyta.ru"}]},
        ],
    },
    {
        "id": 2,
        "name": "Мария Козлова",
        "first_name": "Мария",
        "last_name": "Козлова",
        "responsible_user_id": 1,
        "custom_fields_values": [
            {"field_name": "Телефон", "values": [{"value": "+7 (495) 987-65-43"}]},
        ],
    },
]

COMPANIES = [
    {
        "id": 1,
        "name": "ООО Рога и Копыта",
        "responsible_user_id": 1,
        "custom_fields_values": [
            {"field_name": "ИНН", "values": [{"value": "7701234567"}]},
        ],
    },
    {
        "id": 2,
        "name": "ООО ТехСервис",
        "responsible_user_id": 2,
        "custom_fields_values": [
            {"field_name": "ИНН", "values": [{"value": "7707654321"}]},
        ],
    },
]

PIPELINES = [
    {
        "id": 1,
        "name": "Основная воронка",
        "sort": 1,
        "is_main": True,
        "_embedded": {
            "statuses": [
                {"id": 142, "name": "Новая заявка", "sort": 1, "color": "#99ccff"},
                {"id": 143, "name": "Переговоры", "sort": 2, "color": "#ffcc66"},
                {"id": 142, "name": "Успешно", "sort": 3, "color": "#ccff99"},
            ],
        },
    },
    {
        "id": 2,
        "name": "Дизайн-проекты",
        "sort": 2,
        "is_main": False,
        "_embedded": {
            "statuses": [
                {"id": 200, "name": "Новый запрос", "sort": 1, "color": "#99ccff"},
                {"id": 201, "name": "В работе", "sort": 2, "color": "#ffcc66"},
            ],
        },
    },
]

ACCOUNT = {
    "id": 12345,
    "name": "Тестовый аккаунт",
    "subdomain": "test",
    "current_user_id": 1,
    "country": "RU",
    "currency": "RUB",
}

CRM_ENTITIES: dict[str, list[dict[str, Any]]] = {
    "leads": LEADS,
    "contacts": CONTACTS,
    "companies": COMPANIES,
}

_next_ids: dict[str, int] = {"leads": 100, "contacts": 100, "companies": 100}


# --- Handlers ---

async def entity_list(request: Request) -> Response:
    if err := _check_auth(request):
        return err

    entity_type = request.path_params["entity_type"]
    if entity_type not in CRM_ENTITIES:
        return JSONResponse(
            {"title": "Not Found", "status": 404, "detail": f"Сущность '{entity_type}' не найдена"},
            status_code=404,
        )

    items = list(CRM_ENTITIES[entity_type])

    # Query search
    query = request.query_params.get("query")
    if query:
        query_lower = query.lower()
        items = [i for i in items if query_lower in i.get("name", "").lower()]

    total = len(items)

    # Pagination
    page = int(request.query_params.get("page", 1))
    limit = int(request.query_params.get("limit", 50))
    start = (page - 1) * limit
    items = items[start : start + limit]

    return JSONResponse({
        "_page": page,
        "_links": {"self": {"href": str(request.url)}},
        "_embedded": {entity_type: items},
    })


async def entity_get(request: Request) -> Response:
    if err := _check_auth(request):
        return err

    entity_type = request.path_params["entity_type"]
    entity_id = int(request.path_params["entity_id"])

    if entity_type not in CRM_ENTITIES:
        return JSONResponse({"detail": "Not found"}, status_code=404)

    for item in CRM_ENTITIES[entity_type]:
        if item["id"] == entity_id:
            return JSONResponse(item)

    return JSONResponse(
        {"title": "Not Found", "status": 404, "detail": f"ID {entity_id} не найден"},
        status_code=404,
    )


async def entity_create(request: Request) -> Response:
    if err := _check_auth(request):
        return err

    entity_type = request.path_params["entity_type"]
    if entity_type not in CRM_ENTITIES:
        return JSONResponse({"detail": "Not found"}, status_code=404)

    body = await request.json()
    created = []
    for item in body:
        new_id = _next_ids[entity_type]
        _next_ids[entity_type] += 1
        item["id"] = new_id
        CRM_ENTITIES[entity_type].append(item)
        created.append(item)

    return JSONResponse({"_embedded": {entity_type: created}})


async def entity_update(request: Request) -> Response:
    if err := _check_auth(request):
        return err

    entity_type = request.path_params["entity_type"]
    entity_id = int(request.path_params["entity_id"])

    if entity_type not in CRM_ENTITIES:
        return JSONResponse({"detail": "Not found"}, status_code=404)

    body = await request.json()
    for item in CRM_ENTITIES[entity_type]:
        if item["id"] == entity_id:
            item.update(body)
            return JSONResponse(item)

    return JSONResponse(
        {"title": "Not Found", "status": 404, "detail": f"ID {entity_id} не найден"},
        status_code=404,
    )


async def pipelines_list(request: Request) -> Response:
    if err := _check_auth(request):
        return err
    return JSONResponse({"_embedded": {"pipelines": PIPELINES}})


async def pipeline_get(request: Request) -> Response:
    if err := _check_auth(request):
        return err

    pipeline_id = int(request.path_params["pipeline_id"])
    for p in PIPELINES:
        if p["id"] == pipeline_id:
            return JSONResponse(p)

    return JSONResponse({"detail": f"Воронка {pipeline_id} не найдена"}, status_code=404)


async def account_info(request: Request) -> Response:
    if err := _check_auth(request):
        return err
    return JSONResponse(ACCOUNT)


# --- App ---

app = Starlette(
    routes=[
        Route("/oauth2/access_token", oauth_token, methods=["POST"]),
        Route("/api/v4/account", account_info, methods=["GET"]),
        Route("/api/v4/leads/pipelines/{pipeline_id:int}", pipeline_get, methods=["GET"]),
        Route("/api/v4/leads/pipelines", pipelines_list, methods=["GET"]),
        Route("/api/v4/{entity_type}/{entity_id:int}", entity_get, methods=["GET"]),
        Route("/api/v4/{entity_type}/{entity_id:int}", entity_update, methods=["PATCH"]),
        Route("/api/v4/{entity_type}", entity_list, methods=["GET"]),
        Route("/api/v4/{entity_type}", entity_create, methods=["POST"]),
    ],
)

if __name__ == "__main__":
    import uvicorn

    print("🔧 Mock AmoCRM API v4 Server")
    print("   URL:   http://localhost:8080/api/v4/")
    print("   Token: test_access_value")
    print("   Entities: leads, contacts, companies, pipelines")
    uvicorn.run(app, host="0.0.0.0", port=8080)
