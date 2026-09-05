# NEXT

Tactical queue. Ordered by impact x effort — reasoning and the full spec live in
`docs/DISTRIBUTION.md`. Updated 2026-09-05.

> **Why this order.** 14-day traffic verified 2026-09-05: 85 views / 28 unique,
> **37 clones / 23 unique cloners**, arriving from Google (10 uniq), Yandex and ChatGPT.
> **Zero issues filed.** `pypi.org/pypi/yzel/json` → 404. The demand exists and cannot install.
> Everything below is ordered against that, not against the connector roadmap.

## 0. Ship the working tree — do this first

~20 modified/new files are uncommitted on `master`: v0.1.1, nine console scripts, the corrected
`mcpServers` config, `server.json`, `llms.txt`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`,
CI, three issue templates, `docs/TESTING.md`, `docs/LIVE-CHECKS.md`, `docs/DISTRIBUTION.md`.

- [ ] Read the diff, commit, push. CI runs on push; the badge in the README 404s until then.
- [ ] Cut the v0.1.1 GitHub release once the tag is pushed.

**Why first:** the *published* README documents an MCP config that cannot work outside a
checkout (`uv run` resolves against cwd; MCP clients spawn with an arbitrary cwd). Every day
unpushed, more of the only organic demand this repo has hits a silent startup failure.

## 1. PyPI — the conversion gate

- [ ] Upload `0.1.1` to PyPI (needs the token). `dist/yzel-0.1.1{-py3-none-any.whl,.tar.gz}`
      already build clean.
- [ ] **Clean-machine check:** `uvx --from yzel yzel-1c` somewhere that has never seen the repo.
      CI cannot prove this — it runs inside a checkout, and cwd-independence is the whole fix.
- [ ] Re-pull traffic afterwards. Clones should fall as PyPI downloads rise; that delta is the
      conversion signal. GitHub retains only 14 days, so `docs/DISTRIBUTION.md` holds the baseline.

## 2. MCP Registry — after PyPI, hard dependency

Verification reads `mcp-name: io.github.Aiyo28/yzel` from the **PyPI package description**
(rendered from `README.md`). No package → nothing to verify against. `[I]`#77, re-confirmed
2026-09-05.

- [ ] Install the `mcp-publisher` CLI (Homebrew).
- [ ] Authenticate with GitHub OAuth, run `mcp-publisher validate`, then submit.
- [ ] `server.json` already validates against the `2025-12-11` schema locally.
- [ ] Open question carried from `[I]`#77: one entry per connector, or one per package? The
      schema allows either reading. Ship one entry, learn, then decide on the remaining seven.

## 3. Claude Code plugin — after PyPI

`.claude-plugin/plugin.json` + `.mcp.json` listing all 8 connectors, each
`{"command": "uvx", "args": ["--from", "yzel", "yzel-<name>"]}`. A thin wrapper over the PyPI
package, **not** a replacement for it. Built before PyPI it would have to bundle source and
resolve deps at first run — Claude-Code-only, and a worse install than the one it replaces.

## 4. Close the feedback loop

23 unique cloners, zero issues. The channel now exists (3 templates, `CONTRIBUTING.md`,
Discussions on, 13 topics); nobody has been pointed at it.

- [ ] Seed Discussions with 2-3 real questions — `EmptySchemaError`, OData publication,
      Windows-without-WSL setup.
- [ ] Triage protocol: a drift report fixes the client **and** its `tests/mock_*_server.py`, then
      pins the corrected shape with a test. Skipping the mock re-opens the same gap next quarter.
- [ ] Show HN post — never actually made. Check before assuming a thread exists to reply to.

## 5. Lint + type pass, then gate it

Verified 2026-09-05: `ruff check` **66**, `ruff format --check` **27 files**, `mypy --strict`
**55 errors in 18 files**. All configured in `pyproject.toml`, none ever enforced.

- [ ] One dedicated pass. Do not fold into an unrelated PR.
- [ ] Only then add the jobs to `.github/workflows/ci.yml` — the comment there explains why they
      are absent, so remove it in the same commit.

## 6. Live verification — needs a tenant

`docs/LIVE-CHECKS.md` has the protocol and an empty run log. Read-only probes first; sandbox for
Wildberries and Ozon; 21 of 68 tools mutate production state.

- [ ] ⚠ **The 1C Бухгалтерия smoke test is BLOCKED, not pending.** `[I]`#78: 1C:Fresh *trial*
      tenants structurally block the OData data plane — confirmed on
      `msk1.1cfresh.com/a/sbm_demo/4001896/`, where `/$metadata` returns HTTP 200 with only
      system `ComplexType`s and **zero** `EntityType`s. Publication needs Configurator or
      tenant-admin rights, which trials do not grant. This needs **an on-prem infobase or a paid
      Fresh tenant with admin rights** — an acquisition task, not an afternoon. It sat as an open
      checkbox from 2026-04-24 to 2026-09-05 because it was filed as pending.

## 7. Connector roadmap — `ROADMAP.md`

Unchanged and deliberately last: none of it helps the cloners who cannot install what ships today.

- v0.2 — WhatsApp via `wacli` sidecar · goszakup.gov.kz read-only · AmoCRM OAuth browser flow
- v0.3 — meetings tier, research first (Zoom / Meet / Teams / Telemost / VK / Контур.Толк / SberJazz)
- Deferred — Kaspi Pay/Business, pending a banking tier

- [ ] Trivial: `ROADMAP.md` says "137 tests across all connectors". It is **138**.

## Session context

- v0.1.0 shipped 2026-04-24, public at https://github.com/Aiyo28/yzel. v0.1.1 prepared 2026-09-05.
- Pre-D53 planning fossils (MASTERPLAN/TODO/BRIEF) deleted in commit `f874a37`.
- Key decisions reflected in commit messages + `docs/ARCHITECTURE.md`.
- Live 1C:Fresh probe found the silent-zero bug → fixed via `EmptySchemaError` (commit `f874a37`).
- The v0.1.0 GitHub release step was blocked by a local hook; it was run manually. Expect the
  same on v0.1.1.
- Strategic context is vault-side: `Projects/yzel/_context.md` + `_insights.md`. ⚠ Both are stale
  on two points — they record the credential path as `~/.yzel/vault.db` (it is `store.db`) and
  the install as from-source only.
