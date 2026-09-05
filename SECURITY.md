# Security Policy

## Reporting a vulnerability

Email **hello@ayal.tech** with `[yzel security]` in the subject. Do not open a public issue for
a vulnerability. Expect a first response within 7 days.

Please include the connector, the yzel version (`yzel --version`), and a minimal reproduction.
If the report concerns a third-party service (1C, Bitrix24, Ozon, …), say whether you have
already notified that vendor.

## What yzel touches

Yzel holds credentials for business systems that contain real commercial and personal data.
Treat any credential-handling bug as high severity.

- **Credentials at rest.** AES-256-GCM encrypted in a local SQLite database at `~/.yzel/store.db`.
  The key comes from the `YZEL_KEY` environment variable, or is generated at `~/.yzel/vault.key`
  on first run. **Nothing is transmitted anywhere except to the configured service.**
- **No telemetry.** Yzel makes no network call other than to the service you configured.
- **`~/.yzel/vault.key` is a plaintext key file.** If an attacker has your home directory they
  have your credentials. Set `YZEL_KEY` from your own secret manager if that matters to you.
- **21 of the 68 MCP tools mutate remote state** (see `docs/LIVE-CHECKS.md`). An agent with a
  yzel connector attached can create, update and delete records in your production systems.
  Scope the API keys you give it accordingly — most services support read-only tokens, and
  Wildberries and Ozon both have sandbox modes.

## Supported versions

Only the latest released version receives fixes. Yzel is `0.x`; there is no LTS.
