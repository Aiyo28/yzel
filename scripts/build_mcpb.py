"""Build the Claude Desktop extension bundles into dist/.

Usage: uv run python scripts/build_mcpb.py
Needs Node (for `npx @anthropic-ai/mcpb`). Each bundle is the yzel project itself plus
extensions/<name>/ — the uv runtime installs it from pyproject.toml on the user's machine.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT_FILES = ["pyproject.toml", "uv.lock", "README.md", "LICENSE"]


def build(extension: Path) -> Path:
    version = json.loads((extension / "manifest.json").read_text(encoding="utf-8"))["version"]
    stage = ROOT / "dist" / "mcpb" / extension.name
    shutil.rmtree(stage, ignore_errors=True)
    shutil.copytree(extension, stage, ignore=shutil.ignore_patterns("*.svg"))
    for name in PROJECT_FILES:
        shutil.copy2(ROOT / name, stage / name)
    shutil.copytree(ROOT / "src", stage / "src", ignore=shutil.ignore_patterns("__pycache__"))

    out = ROOT / "dist" / f"yzel-{extension.name}-{version}.mcpb"
    npx = shutil.which("npx")
    if npx is None:
        raise SystemExit("npx not found — install Node to pack .mcpb bundles")
    mcpb = [npx, "-y", "@anthropic-ai/mcpb@2"]
    subprocess.run([*mcpb, "validate", str(stage / "manifest.json")], check=True)
    subprocess.run([*mcpb, "pack", str(stage), str(out)], check=True)
    return out


if __name__ == "__main__":
    for ext in sorted(p for p in (ROOT / "extensions").iterdir() if p.is_dir()):
        print(build(ext))
