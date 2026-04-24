# Yzel (Узел) — Agent Protocol

## Context

Not-for-profit OSS MCP connector portfolio for CIS business tools (1C, Bitrix24, AmoCRM, Moysklad, Wildberries, Ozon, Telegram, iiko — plus WhatsApp-via-wacli, goszakup, meetings platforms on the roadmap). MIT end-to-end. No paid tier, no closed cloud layer. Publish-and-help positioning.

| Component | Stack | Constraints |
|-----------|-------|-------------|
| MCP Servers | Python 3.11+, mcp SDK, uv | Must run on Windows without WSL |
| Connectors | OData v3 (1C), REST (most), Playwright/scrape (goszakup if no token) | MIT license everywhere |
| Sidecars | WhatsApp via `wacli` subprocess per tenant | Reference: github.com/steipete/wacli |

## Session Protocol

1. **Start:** Read `ROADMAP.md` for shipped scope + active workstreams
2. **Architecture:** `docs/ARCHITECTURE.md`
3. **End:** Update `ROADMAP.md` if you change scope

## Where to Find Things

| Topic | Location |
|-------|----------|
| Architecture | `docs/ARCHITECTURE.md` |
| Public roadmap | `ROADMAP.md` |
| User-facing docs | `README.md` |
| Per-connector design notes | `docs/ARCHITECTURE.md` → "Per-connector design notes" section |

## Rules

- **MIT everywhere.** Every file under `src/` is MIT. No closed server engine. If a feature needs a closed component, it doesn't belong in Yzel.
- **Not-for-profit framing.** README, docs, CLI help, issue templates: good-faith OSS language. No pricing, no sales funnel. EN + RU.
- **Never require changes to client's 1C configuration.** Connect via published OData/HTTP APIs only. No BSL extensions, no config modifications.
- **Cyrillic field names stay Cyrillic.** 1C OData returns Cyrillic object names (`Справочник_Номенклатура`). Do not transliterate — preserve as-is in code and API responses.
- **Always request `?$format=json` for 1C.** OData defaults to XML. Every 1C request must include the format parameter.
- **RU-first docs.** README, CLI help, error messages: Russian primary, English secondary.
- **Dynamic schema, never hardcode.** 1C installations have different configs. Always discover available objects via `$metadata` at runtime.

## Critical Gotchas

1. **1C OData uses Cyrillic URL segments** — `Catalog_Номенклатура` not `Catalog_Products`. URL-encode Cyrillic in requests. Test with real Cyrillic paths, not mocks.
2. **1C Basic Auth has no token — it's per-request.** Every HTTP call sends base64(user:pass). There is no session token to cache or refresh. Don't build token refresh logic for 1C.
3. **AmoCRM refresh tokens expire after 3 months of inactivity.** If background refresh stops (server down, job killed), the token silently dies. Must monitor refresh health, not just access token expiry.
4. **Bitrix24 rate limit is 2 req/sec (leaky bucket).** Exceeding returns 429 with no retry-after header. Implement client-side rate limiting, don't rely on server response.
5. **1C `$metadata` can be enormous** (10MB+ for complex ERP configs). Parse streaming, never load full XML into memory. Cache discovered schema with TTL.
6. **Moysklad nested entities require explicit `expand` parameter.** Without it, you get UUIDs instead of objects. Always expand in list queries or users get useless IDs.
7. **1C:Fresh OData endpoint format differs from on-prem:** `1cfresh.com/a/<config>/<id>/odata/` vs `<host>/<base>/odata/`. The connector must detect deployment type.

## Build & Run

```bash
# Install
uv sync

# Run individual connector
uv run python -m yzel.connectors.onec.server
uv run python -m yzel.connectors.bitrix24.server
uv run python -m yzel.connectors.wildberries.server
uv run python -m yzel.connectors.ozon.server
uv run python -m yzel.connectors.telegram.server
uv run python -m yzel.connectors.iiko.server

# Test
uv run pytest
uv run pytest tests/test_onec.py -k "test_schema_discovery"

# Build package
uv build
```
