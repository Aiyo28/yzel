# Yzel (Узел) — Master Plan

> The bridge between Russian business tools and AI — unified MCP connectors for 1C, Bitrix24, AmoCRM, and Moysklad.

**Repo:** `yzel/`
**Vault:** `Projects/yzel/_context.md`
**Last Updated:** 2026-04-11
**Current Phase:** Phase 1 — Foundation
**Status:** Pre-Development

---

## The Problem

Russian SMBs run 3-4 disconnected business tools (1C for accounting, Bitrix24 for CRM, AmoCRM for sales, Moysklad for inventory). Each tool is a data silo. AI assistants (Claude, YandexGPT, GigaChat) can't access any of this data without custom integration work that costs 60K+ RUB per workstation.

6+ independent MCP servers exist for 1C alone, but:
- Each is standalone (no cross-system queries)
- No managed/enterprise-grade hosting
- No unified auth layer
- No dynamic schema discovery that handles custom 1C configurations
- No funded startup owns the space

The gap: **nobody has built the unified cross-system integration layer.**

## Problem→Solution Chain

- **Problem:** CIS business tools are data silos, AI can't access them without expensive custom integration
- → **Solution:** Open-source MCP connectors with unified auth + dynamic schema discovery
- → **New problem:** Individual connectors don't talk to each other — cross-system queries need an orchestration layer
- → **Solution:** Enterprise platform layer (BSL-licensed) that unifies queries across connectors

## Not This

- Not a replacement for 1C, Bitrix24, or any existing business tool — connectors only, never operational logic
- Not a data warehouse or ETL pipeline — real-time MCP queries, not batch sync
- Not a UI product (Phase 1) — developer infrastructure first, dashboard later
- Not for non-CIS markets — Russian business tool ecosystem only

## The Vision

A 1C integrator installs Yzel once for a client. Suddenly their client's AI assistant can answer: "Show me client Рога и Копыта's outstanding invoices from 1C, their open deals in AmoCRM, and their current inventory levels in Moysklad" — in one query, with one authentication.

## Who It's For

**Primary:** 1C integrator firms (7,000 franchisees across 750+ cities in RU/CIS). They resell AI integration to their clients. Yzel is the tool they deploy.

**Secondary:** Tech-savvy SMB owners who self-integrate (the Habr/Infostart audience, ~800K registered devs).

**Out of scope (Phase 1):** Enterprise (500+ employees), non-CIS markets, non-Russian-language tooling.

## How It Works

```
1. Integrator installs Yzel (pip install yzel)
2. Configures connections:
   - 1C: OData endpoint URL + service account credentials
   - Bitrix24: Webhook URL
   - AmoCRM: OAuth redirect flow
   - Moysklad: Bearer token
3. Yzel auto-discovers 1C schema (catalogs, registers, custom fields)
4. AI assistant connects via MCP protocol
5. Cross-system queries work: "Find all clients with overdue invoices AND open deals"
```

## Key Decisions

### [D] Component-first, product-later (Stripe/Airbyte model)
Build open-source MCP connectors. Enterprise product comes after install base exists. Invalidates if: market demands full product before infra, or infra alone generates zero adoption after 6 months.
Priority: critical. Date: 2026-04-11.

### [D] Monorepo with MIT-licensed connectors + BSL enterprise layer
Individual MCP servers are MIT (maximum adoption). The unified platform/enterprise features are BSL (protects against cloud resellers). Airbyte uses exactly this split (MIT connectors + ELv2 platform).
Invalidates if: MIT connectors get forked and unified by a competitor faster than we ship the platform.
Priority: critical. Date: 2026-04-11.

### [D] Python for MCP servers
1C developer community uses Python. Existing 1C MCP repos are Python. Target users are on Windows (Python runs everywhere). TypeScript dashboard deferred to Phase 2+.
Invalidates if: MCP ecosystem shifts heavily to TypeScript-only tooling.
Priority: settled. Date: 2026-04-11.

### [D] Credential proxy pattern for unified auth
User authenticates once to Yzel. Backend stores encrypted per-service tokens. 1C=Basic Auth, Bitrix24=Webhook, AmoCRM=OAuth2, Moysklad=Bearer. Airbyte's connection_id abstraction is the reference.
Invalidates if: a Russian SSO standard emerges that spans business tools (currently none exists).
Priority: critical. Date: 2026-04-11.

