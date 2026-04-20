"""Mock Ozon Seller API server.

Validates dual-header auth (Client-Id + Api-Key). All endpoints are POST
with JSON body, matching production Ozon. Data is mutable across requests
so stock/price updates survive a round-trip within one test.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

VALID_CLIENT_ID = "123456"
VALID_API_KEY = "test-ozon-key"  # noqa: S105 — mock


def _auth(request: Request) -> Response | None:
    if (
        request.headers.get("client-id") != VALID_CLIENT_ID
        or request.headers.get("api-key") != VALID_API_KEY
    ):
        return JSONResponse(
            {"code": 7, "message": "Client-Id или Api-Key неверны", "details": []},
            status_code=403,
        )
    return None


# --- Mutable demo state ---

WAREHOUSES = [
    {"warehouse_id": 1001, "name": "Хоргос FBS", "is_rfbs": False},
    {"warehouse_id": 1002, "name": "Алматы FBS", "is_rfbs": False},
]

PRODUCTS = [
    {"product_id": 501, "offer_id": "BUM-A4-500", "sku": 9000001, "name": "Бумага А4"},
    {"product_id": 502, "offer_id": "DT-L-001", "sku": 9000002, "name": "ДТ-Л"},
]

STOCKS: dict[str, int] = {"BUM-A4-500": 120, "DT-L-001": 45}
PRICES: dict[str, str] = {"BUM-A4-500": "1200", "DT-L-001": "85000"}

UNFULFILLED = [
    {"posting_number": "1234-5678-0001", "status": "awaiting_packaging", "order_id": 77001},
    {"posting_number": "1234-5678-0002", "status": "awaiting_deliver", "order_id": 77002},
]

POSTINGS = [
    {"posting_number": "1234-5678-0001", "status": "awaiting_packaging", "order_id": 77001},
    {"posting_number": "1234-5678-0009", "status": "delivered", "order_id": 77009},
]

TRANSACTIONS = [
    {"operation_id": 1, "operation_type": "OperationMarketplaceServiceItemDeliv", "amount": -150},
    {"operation_id": 2, "operation_type": "ClientReturnAgentOperation", "amount": 3500},
]


# --- Handlers ---


async def warehouses(request: Request) -> Response:
    if err := _auth(request):
        return err
    return JSONResponse({"result": WAREHOUSES})


async def product_list(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    limit = body.get("limit", 100)
    items = [{"product_id": p["product_id"], "offer_id": p["offer_id"]} for p in PRODUCTS]
    return JSONResponse(
        {"result": {"items": items[:limit], "total": len(PRODUCTS), "last_id": ""}}
    )


async def product_info(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    offer_ids = set(body.get("offer_id") or [])
    items = [p for p in PRODUCTS if p["offer_id"] in offer_ids] if offer_ids else PRODUCTS
    return JSONResponse({"result": {"items": items}})


async def stock_info(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    skus = set(body.get("sku") or [])
    items = [
        {
            "sku": p["sku"],
            "offer_id": p["offer_id"],
            "stocks": [{"present": STOCKS.get(p["offer_id"], 0), "type": "fbs"}],
        }
        for p in PRODUCTS
        if not skus or p["sku"] in skus
    ]
    return JSONResponse({"items": items})


async def stock_update(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    results = []
    for entry in body.get("stocks", []):
        STOCKS[entry["offer_id"]] = entry["stock"]
        results.append({"offer_id": entry["offer_id"], "updated": True, "errors": []})
    return JSONResponse({"result": results})


async def price_update(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    results = []
    for entry in body.get("prices", []):
        PRICES[entry["offer_id"]] = entry["price"]
        results.append({"offer_id": entry["offer_id"], "updated": True, "errors": []})
    return JSONResponse({"result": results})


async def unfulfilled(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    limit = body.get("limit", 100)
    return JSONResponse({"result": {"postings": UNFULFILLED[:limit], "count": len(UNFULFILLED)}})


async def postings_list(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    fltr = body.get("filter", {})
    since = fltr.get("since")
    to = fltr.get("to")
    return JSONResponse(
        {"result": {"postings": POSTINGS, "has_next": False, "since": since, "to": to}}
    )


async def posting_get(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    number = body.get("posting_number")
    for p in POSTINGS + UNFULFILLED:
        if p["posting_number"] == number:
            return JSONResponse({"result": p})
    return JSONResponse(
        {"code": 5, "message": "Отправление не найдено", "details": []},
        status_code=404,
    )


async def analytics_data(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    return JSONResponse(
        {
            "result": {
                "data": [
                    {
                        "dimensions": [{"id": "9000001", "name": "Бумага А4"}],
                        "metrics": [100.0, 5.0],
                    }
                ],
                "totals": [100.0, 5.0],
                "date_from": body.get("date_from"),
                "date_to": body.get("date_to"),
            }
        }
    )


async def transaction_list(request: Request) -> Response:
    if err := _auth(request):
        return err
    body = await request.json()
    page = body.get("page", 1)
    return JSONResponse(
        {
            "result": {
                "operations": TRANSACTIONS,
                "page_count": 1,
                "row_count": len(TRANSACTIONS),
                "page": page,
            }
        }
    )


# --- App ---

app = Starlette(
    routes=[
        Route("/v1/warehouse/list", warehouses, methods=["POST"]),
        Route("/v3/product/list", product_list, methods=["POST"]),
        Route("/v2/product/info/list", product_info, methods=["POST"]),
        Route("/v4/product/info/stocks", stock_info, methods=["POST"]),
        Route("/v2/products/stocks", stock_update, methods=["POST"]),
        Route("/v1/product/import/prices", price_update, methods=["POST"]),
        Route("/v3/posting/fbs/unfulfilled/list", unfulfilled, methods=["POST"]),
        Route("/v3/posting/fbs/list", postings_list, methods=["POST"]),
        Route("/v3/posting/fbs/get", posting_get, methods=["POST"]),
        Route("/v1/analytics/data", analytics_data, methods=["POST"]),
        Route("/v3/finance/transaction/list", transaction_list, methods=["POST"]),
    ],
)


if __name__ == "__main__":
    import uvicorn

    print("🔵 Mock Ozon Seller API — http://localhost:8080 — Client-Id: 123456 / Api-Key: test-ozon-key")
    uvicorn.run(app, host="0.0.0.0", port=8080)
