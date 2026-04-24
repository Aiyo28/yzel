# Roadmap

## v0.1 — Shipped

| Connector | Scope |
|---|---|
| 1C:Enterprise | OData v3, CRUD, count, dynamic schema discovery via `$metadata`, streaming parser, on-prem + 1C:Fresh auto-detection, Cyrillic entity names preserved |
| Wildberries Seller | 5-host client (content/marketplace/statistics/prices/common), per-host rate limits, 10 MCP tools |
| Ozon Seller | Dual-header auth (Client-Id + Api-Key), sandbox overridable, 11 MCP tools |
| Bitrix24 | Webhook client, 2 req/sec client-side limiter, unified error wrapping, RU error text in MCP |
| AmoCRM / Kommo | OAuth2 with 3-month refresh-inactivity guard (`days_until_refresh_expiry()`, `ensure_refresh_fresh()`) |
| МойСклад | Bearer token, 5 rps rate limiter, nested-entity expand awareness, unified 4xx parser |
| Telegram Bot | 12 MCP tools, `retry_after` handling, self-hosted Bot API support |
| iiko Cloud | `apiLogin` → 1h Bearer auto-refresh on 401, 9 MCP tools (organizations, terminal groups, nomenclature, deliveries, etc.) |

137 tests across all connectors.

## v0.2 — Next

- **WhatsApp** via [`wacli`](https://github.com/steipete/wacli) sidecar (subprocess per tenant, not library import).
- **goszakup.gov.kz** — KZ government procurement, read-only. Scrape + API token path TBD.
- **AmoCRM OAuth browser flow** — replace token-bundle CLI input with interactive authorization.

## v0.3 — Meetings tier (research first)

Rank and build 3-4 of:
- Zoom
- Google Meet
- Microsoft Teams
- Yandex Telemost
- VK Звонки
- Контур.Толк
- SberJazz

Selection criteria: KZ+RU adoption × public-API availability.

## Deferred

- **Kaspi Pay / Kaspi Business** — 77% of KZ e-commerce, but public merchant API is thin and scattered. Parked until a banking tier is scoped; likely bundled with Halyk Market / Jusan Market.

## Contributing

Highest-value contributions:
1. Real-configuration testing (1С:Бухгалтерия, УТ, ERP, Fresh).
2. New connectors — keep MIT, follow the existing `src/yzel/connectors/<name>/` pattern and add a `tests/mock_<name>_server.py`.
3. Translations of MCP tool descriptions / error messages.
4. Claude / ChatGPT use-case documentation.

Open an issue first for anything larger than a bug fix.
