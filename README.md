# Yzel (Узел)

> Единый MCP-фреймворк для подключения 1С, Битрикс24, AmoCRM и МойСклад к AI-ассистентам.

**Unified MCP connector framework for CIS business tools — bridge between 1C, Bitrix24, AmoCRM, Moysklad and AI assistants.**

## Установка / Installation

```bash
pip install yzel
```

## Быстрый старт / Quick Start

```bash
# Добавить подключение к 1С
yzel config add-1c

# Добавить подключение к Битрикс24
yzel config add-bitrix

# Добавить подключение к МойСклад
yzel config add-moysklad

# Показать все подключения
yzel config list
```

## MCP серверы / MCP Servers

Каждый коннектор — это отдельный MCP-сервер:

```bash
# 1С Enterprise
python -m yzel.connectors.onec.server

# Битрикс24
python -m yzel.connectors.bitrix24.server

# AmoCRM
python -m yzel.connectors.amocrm.server

# МойСклад
python -m yzel.connectors.moysklad.server
```

## Поддерживаемые сервисы / Supported Services

| Сервис | API | Авторизация | Статус |
|--------|-----|-------------|--------|
| 1С:Предприятие | OData v3 REST | Basic Auth | ✅ В разработке |
| Битрикс24 | REST API | Webhook | 🔲 Запланировано |
| AmoCRM/Kommo | REST API v4 | OAuth2 | 🔲 Запланировано |
| МойСклад | JSON API 1.2 | Bearer Token | 🔲 Запланировано |

## Лицензия / License

- Коннекторы (`src/yzel/connectors/`): MIT
- Enterprise функции (`src/yzel/enterprise/`): BSL
