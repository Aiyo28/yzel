"""Mock Wildberries Seller API server.

Emulates the five MVP hosts (common, content, marketplace, statistics, prices)
behind a single Starlette app. Route prefixes match production paths so the
client can point each host at the same base URL in tests.

Auth: `Authorization: test-wb-token` (no `Bearer ` prefix — matches WB).
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

VALID_TOKEN = "test-wb-token"  # noqa: S105 — mock


def _auth(request: Request) -> Response | None:
    if request.headers.get("authorization") != VALID_TOKEN:
        return JSONResponse(
            {"title": "unauthorized", "detail": "Неверный токен", "code": "401"},
            status_code=401,
        )
    return None


# --- Demo data ---

WAREHOUSES = [
    {"id": 507, "name": "Коледино", "address": "Московская обл., Подольск"},
    {"id": 686, "name": "Алматы FBS", "address": "г. Алматы, ул. Розыбакиева"},
]

NEW_ORDERS = {
    "orders": [
        {
            "id": 10001,
            "rid": "rid-1",
            "createdAt": "2026-04-20T07:15:00Z",
            "article": "BUM-A4-500",
            "convertedPrice": 45000,
            "warehouseId": 507,
            "offices": ["Подольск"],
            "skus": ["2000000000017"],
        },
        {
            "id": 10002,
            "rid": "rid-2",
            "createdAt": "2026-04-20T08:00:00Z",
            "article": "DT-L-001",
            "convertedPrice": 128500,
            "warehouseId": 686,
            "offices": ["Алматы"],
            "skus": ["2000000000024"],
        },
    ]
}

ORDERS_HISTORY = {
    "next": 0,
    "orders": [
        {
            "id": 9001,
            "rid": "rid-old-1",
            "createdAt": "2026-04-18T10:00:00Z",
            "article": "BUM-A4-500",
            "warehouseId": 507,
            "skus": ["2000000000017"],
            "isZeroOrder": False,
        }
    ],
}

STOCKS_BY_WAREHOUSE: dict[int, dict[str, int]] = {
    507: {"2000000000017": 120, "2000000000024": 45},
    686: {"2000000000017": 30},
}

SALES = [
    {
        "date": "2026-04-19T12:00:00",
        "lastChangeDate": "2026-04-19T12:05:00",
        "saleID": "S123",
        "supplierArticle": "BUM-A4-500",
        "totalPrice": 45000,
        "finishedPrice": 40500,
        "forPay": 38475,
    }
]

ORDER_STATS = [
    {
        "date": "2026-04-19T10:00:00",
        "lastChangeDate": "2026-04-19T10:05:00",
        "supplierArticle": "BUM-A4-500",
        "totalPrice": 45000,
        "warehouseName": "Коледино",
    }
]

CARDS = {
    "cards": [
        {"nmID": 111111, "vendorCode": "BUM-A4-500", "title": "Бумага А4 офисная"},
        {"nmID": 222222, "vendorCode": "DT-L-001", "title": "Дизельное топливо ДТ-Л"},
    ],
    "cursor": {"updatedAt": "2026-04-20T00:00:00Z", "nmID": 222222, "total": 2},
}

PRICES = {
    "data": {
        "listGoods": [
            {"nmID": 111111, "vendorCode": "BUM-A4-500", "prices": [{"price": 1200, "discount": 10}]},
            {"nmID": 222222, "vendorCode": "DT-L-001", "prices": [{"price": 85000, "discount": 5}]},
        ]
    }
}


# --- Handlers ---


async def seller_info(request: Request) -> Response:
    if err := _auth(request):
        return err
    return JSONResponse(
        {"name": "ИП Тестовый Продавец", "sid": "test-sid", "tradeMark": "TestMark"}
    )


async def warehouses(request: Request) -> Response:
    if err := _auth(request):
        return err
    return JSONResponse(WAREHOUSES)


async def new_orders(request: Request) -> Response:
    if err := _auth(request):
        return err
    return JSONResponse(NEW_ORDERS)


async def orders(request: Request) -> Response:
    if err := _auth(request):
        return err
    # Echo pagination params so tests can assert they were forwarded
    date_from = request.query_params.get("dateFrom")
    limit = int(request.query_params.get("limit", 1000))
    payload = dict(ORDERS_HISTORY)
    payload["dateFrom"] = date_from  # type: ignore[assignment]
    payload["limit"] = limit  # type: ignore[assignment]
    return JSONResponse(payload)


async def get_stocks(request: Request) -> Response:
    if err := _auth(request):
        return err
    warehouse_id = int(request.path_params["warehouse_id"])
    body = await request.json()
    skus = body.get("skus", [])
    available = STOCKS_BY_WAREHOUSE.get(warehouse_id, {})
    return JSONResponse(
        {"stocks": [{"sku": s, "amount": available.get(s, 0)} for s in skus]}
    )


async def put_stocks(request: Request) -> Response:
    if err := _auth(request):
        return err
    warehouse_id = int(request.path_params["warehouse_id"])
    body = await request.json()
    for stock in body.get("stocks", []):
        STOCKS_BY_WAREHOUSE.setdefault(warehouse_id, {})[stock["sku"]] = stock["amount"]
    return Response(status_code=204)


async def sales(request: Request) -> Response:
    if err := _auth(request):
        return err
    return JSONResponse(SALES)


async def order_stats(request: Request) -> Response:
    if err := _auth(request):
        return err
    return JSONResponse(ORDER_STATS)


async def cards_list(request: Request) -> Response:
    if err := _auth(request):
        return err
    return JSONResponse(CARDS)


async def prices_list(request: Request) -> Response:
    if err := _auth(request):
        return err
    return JSONResponse(PRICES)


# --- App ---

app = Starlette(
    routes=[
        Route("/api/v1/seller-info", seller_info, methods=["GET"]),
        Route("/api/v3/warehouses", warehouses, methods=["GET"]),
        Route("/api/v3/orders/new", new_orders, methods=["GET"]),
        Route("/api/v3/orders", orders, methods=["GET"]),
        Route("/api/v3/stocks/{warehouse_id:int}", get_stocks, methods=["POST"]),
        Route("/api/v3/stocks/{warehouse_id:int}", put_stocks, methods=["PUT"]),
        Route("/api/v1/supplier/sales", sales, methods=["GET"]),
        Route("/api/v1/supplier/orders", order_stats, methods=["GET"]),
        Route("/content/v2/get/cards/list", cards_list, methods=["POST"]),
        Route("/api/v2/list/goods/filter", prices_list, methods=["GET"]),
    ],
)


if __name__ == "__main__":
    import uvicorn

    print("🟣 Mock Wildberries Seller API — http://localhost:8079 — token: test-wb-token")
    uvicorn.run(app, host="0.0.0.0", port=8079)
