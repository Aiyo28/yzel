"""Version strings must agree across every file that carries one.

This exists because they drifted twice inside a single afternoon: `__init__.py` said 0.1.0
while the package shipped 0.1.2, and `llms.txt` advertised 0.1.1 after three releases. Both
were invisible to every other gate. `pyproject.toml` is the single source of truth; everything
else is asserted against it.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def declared_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return str(tomllib.load(fh)["project"]["version"])


def test_importable_version_matches(declared_version: str) -> None:
    """`yzel --version` and every server's MCP handshake read this."""
    from yzel import __version__

    assert __version__ == declared_version


def test_server_json_matches(declared_version: str) -> None:
    """The MCP Registry publishes these two; a mismatch ships a lie to the registry."""
    doc = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert doc["version"] == declared_version
    assert doc["packages"][0]["version"] == declared_version
    assert doc["packages"][0]["identifier"] == "yzel"


def test_plugin_manifest_matches(declared_version: str) -> None:
    doc = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert doc["version"] == declared_version


def test_llms_txt_matches(declared_version: str) -> None:
    """llms.txt is what AI assistants read; a stale version there propagates outward."""
    text = (ROOT / "llms.txt").read_text(encoding="utf-8")
    found = re.search(r"Version (\d+\.\d+\.\d+), MIT\.", text)
    assert found, "llms.txt has no `Version X.Y.Z, MIT.` line to check"
    assert found.group(1) == declared_version


def test_mcp_is_upper_bounded() -> None:
    """mcp 2.x removed Server.list_tools; unbounded, 0.1.1 was dead on arrival for everyone."""
    with (ROOT / "pyproject.toml").open("rb") as fh:
        deps = tomllib.load(fh)["project"]["dependencies"]
    mcp = next((d for d in deps if d.replace(" ", "").startswith("mcp")), None)
    assert mcp is not None, "mcp dependency disappeared"
    assert "<2" in mcp.replace(" ", ""), (
        f"mcp must stay upper-bounded until the 2.x port lands; found {mcp!r}"
    )
