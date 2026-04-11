"""Dynamic schema discovery for 1C OData $metadata.

Parses the OData v3 $metadata XML to discover available entities,
their fields, and types. Handles Cyrillic entity names.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

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


def parse_metadata_xml(xml_content: str) -> list[SchemaEntity]:
    """Parse OData $metadata XML into SchemaEntity list.

    Handles Cyrillic entity names (e.g., Справочник_Контрагенты).
    Streams parsing for large metadata documents.
    """
    root = ET.fromstring(xml_content)

    entities: list[SchemaEntity] = []

    # Find all EntityType definitions
    for schema in root.iter(f"{{{_EDMX_NS}}}DataServices"):
        for ns_schema in schema.iter(f"{{{_EDM_NS}}}Schema"):
            for entity_type in ns_schema.iter(f"{{{_EDM_NS}}}EntityType"):
                name = entity_type.get("Name", "")
                fields: list[SchemaField] = []

                for prop in entity_type.iter(f"{{{_EDM_NS}}}Property"):
                    prop_name = prop.get("Name", "")
                    prop_type = prop.get("Type", "Edm.String")
                    nullable = prop.get("Nullable", "true").lower() == "true"

                    fields.append(
                        SchemaField(
                            name=prop_name,
                            field_type=_simplify_type(prop_type),
                            nullable=nullable,
                        )
                    )

                entities.append(
                    SchemaEntity(
                        service=ServiceType.ONEC,
                        entity_name=name,
                        fields=fields,
                    )
                )

    return entities


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
