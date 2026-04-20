# Next

## Identity (reaffirmed 2026-04-20 — D53)
Yzel = **not-for-profit OSS** MCP connector portfolio. No sale, no paid tier, no AIYO OS commercial layer. MIT across the board. Publish and help CIS businesses integrate tools easily. Revenue Gate `[—]`.

`CLAUDE.md` superseded 2026-04-20 (post-D53). Enterprise scaffold removed. Committed `8218dbc` + `a2f660c`.

## Tier 1 — Marketplaces (shipped)
- [x] 1C:Enterprise — CRUD + count + schema, OneCError, streaming `$metadata`, Fresh detection, 14 tests (commit `8218dbc`)
- [x] Wildberries Seller API — 5-host client, per-host rate limits, 10 MCP tools, 12 tests (commit `a2f660c`)
- [x] Ozon Seller API — dual-header auth, sandbox overridable, 11 MCP tools, 15 tests (commit `a2f660c`)

## Tier 2 — Already-scaffolded + adjacent (next)
- [ ] Finish Bitrix24 — scaffolded, audit + close gaps (rate-limit cases, pagination helpers, webhook refresh guard)
- [x] Finish AmoCRM — 3-month silent-death guard shipped: `refresh_token_updated_at` tracked, `days_since_refresh()` / `days_until_refresh_expiry()` / `ensure_refresh_fresh(min_remaining_days)` methods, 5 new tests 2026-04-20
- [ ] Finish Moysklad — scaffolded, audit + close gaps (expand handling, entity relationships)
- [x] Telegram Bot API — 12 MCP tools, TelegramError with retry_after, 13 tests 2026-04-20
- [x] iiko (F&B POS) — apiLogin→1h Bearer, auto-refresh on 401, 9 MCP tools (organizations, terminal_groups, nomenclature, stop_list, deliveries by phone, create_delivery, order/payment types, employees), 15 tests 2026-04-20
- [ ] Reintroduce WhatsApp via wacli sidecar — reference `github.com/steipete/wacli`
- [ ] goszakup.gov.kz (B2G niche) — read-only via GUI scrape or API token

## Tier 3 — Meetings (research first)
- [ ] Rank Zoom / Google Meet / Microsoft Teams / Yandex Telemost / VK Звонки / Контур.Толк / SberJazz by KZ+RU adoption + public-API availability, then build 3-4

## Banking — deferred
- [ ] Kaspi Pay / Kaspi Business — 77% KZ e-commerce share, but public merchant API is thin and scattered. Park until Banking tier work begins; bundle with Halyk Market / Jusan Market if those reach scope.

## Decide
- Moysklad: extend their official MCP server or build independent?
- wacli sidecar scope: minimal CLI wrapper vs full BSP abstraction

## Validate
- 100-req rate-limit probe on goszakup `/ru/search/announce` — CAPTCHA threshold?
- Playwright full-page render on zakup.sk.kz — Cloudflare or other bot detection?

## Skipped
- zakup.sk.kz / Samruk-Kazyna partner probe (D54)
- Atameken chamber direct-email data request (D55)
- Freedom Market (doesn't exist — prior research error)

## Blocked
- (none)

## Key vault reference
- `Knowledge/Business Strategy - Kazakhstan SMB Landscape - Atyrau Almaty Astana Legal Forms and OKED Distribution (2026-04-19).md` — extracted stat.gov.kz 2024 data, marketplace ecosystem, goszakup API feasibility, SPOT impact, VAT reform, Atameken signals.

Updated: 2026-04-20