### [D] Dynamic schema discovery for 1C
Every 1C installation has different configurations. Yzel must auto-discover available catalogs, registers, and custom fields at connection time — not hardcode object names. ROCTUP's approach (runs inside 1C processing) is the reference.
Invalidates if: 1C standardizes configurations (extremely unlikely).
Priority: critical. Date: 2026-04-11.

### [D] CIS geography first, global via GitHub credibility
Cornered resource: Russian-speaking, KZ-based, understands 1C business logic. Western AI companies structurally cannot/will not enter RU market. Global play is OSS GitHub reputation trail.
Invalidates if: sanctions ease significantly AND Western AI companies target RU SMB market.
Priority: critical. Date: 2026-04-11.

### [D] Target 1C integrators, not end businesses
7,000 franchisees are the distribution channel. They have the client relationships and technical skills to deploy. End-business sales require support infrastructure we can't build solo.
Invalidates if: self-serve adoption outpaces integrator channel.
Priority: settled. Date: 2026-04-11.

## Business Model

### Free Tier (MIT — OSS)
- Individual MCP connectors (1C, Bitrix24, AmoCRM, Moysklad)
- Self-hosted deployment
- Community support (GitHub Issues, Telegram)
- Single-user, basic auth

### Enterprise Tier (BSL — Paid)
- Cross-system queries ("client X across all systems")
- SAML/SSO authentication
- Audit logs and compliance reporting
- Multi-tenancy / workspace isolation
- SLA + priority support
- Premium connectors (bank-client APIs, government reporting)

### Revenue Path
| Phase | Timeline | Revenue |
|---|---|---|
| OSS connectors | Apr–Aug 2026 | $0 — build install base + credibility |
| Enterprise self-managed | Sep 2026–Feb 2027 | First revenue — target integrators |
| Cloud hosted | 2027 | Scale revenue |
| Enterprise contracts | 2027+ | 1C integrator franchisees license for clients |
| Acquisition/partnership | 2027-2028 | Yandex B2B or 1C Group (post-IPO) |

### Pricing (tentative, validate in Phase 2)
- Enterprise self-managed: ~$50-100/month per workspace
- Enterprise contracts for integrators: custom, per-client licensing

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| MCP Servers | Python 3.11+ | 1C community overlap, existing repos are Python, cross-platform |
| MCP Protocol | mcp Python SDK | Official Anthropic SDK |
| 1C Integration | OData v3 REST + Basic Auth | Universal across all 1C installations (on-prem + Fresh) |
| Bitrix24 Integration | REST API + Webhooks | Official vendor support, no expiry |
| AmoCRM Integration | REST API + OAuth2 | Mandatory OAuth, 24h access / 3mo refresh |
| Moysklad Integration | JSON API 1.2 + Bearer | Static tokens, well-documented |
| Credential Storage | SQLite (dev) → PostgreSQL (prod) | Encrypted at rest, AES-256 |
| Schema Discovery | Runtime OData $metadata parsing | Handles custom 1C configurations dynamically |
| Testing | pytest + pytest-asyncio | Standard Python MCP testing |
| Package Manager | uv | Fast, modern Python package management |
| Dashboard (Phase 2+) | TypeScript / Next.js | Web-based enterprise management UI |

## Project Structure

