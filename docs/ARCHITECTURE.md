# Architecture

## Layout

```
src/yzel/
├── cli.py               # yzel CLI — config add-*, list, remove
├── core/
│   ├── types.py         # ServiceCredential + 8 subclasses + EntityRecord + SchemaEntity
│   ├── vault.py         # SQLite vault, AES-256 at rest, ~/.yzel/vault.db
│   └── discovery.py     # Dynamic schema discovery (1C $metadata streaming parser)
└── connectors/
    ├── onec/            # 1C Enterprise (OData v3 + JSON)
    ├── wildberries/     # Wildberries Seller API (5 hosts)
    ├── ozon/            # Ozon Seller API (Client-Id + Api-Key)
    ├── bitrix24/        # Bitrix24 (webhook)
    ├── amocrm/          # AmoCRM/Kommo (OAuth2 + 3mo refresh guard)
    ├── moysklad/        # Moysklad (Bearer + RateLimiter)
    ├── telegram/        # Telegram Bot API
    └── iiko/            # iiko Cloud (apiLogin → 1h Bearer)

tests/
├── conftest.py
├── mock_<service>_server.py   # httpx mock per service
└── test_<service>.py          # unit tests against mocks
```

Every connector is an independent package with:
- `server.py` — MCP server entry point (`python -m yzel.connectors.<name>.server`)
- `<api>.py` — HTTP client, typed errors, rate limiting where relevant
- Service-specific extras (OData client for 1C, OAuth helpers for AmoCRM, etc.)

## Credential flow

```
CLI (yzel config add-1c)
  → OneCCredential(host, username, password, is_fresh)
  → CredentialVault.store(connection_id, cred)
  → SQLite (~/.yzel/vault.db) with AES-256-GCM encrypted blob

MCP Server startup
  → CredentialVault.list_connections()
  → picks first connection of the matching service type
  → instantiates HTTP client
  → for 1C: also calls discover_schema() to populate available entities
```

First connection of each service type is selected automatically. Multi-tenant / connection-switching is out of scope for v0.1.

## Per-connector design notes

### 1C (`onec/`)
- OData v3 with mandatory `?$format=json` (default XML otherwise).
- `$metadata` parsed as streaming XML (handles 10MB+ ERP configs).
- Cyrillic URL segments preserved (`Catalog_Номенклатура`, not transliterated).
- On-prem vs 1C:Fresh detected from URL shape.
- No token/session — Basic Auth on every request (there is no refresh flow in 1C).

### Wildberries (`wildberries/`)
- Single JWT reused across 5 hosts: `content-api`, `marketplace-api`, `statistics-api`, `prices-api`, `common-api`.
- Per-host rate limiters (WB enforces different limits per host).
- Token scope is fixed at creation in seller cabinet — wrong-scope tokens surface as 401 per-call.

### Ozon (`ozon/`)
- Dual-header auth: `Client-Id` + `Api-Key`. Missing either = 403.
- `base_url` is overridable for sandbox (`api-seller-sandbox.ozon.ru`).
- KZ sellers use `seller.ozon.kz` cabinet; API host is shared.

### Bitrix24 (`bitrix24/`)
- Webhook URL contains the secret inline — treat as credential.
- Rate limit: 2 req/sec leaky bucket; client-side limiter (no retry-after in 429 response).
- Unified error wrapping: 4xx/5xx → `Bitrix24Error` with `status_code`, MCP server converts to RU text.

### AmoCRM (`amocrm/`)
- OAuth2 with 24h access + 3mo refresh **inactivity** window.
- `refresh_token_updated_at` tracked — if no refresh call made in ~3 months, refresh token silently dies.
- `days_since_refresh()`, `days_until_refresh_expiry()`, `ensure_refresh_fresh(min_remaining_days)` expose staleness.
- v0.1 takes tokens via CLI; built-in OAuth browser-flow planned for v0.2.

### Moysklad (`moysklad/`)
- Static Bearer token.
- RateLimiter at 5 req/sec (configurable).
- Nested entities return UUIDs by default — always pass `expand` in list queries to hydrate.
- Error parser handles 4xx without `errors[]` array (unlike typical REST conventions).

### Telegram (`telegram/`)
- Bot token lives in URL path (`/bot<token>/method`) — URL logging leaks token; client masks in logs.
- `retry_after` extracted from 429 responses and respected.
- `base_url` overridable for self-hosted Telegram Bot API.

### iiko (`iiko/`)
- Two-step auth: `apiLogin` (long-lived) → 1h Bearer token.
- Auto-refresh on 401 from any endpoint.
- Region-specific `base_url` (RU default: `api-ru.iiko.services`).

## Testing

- 137 unit tests, all against in-process httpx mocks (`tests/mock_<service>_server.py`).
- Each mock mirrors the real API's auth, error shapes, and quirks (e.g., Bitrix24 2 rps, Ozon dual-header, AmoCRM refresh semantics).
- Mocks are evaluator-useful for regression but do not substitute for live smoke tests against real accounts.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Runtime | Python 3.11+ | CIS dev community overlap, existing 1C MCP repos are Python, cross-platform (runs on Windows without WSL) |
| MCP SDK | `mcp` (official) | Anthropic reference SDK |
| HTTP | `httpx` | async, transports support makes mocking clean |
| Validation | `pydantic` v2 | credential type safety, no manual dict-wrangling |
| Encryption | `cryptography` (AES-256-GCM) | credential vault at rest |
| CLI | `click` | prompt/hide-input ergonomics |
| Packaging | `uv` + PEP 621 | fast, reproducible |
| Tests | `pytest` + `pytest-asyncio` | standard |

## What Yzel is not

- Not an ETL pipeline or data warehouse — real-time MCP queries only.
- Not a replacement for any CIS business tool — connectors only, no operational logic.
- Not a hosted service — self-host on your own machine.
- Not a commercial product — MIT, no paid tier, no enterprise layer, no SaaS on top.
- Not a modification to your 1C — connects via published OData/HTTP APIs only.
