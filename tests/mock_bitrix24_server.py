"""Mock Bitrix24 REST API server for testing.

Simulates a Bitrix24 portal webhook endpoint with:
- CRM entities: leads, contacts, deals, companies
- Tasks
- Pagination (50 items per page, Bitrix24 default)
- Error responses for invalid methods/IDs

Usage:
    python -m tests.mock_bitrix24_server
    # Runs on http://localhost:8078/rest/1/test_webhook_secret/
"""

from __future__ import annotations

import json
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

# --- Demo Data ---

LEADS = [
    {
        "ID": "1",
        "TITLE": "Заявка с сайта — офисная мебель",
        "NAME": "Алексей",
        "LAST_NAME": "Смирнов",
        "STATUS_ID": "NEW",
        "OPPORTUNITY": "150000",
        "CURRENCY_ID": "RUB",
        "PHONE": [{"VALUE": "+7 (495) 123-45-67", "VALUE_TYPE": "WORK"}],
        "DATE_CREATE": "2026-04-01T10:30:00+03:00",
        "ASSIGNED_BY_ID": "1",
    },
    {
        "ID": "2",
        "TITLE": "Входящий звонок — IT-аутсорсинг",
        "NAME": "Мария",
        "LAST_NAME": "Козлова",
        "STATUS_ID": "IN_PROCESS",
        "OPPORTUNITY": "500000",
        "CURRENCY_ID": "RUB",
        "PHONE": [{"VALUE": "+7 (495) 987-65-43", "VALUE_TYPE": "WORK"}],
        "DATE_CREATE": "2026-04-05T14:00:00+03:00",
        "ASSIGNED_BY_ID": "1",
    },
    {
        "ID": "3",
        "TITLE": "Конференция — контакт с ТОО КазМунайГаз",
        "NAME": "Ержан",
        "LAST_NAME": "Нургалиев",
        "STATUS_ID": "PROCESSED",
        "OPPORTUNITY": "2000000",
        "CURRENCY_ID": "KZT",
        "PHONE": [{"VALUE": "+7 (727) 333-22-11", "VALUE_TYPE": "WORK"}],
        "DATE_CREATE": "2026-04-08T09:00:00+03:00",
        "ASSIGNED_BY_ID": "2",
    },
]

CONTACTS = [
    {
        "ID": "1",
        "NAME": "Алексей",
        "LAST_NAME": "Смирнов",
        "COMPANY_ID": "1",
        "POST": "Директор по закупкам",
        "PHONE": [{"VALUE": "+7 (495) 123-45-67", "VALUE_TYPE": "WORK"}],
        "EMAIL": [{"VALUE": "smirnov@rogakopyta.ru", "VALUE_TYPE": "WORK"}],
        "DATE_CREATE": "2026-03-15T12:00:00+03:00",
    },
    {
        "ID": "2",
        "NAME": "Мария",
        "LAST_NAME": "Козлова",
        "COMPANY_ID": "2",
        "POST": "CTO",
        "PHONE": [{"VALUE": "+7 (495) 987-65-43", "VALUE_TYPE": "WORK"}],
        "EMAIL": [{"VALUE": "kozlova@techserv.ru", "VALUE_TYPE": "WORK"}],
        "DATE_CREATE": "2026-03-20T10:00:00+03:00",
    },
]

DEALS = [
    {
        "ID": "1",
        "TITLE": "Поставка офисной мебели — Рога и Копыта",
        "STAGE_ID": "PREPARATION",
        "OPPORTUNITY": "150000",
        "CURRENCY_ID": "RUB",
        "CONTACT_ID": "1",
        "COMPANY_ID": "1",
        "DATE_CREATE": "2026-04-02T11:00:00+03:00",
        "CLOSEDATE": "2026-05-01T00:00:00+03:00",
        "ASSIGNED_BY_ID": "1",
    },
    {
        "ID": "2",
        "TITLE": "IT-аутсорсинг — годовой контракт",
        "STAGE_ID": "NEGOTIATION",
        "OPPORTUNITY": "500000",
        "CURRENCY_ID": "RUB",
        "CONTACT_ID": "2",
        "COMPANY_ID": "2",
        "DATE_CREATE": "2026-04-06T15:00:00+03:00",
        "CLOSEDATE": "2026-06-01T00:00:00+03:00",
        "ASSIGNED_BY_ID": "1",
    },
]