```
yzel/
├── MASTERPLAN.md
├── TODO.md
├── ROADMAP.md
├── CLAUDE.md                    # Agent protocol (generated by init-aiyo)
├── NEXT.md                      # Session continuity
├── LICENSE                      # MIT (root)
├── LICENSE-ENTERPRISE           # BSL (enterprise/)
├── pyproject.toml
├── README.md
├─�� docs/
│   ├── _context/
│   │   └── BRIEF.md
│   └── ARCHITECTURE.md
├── src/
│   └── yzel/
│       ├── __init__.py
│       ├── core/                # Shared: credential vault, schema discovery, query engine
│       │   ├── __init__.py
│       │   ├── credentials.py  # Encrypted credential storage (Airbyte connection_id pattern)
│       │   ├── discovery.py    # Dynamic schema discovery
│       │   ├── query.py        # Cross-system query engine (enterprise)
│       │   └── types.py        # Shared data models
│       ├── connectors/         # Individual MCP servers (MIT)
│       │   ├── __init__.py
│       │   ├── oneс/           # 1C Enterprise connector
│       │   │   ├── __init__.py
│       │   │   ├── server.py   # MCP server entry point
│       │   │   ├── odata.py    # OData v3 client
│       │   │   └── schema.py   # 1C schema discovery
│       │   ├── bitrix24/       # Bitrix24 connector
│       │   │   ├── __init__.py
│       │   │   ├── server.py
│       │   │   └── api.py
│       │   ├── amocrm/         # AmoCRM/Kommo connector
│       │   │   ├── __init__.py
│       │   │   ├── server.py
│       │   │   ├── api.py
│       │   │   └── oauth.py    # Token refresh logic
│       │   └── moysklad/       # Moysklad connector
│       │       ├── __init__.py
│       │       ├── server.py
│       │       └── api.py
│       └── enterprise/         # Enterprise features (BSL)
│           ├── __init__.py
│           ├── sso.py
│           ├── audit.py
│           └── multi_tenant.py
└── tests/
    ├── conftest.py
    ├── test_odata.py
    ├── test_bitrix24.py
    ├── test_amocrm.py
    └── test_moysklad.py
```

## Phase 1 — Foundation (Apr–Jun 2026)

**Goal:** Ship working MCP connectors for all 4 tools. 1C deep, others functional.

**What It Delivers:** A developer or integrator can `pip install yzel`, configure their business tool credentials, and have an AI assistant query their business data.

### Core Features

**1C Connector (deep focus):**
- OData v3 client with JSON support
- Basic Auth credential management
- Dynamic schema discovery ($metadata parsing)
- Read operations: catalogs, documents, registers
- Write operations: create/update documents
- Both on-prem and 1C:Fresh support
- Error handling for common 1C quirks (encoding, Cyrillic field names)

**Bitrix24 Connector:**
- Webhook-based integration (no OAuth complexity)
- CRM entities: leads, contacts, deals, companies
- Tasks and activity feed
- Rate limiting (2 req/sec standard)

**AmoCRM Connector:**
- OAuth2 flow with automatic token refresh
- Leads, contacts, companies, pipelines
- Proactive refresh 5 min before expiry

**Moysklad Connector:**
- Bearer token auth
- Products, orders, counterparties, inventory
- Nested entity resolution

**Shared Infrastructure:**
- Credential vault (SQLite, AES-256 encrypted)
- MCP server base class with common patterns
- CLI for configuration (`yzel config add-1c`, `yzel config add-bitrix`, etc.)
- Basic logging and error reporting

### Out of Scope (Phase 1)
- Cross-system queries (Phase 2)
- Web dashboard (Phase 2)
- SSO/SAML (Phase 2)
- Audit logs (Phase 2)
- Multi-tenancy (Phase 2)
- Bank-client APIs (Phase 3)
- YandexGPT-specific optimizations (Phase 2)

### Success Criteria
- [ ] All 4 connectors pass integration tests against real services
- [ ] 1C connector handles 3+ different standard configurations (Бухгалтерия, УТ, ERP)
- [ ] Published on PyPI as `yzel`
- [ ] README with setup instructions in RU and EN
- [ ] At least 1 Habr article published
- [ ] 50+ GitHub stars within 30 days of launch

## Phase 2 — Enterprise Foundation (Jul–Sep 2026)

**Goal:** Ship self-managed enterprise tier. First paying customers.

**What It Delivers:** An integrator deploys Yzel for a client with SSO, audit logging, and cross-system queries — the features that justify a monthly fee.

### Core Features

**Cross-System Query Engine:**
- "Find client X across 1C + AmoCRM + Moysklad"
- Entity matching (client name normalization across systems)
- Unified response format

**Enterprise Auth:**
- SAML/SSO integration (Keycloak, Azure AD)
- Workspace isolation (multi-tenant)

**Audit & Compliance:**
- Query logging with user attribution
- Data access audit trail
- Export for compliance reporting

**Management Dashboard (TypeScript/Next.js):**
- Connection health monitoring
- Credential management UI
- Query history and analytics

### Success Criteria
- [ ] 3+ paying enterprise customers (integrators)
- [ ] Cross-system queries working for 1C+AmoCRM combination
- [ ] Dashboard deployed and functional
- [ ] $1K MRR

