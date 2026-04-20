"""Mock 1C OData v3 server for testing.

Simulates a real 1C:Бухгалтерия OData endpoint with:
- $metadata endpoint (real XML structure)
- Catalog_Контрагенты (counterparties)
- Catalog_Номенклатура (products/services)
- Document_РеализацияТоваровУслуг (sales documents)
- Basic Auth
- $format=json, $top, $filter, $select support

Usage:
    python -m tests.mock_odata_server
    # Runs on http://localhost:8077/odata/standard.odata/
    # Auth: admin / test
"""

from __future__ import annotations

import json
import re
import secrets
import uuid
from base64 import b64decode
from datetime import datetime, timedelta

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

# --- Auth ---
VALID_USER = "admin"
VALID_PASS = "test"  # noqa: S105 — mock server only


def _check_auth(request: Request) -> bool:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Basic "):
        return False
    decoded = b64decode(auth[6:]).decode("utf-8")
    user, _, password = decoded.partition(":")
    return user == VALID_USER and password == VALID_PASS


def _auth_required(request: Request) -> Response | None:
    if not _check_auth(request):
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="1C:Enterprise"'},
        )
    return None


# --- Demo Data ---
КОНТРАГЕНТЫ = [
    {
        "Ref_Key": "b1c2d3e4-f5a6-7890-abcd-ef1234567890",
        "Description": "ООО Рога и Копыта",
        "ИНН": "7701234567",
        "КПП": "770101001",
        "DeletionMark": False,
        "IsFolder": False,
        "ЮридическоеФизическоеЛицо": "ЮридическоеЛицо",
        "Комментарий": "Основной поставщик канцтоваров",
    },
    {
        "Ref_Key": "a2b3c4d5-e6f7-8901-bcde-f12345678901",
        "Description": "ИП Иванов И.И.",
        "ИНН": "770987654321",
        "КПП": "",
        "DeletionMark": False,
        "IsFolder": False,
        "ЮридическоеФизическоеЛицо": "ФизическоеЛицо",
        "Комментарий": "Подрядчик по ремонту",
    },
    {
        "Ref_Key": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "Description": "АО Газпром Нефть",
        "ИНН": "5504025348",
        "КПП": "550401001",
        "DeletionMark": False,
        "IsFolder": False,
        "ЮридическоеФизическоеЛицо": "ЮридическоеЛицо",
        "Комментарий": "Поставщик ГСМ",
    },
    {
        "Ref_Key": "d4e5f6a7-b8c9-0123-defa-234567890123",
        "Description": "ТОО КазМунайГаз",
        "ИНН": "040240003505",
        "КПП": "",
        "DeletionMark": False,
        "IsFolder": False,
        "ЮридическоеФизическоеЛицо": "ЮридическоеЛицо",
        "Комментарий": "Партнёр в Казахстане",
    },
    {
        "Ref_Key": "e5f6a7b8-c9d0-1234-efab-345678901234",
        "Description": "Физлицо Петров П.П.",
        "ИНН": "771234567890",
        "КПП": "",
        "DeletionMark": True,
        "IsFolder": False,
        "ЮридическоеФизическоеЛицо": "ФизическоеЛицо",
        "Комментарий": "Удалён — дубль",
    },
]

НОМЕНКЛАТУРА = [
    {
        "Ref_Key": "f6a7b8c9-d0e1-2345-fabc-456789012345",
        "Description": "Бумага А4 офисная",
        "Code": "00001",
        "IsFolder": False,
        "ЕдиницаИзмерения_Key": "упак",
        "Артикул": "BUM-A4-500",
        "ВидНоменклатуры": "Товар",
    },
    {
        "Ref_Key": "a7b8c9d0-e1f2-3456-abcd-567890123456",
        "Description": "Консультационные услуги",
        "Code": "00002",
        "IsFolder": False,
        "ЕдиницаИзмерения_Key": "час",
        "Артикул": "",
        "ВидНоменклатуры": "Услуга",
    },
    {
        "Ref_Key": "b8c9d0e1-f2a3-4567-bcde-678901234567",
        "Description": "Дизельное топливо ДТ-Л",
        "Code": "00003",
        "IsFolder": False,
        "ЕдиницаИзмерения_Key": "л",
        "Артикул": "DT-L-001",
        "ВидНоменклатуры": "Товар",
    },
]

