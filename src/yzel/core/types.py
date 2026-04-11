"""Shared data models for Yzel connectors."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ServiceType(str, Enum):
    """Supported business tool services."""

    ONEC = "1c"
    BITRIX24 = "bitrix24"
    AMOCRM = "amocrm"
    MOYSKLAD = "moysklad"


class ConnectionStatus(str, Enum):
    """Connection health status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    AUTH_EXPIRED = "auth_expired"


class ServiceCredential(BaseModel):
    """Base credential model. Subclassed per service."""

    service: ServiceType
    name: str = Field(description="Human-readable connection name")


class OneCCredential(ServiceCredential):
    """1C Enterprise credentials — Basic Auth over OData."""

    service: ServiceType = ServiceType.ONEC
    host: str = Field(description="1C OData endpoint URL (e.g., https://server/base/odata/standard.odata)")
    username: str
    password: str
    is_fresh: bool = Field(default=False, description="True if 1C:Fresh cloud, false if on-prem")


class Bitrix24Credential(ServiceCredential):
    """Bitrix24 credentials — Webhook URL (no expiry)."""

    service: ServiceType = ServiceType.BITRIX24
    webhook_url: str = Field(description="Full webhook URL with secret")


class AmoCRMCredential(ServiceCredential):
    """AmoCRM/Kommo credentials — OAuth2 with refresh."""

    service: ServiceType = ServiceType.AMOCRM
    subdomain: str = Field(description="AmoCRM subdomain (e.g., mycompany)")
    access_token: str
    refresh_token: str
    expires_at: float = Field(description="Unix timestamp when access token expires")
    client_id: str
    client_secret: str
    redirect_uri: str


class MoyskladCredential(ServiceCredential):
    """Moysklad credentials — Static bearer token."""

    service: ServiceType = ServiceType.MOYSKLAD
    bearer_token: str


class EntityRecord(BaseModel):
    """Normalized entity from any service."""

    source: ServiceType
    entity_type: str = Field(description="Original entity type name (e.g., Справочник_Контрагенты)")
    entity_id: str
    data: dict[str, Any]
    raw: dict[str, Any] | None = Field(default=None, description="Original API response")


class SchemaField(BaseModel):
    """Single field in a discovered schema."""

    name: str
    field_type: str
    nullable: bool = True
    description: str | None = None


class SchemaEntity(BaseModel):
    """Discovered entity schema from a service."""

    service: ServiceType
    entity_name: str
    fields: list[SchemaField]
    is_collection: bool = True
