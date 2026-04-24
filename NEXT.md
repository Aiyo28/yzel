# NEXT

Tactical follow-ups after v0.1.0 launch (2026-04-24).

## Immediate (this week)

- [ ] **PyPI publish** — `uv publish` with PyPI token; verify `pip install yzel` resolves; flip README from "install from source" back to `pip install yzel` as primary
- [ ] **MCP Server Registry listing** — prereq: PyPI done. Then:
  - Install `mcp-publisher` CLI (`brew install mcp-publisher`)
  - Add `mcpName: io.github.Aiyo28/yzel` to package metadata
  - Run `mcp-publisher init` → edit `server.json` (8 entries, one per connector)
  - `mcp-publisher login` (GitHub OAuth) → `mcp-publisher publish`
  - Doc: https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx
- [ ] **Бухгалтерия-template live smoke test** — create second 1C:Fresh app from «1С:Бухгалтерия предприятия (демо)», check if its default OData publication exposes `Catalog_*` entities; if yes, record 30-sec screencap of `onec_query` returning real rows → add to README as the moat proof

## Follow-ups from launch feedback

- [ ] Respond to HN thread (Show HN post)
- [ ] Triage first real-user issues (likely OData publication + user-permissions questions — see `docs/TROUBLESHOOTING-1C.md`)
- [ ] If users hit `EmptySchemaError`, confirm error message + doc link is actionable; iterate text

## v0.2 scope (ROADMAP.md)

- WhatsApp via `wacli` sidecar
- goszakup.gov.kz (read-only)
- AmoCRM OAuth browser flow

## Session context

- v0.1.0 shipped 2026-04-24, public at https://github.com/Aiyo28/yzel
- Pre-D53 planning fossils (MASTERPLAN/TODO/BRIEF) deleted in commit `f874a37`
- Key decisions reflected in commit messages + `docs/ARCHITECTURE.md`
- Live 1C:Fresh probe found silent-zero bug → fixed via `EmptySchemaError` (commit `f874a37`)
- GitHub release step blocked by local hook; user ran manually
