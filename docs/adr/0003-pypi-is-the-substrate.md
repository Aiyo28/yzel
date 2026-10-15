# PyPI is the distribution substrate; the MCP Registry entry and the Claude plugin sit on top of it

PyPI carries the code, MCP is the protocol, the MCP Registry is cross-client discovery, and the Claude Code plugin is a one-command installer for Claude Code only. The plugin's `.mcp.json` launches the PyPI package through `uvx`, so it depends on PyPI rather than replacing it. The Registry verifies ownership by finding the `mcp-name: io.github.Aiyo28/yzel` token in the PyPI package description, which is rendered from `README.md`, so a package must exist on PyPI before it can be registered, and the token must stay in the README.

Consequences: PyPI publish comes first, the plugin and the Registry entry come after it, and the README is shipped content that the Registry reads. Whether the Registry wants one entry per connector or one per package is unresolved; we publish one entry (`io.github.Aiyo28/yzel`) and learn from it before adding more.
