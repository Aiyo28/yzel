"""Wildberries Seller API MCP connector — multi-host REST with JWT auth."""

from yzel.connectors.wildberries.client import WildberriesClient, WildberriesError

__all__ = ["WildberriesClient", "WildberriesError"]