COMPANIES = [
    {
        "ID": "1",
        "TITLE": "ООО Рога и Копыта",
        "COMPANY_TYPE": "CUSTOMER",
        "INDUSTRY": "MANUFACTURING",
        "PHONE": [{"VALUE": "+7 (495) 100-00-01", "VALUE_TYPE": "WORK"}],
        "EMAIL": [{"VALUE": "info@rogakopyta.ru", "VALUE_TYPE": "WORK"}],
        "DATE_CREATE": "2026-03-10T09:00:00+03:00",
    },
    {
        "ID": "2",
        "TITLE": "ООО ТехСервис",
        "COMPANY_TYPE": "CUSTOMER",
        "INDUSTRY": "IT",
        "PHONE": [{"VALUE": "+7 (495) 200-00-02", "VALUE_TYPE": "WORK"}],
        "EMAIL": [{"VALUE": "info@techserv.ru", "VALUE_TYPE": "WORK"}],
        "DATE_CREATE": "2026-03-12T10:00:00+03:00",
    },
]

TASKS = [
    {
        "id": "1",
        "title": "Подготовить КП для Рога и Копыта",
        "description": "Коммерческое предложение на офисную мебель",
        "status": "3",  # In progress
        "priority": "1",  # High
        "responsibleId": "1",
        "createdDate": "2026-04-02T12:00:00+03:00",
        "deadline": "2026-04-15T18:00:00+03:00",
    },
    {
        "id": "2",
        "title": "Звонок Козловой — уточнить ТЗ",
        "description": "Уточнить требования по IT-аутсорсингу",
        "status": "2",  # New
        "priority": "0",  # Normal
        "responsibleId": "1",
        "createdDate": "2026-04-06T16:00:00+03:00",
        "deadline": "2026-04-12T12:00:00+03:00",
    },
]

# Entity registries
CRM_ENTITIES: dict[str, list[dict[str, Any]]] = {
    "lead": LEADS,
    "contact": CONTACTS,
    "deal": DEALS,
    "company": COMPANIES,
}

# Auto-increment counters for create operations
_next_ids: dict[str, int] = {
    "lead": 100,
    "contact": 100,
    "deal": 100,
    "company": 100,
    "task": 100,
}

# --- Method routing ---

CRM_METHODS: dict[str, tuple[str, str]] = {
    "crm.lead.list": ("lead", "list"),
    "crm.lead.get": ("lead", "get"),
    "crm.lead.add": ("lead", "add"),
    "crm.lead.update": ("lead", "update"),
    "crm.contact.list": ("contact", "list"),
    "crm.contact.get": ("contact", "get"),
    "crm.contact.add": ("contact", "add"),
    "crm.contact.update": ("contact", "update"),
    "crm.deal.list": ("deal", "list"),
    "crm.deal.get": ("deal", "get"),
    "crm.deal.add": ("deal", "add"),
    "crm.deal.update": ("deal", "update"),
    "crm.company.list": ("company", "list"),
    "crm.company.get": ("company", "get"),
    "crm.company.add": ("company", "add"),
    "crm.company.update": ("company", "update"),
}


def _handle_crm_list(entity_type: str, params: dict[str, Any]) -> dict[str, Any]:
    items = list(CRM_ENTITIES[entity_type])
    start = params.get("start", 0)

    # Apply filter (basic — exact match on top-level string fields)
    filter_params = params.get("filter", {})
    for key, value in filter_params.items():
        # Strip comparison prefixes like >, <, >=, etc.
        clean_key = key.lstrip("><=!")
        items = [i for i in items if str(i.get(clean_key, "")) == str(value)]

    total = len(items)
    page = items[start : start + 50]

    # Apply select
    select = params.get("select")
    if select:
        page = [{k: v for k, v in item.items() if k in select} for item in page]

    result: dict[str, Any] = {"result": page, "total": total}
    if start + 50 < total:
        result["next"] = start + 50
    return result


