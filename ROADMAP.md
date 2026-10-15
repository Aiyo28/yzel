# Roadmap

## Shipped

The eight v0.1 connectors (1C, Wildberries, Ozon, Bitrix24, AmoCRM, МойСклад, Telegram, iiko) are listed with their tools in [`llms.txt`](llms.txt) and the [README](README.md).

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

- **Kaspi Pay / Kaspi Business** — public merchant API is thin and scattered. Parked until a banking tier is scoped; likely bundled with Halyk Market / Jusan Market.

## Contributing

Highest-value contributions:
1. Real-configuration testing (1С:Бухгалтерия, УТ, ERP, Fresh).
2. New connectors — keep MIT, follow the existing `src/yzel/connectors/<name>/` pattern and add a `tests/mock_<name>_server.py`.
3. Translations of MCP tool descriptions / error messages.
4. Claude / ChatGPT use-case documentation.

Open an issue first for anything larger than a bug fix.
