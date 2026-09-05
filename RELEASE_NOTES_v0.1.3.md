# v0.1.3 — Yzel is now one line to install

**Установка теперь в одну строку. Ничего клонировать не нужно.**
Install is now a one-liner — no clone, no working directory, nothing to set up first.

## The short version

```json
{ "command": "uvx", "args": ["--from", "yzel", "yzel-1c"] }
```

Drop that into your MCP client config and you're done. `uvx` fetches the package on
demand, so there's nothing to install beforehand and it doesn't care what directory
you're in.

Yzel is on **PyPI** and listed in the **MCP Registry**, so clients that browse the
registry can find it on their own.

## Each connector is its own command

One console script per system — connect only what you need:

| | | | |
|---|---|---|---|
| `yzel-1c` | `yzel-bitrix24` | `yzel-amocrm` | `yzel-moysklad` |
| `yzel-ozon` | `yzel-wildberries` | `yzel-telegram` | `yzel-iiko` |

Credentials still go in first — `yzel config add-1c`, `yzel config add-ozon`, and so
on. They stay encrypted on your machine in `~/.yzel/store.db` and are never sent
anywhere except the service you configured.

## ⚠️ If you installed 0.1.1 or 0.1.2, please upgrade

Both are broken and have been yanked:

- **0.1.1** didn't pin the MCP SDK, so a fresh install pulled `mcp` 2.x and every
  server crashed on startup.
- **0.1.2** worked, but each server reported the SDK's version number instead of its
  own, which made bug reports confusing.

`uvx --refresh --from yzel yzel-1c` picks up the fix. The `--refresh` matters — uvx
caches aggressively and will happily keep running the old copy.

## Also in this release

- 138 tests, plus lint and type checks, now run in CI on Python 3.11, 3.12 and 3.13.
- A CI job that installs the built package the way *you* would, with no lockfile —
  that's the check that would have caught 0.1.1 before it ever reached PyPI.
- `CONTRIBUTING.md`, `SECURITY.md`, issue templates, and Discussions are open.

If something breaks, please open an issue — especially if a service has changed its
API on us. Our tests run against mocks we wrote, so they genuinely cannot detect that
on their own. You can.
