"""Shared test fixtures for Yzel tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from yzel.core.vault import CredentialVault


@pytest.fixture
def temp_vault(tmp_path: Path) -> CredentialVault:
    """Create a temporary credential vault for testing."""
    db_path = tmp_path / "test_store.db"
    return CredentialVault(db_path=db_path)
