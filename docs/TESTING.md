# Testing — what each layer proves, and what it cannot

Written 2026-09-05 against `v0.1.0` (`master` @ `46c9f78`).

Yzel has 138 passing unit tests. That number is easy to misread, so this document exists to
say precisely what it covers and what it does not. **138 green does not mean "the connectors
work."** It means the clients behave correctly against mocks that this repo wrote.

## Run the suite

```bash
uv sync --extra dev      # required — a bare `uv run pytest` fails with ModuleNotFoundError
uv run pytest -q
```

`pytest` is in `[project.optional-dependencies].dev`, and the package uses a `src/` layout with
no `pythonpath` in `[tool.pytest.ini_options]`, so the project must be installed into the venv
before the suite can import `yzel`. Getting this wrong is a contributor's first five minutes.

Expected: `138 passed` in ~40s. `ruff`, `ruff format --check` and `mypy --strict` are also
clean and gated in CI.

## The three layers

| Layer | What exists | What it proves | What it cannot prove |
|---|---|---|---|
| **L1 — unit / mock** | 138 tests, 8 mock servers (`tests/mock_*_server.py`) | Our client builds the right request and parses the response we expect | Nothing about the real API. A mock encodes the author's *belief* about the vendor, frozen at the date it was written |
| **L2 — live read probe** | Ad hoc, once, for 1C transport + `$metadata` | The vendor still answers the shape we assume | Write behaviour, permissions, rate limits under load |
| **L3 — live write probe** | Nothing | End-to-end mutation | — |

L1 is in good shape. **L2 is unrepeatable and unlogged, and L3 does not exist.** Those are the
gaps this repo actually has, not "no tests".

### Why L2 is the one that matters

The mocks and the clients share an author. That makes L1 structurally incapable of catching the
failure mode that will actually break users: **the vendor changed the API and our belief is now
stale.** Ozon and Wildberries revise seller-API endpoints on their own schedule and do not
consult us. A green suite in September proves the same thing it proved in April — that we are
self-consistent.

This is why `docs/LIVE-CHECKS.md` is a checklist to re-run on a schedule, not a one-time task.

## Per-layer acceptance criteria

**L1 — a unit test earns its place if** it covers request construction, response parsing, or an
error path that has a distinct user-visible message. It does not earn its place if it asserts
that a mock returns what the mock was told to return. Prefer one test per real branch over
coverage theatre; see `EmptySchemaError` in `docs/TROUBLESHOOTING-1C.md` for the shape of a test
worth writing — it exists because a live probe found a silent-zero bug.

**L2 — a connector passes live-read if** every read-only tool returns a well-formed result or a
documented error against a real tenant, and the result shape matches what the mock asserts. Any
divergence is an API-drift finding and updates the mock, not just the client.

**L3 — a connector passes live-write if** a mutation succeeds against a sandbox or disposable
tenant and is verified by a subsequent read. **Never against production.** See the safety rules
in `docs/LIVE-CHECKS.md`.

## Surface being tested

68 MCP tools across 8 connectors — **47 read-only, 21 mutating.**

| Connector | Tools | Mutating | L1 tests | Sandbox available |
|---|---|---|---|---|
| 1C (`onec_*`) | 8 | 3 | 14 | no — needs a disposable infobase |
| Ozon (`ozon_*`) | 11 | 2 | 15 | **yes** — `yzel config add-ozon --sandbox` |
| Wildberries (`wb_*`) | 10 | 1 | 12 | **yes** — `yzel config add-wildberries --sandbox` |
| Telegram (`tg_*`) | 12 | 8 | 13 | no — use a throwaway bot |
| iiko (`iiko_*`) | 9 | 1 | 15 | no |
| AmoCRM (`amocrm_*`) | 6 | 2 | 20 | no |
| Bitrix24 (`bitrix24_*`) | 6 | 2 | 18 | no |
| МойСклад (`moysklad_*`) | 6 | 2 | 19 | no |
| core: vault + discovery | — | — | 12 | — |

## Known gaps, ranked

1. ~~**No CI.**~~ Fixed 2026-09-05 — `.github/workflows/ci.yml` runs the suite on Python
   3.11/3.12/3.13 and gates `ruff check`, `ruff format --check` and `mypy --strict`, all of
   which now pass.
2. **No repeatable live checks.** The 1C transport and `$metadata` parsing were confirmed against
   a live 1C:Fresh endpoint once. There is no record of when, and no way to notice when it stops
   being true. `docs/LIVE-CHECKS.md` addresses this.
3. **No coverage measurement.** 4,384 test lines against 5,272 source lines is a healthy ratio,
   but ratio is not coverage. Nothing currently reports which branches are exercised.
4. **`src/yzel/cli.py` is untested.** It is the only entry point a user touches before anything
   else works — every credential lands through `yzel config add-*`.
5. **Mock drift is undetected by construction.** Nothing compares a mock's fixtures against a
   live response, so a mock can be confidently wrong indefinitely.

## What this document does not cover

Performance, concurrency, and rate-limit behaviour. No connector has been tested under load, and
none of the clients implement backoff. That is a real gap and is deliberately out of scope here.
