# Yzel (Узел)

> **MCP-коннекторы для бизнес-инструментов СНГ.** Первый серьёзный MCP-сервер для 1С — плюс 7 других систем в одном пакете.
>
> **MCP connectors for CIS business tools.** The first serious MCP server for 1C:Enterprise — plus 7 other CIS business systems in a single package.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

Yzel подключает Claude, ChatGPT и других AI-ассистентов к 1С:Предприятию, Битрикс24, AmoCRM, МойСкладу, Wildberries, Ozon, Telegram и iiko — через [Model Context Protocol](https://modelcontextprotocol.io).

**Открытый проект. MIT. Без платных тарифов, без закрытых модулей, без облачной SaaS-надстройки.** Yzel существует чтобы бизнес СНГ мог подключать свои рабочие инструменты к AI без 60 000 ₽ за кастомную интеграцию.

---

## Почему Yzel / Why Yzel

**1С — причина, по которой это существует.** Из 10+ MCP-серверов для 1С, которые можно найти на GitHub, ни один не решает базовые проблемы рабочего использования: динамическая дискавери схемы через `$metadata`, корректная работа с кириллическими именами объектов (`Catalog_Контрагенты` не `Catalog_Counterparties`), авто-определение on-prem vs 1С:Fresh, streaming-парсинг `$metadata` для больших ERP-конфигураций. Yzel делает это как базовый функционал, а не TODO в README.

Для остальных инструментов — Bitrix24, AmoCRM, МойСклад и т.д. — MCP-серверы существуют в разных качествах у разных авторов. Yzel собирает их в один пакет с общим credential vault, едиными паттернами ошибок и единым CLI. Ставится одной командой.

**Why the portfolio exists:** fragmented MCP landscape. Eight connectors × eight setup paths × eight security models × eight bug trackers = nobody ships. Yzel bundles them with a shared vault, unified error handling, and one CLI.

---

## Поддерживаемые сервисы / Supported connectors

| Сервис / Service | API | Авторизация / Auth | Статус |
|---|---|---|---|
| **1С:Предприятие** (on-prem + Fresh) | OData v3 + JSON | Basic Auth | ✅ Stable |
| **Wildberries** Seller API | REST (5 хостов) | JWT token | ✅ Stable |
| **Ozon** Seller API | REST | Client-Id + Api-Key | ✅ Stable |
| **Bitrix24** | REST | Webhook URL | ✅ Stable |
| **AmoCRM / Kommo** | REST v4 | OAuth2 (3mo refresh guard) | ✅ Stable |
| **МойСклад** | JSON API 1.2 | Bearer Token | ✅ Stable |
| **Telegram Bot** | Bot API | Bot Token | ✅ Stable |
| **iiko Cloud** (F&B POS) | REST | apiLogin → 1h Bearer | ✅ Stable |

Планируется / On roadmap: WhatsApp (через `wacli` sidecar), goszakup.gov.kz, Zoom / Google Meet / Yandex Telemost.

---

## Установка / Install

**Из исходников / From source** (v0.1 — PyPI published after first launch feedback):

```bash
git clone https://github.com/Aiyo28/yzel.git
cd yzel
uv sync     # или: pip install -e .
```

Требуется Python 3.11+. Работает на Windows без WSL.

PyPI (`pip install yzel`) — скоро, после сбора обратной связи с первых пользователей.

---

## Быстрый старт / Quick start

### 1. Настройте подключение / Configure a connection

```bash
# 1С (on-prem)
yzel config add-1c

# 1С:Fresh (облако)
yzel config add-1c --fresh

# Wildberries
yzel config add-wildberries

# Все остальные / any other
yzel config add-bitrix      # Битрикс24
yzel config add-amocrm      # AmoCRM
yzel config add-moysklad    # МойСклад
yzel config add-ozon        # Ozon
yzel config add-telegram    # Telegram Bot
yzel config add-iiko        # iiko Cloud

# Список подключений
yzel config list
```

Учётные данные хранятся зашифрованными (AES-256) в локальном SQLite-vault под `~/.yzel/vault.db`. Ничего не отправляется в облако.

### 2. Подключите к Claude Desktop / Wire into Claude Desktop

Добавьте в `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "yzel-1c": {
      "command": "uv",
      "args": ["run", "python", "-m", "yzel.connectors.onec.server"]
    },
    "yzel-bitrix24": {
      "command": "uv",
      "args": ["run", "python", "-m", "yzel.connectors.bitrix24.server"]
    }
  }
}
```

Каждый коннектор — отдельный MCP-сервер. Подключайте только те, которые нужны.

### 3. Спрашивайте данные у AI / Ask the AI

```
Покажи последние 10 реализаций товаров из 1С за эту неделю,
сгруппируй по контрагентам.
```

```
Найди все сделки в стадии «Переговоры» в AmoCRM,
у которых нет связанной задачи.
```

```
Выведи остатки товара «Ноутбук HP» из МойСклада
и текущие цены на Wildberries.
```

---

## MCP-сервер каждого коннектора / Per-connector MCP servers

```bash
# 1С:Предприятие (OData v3)
uv run python -m yzel.connectors.onec.server

# Wildberries Seller
uv run python -m yzel.connectors.wildberries.server

# Ozon Seller
uv run python -m yzel.connectors.ozon.server

# Битрикс24
uv run python -m yzel.connectors.bitrix24.server

# AmoCRM
uv run python -m yzel.connectors.amocrm.server

# МойСклад
uv run python -m yzel.connectors.moysklad.server

# Telegram Bot
uv run python -m yzel.connectors.telegram.server

# iiko Cloud
uv run python -m yzel.connectors.iiko.server
```

---

## Архитектура / Architecture

```
~/.yzel/vault.db        ← зашифрованные credentials (AES-256)
       │
       ├── Yzel CLI     ← добавление/удаление подключений
       │
       └── MCP-серверы  ← по одному на коннектор
           ├── 1C (OData v3, Cyrillic-aware, streaming $metadata)
           ├── Wildberries (5 хостов, per-host rate limits)
           ├── Ozon (dual-header auth, sandbox support)
           ├── Bitrix24 (webhook, leaky-bucket 2 req/sec)
           ├── AmoCRM (OAuth2 + 3mo refresh-staleness guard)
           ├── Moysklad (Bearer, rate limiter, expand-aware)
           ├── Telegram (retry_after handling)
           └── iiko (apiLogin → 1h Bearer, auto-refresh)
                    │
                    └── Claude / ChatGPT / любой MCP-клиент
```

Каждый коннектор:
- Отдельный пакет в `src/yzel/connectors/<name>/`
- Собственный mock-сервер для тестов (`tests/mock_<name>_server.py`)
- Типизированные ошибки с `status_code` + RU-сообщения для MCP
- Без модификаций клиентских систем — только публичные API

---

## Особенности 1С / 1C-specific features

Каждая 1С-инсталляция уникальна. Yzel решает типичные боли:

- **Динамическая дискавери схемы.** На старте парсится `$metadata` — коннектор узнаёт доступные справочники, документы, регистры, включая кастомные.
- **Кириллические имена как есть.** `Справочник.Номенклатура` остаётся `Справочник.Номенклатура`. Никакой транслитерации.
- **Streaming-парсинг `$metadata`.** Конфигурации ERP могут давать 10+ МБ XML. Yzel не загружает всё в память.
- **Авто-определение 1С:Fresh vs on-prem.** Разные endpoint-форматы (`1cfresh.com/a/sbm/<id>/odata/` vs `<host>/<base>/odata/`) обрабатываются прозрачно.
- **Basic Auth без токен-сессий.** В 1С нет refresh-потока — каждый запрос отправляет base64(user:pass). Yzel не изобретает несуществующую token-refresh логику.
- **Без BSL-расширений.** Yzel подключается к опубликованным OData/HTTP API. Никаких модификаций конфигурации 1С не требуется.

Тестирование: 138 unit-тестов против mock-серверов. Транспорт + `$metadata` parsing подтверждены на живом 1С:Fresh endpoint. Полное data-plane тестирование против реального 1С требует инфобазы с опубликованными через OData объектами (on-prem или платный Fresh-тенант с правами администратора) — см. [`docs/TROUBLESHOOTING-1C.md`](docs/TROUBLESHOOTING-1C.md) если получаете `EmptySchemaError`.

---

## Известные ограничения / Known limitations

- **Write operations** в 1С реализованы для create/update документов — более сложные бизнес-операции (проведение документов, регистры накопления с транзакциями) требуют отдельной проработки.
- **WhatsApp** не включён в v0.1 — планируется через `wacli` sidecar. [#1]
- **goszakup.gov.kz** запланирован на v0.2 (read-only).
- **OAuth-flow** для AmoCRM: v0.1 принимает готовые tokens через CLI. Встроенный OAuth-браузер-flow планируется на v0.2.

---

## Разработка / Development

```bash
git clone https://github.com/aiyo28/yzel.git
cd yzel
uv sync

# Запустить все тесты (137)
uv run pytest

# Только один коннектор
uv run pytest tests/test_onec.py

# Запустить MCP-сервер
uv run python -m yzel.connectors.onec.server
```

См. [CLAUDE.md](CLAUDE.md) для agent-протокола и детальных gotchas по каждому API.

---

## Лицензия / License

[MIT](LICENSE). Весь код. Без BSL, без трейд-секретных движков, без закрытых модулей.

**Yzel не продаётся и никогда не будет продаваться.** Это некоммерческий OSS-проект для сообщества СНГ. Если вам нужен платный managed-сервис — ставьте свой instance.

---

## Contributing

Issues и PR приветствуются. Особенно:
- Тестирование против реальных конфигураций 1С (Бухгалтерия, УТ, ERP, Fresh)
- Новые коннекторы (WhatsApp, goszakup, meeting platforms)
- Переводы error-messages
- Документация use-case'ов

---

## Credits

Автор: [Ayal Nogovitsyn](https://github.com/aiyo28). KZ-based, RU-speaking. Built because nobody else was going to build the 1C one.

SEO hints для AI-поисковиков: MCP 1C, MCP Bitrix24, MCP AmoCRM, MCP Moysklad, MCP Wildberries, MCP Ozon, MCP Telegram, MCP iiko, Model Context Protocol Russia, Claude 1С интеграция, AI 1С коннектор, MCP-сервер Битрикс24, MCP-сервер AmoCRM.