ДОКУМЕНТЫ = [
    {
        "Ref_Key": "c9d0e1f2-a3b4-5678-cdef-789012345678",
        "Number": "00000001",
        "Date": "2026-03-15T10:30:00",
        "Posted": True,
        "DeletionMark": False,
        "Контрагент_Key": "b1c2d3e4-f5a6-7890-abcd-ef1234567890",
        "Сумма": 45000.00,
        "Валюта": "RUB",
        "Комментарий": "Поставка канцтоваров за март",
    },
    {
        "Ref_Key": "d0e1f2a3-b4c5-6789-defa-890123456789",
        "Number": "00000002",
        "Date": "2026-04-01T14:00:00",
        "Posted": True,
        "DeletionMark": False,
        "Контрагент_Key": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "Сумма": 128500.50,
        "Валюта": "RUB",
        "Комментарий": "Закупка ГСМ на апрель",
    },
    {
        "Ref_Key": "e1f2a3b4-c5d6-7890-efab-901234567890",
        "Number": "00000003",
        "Date": "2026-04-10T09:15:00",
        "Posted": False,
        "DeletionMark": False,
        "Контрагент_Key": "a2b3c4d5-e6f7-8901-bcde-f12345678901",
        "Сумма": 75000.00,
        "Валюта": "RUB",
        "Комментарий": "Ремонт офиса — не проведён",
    },
]

# Entity registry
ENTITIES: dict[str, list[dict]] = {
    "Catalog_Контрагенты": КОНТРАГЕНТЫ,
    "Catalog_Номенклатура": НОМЕНКЛАТУРА,
    "Document_РеализацияТоваровУслуг": ДОКУМЕНТЫ,
}

