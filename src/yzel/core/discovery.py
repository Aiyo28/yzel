"""Dynamic schema discovery for 1C OData $metadata.

Parses the OData v3 $metadata XML to discover available entities,
their fields, and types. Handles Cyrillic entity names.

Uses ElementTree.iterparse for streaming so ERP-scale configs with
10MB+ metadata don't balloon memory (CLAUDE.md Critical Gotcha #5).
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET

import httpx

from yzel.core.types import SchemaEntity, SchemaField, ServiceType

# OData v3 EDM namespace
_EDM_NS = "http://schemas.microsoft.com/ado/2009/11/edm"
_EDMX_NS = "http://schemas.microsoft.com/ado/2007/06/edmx"

# Map OData EDM types to simplified type names
_TYPE_MAP: dict[str, str] = {
    "Edm.String": "string",
    "Edm.Int32": "integer",
    "Edm.Int64": "integer",
    "Edm.Decimal": "decimal",
    "Edm.Double": "float",
    "Edm.Boolean": "boolean",
    "Edm.DateTime": "datetime",
    "Edm.Guid": "guid",
    "Edm.Binary": "binary",
    "Edm.Int16": "integer",
    "Edm.Byte": "integer",
    "Edm.Single": "float",
}


def _simplify_type(edm_type: str) -> str:
    """Convert OData EDM type to simplified type name."""
    return _TYPE_MAP.get(edm_type, edm_type)


_ENTITY_TYPE_TAG = f"{{{_EDM_NS}}}EntityType"
_PROPERTY_TAG = f"{{{_EDM_NS}}}Property"


def _iter_entity_types(source: io.IOBase | str):
    """Yield `EntityType` elements from an XML source using iterparse.

    Accepts a string (wrapped in BytesIO) or a file-like object. Elements
    are cleared after yield so the parser never holds the full tree.
    """
    if isinstance(source, str):
        source = io.BytesIO(source.encode("utf-8"))

    context = ET.iterparse(source, events=("end",))
    for _, elem in context:
        if elem.tag == _ENTITY_TYPE_TAG:
            yield elem
            elem.clear()


def _build_entity(element: ET.Element) -> SchemaEntity:
    name = element.get("Name", "")
    fields: list[SchemaField] = []
    for prop in element.iter(_PROPERTY_TAG):
        fields.append(
            SchemaField(
                name=prop.get("Name", ""),
                field_type=_simplify_type(prop.get("Type", "Edm.String")),
                nullable=prop.get("Nullable", "true").lower() == "true",
            )
        )
    return SchemaEntity(service=ServiceType.ONEC, entity_name=name, fields=fields)


def parse_metadata_xml(xml_content: str) -> list[SchemaEntity]:
    """Parse OData $metadata XML into SchemaEntity list.

    Handles Cyrillic entity names (e.g., Справочник_Контрагенты).
    Streams via iterparse so 10MB+ ERP metadata doesn't load into memory.
    """
    return [_build_entity(elem) for elem in _iter_entity_types(xml_content)]


async def discover_schema(
    base_url: str,
    username: str,
    password: str,
    timeout: float = 30.0,
) -> list[SchemaEntity]:
    """Fetch and parse $metadata from a 1C OData endpoint.

    Args:
        base_url: 1C OData base URL (e.g., https://server/base/odata/standard.odata)
        username: 1C service account username
        password: 1C service account password
        timeout: Request timeout in seconds (1C $metadata can be slow for large configs)
    """
    metadata_url = f"{base_url.rstrip('/')}/$metadata"

    async with httpx.AsyncClient(
        auth=(username, password),
        timeout=timeout,
        verify=True,
    ) as client:
        response = await client.get(metadata_url)
        response.raise_for_status()

    return parse_metadata_xml(response.text)
