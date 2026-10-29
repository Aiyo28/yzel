"""Entry point for the Claude Desktop extension (.mcpb, uv runtime).

The host runs `uv run --directory <bundle> server.py`, which installs the bundled `yzel`
project from its pyproject.toml and then starts the 1C stdio server. Credentials arrive as
YZEL_1C_* env vars from the extension's settings form.
"""

from yzel.connectors.onec.server import run

run()
