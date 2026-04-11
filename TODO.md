# TODO — Yzel (Узел)

## Phase 1 — Foundation

### Setup
- [ ] Initialize Python project with uv + pyproject.toml
- [ ] Configure monorepo structure (src/yzel/)
- [ ] Set up pytest + pytest-asyncio
- [ ] Create MIT LICENSE + BSL LICENSE-ENTERPRISE
- [ ] Configure GitHub repo with issue templates
- [ ] Set up CI (GitHub Actions: lint + test)

### Core Infrastructure
- [ ] Implement credential vault (SQLite + AES-256 encryption)
- [ ] Implement base MCP server class with common patterns
- [ ] Implement CLI entry point (`yzel config add-1c`, `yzel config add-bitrix`, etc.)
- [ ] Implement shared data types and models
- [ ] Add bilingual logging (RU/EN)

### 1C Connector (Deep Focus)
- [ ] Implement OData v3 client with JSON support
- [ ] Implement Basic Auth credential handling
- [ ] Implement dynamic schema discovery via $metadata endpoint
- [ ] Implement catalog read operations (Сп��ав��чники)
- [ ] Implement document read operations (Документы)
- [ ] Implement register read operations (Регистры)
- [ ] Implement document create/update operations
- [ ] Handle Cyrillic field names and encoding quirks
- [ ] Test against 1C:Бухгалтерия configuration
- [ ] Test against 1C:Управление торговлей configuration
- [ ] Test against 1C:ERP configuration
- [ ] Test against 1C:Fresh cloud endpoint
- [ ] Write MCP server entry point with tool definitions

### Bitrix24 Connector
- [ ] Implement webhook-based API client
- [ ] Implement CRM entity operations (leads, contacts, deals, companies)
- [ ] Implement task operations
- [ ] Implement rate limiting (2 req/sec bucket)
- [ ] Write MCP server entry point with tool definitions

### AmoCRM Connector
- [ ] Implement OAuth2 flow with PKCE
- [ ] Implement automatic token refresh (5 min before expiry)
- [ ] Implement lead/contact/company operations
- [ ] Implement pipeline operations
- [ ] Write MCP server entry point with tool definitions

### Moysklad Connector
- [ ] Implement Bearer token auth
- [ ] Implement product/order/counterparty operations
- [ ] Implement inventory queries
- [ ] Implement nested entity resolution
- [ ] Write MCP server entry point with tool definitions

### Testing
- [ ] Write integration tests for 1C OData client
- [ ] Write integration tests for Bitrix24 webhook client
- [ ] Write integration tests for AmoCRM OAuth flow
- [ ] Write integration tests for Moysklad API client
- [ ] Write unit tests for credential vault encryption
- [ ] Write unit tests for schema discovery

### Documentation
- [ ] Write README.md (bilingual RU/EN)
- [ ] Write setup guide for each connector
- [ ] Write ARCHITECTURE.md
- [ ] Create docs/_context/BRIEF.md

### Launch
- [ ] Publish to PyPI as `yzel`
- [ ] Write Habr article (RU) — "Как подключить 1�� к AI через MCP"
- [ ] Post on Infostart forum
- [ ] Create Telegram community channel
- [ ] Record demo video/GIF for README

## Phase 2 — Enterprise Foundation

### Cross-System Queries
- [ ] Implement entity matching engine (client name normalization)
- [ ] Implement cross-system query parser
- [ ] Implement unified response format

### Enterprise Auth
- [ ] Implement SAML/SSO integration
- [ ] Implement multi-tenant workspace isolation
- [ ] Implement enterprise credential management

### Audit & Compliance
- [ ] Implement query logging with user attribution
- [ ] Implement data access audit trail
- [ ] Implement compliance export

### Dashboard
- [ ] Initialize Next.js project
- [ ] Implement connection health monitoring UI
- [ ] Implement credential management UI
- [ ] Implement query history view

### Revenue
- [ ] Set up payment processing (Stripe + RU alternative)
- [ ] Implement license key system
- [ ] Create pricing page
- [ ] Reach out to 3+ 1C integrator firms
