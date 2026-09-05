# Live checks — the repeatable protocol

Companion to `docs/TESTING.md`. That document explains why the 138 unit tests cannot catch API
drift; this one is the thing you actually re-run.

**Cadence: before every release, and quarterly regardless.** Vendors change seller APIs without
notice; the whole point is to find out before a user does.

Every run appends a row to the log at the bottom. A run with no log row did not happen.

---

## Safety rules — read these before the first check

1. **Read-only probes first, always.** 47 of the 68 tools are read-only. A connector that fails
   its read probes is not ready to be write-tested.
2. **Never run a mutating tool against a production tenant.** The 21 mutating tools are listed
   per connector below. `ozon_update_prices` against a live seller account changes real prices;
   `wb_update_stocks` changes real stock; `tg_set_webhook` silently breaks whatever integration
   that bot already had.
3. **Sandbox where it exists.** Ozon and Wildberries both take `--sandbox`:
   `yzel config add-ozon --sandbox` / `yzel config add-wildberries --sandbox`. Use it.
4. **Where no sandbox exists, use a disposable tenant** — a trial CRM, a demo infobase, a
   throwaway bot. Not the company's real one, not a client's.
5. Credentials live encrypted in `~/.yzel/store.db`, key from `YZEL_KEY` or `~/.yzel/vault.key`.
   Use a separate `YZEL_KEY` for check runs so a test vault never mixes with a working one.

---

## Per-connector checks

Each block: configure → run read probes in order → record. Pass = well-formed result **or** a
documented error. Fail = unhandled exception, empty-where-data-exists, or a response shape the
matching `tests/mock_*_server.py` does not model.

**Any shape divergence updates the mock as well as the client.** A live fix that leaves the mock
stale re-opens the same gap next quarter.

### 1C — `yzel config add-1c` (or `--fresh`)

The headline connector, and the least verified. Transport and `$metadata` parsing were confirmed
against a live 1C:Fresh endpoint once; the data plane never was.

- [ ] `onec_schema` — returns entities, not an empty set. Empty → `EmptySchemaError`, see
      `docs/TROUBLESHOOTING-1C.md`; the infobase has no OData-published objects and the check
      cannot proceed.
- [ ] `onec_list_entities` — Cyrillic entity names survive round-trip intact.
- [ ] `onec_count` on one catalogue — a plausible non-zero integer.
- [ ] `onec_query` on the same catalogue — rows come back, fields match `onec_schema`.
- [ ] `onec_get` on one id from that result.
- Mutating (`onec_create`, `onec_update`, `onec_delete`): **disposable infobase only.**

> This is the check `NEXT.md` has carried unrun since 2026-04-24 as the Бухгалтерия-template
> smoke test. It is the evidence for the README's central claim. Until it passes on a real
> infobase, the claim rests on transport alone.

### Ozon — `yzel config add-ozon --sandbox`

- [ ] `ozon_list_warehouses` · `ozon_list_products` · `ozon_product_info`
- [ ] `ozon_list_postings` · `ozon_unfulfilled` · `ozon_get_posting`
- [ ] `ozon_get_stocks` · `ozon_analytics` · `ozon_transactions`
- Mutating (`ozon_update_prices`, `ozon_update_stocks`): **sandbox only.**

### Wildberries — `yzel config add-wildberries --sandbox`

- [ ] `wb_seller_info` · `wb_list_cards` · `wb_list_warehouses`
- [ ] `wb_get_orders` · `wb_new_orders` · `wb_order_stats` · `wb_sales`
- [ ] `wb_get_prices` · `wb_get_stocks`
- Mutating (`wb_update_stocks`): **sandbox only.**

### Telegram — `yzel config add-telegram` (throwaway bot)

- [ ] `tg_get_me` · `tg_get_chat` · `tg_get_webhook_info` · `tg_get_updates`
- Mutating (8 tools — `tg_send_*`, `tg_edit_message`, `tg_delete_message`, `tg_set_webhook`,
  `tg_delete_webhook`, `tg_answer_callback`): throwaway bot only. **`tg_set_webhook` on a bot
  already in use silently hijacks its updates** — check `tg_get_webhook_info` first and restore
  what you found.

### iiko — `yzel config add-iiko`

- [ ] `iiko_organizations` → feeds every other call
- [ ] `iiko_terminal_groups` · `iiko_nomenclature` · `iiko_stop_list`
- [ ] `iiko_order_types` · `iiko_payment_types` · `iiko_employees`
- [ ] `iiko_deliveries_by_phone` with a known number
- Mutating (`iiko_create_delivery`): demo org only — it creates a real delivery.

### AmoCRM — `yzel config add-amocrm`

- [ ] `amocrm_account` · `amocrm_pipelines` · `amocrm_list` · `amocrm_get`
- Mutating (`amocrm_create`, `amocrm_update`): trial account only.

### Bitrix24 — `yzel config add-bitrix`

- [ ] `bitrix24_crm_list` · `bitrix24_crm_get` · `bitrix24_tasks_list` · `bitrix24_task_get`
- Mutating (`bitrix24_crm_create`, `bitrix24_crm_update`): trial portal only.

### МойСклад — `yzel config add-moysklad`

- [ ] `moysklad_organizations` · `moysklad_list` · `moysklad_get` · `moysklad_stock`
- Mutating (`moysklad_create`, `moysklad_update`): trial account only.

---

## Run log

One row per connector per run. `R` = read probes, `W` = write probes. Status: `pass` / `fail` /
`blocked` (no tenant available) / `skipped`.

| Date | Connector | R | W | Version | Finding |
|---|---|---|---|---|---|
| 2026-09-05 | — | — | — | v0.1.0 | Protocol written. No live run yet — every connector is `blocked` until a tenant is available. L1 suite verified: 138 passed. |

## What a failure obliges

A failed read probe is an **API-drift finding**, not a flaky test. It gets:

1. an issue with the live response body pasted in,
2. a client fix,
3. **a mock update** in the matching `tests/mock_*_server.py`, and
4. a new L1 test pinning the corrected shape.

Steps 3 and 4 are the ones that get skipped, and skipping them means the next quarterly run
re-discovers the same drift.
