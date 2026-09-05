# Contributing

Пишите по-русски или по-английски. / Russian or English, whichever is easier.

## The most useful thing you can do

**Tell us it broke.** Yzel gets cloned far more often than it gets issues, which means failures
are going unreported — most likely silent MCP-server startup failures, which no client surfaces
well. A three-line issue saying "1C, Fresh, server never starts" is worth more than a patch.

The second most useful: an [API drift report](.github/ISSUE_TEMPLATE/api_drift.yml). Our 138
tests run against mock servers written in this repo, so they are structurally incapable of
noticing that Ozon or Wildberries changed a response shape. Only a real tenant sees that.

## Setup

```bash
git clone https://github.com/Aiyo28/yzel.git
cd yzel
uv sync --extra dev      # `--extra dev` is required — a bare `uv run pytest` cannot import yzel
uv run pytest -q         # expect: 138 passed
```

Python 3.11+. Windows works without WSL.

## Working on a connector

Each connector is `src/yzel/connectors/<name>/` with:

- `client.py` — HTTP against the vendor, auth and rate limiting
- `server.py` — MCP tool definitions, `main()` and the `run()` console-script entry point
- a matching `tests/test_<name>.py` and `tests/mock_<name>_server.py`

Adding a tool means touching all four. A new connector also needs a credential type in
`src/yzel/core/types.py`, a `yzel config add-…` command in `cli.py`, and a console script in
`[project.scripts]`.

## Tests

Read `docs/TESTING.md` first — it states what each test layer proves and what it cannot. Short
version: a unit test earns its place if it covers request construction, response parsing, or an
error path with a distinct user-visible message. A test asserting that a mock returns what the
mock was told to return is noise.

If you fix a bug found against a live service, **update the mock too**. A client fix that leaves
`tests/mock_*_server.py` stale re-opens the same gap next quarter.

Never point a test, or a manual check, at a production tenant. `docs/LIVE-CHECKS.md` has the
protocol: read-only probes first, sandbox for Wildberries and Ozon, disposable tenants elsewhere.
21 of the 68 tools mutate remote state.

## Style

`ruff check`, `ruff format --check` and `mypy --strict` all pass and are **gated in CI**. Run
them before opening a PR:

```bash
uv run ruff format . && uv run ruff check --fix . && uv run --with mypy mypy src/yzel
```

Two exemptions exist, both scoped and commented in `pyproject.toml`: `tests/mock_*_server.py`
is exempt from `E501` (vendor payloads stay verbatim), and `yzel.connectors.*.server` relaxes
decorator strictness because the MCP SDK's decorators are untyped. Don't widen either.

Match the file you are editing. Comments and user-facing error strings are Russian in this
codebase; identifiers are English.

## Commits and PRs

Conventional-ish subjects (`fix(ozon): …`, `feat(1c): …`). Say what broke and how you know it is
fixed. If you tested against a live tenant, say which service and edition — that detail is worth
more than the diff.