## Phase 3 — Scale (Oct 2026–Mar 2027)

**Goal:** Cloud hosted service. Enterprise contracts with 1C integrator franchisees.

**What It Delivers:** Zero-config managed Yzel — an integrator signs up, connects their client's tools, and it works without self-hosting.

### Core Features
- Cloud hosted managed service
- Premium connectors (bank-client APIs, 1C government reporting configs)
- Integrator reseller program
- API rate limiting and usage metering
- Billing integration (Stripe + Russian payment alternatives)

### Success Criteria
- [ ] 10+ enterprise customers
- [ ] Cloud service live and stable
- [ ] $10K MRR
- [ ] At least 1 formal integrator partnership

## Phase 4 — Platform (2027+)

**Goal:** Become the standard AI integration layer for CIS business tools.

- Custom connector SDK (community can build connectors)
- Marketplace for connectors
- Yandex Cloud / Sber partnership exploration
- 1C Group partnership (post-IPO)
- Expansion to other CIS tools (Planfix, Megaplan, ELMA)

## Future Vision

Yzel becomes to Russian business tools what Plaid is to US banking APIs — the default middleware that every AI application uses to access business data. The open-source connectors create the install base. The enterprise tier creates the revenue. The integrator network creates the distribution. The geopolitical moat protects from Western competition.

## Constraints

- **Solo developer** — no team. Architecture must be simple enough for one person to maintain all 4 connectors + core
- **No VC (Phase 1-2)** — revenue must come from product, not fundraising. Bootstrap mentality
- **Windows compatibility required** — target users are on Windows. All MCP servers must work on Windows without WSL
- **Russian language first** — all error messages, CLI output, and documentation must be bilingual (RU primary, EN secondary)
- **No 1C platform modifications** — Yzel connects via published APIs only. Never require changes to client's 1C configuration (the ROCTUP lesson: run alongside, not inside)
- **MIT individual connectors, BSL enterprise** — this split is non-negotiable. Changing MIT to restrictive license later would destroy trust

## Success Metrics

| Phase | Metric | Target |
|---|---|---|
| 1 | GitHub stars | 50+ (30 days) |
| 1 | PyPI installs | 500+ (60 days) |
| 1 | Habr article views | 5,000+ |
| 2 | Paying customers | 3+ |
| 2 | MRR | $1,000 |
| 3 | Paying customers | 10+ |
| 3 | MRR | $10,000 |
| 3 | Integrator partnerships | 1+ formal |

## Open Decisions

- [ ] Exact enterprise pricing (validate with integrator interviews in Phase 2)
- [ ] Russian payment processing (Юкасса? Robokassa? Direct bank transfer?)
- [ ] Legal entity (TOO in KZ or OOO in RU?) — needed for enterprise contracts
- [ ] YandexGPT integration specifics (their function calling format differs from MCP)
- [ ] Hosting provider for cloud service (Yandex Cloud? Selectel? Hetzner?)
- [ ] Whether to list on Infostart marketplace (reach vs platform dependency)

## Moat Assessment

| Moat | Strength | Evidence |
|---|---|---|
| Cornered Resource | Moderate-Strong | RU-speaking, KZ-based, 1C domain knowledge, willing to operate in RU market |
| Process Power | Moderate | Ontology system + context architecture from Knowledge OS vault work |
| Counter-Positioning | Strong | Geopolitical barrier — Western AI cos can't/won't serve RU. Yandex won't build OSS connectors (conflicts with cloud lock-in) |
| Switching Costs | Future-Moderate | Once businesses wire up, ripping out = reconfiguring everything |

Count: 3 Moderate+ = **Defensible.**

## Vault References

- `Knowledge/Business - Market Research - CIS Business Tool MCP Ecosystem 2026.md`
- `Knowledge/Business - Strategy - OSS Infrastructure to Revenue Playbook.md`
- `Knowledge/AI & Tech - Integration - 1C Enterprise API and Cloud Architecture.md`
- `Knowledge/AI & Tech - Integration - Unified Auth for CIS Business Tools.md`
- `Knowledge/Business - Brand Strategy - Selling Boring Digital Products.md`
- `Projects/ai-knowledge-os/Decisions/2026-04-11 Portfolio Grill - CIS Infrastructure Pivot.md`
