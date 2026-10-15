# Launch connectors through console scripts and `uvx`, not `uv run python -m`

`uv run` resolves against the current working directory's project, and MCP clients spawn servers with an arbitrary cwd, so a `uv run python -m yzel.connectors.<name>.server` config only starts inside a yzel checkout and otherwise fails silently at launch. We ship nine console scripts (`yzel` plus one `yzel-<connector>` each) that target a synchronous `run()` in each connector's `server.py` (distinct from the async `main()`), and document launching them with `uvx` (see the README for the exact form).

Consequence: CI runs inside a checkout and cannot prove cwd-independence, so the real check is a clean-machine `uvx` launch of a connector after each publish.
