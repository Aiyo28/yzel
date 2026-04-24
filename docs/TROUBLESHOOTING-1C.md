# Troubleshooting 1C

## `EmptySchemaError`: `$metadata` parses but returns zero entities

### Symptom

```python
yzel.core.discovery.EmptySchemaError: 1C OData endpoint ... returned $metadata
with zero EntityType declarations.
```

The transport is published (HTTP 200 on `/$metadata`, you got an XML body back), but the XML contains only system `ComplexType`s — no `EntityType`s for your catalogs, documents, or registers.

### Cause

In 1C, each business object must be explicitly **published to OData**. The standard OData endpoint (`/odata/standard.odata/`) exposes only objects flagged as publishable. The transport itself being up does **not** mean any business data is reachable.

Common scenarios:

| Environment | Why |
|---|---|
| 1C:Fresh trial tenant | Trial tier does not allow Configurator access; demo templates (e.g., «sbm_demo» / УНФ trial) often ship with zero objects published |
| Fresh paid tenant | OData publication is a tenant-admin action; never done on fresh provisioning |
| On-prem, first-time deploy | Configurator flag «Включать в состав содержимого справочника» / «Публикация стандартного OData-интерфейса» not set on objects |
| Restricted user | User profile missing «Чтение» on the objects — they exist in metadata but are filtered out for this user |

### Fix

**Path A — Configurator (on-prem or Fresh with Configurator access)**

1. Open the infobase in Configurator.
2. **Администрирование → Публикация на веб-сервере → Настроить** → tick «Стандартный OData-интерфейс».
3. For each catalog/document/register to expose:
   - Right-click the object → **Свойства** → locate «Состав Стандартного интерфейса OData».
   - Or use the batch action: **Сервис → Опубликовать стандартный OData-интерфейс** → select objects → confirm.
4. Re-parse metadata.

**Path B — Tenant admin (1C:Fresh paid tiers)**

Via the tenant administrator portal:
- **Администрирование → Интеграция с другими программами → Настройки публикации стандартного OData**
- Tick object groups (Справочники, Документы, Регистры сведений, etc.).
- Apply.

Exact menu path varies by configuration (УНФ / Бухгалтерия / УТ / ERP all differ slightly).

**Path C — If you can't publish, use an infobase that already has it**

Not every Fresh template blocks OData. If you're smoke-testing:
- Create a second infobase from a different template.
- Some 1C partner demo servers expose pre-published OData; search «1C OData demo» + your configuration name.

### Verification

```bash
curl -u 'user' 'https://host/base/odata/standard.odata/$metadata' | grep -c '<EntityType'
```

- `0` → still not published.
- `>0` → works; Yzel will now succeed.

### Authentication works but metadata is still empty — read-permission check

If `$metadata` has `EntityType`s but `get_entity_list` returns 0 rows on every catalog:

1. Web client → **Администрирование → Настройки пользователей и прав → Пользователи**.
2. Open your API user → **Профили групп доступа** — check for «Чтение» profile on the objects you need.
3. Save, retry.

---

## Other common failures

### `OneCError [401/Invalid credentials]`

- Wrong username/password.
- User is deactivated.
- User has «Запрет входа в программу» set — Basic Auth fails silently at the application layer.

### `OneCError [404]` on valid entity name

- Entity exists but isn't published to OData (see above).
- You typed the English name — 1C uses `Catalog_<Cyrillic>`, not `Catalog_<Transliterated>`. Correct: `Catalog_Контрагенты`, not `Catalog_Counterparties`.

### Very slow `$metadata` fetch (20+ seconds)

Expected on 10MB+ ERP configurations. Yzel uses streaming iterparse so memory stays flat, but wall-clock depends on server CPU + network. Increase `timeout` on `discover_schema()` if needed.

### Cyrillic entity names garbled in output

`httpx` defaults and 1C's UTF-8 encoding should Just Work. If you see mojibake, check: (a) your terminal is UTF-8, (b) you're not logging via a Windows-1251-defaulting pipeline.
