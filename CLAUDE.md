# Yzel (Узел) — Agent Protocol

## Context

Not-for-profit OSS MCP connector portfolio for CIS business tools (1C, Bitrix24, AmoCRM, Moysklad, Wildberries, Ozon KZ, Kaspi, Telegram, iiko, goszakup, WhatsApp-via-wacli, meetings platforms). MIT end-to-end. No paid tier, no closed cloud layer. Publish-and-help positioning. Revenue Gate `[—]`.

Reaffirmed 2026-04-20 (D53). Supersedes prior MIT-connectors + BSL-enterprise + AIYO-OS-commercial-layer framing (D2, D10, D13, D17 all effectively retired for Yzel's scope).

| Component | Stack | Constraints |
|-----------|-------|-------------|
| MCP Servers | Python 3.11+, mcp SDK, uv | Must run on Windows without WSL |
| Connectors | OData v3 (1C), REST (most), Playwright/scrape (goszakup if no token) | MIT license everywhere |
| Sidecars | WhatsApp via `wacli` subprocess per tenant | Reference: github.com/steipete/wacli |

## Session Protocol

1. **Start:** Read `NEXT.md` + `docs/_context/BRIEF.md`
2. **Check:** Read `TODO.md` for current phase tasks
3. **Deep dive:** Vault `Projects/yzel/_context.md` for strategic context
4. **End:** Update `NEXT.md` with continuity notes

## Where to Find Things

| Topic | Location |
|-------|----------|
| Architecture | `docs/ARCHITECTURE.md` |
| Planning | `MASTERPLAN.md`, `TODO.md`, `ROADMAP.md` |
| Session log | Vault: `Projects/yzel/sessions/` |
| Strategy + research | Vault: `Projects/yzel/` |
| 1C API reference | Vault: `Knowledge/AI & Tech - Integration - 1C Enterprise API and Cloud Architecture.md` |
| Auth patterns | Vault: `Knowledge/AI & Tech - Integration - Unified Auth for CIS Business Tools.md` |
| Competitive landscape | Vault: `Knowledge/Business - Market Research - CIS Business Tool MCP Ecosystem 2026.md` |

> Vault = `~/Documents/Developer/knowledge-os/`

## Rules

- **MIT everywhere.** Every file under `src/` is MIT. No BSL, no trade-secret carve-outs, no closed server engine. If a feature needs a closed component, it doesn't belong in Yzel.
- **Not-for-profit framing.** README, docs, CLI help, issue templates: good-faith OSS language. No pricing, no sales funnel, no lighthouse pitches. EN + RU.
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
7. **1C:Fresh OData endpoint format differs from on-prem:** `1cfresh.com/a/sbm/<id>/odata/` vs `<host>/<base>/odata/`. The connector must detect deployment type.

## Build & Run

```bash
# Install
uv sync

# Run individual connector
uv run python -m yzel.connectors.onec.server
uv run python -m yzel.connectors.bitrix24.server
uv run python -m yzel.connectors.wildberries.server
uv run python -m yzel.connectors.ozon.server

# Test
uv run pytest
uv run pytest tests/test_odata.py -k "test_schema_discovery"

# Build package
uv build
```