def _handle_crm_get(entity_type: str, params: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(params.get("ID", params.get("id", "")))
    for item in CRM_ENTITIES[entity_type]:
        if item["ID"] == entity_id:
            return {"result": item}
    return {"error": "NOT_FOUND", "error_description": f"{entity_type} {entity_id} не найден"}


def _handle_crm_add(entity_type: str, params: dict[str, Any]) -> dict[str, Any]:
    fields = params.get("fields", {})
    new_id = _next_ids[entity_type]
    _next_ids[entity_type] += 1
    fields["ID"] = str(new_id)
    CRM_ENTITIES[entity_type].append(fields)
    return {"result": new_id}


def _handle_crm_update(entity_type: str, params: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(params.get("ID", params.get("id", "")))
    fields = params.get("fields", {})
    for item in CRM_ENTITIES[entity_type]:
        if item["ID"] == entity_id:
            item.update(fields)
            return {"result": True}
    return {"error": "NOT_FOUND", "error_description": f"{entity_type} {entity_id} не найден"}


def _handle_tasks_list(params: dict[str, Any]) -> dict[str, Any]:
    items = list(TASKS)
    start = params.get("start", 0)
    total = len(items)
    page = items[start : start + 50]
    result: dict[str, Any] = {"result": {"tasks": page}, "total": total}
    if start + 50 < total:
        result["next"] = start + 50
    return result


def _handle_task_get(params: dict[str, Any]) -> dict[str, Any]:
    task_id = str(params.get("taskId", ""))
    for task in TASKS:
        if task["id"] == task_id:
            return {"result": {"task": task}}
    return {"error": "NOT_FOUND", "error_description": f"Задача {task_id} не найдена"}


def _handle_task_add(params: dict[str, Any]) -> dict[str, Any]:
    fields = params.get("fields", {})
    new_id = _next_ids["task"]
    _next_ids["task"] += 1
    fields["id"] = str(new_id)
    TASKS.append(fields)
    return {"result": {"task": {"id": str(new_id)}}}


def _handle_task_update(params: dict[str, Any]) -> dict[str, Any]:
    task_id = str(params.get("taskId", ""))
    fields = params.get("fields", {})
    for task in TASKS:
        if task["id"] == task_id:
            task.update(fields)
            return {"result": {"task": task}}
    return {"error": "NOT_FOUND", "error_description": f"Задача {task_id} не найдена"}


# --- Starlette Handler ---

async def rest_handler(request: Request) -> JSONResponse:
    """Handle all Bitrix24 REST API calls."""
    method_raw = request.path_params["method"]
    # Strip .json suffix
    method = method_raw.removesuffix(".json")

    # Parse body
    body = await request.body()
    params: dict[str, Any] = {}
    if body:
        params = json.loads(body)

    # CRM methods
    if method in CRM_METHODS:
        entity_type, action = CRM_METHODS[method]
        if action == "list":
            return JSONResponse(_handle_crm_list(entity_type, params))
        elif action == "get":
            return JSONResponse(_handle_crm_get(entity_type, params))
        elif action == "add":
            return JSONResponse(_handle_crm_add(entity_type, params))
        elif action == "update":
            return JSONResponse(_handle_crm_update(entity_type, params))

    # Task methods
    if method == "tasks.task.list":
        return JSONResponse(_handle_tasks_list(params))
    elif method == "tasks.task.get":
        return JSONResponse(_handle_task_get(params))
    elif method == "tasks.task.add":
        return JSONResponse(_handle_task_add(params))
    elif method == "tasks.task.update":
        return JSONResponse(_handle_task_update(params))

    # Real Bitrix24 returns 200 with error in body for unknown methods
    return JSONResponse(
        {"error": "ERROR_METHOD_NOT_FOUND", "error_description": f"Метод '{method}' не найден"},
    )


# --- App ---

app = Starlette(
    routes=[
        Route("/rest/1/test_webhook_secret/{method:path}", rest_handler, methods=["GET", "POST"]),
    ],
)

if __name__ == "__main__":
    import uvicorn

    print("🔧 Mock Bitrix24 REST API Server")
    print("   URL:  http://localhost:8078/rest/1/test_webhook_secret/")
    print("   Entities: leads, contacts, deals, companies, tasks")
    uvicorn.run(app, host="0.0.0.0", port=8078)
