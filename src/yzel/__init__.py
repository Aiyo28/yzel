"""Yzel (Узел) — Unified MCP connectors for CIS business tools."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    # Single source of truth is pyproject.toml. Hardcoding it here drifted once:
    # this said 0.1.0 while the package shipped 0.1.2, so `yzel --version` lied.
    __version__ = _pkg_version("yzel")
except PackageNotFoundError:  # running from a source tree with no install
    __version__ = "0.0.0+unknown"
