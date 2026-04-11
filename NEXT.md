# Next

## Continue
- Test against real 1C instance (Training Version on Windows VM or partner access)
- Build Bitrix24 connector (webhook API client + MCP server)
- Build AmoCRM connector (OAuth2 flow + token refresh)
- Build Moysklad connector (Bearer token + nested entities)
- Write integration tests using mock_odata_server
- Write Habr article draft

## Decide
- Windows VM tool: Parallels vs UTM for 1C Training Version testing
- Whether to add HTTP Service mode (vladimir-kharin pattern) alongside OData

## Blocked
- Real 1C integration test blocked until VM or partner access obtained

## Done (2026-04-11)
- ✅ Project scaffold (MASTERPLAN, TODO, ROADMAP, CLAUDE.md)
- ✅ Credential vault (AES-256 encrypted SQLite)
- ✅ 1C OData v3 client (Cyrillic URLs, Basic Auth, JSON format)
- ✅ Schema discovery ($metadata XML parsing)
- ✅ 1C MCP server (4 tools: list_entities, query, get, schema)
- ✅ CLI (yzel config add-1c/add-bitrix/add-moysklad/list/remove)
- ✅ Mock 1C OData server (3 entities, realistic data)
- ✅ 11 tests passing
- ✅ Full pipeline verified end-to-end

Updated: 2026-04-11
