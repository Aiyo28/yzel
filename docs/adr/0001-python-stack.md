# Python 3.11+ on the official `mcp` SDK, httpx, pydantic, cryptography, click and uv

Yzel runs on Windows machines without WSL and has to be installable by people who only have Python. We chose Python 3.11+ (cross-platform, and the existing 1C MCP servers are Python) and the smallest standard set around it: the official `mcp` SDK, `httpx` (async, and its transports make in-process mocks clean), `pydantic` v2 (typed credentials instead of dict-wrangling), `cryptography` (AES-256-GCM for the credential vault at rest), `click` (hidden-input prompts for secrets), `uv` with PEP 621 packaging, and `pytest` + `pytest-asyncio`.

Consequence: anything needing Linux-only primitives is out. Swapping the HTTP client or the SDK later touches every connector, so treat these as fixed unless a connector cannot work without a change.
