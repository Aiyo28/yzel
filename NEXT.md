# NEXT

Tactical queue. Reasoning and the full spec live in `docs/DISTRIBUTION.md`.

**Read the State table before the Queue.** These are separated on purpose: the previous version
of this file was a queue that described finished work as pending, and four releases went past it
in one afternoon without it noticing.

## State — verified 2026-09-05

| | |
|---|---|
| PyPI | `yzel 0.1.3` · `Requires-Dist: mcp<2.0.0,>=1.0.0` |
| MCP Registry | `io.github.Aiyo28/yzel` v0.1.3, `isLatest: true`, pypi + uvx |
| Install | `uvx --from yzel yzel-<connector>` — all 8 complete an MCP `initialize` handshake reporting `v0.1.3` |
| CI | tests on 3.11/3.12/3.13 · ruff · ruff format · mypy `--strict` · build · `installed` (wheel, no lockfile) · weekly cron |
| Quality | 143 tests, 0 ruff findings, 0 mypy findings |
| Version drift | `tests/test_versions.py` asserts pyproject == `__version__` == `server.json` == `plugin.json` == `llms.txt`, and that `mcp` stays `<2` |
| Plugin | `.claude-plugin/plugin.json` + `.mcp.json` exist; **not listed in any marketplace yet** |

**Traffic baseline** — 14 days to 2026-09-05, captured *before* any of the above was live:
85 views / 28 unique, **37 clones / 23 unique cloners**, arriving from Google (10 uniq), Yandex
and ChatGPT. **Zero issues filed.** GitHub retains only 14 days, so this line is the baseline;
`docs/DISTRIBUTION.md` holds the reasoning. Re-pull traffic in a fortnight — clones should fall
as PyPI downloads rise, and that delta is the conversion signal.

## Queue

### 1. List yzel in a Claude Code marketplace

`.mcp.json` and `plugin.json` ship, but no marketplace carries them, so `/plugin install` cannot
find yzel. The `aiyo` marketplace lives in the **memento-os** repo, which makes this a
cross-repo source.

- [ ] ⚠ Do **not** use a `github` source. It round-trips through SSH and fails with
      `Permission denied (publickey)` for anyone who does not own the repo — i.e. every user.
      This exact bug shipped in memento-os v2.3.1 and was fixed in v2.3.2 by switching to a
      relative path. A relative path is not available across repos; read the `git` source type
      (explicit HTTPS URL) before writing the entry.

### 2. Handshake assertion in `docs/LIVE-CHECKS.md`

Pipe an `initialize` request at each of the 8 servers and assert `serverInfo.name` and
`serverInfo.version`. Run by hand on 2026-09-05 it caught two real defects that every other
gate passed: servers advertising the mcp SDK's version as their own, and `yzel --version`
reporting 0.1.0 while the package shipped 0.1.2.

- [ ] Script it into the live-check protocol, and into CI where it needs no credentials —
      `initialize` requires no vault entry.

### 3. Close the feedback loop

23 unique cloners, zero issues. The channel exists (3 issue templates, `CONTRIBUTING.md`,
Discussions on, 13 topics); nobody has been pointed at it.

- [ ] Seed Discussions with 2-3 real questions — `EmptySchemaError`, OData publication,
      Windows-without-WSL setup.
- [ ] Triage protocol: an API-drift report fixes the client **and** its
      `tests/mock_*_server.py`, then pins the corrected shape with a test. Skipping the mock
      re-opens the same gap next quarter.
- [ ] Show HN post — never actually made. Check before assuming a thread exists to reply to.

### 4. Live verification — BLOCKED on tenant access, not on effort

`docs/LIVE-CHECKS.md` has the protocol and an empty run log. Read-only probes first; sandbox for
Wildberries and Ozon; 21 of 68 tools mutate production state.

- ⛔ **The 1C Бухгалтерия smoke test is BLOCKED.** `[I]`#78: 1C:Fresh *trial* tenants
  structurally block the OData data plane — confirmed on `msk1.1cfresh.com/a/sbm_demo/4001896/`,
  where `/$metadata` returns HTTP 200 with only system `ComplexType`s and **zero** `EntityType`s.
  Publication needs Configurator or tenant-admin rights that trials do not grant. This needs an
  on-prem infobase or a paid Fresh tenant — an acquisition task. It sat as an open checkbox from
  2026-04-24 to 2026-09-05 because it was filed as pending rather than blocked.
- Owner is asking ODAS for read-only access to a live 1С:Бухгалтерия (2026-09-05). Parked until
  that lands.

### 5. Connector roadmap — `ROADMAP.md`

Deliberately last: none of it helps the cloners who arrive today.

- v0.2 — WhatsApp via `wacli` sidecar · goszakup.gov.kz read-only · AmoCRM OAuth browser flow
- v0.3 — meetings tier, research first (Zoom / Meet / Teams / Telemost / VK / Контур.Толк / SberJazz)
- Deferred — Kaspi Pay/Business, pending a banking tier

### 6. mcp 2.x port — deliberate debt

`mcp` is pinned `<2.0.0`. 2.x removed `Server.list_tools`, and every connector server module
fails at import against it. Lifting the pin means migrating `@server.list_tools()` /
`@server.call_tool()` across all 8 servers.

- [ ] Do not widen the bound without running CI's `installed` job against the real latest release.

## Shipped 2026-09-05

- **0.1.1** — packaging: 8 sync `run()` entry points, 9 console scripts, `server.json`,
  `.mcp.json`, `llms.txt`, CI, issue templates, `CONTRIBUTING`/`SECURITY`/`CHANGELOG`, lint and
  type clean (was 66 ruff / 55 mypy). Fixed the documented MCP config, which used `uv run` and so
  could not work outside a checkout. **Dead on arrival** — see 0.1.2.
- **0.1.2** — bounded `mcp<2.0.0`. `mcp>=1.0.0` was unbounded; `uv.lock` pinned a working 1.27.0
  so every gate passed, while a real install resolved 2.1.1 and died at import.
- **0.1.3** — all 8 servers pass `version=__version__` (they advertised the SDK's version), and
  `__version__` now derives from package metadata (it was hardcoded `0.1.0`).
- Yank 0.1.1 and 0.1.2 on PyPI when convenient. Both are traps for anyone who pins.

## Session context

- v0.1.0 shipped 2026-04-24. Pre-D53 planning fossils (MASTERPLAN/TODO/BRIEF) deleted in `f874a37`.
- Live 1C:Fresh probe found the silent-zero bug → fixed via `EmptySchemaError` (`f874a37`).
- **Every defect found on 2026-09-05 got through the same way: the check ran against something
  other than what a user gets.** Tests ran against `uv.lock`, not a fresh resolve. The install
  check confirmed the process started, not that it spoke the protocol. `--version` was asserted
  nowhere. CI now covers the first two; queue item 2 covers the third.
- Strategic context is vault-side: `Projects/yzel/_context.md` + `_insights.md`. ⚠ Both are stale
  on two points — they record the credential path as `~/.yzel/vault.db` (it is `store.db`) and
  the install as from-source only.
