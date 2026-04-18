---
title: "Yzel (Узел) — Brief"
type: project-context
project: yzel
created: 2026-04-11
updated: 2026-04-18
status: active
---

# Yzel (Узел) — Brief

## What

Yzel = MIT-licensed MCP connector portfolio (1C, Bitrix24, AmoCRM, Moysklad, Telegram, Email/IMAP) bridging CIS business tools to AI. Public OSS layer for developer pull + integrator credibility. AIYO OS (closed cloud SaaS) sits on top as the revenue surface — cross-system entity matcher, context graph, and audit engine run **server-only** (trade-secret moat, not license moat). Architecture per D17 (Option 1). Target buyer: RU-speaking mid-upper ops leaders at $5–50M businesses globally.

## Current Phase

Phase 1 (Apr 2026). Post-grill 2026-04-18: ICP locked = mid-upper RU-speaking ops (D14, reaffirmed). WhatsApp dropped from Phase 1 (D19). ICP C parked as fallback (D20). Atyrau/Zhenis lighthouse deprioritized (D21) — lighthouse path now unsourced. Next: grill warm-intro sourcing vs cold outbound, then rewrite MASTERPLAN.md.

## Active Work

- **Connectors:** 1C / Bitrix24 / AmoCRM / Moysklad complete + mock servers. Adding Telegram, Email/IMAP. WhatsApp dropped.
- **AIYO OS:** Landing page draft, pricing tiers ($49–$499/seat/mo), lighthouse pilot SOW template (anchor TBD).
- **GTM:** Lighthouse anchor sourcing — needs separate grill session (warm-intro mining vs cold outbound commit).

## Key Decisions

| # | Decision | Date |
|---|---|---|
| D1 | Component-first strategy (Stripe/Airbyte model) | 2026-04-11 |
| D2 | MIT connectors + BSL enterprise — **superseded by D14** | 2026-04-11 |
| D3 | Python MCP servers | 2026-04-11 |
| D4 | Credential proxy pattern | 2026-04-11 |
| D5 | Dynamic schema discovery for 1C | 2026-04-11 |
| D6 | CIS-origin geography, global via GitHub | 2026-04-11 |
| D7 | 1C integrators as distribution channel — **supplemented by D15** | 2026-04-11 |
| D8 | Monorepo structure | 2026-04-11 |
| D8a | WhatsApp: wacli free tier + BSP paid tier, sidecar subprocess per tenant | 2026-04-17 |
| D9 | Add Telegram + WhatsApp + Email/IMAP to connector portfolio | 2026-04-17 |
| D10 | JWT license-key enforcement — **superseded by D14** | 2026-04-11 |
| D11 | MCP+CLI now → web dashboard (AIYO OS) → cloud | 2026-04-11 |
| D12 | Cloud tier = piracy-proof via server-side cross-system queries | 2026-04-11 |
| D13 | License split = MIT (connectors) + trade-secret (server-only engine) + contract/services (packs). No BSL. | 2026-04-17 |
| D14 | Primary buyer = RU-speaking mid-upper businesses ($5–50M revenue) globally. KZ is evidence-factory, not market ceiling. **Reaffirmed 2026-04-18 after detour to ICP C.** | 2026-04-17 |
| D15 | GTM shape = Mid-Market SaaS. Atyrau lighthouse anchor **deprioritized 2026-04-18 (D21)** — lighthouse path now unsourced. | 2026-04-17 |
| D16 | Education RAG wedge parked as [S]; revisit month 12 or sooner if business SKU stalls | 2026-04-17 |
| D17 | Yzel/AIYO OS architecture = Option 1: Yzel OSS standalone (MIT) + AIYO OS closed SaaS on top, shared connector code + trade-secret engine | 2026-04-18 |
| D18 | ICP locked = B (mid-upper). Hold 90 days minimum, adjust on customer evidence not new framings. | 2026-04-18 |
| D19 | WhatsApp connector (wacli + BSP) dropped from Phase 1. ICP B uses Telegram for biz comms. Supersedes D8a. | 2026-04-18 |
| D20 | ICP C (1–10 person AI-native founders) parked as fallback. Activate IFF B fails by month 9 OR B saturates. Sequential not parallel. | 2026-04-18 |
| D21 | Atyrau/Zhenis lighthouse anchor deprioritized — Zhenis remains possible warm-intro option but no longer load-bearing. Lighthouse anchor for Phase 1 is **unsourced**. Needs separate grill on warm-intro vs cold outbound. | 2026-04-18 |
