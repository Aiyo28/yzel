---
title: "Yzel (Узел) — Brief"
type: project-context
project: yzel
created: 2026-04-11
updated: 2026-04-11
status: active
---

# Yzel (Узел) — Brief

## What

Yzel is a unified MCP connector framework that bridges Russian business tools (1C Enterprise, Bitrix24, AmoCRM, Moysklad) to AI assistants. It normalizes data access across all four tools via the Model Context Protocol, with a credential proxy pattern for unified authentication. Open-source MIT connectors build the install base; BSL-licensed enterprise features (SSO, audit, cross-system queries) generate revenue. Target distribution: 1C integrator firms (7,000 franchisees across 750+ RU/CIS cities).

## Current Phase

Phase 1 — Foundation (Apr–Jun 2026). Ship working MCP connectors for all 4 tools, 1C deep-first. Publish to PyPI, write Habr article, target 50+ GitHub stars.

## Active Work

- Project scaffold complete (MASTERPLAN, TODO, ROADMAP)
- Next: Python project init, credential vault, 1C OData client

## Key Decisions

| # | Decision | Date |
|---|---|---|
| D1 | Component-first strategy (Stripe/Airbyte model) | 2026-04-11 |
| D2 | MIT connectors + BSL enterprise (Airbyte license split) | 2026-04-11 |
| D3 | Python MCP servers (1C community overlap) | 2026-04-11 |
| D4 | Credential proxy pattern (Airbyte connection_id) | 2026-04-11 |
| D5 | Dynamic schema discovery for 1C | 2026-04-11 |
| D6 | CIS geography first, global via GitHub | 2026-04-11 |
| D7 | Target 1C integrators as distribution channel | 2026-04-11 |
| D8 | Monorepo structure | 2026-04-11 |
