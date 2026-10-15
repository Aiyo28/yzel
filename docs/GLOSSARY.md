# Yzel — Glossary

The project's own words. Every doc, spec and PR uses these terms and avoids the aliases.

## Domain

| Term | Definition | Aliases to avoid |
|------|------------|------------------|
| **Connector** | One MCP server for one upstream system. Lives in `src/yzel/connectors/<name>/`. | — |
| **Sidecar** | An external subprocess a connector launches (e.g. `wacli` for WhatsApp). Per tenant, not per connector. | — |
| **Tenant** | One end user's credentials plus their 1C / Bitrix24 / other instance. | — |
| **Users** | Third parties who install Yzel and connect their own systems. | — |

## Distribution

| Term | Definition | Aliases to avoid |
|------|------------|------------------|
| **Console script** | A `[project.scripts]` entry point installed on PATH. Yzel ships 9: `yzel` plus one per connector. | "binary", "executable", "command" |
| **Entry point** | The sync `run()` in a connector's `server.py` that a console script targets. Distinct from `main()`, which is async. | "main", "launcher" |
| **Registry entry** | One `server.json` published to registry.modelcontextprotocol.io under an `io.github.Aiyo28/…` name. One entry = one MCP server. | "listing", "package", "registration" |
| **Plugin** | A Claude Code plugin: `.claude-plugin/plugin.json` + `.mcp.json`. A thin wrapper over the PyPI package, **not** an alternative to it. | "extension", "add-on", "integration" |
| **Directory entry** | The Plugin as published in Anthropic's Claude directory after portal review. Distinct from the Registry entry (MCP Registry). | "listing", "marketplace", "store page" |
| **Pinned launcher** | An `.mcp.json` server entry whose `uvx` argument names an exact version (`yzel==X.Y.Z`). | "locked", "frozen" |
| **Portal Validate** | The Validate button at claude.ai/directory/manage. Runs more checks than `claude plugin validate`. | "lint", "CI check" |
| **Reviewer hold** | A version waiting for an Anthropic reviewer before it can go live. Not a rejection. | "rejected", "blocked" |
| **Drift report** | An issue on the `api_drift` template: a vendor changed a response shape. | "bug", "regression" |
