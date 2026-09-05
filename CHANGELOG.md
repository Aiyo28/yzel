# Changelog

## [0.1.2] — 2026-09-05

### Fixed
- **0.1.1 was dead on arrival for every user.** `mcp>=1.0.0` had no upper bound. `uv.lock`
  pins 1.27.0, so the 138 tests, `mypy --strict` and CI all ran against a working SDK — but a
  real install resolves fresh, gets **mcp 2.1.1**, and every connector server module dies at
  import with `AttributeError: 'Server' object has no attribute 'list_tools'`. Bounded to
  `<2.0.0`.

### Added
- **CI now installs the built wheel with fresh dependency resolution and imports all eight
  servers**, and runs weekly on a cron. The lockfile is what hid this: `uv sync` is not what a
  user experiences, and nothing in the pipeline exercised the published artifact.

### Known
- The mcp 2.x port is not done. The pin is deliberate, not an oversight — lifting it requires
  migrating the `@server.list_tools()` / `@server.call_tool()` handlers across all 8 servers.

All notable changes to Yzel are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-09-05

First PyPI release. No connector behaviour changed; this release exists to make the thing
installable and its integration path correct.

### Added

- **A console script per connector** — `yzel-1c`, `yzel-bitrix24`, `yzel-amocrm`,
  `yzel-moysklad`, `yzel-wildberries`, `yzel-ozon`, `yzel-telegram`, `yzel-iiko`. Each is a
  standalone stdio MCP server entry point (`run()` in the connector's `server.py`).
- `server.json` for the MCP Registry, plus the `mcp-name` ownership token in the README.
- `docs/TESTING.md` — what the 138 tests prove and what they cannot.
- `docs/LIVE-CHECKS.md` — the repeatable live-verification protocol, with the read-only /
  mutating split for all 68 tools.
- `CONTRIBUTING.md`, `SECURITY.md`, `llms.txt`, issue templates, and CI running the suite on
  Python 3.11 / 3.12 / 3.13.

### Fixed

- **The documented MCP client config could not work outside the repo.** It used
  `{"command": "uv", "args": ["run", "python", "-m", "yzel.connectors.onec.server"]}`, and
  `uv run` resolves against the current working directory's project. MCP clients spawn servers
  with an arbitrary cwd, so this only started if the cwd happened to be a yzel checkout —
  otherwise it failed silently at launch. Now `{"command": "uvx", "args": ["--from", "yzel",
  "yzel-1c"]}`, which is cwd-independent and needs no clone.
- **Documented credential path was wrong.** README and `docs/ARCHITECTURE.md` said
  `~/.yzel/vault.db`; the code has always used `~/.yzel/store.db` (with the key at
  `~/.yzel/vault.key`). Anyone backing up or deleting credentials was looking in the wrong place.

### Changed

- **Lint and types are clean and now gated in CI.** Was 66 `ruff` findings and 55
  `mypy --strict` errors, neither ever enforced. Now zero of both, plus `ruff format` across
  the tree. Two exemptions, each scoped and commented: `tests/mock_*_server.py` keeps long
  lines (re-wrapping vendor payloads would make the fixtures diverge from what the services
  actually send), and `yzel.connectors.*.server` relaxes decorator strictness because the MCP
  SDK ships `@server.list_tools()` untyped.
- `ServiceType` and `ConnectionStatus` are now `StrEnum` rather than `(str, Enum)`.
- **AmoCRM `_request` now accepts a JSON array.** The bulk create endpoints post a list; the
  annotation said `dict | None`, so the type checker was right and the signature was wrong.
- **iiko: a failed token refresh after a 401 now raises** instead of retrying with `None` in
  the `Authorization` header, which would have sent `Bearer None`.

### Known

- No connector has been verified against a live tenant on a repeatable basis. See
  `docs/LIVE-CHECKS.md`; the run log is empty. The 1C data-plane check is blocked on tenant
  access, not on effort — 1C:Fresh trials cannot publish OData objects (vault `[I]`#78).

## [0.1.0] — 2026-04-24

Initial public release. Eight connectors — 1C:Enterprise (OData v3), Bitrix24, AmoCRM,
МойСклад, Wildberries, Ozon, Telegram, iiko — 68 MCP tools, encrypted local credential vault,
138 tests against mock servers. Install from source only.

[0.1.1]: https://github.com/Aiyo28/yzel/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Aiyo28/yzel/releases/tag/v0.1.0
