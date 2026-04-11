"""Tests for 1C OData schema discovery."""

from __future__ import annotations

from yzel.core.discovery import parse_metadata_xml
from yzel.core.types import ServiceType

SAMPLE_METADATA = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
  <edmx:DataServices m:DataServiceVersion="3.0" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <Schema Namespace="StandardODATA" xmlns="http://schemas.microsoft.com/ado/2009/11/edm">
      <EntityType Name="Catalog_Контрагенты">
        <Property Name="Ref_Key" Type="Edm.Guid" Nullable="false"/>
        <Property Name="Description" Type="Edm.String"/>
        <Property Name="ИНН" Type="Edm.String"/>
        <Property Name="КПП" Type="Edm.String"/>
        <Property Name="DeletionMark" Type="Edm.Boolean"/>
      </EntityType>
      <EntityType Name="Document_РеализацияТоваровУслуг">
        <Property Name="Ref_Key" Type="Edm.Guid" Nullable="false"/>
        <Property Name="Number" Type="Edm.String"/>
        <Property Name="Date" Type="Edm.DateTime"/>
        <Property Name="Сумма" Type="Edm.Decimal"/>
        <Property Name="Posted" Type="Edm.Boolean"/>
      </EntityType>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>"""


def test_parse_metadata_finds_entities() -> None:
    """Parse $metadata XML and find entity types."""
    entities = parse_metadata_xml(SAMPLE_METADATA)
    assert len(entities) == 2

    names = [e.entity_name for e in entities]
    assert "Catalog_Контрагенты" in names
    assert "Document_РеализацияТоваровУслуг" in names


def test_parse_metadata_fields() -> None:
    """Parse fields with correct types."""
    entities = parse_metadata_xml(SAMPLE_METADATA)
    catalog = next(e for e in entities if e.entity_name == "Catalog_Контрагенты")

    assert len(catalog.fields) == 5
    ref_key = next(f for f in catalog.fields if f.name == "Ref_Key")
    assert ref_key.field_type == "guid"
    assert ref_key.nullable is False

    inn = next(f for f in catalog.fields if f.name == "ИНН")
    assert inn.field_type == "string"
    assert inn.nullable is True


def test_parse_metadata_decimal_type() -> None:
    """Decimal fields map correctly."""
    entities = parse_metadata_xml(SAMPLE_METADATA)
    doc = next(e for e in entities if e.entity_name == "Document_РеализацияТоваровУслуг")

    summa = next(f for f in doc.fields if f.name == "Сумма")
    assert summa.field_type == "decimal"


def test_parse_metadata_service_type() -> None:
    """All entities have ServiceType.ONEC."""
    entities = parse_metadata_xml(SAMPLE_METADATA)
    for entity in entities:
        assert entity.service == ServiceType.ONEC


def test_parse_empty_metadata() -> None:
    """Empty $metadata returns empty list."""
    xml = """<?xml version="1.0"?>
    <edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
      <edmx:DataServices xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
        <Schema Namespace="StandardODATA" xmlns="http://schemas.microsoft.com/ado/2009/11/edm">
        </Schema>
      </edmx:DataServices>
    </edmx:Edmx>"""
    entities = parse_metadata_xml(xml)
    assert entities == []
