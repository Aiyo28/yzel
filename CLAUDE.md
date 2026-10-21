# Yzel (Узел) — Operator Letter

You are working on Yzel with me. Here is the headspace.

## What this is, in one breath

Yzel is the OSS MCP connector portfolio I'm building for the CIS business
stack — 1C, Bitrix24, AmoCRM, Moysklad, Wildberries, Ozon, Telegram, iiko,
and more coming (WhatsApp via wacli, goszakup, meetings platforms). Every
line MIT. No paid tier. No closed cloud. The point is to publish useful
code and help people who are stuck integrating these systems on Windows
boxes in Almaty and Almaty-adjacent offices that don't have WSL and don't
want it.

## Who I am here

I'm a solo founder running this as the reputation lane next to my revenue
projects. Yzel does not need to make money. It needs to be the thing people
find when they search "1C MCP" or "Bitrix24 MCP." Engagement that doesn't
ship code is noise. If you find yourself adding pricing pages, sales funnels,
or "Pro tier" hints — stop and ask me. That's not what this is.

## What you should believe about the domain

- **1C is not Salesforce.** Its OData is XML by default, Cyrillic by default,
  and the schema changes per client deployment. There is no canonical
  "Products" table — there's `Справочник_Номенклатура` and it's different
  in every install. Assume nothing. Discover everything via `$metadata`.
- **Russian is primary.** The user is reading the README in Russian. English
  is the courtesy translation. Error messages, CLI help, docs — Russian first.
- **Windows without WSL.** Half our target users can't run WSL. If your code
  needs Linux primitives, it doesn't work for them, which means it doesn't
  exist.

## How we work together

- When you don't know which connector this change belongs in, ask. Don't
  guess and refactor.
- When you want to add a closed dependency to make life easier — don't.
  Find the open alternative or skip the feature.
- When you read a 1C field name and want to "fix" the Cyrillic — leave it.
  That's not a typo, that's the schema.
- If a rule below feels wrong for the change you're making, push back. Tell
  me. Don't silently work around it.

## Glossary

- **Connector** — one MCP server, one upstream system. Lives in
  `src/yzel/connectors/<name>/`.
- **Sidecar** — external subprocess a connector launches (e.g. wacli for
  WhatsApp). Per-tenant, not per-connector.
- **Tenant** — one end-user's credentials + their 1C/Bitrix instance.
- **You** — the agent making the change.
- **I / me / we** — the human running Yzel.
- **Users** — third parties who install Yzel and connect their own systems.

---

# Critical Gotchas

These come from real incidents. Each one cost me hours the first time.

1. **1C OData URL segments are Cyrillic, URL-encoded.** `Catalog_Номенклатура`
   not `Catalog_Products`. Test with real Cyrillic paths, not mocks.
2. **1C Basic Auth has no session token.** Every request sends
   `base64(user:pass)`. Don't build token refresh logic for 1C — there's
   nothing to refresh.
3. **AmoCRM refresh tokens die silently after 3 months of inactivity.**
   Monitor refresh health, not access-token expiry.
4. **Bitrix24 rate limit is 2 req/sec, leaky bucket, no `Retry-After` header.**
   Rate-limit client-side. Don't trust the server to tell you.
5. **1C `$metadata` can be 10MB+.** Stream-parse, never load the full XML.
   Cache discovered schema with TTL.
6. **Moysklad: always `expand` nested entities.** Without it you get UUIDs
   instead of objects, and the user gets garbage.
7. **1C:Fresh ≠ on-prem URL format.** `1cfresh.com/a/<config>/<id>/odata/`
   vs `<host>/<base>/odata/`. Detect deployment type, don't assume.
8. **Every 1C request needs `?$format=json`.** Default is XML. Forget once
   and you're parsing XML by hand for an hour.
9. **MIT everywhere under `src/`.** If a feature needs a closed component,
   it doesn't belong in Yzel.
