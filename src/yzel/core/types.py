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
    WILDBERRIES = "wildberries"
    OZON = "ozon"
    TELEGRAM = "telegram"
    IIKO = "iiko"


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


class OzonCredential(ServiceCredential):
    """Ozon Seller API credentials — Client-Id + Api-Key dual header.

    Both headers are required on every request (Ozon returns 403 if either
    is missing or mismatched). Client-Id is the seller's numeric ID from the
    Ozon seller cabinet; api_key is the token issued alongside it.

    KZ-domiciled sellers obtain credentials via the seller.ozon.kz cabinet.
    The base_url defaults to the shared production host and can be pointed
    at Ozon's sandbox for integration testing.
    """

    service: ServiceType = ServiceType.OZON
    client_id: str = Field(description="Numeric seller ID from Ozon cabinet")
    api_key: str = Field(description="API key issued for this Client-Id")
    base_url: str = Field(
        default="https://api-seller.ozon.ru",
        description="API host override (use https://api-seller-sandbox.ozon.ru for sandbox)",
    )


class IikoCredential(ServiceCredential):
    """iiko Cloud API credentials — apiLogin (exchanged for a 1h Bearer token).

    The `apiLogin` is the long-lived secret issued in the iikoWeb back office
    (Настройки → API). Every access token minted from it expires in 1 hour;
    the client refreshes on demand, so only the apiLogin must be stored.

    base_url differs by region — Russia uses `api-ru.iiko.services`; other
    regions ship their own hostnames. Default points at RU since the MVP
    audience is CIS.
    """

    service: ServiceType = ServiceType.IIKO
    api_login: str = Field(description="apiLogin issued in iikoWeb back office")
    base_url: str = Field(
        default="https://api-ru.iiko.services",
        description="iiko Cloud API host (region-specific)",
    )


class TelegramCredential(ServiceCredential):
    """Telegram Bot API credentials — single bot token.

    Tokens are issued by @BotFather and carry the bot's identity; they live
    in the URL path (`https://api.telegram.org/bot<token>/<method>`) rather
    than a header, which means accidental logging of the URL leaks the token.
    """

    service: ServiceType = ServiceType.TELEGRAM
    bot_token: str = Field(description="Token from @BotFather (format: 123456:ABC-...)")
    base_url: str = Field(
        default="https://api.telegram.org",
        description="Override for self-hosted Telegram Bot API (local-mode deployments)",
    )


class WildberriesCredential(ServiceCredential):
    """Wildberries Seller API credentials — single JWT api_key from seller cabinet.

    Same token is reused across WB's split hosts (content-api, marketplace-api,
    statistics-api, prices-api, common-api). Token is scoped per category at
    creation time in the seller cabinet — the client never sees scopes, so a
    wrong-scope token surfaces as 401 on call rather than rejection on init.
    """

    service: ServiceType = ServiceType.WILDBERRIES
    api_key: str = Field(description="JWT token issued in WB seller cabinet (Настройки → Доступ к API)")
    is_sandbox: bool = Field(default=False, description="True if token targets WB sandbox hosts")


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