# --- $metadata XML ---
METADATA_XML = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
  <edmx:DataServices m:DataServiceVersion="3.0" m:MaxDataServiceVersion="3.0"
    xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <Schema Namespace="StandardODATA" xmlns="http://schemas.microsoft.com/ado/2009/11/edm">
      <EntityType Name="Catalog_Контрагенты">
        <Key><PropertyRef Name="Ref_Key"/></Key>
        <Property Name="Ref_Key" Type="Edm.Guid" Nullable="false"/>
        <Property Name="Description" Type="Edm.String"/>
        <Property Name="ИНН" Type="Edm.String"/>
        <Property Name="КПП" Type="Edm.String"/>
        <Property Name="DeletionMark" Type="Edm.Boolean"/>
        <Property Name="IsFolder" Type="Edm.Boolean"/>
        <Property Name="ЮридическоеФизическоеЛицо" Type="Edm.String"/>
        <Property Name="Комментарий" Type="Edm.String"/>
      </EntityType>
      <EntityType Name="Catalog_Номенклатура">
        <Key><PropertyRef Name="Ref_Key"/></Key>
        <Property Name="Ref_Key" Type="Edm.Guid" Nullable="false"/>
        <Property Name="Description" Type="Edm.String"/>
        <Property Name="Code" Type="Edm.String"/>
        <Property Name="IsFolder" Type="Edm.Boolean"/>
        <Property Name="ЕдиницаИзмерения_Key" Type="Edm.String"/>
        <Property Name="Артикул" Type="Edm.String"/>
        <Property Name="ВидНоменклатуры" Type="Edm.String"/>
      </EntityType>
      <EntityType Name="Document_РеализацияТоваровУслуг">
        <Key><PropertyRef Name="Ref_Key"/></Key>
        <Property Name="Ref_Key" Type="Edm.Guid" Nullable="false"/>
        <Property Name="Number" Type="Edm.String"/>
        <Property Name="Date" Type="Edm.DateTime" Nullable="false"/>
        <Property Name="Posted" Type="Edm.Boolean"/>
        <Property Name="DeletionMark" Type="Edm.Boolean"/>
        <Property Name="Контрагент_Key" Type="Edm.Guid"/>
        <Property Name="Сумма" Type="Edm.Decimal"/>
        <Property Name="Валюта" Type="Edm.String"/>
        <Property Name="Комментарий" Type="Edm.String"/>
      </EntityType>
      <EntityContainer Name="EnterpriseV8" m:IsDefaultEntityContainer="true">
        <EntitySet Name="Catalog_Контрагенты" EntityType="StandardODATA.Catalog_Контрагенты"/>
        <EntitySet Name="Catalog_Номенклатура" EntityType="StandardODATA.Catalog_Номенклатура"/>
        <EntitySet Name="Document_РеализацияТоваровУслуг" EntityType="StandardODATA.Document_РеализацияТоваровУслуг"/>
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>"""


# --- Handlers ---

async def root(request: Request) -> Response:
    """OData service root — list available entity sets."""
    if err := _auth_required(request):
        return err

    fmt = request.query_params.get("$format", "json")
    if fmt != "json":
        return Response(METADATA_XML, media_type="application/xml")

    entity_sets = [{"name": name, "url": name} for name in ENTITIES]
    return JSONResponse({
        "odata.metadata": f"{request.url.scheme}://{request.url.netloc}/odata/standard.odata",
        "value": entity_sets,
    })


async def metadata(request: Request) -> Response:
    """$metadata endpoint — returns full schema XML."""
    if err := _auth_required(request):
        return err
    return Response(METADATA_XML, media_type="application/xml")


async def entity_list(request: Request) -> Response:
    """Query an entity set with OData params. Also handles single-entity (guid'...') requests."""
    if err := _auth_required(request):
        return err

    raw_entity = request.path_params["entity"]

    # Handle URL-encoded Cyrillic
    from urllib.parse import unquote
    raw_entity = unquote(raw_entity)

    # Check for single-entity request: Entity(guid'xxxxx')
    guid_match = re.match(r"^(.+)\(guid'([^']+)'\)$", raw_entity)
    if guid_match:
        entity_name = guid_match.group(1)
        key = guid_match.group(2)
        if entity_name not in ENTITIES:
            return JSONResponse(
                {"odata.error": {"code": "8", "message": {"lang": "ru", "value": f"Сущность '{entity_name}' не найдена"}}},
                status_code=404,
            )
        for item in ENTITIES[entity_name]:
            if item.get("Ref_Key") == key:
                return JSONResponse(item)
        return JSONResponse(
            {"odata.error": {"code": "404", "message": {"lang": "ru", "value": "Запись не найдена"}}},
            status_code=404,
        )

    entity_name = raw_entity

    if entity_name not in ENTITIES:
        return JSONResponse(
            {"odata.error": {"code": "8", "message": {"lang": "ru", "value": f"Сущность '{entity_name}' не найдена"}}},
            status_code=404,
        )

    data = list(ENTITIES[entity_name])

    # $filter (basic support) — applied before $top so $inlinecount reflects the filtered set
    filter_expr = request.query_params.get("$filter")
    if filter_expr:
        data = _apply_filter(data, filter_expr)

    # $inlinecount=allpages returns the pre-pagination total alongside the page
    inlinecount = request.query_params.get("$inlinecount") == "allpages"
    total = len(data)

    # $top (must be applied after the count is captured)
    top = request.query_params.get("$top")
    if top is not None:
        data = data[: int(top)]

    # $select (after filtering + pagination)
    select = request.query_params.get("$select")
    if select:
        fields = [f.strip() for f in select.split(",")]
        data = [{k: v for k, v in item.items() if k in fields} for item in data]

    payload: dict = {
        "odata.metadata": f"{request.url.scheme}://{request.url.netloc}/odata/standard.odata/$metadata##{entity_name}",
        "value": data,
    }
    if inlinecount:
        payload["odata.count"] = str(total)
    return JSONResponse(payload)


async def entity_single(request: Request) -> Response:
    """Get single entity by GUID key."""
    if err := _auth_required(request):
        return err

    entity_name = request.path_params["entity"]
    key = request.path_params["key"]

    from urllib.parse import unquote
    entity_name = unquote(entity_name)

    if entity_name not in ENTITIES:
        return JSONResponse(
            {"odata.error": {"code": "8", "message": {"lang": "ru", "value": f"Сущность '{entity_name}' не найдена"}}},
            status_code=404,
        )

    for item in ENTITIES[entity_name]:
        if item.get("Ref_Key") == key:
            return JSONResponse(item)

    return JSONResponse(
        {"odata.error": {"code": "404", "message": {"lang": "ru", "value": "Запись не найдена"}}},
        status_code=404,
    )


def _apply_filter(data: list[dict], expr: str) -> list[dict]:
    """Very basic OData $filter support."""
    # Support: Field eq 'value'
    match = re.match(r"(\w+)\s+eq\s+'([^']*)'", expr)
    if match:
        field, value = match.groups()
        return [d for d in data if str(d.get(field, "")) == value]

    # Support: Field eq true/false
    match = re.match(r"(\w+)\s+eq\s+(true|false)", expr)
    if match:
        field = match.group(1)
        value = match.group(2) == "true"
        return [d for d in data if d.get(field) == value]

    return data


# --- App ---

app = Starlette(
    routes=[
        Route("/odata/standard.odata/", root),
        Route("/odata/standard.odata/$metadata", metadata),
        Route("/odata/standard.odata/{entity:path}", entity_list),
    ],
)

if __name__ == "__main__":
    import uvicorn
    print("🔧 Mock 1C OData Server")
    print("   URL:  http://localhost:8077/odata/standard.odata/")
    print("   Auth: admin / test")
    print("   Entities: Catalog_Контрагенты, Catalog_Номенклатура, Document_РеализацияТоваровУслуг")
    uvicorn.run(app, host="0.0.0.0", port=8077)
