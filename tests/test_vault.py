"""Tests for the encrypted credential vault."""

from __future__ import annotations

from yzel.core.types import Bitrix24Credential, OneCCredential, ServiceType
from yzel.core.vault import CredentialVault


# Test fixtures use obviously fake values — not real secrets
_TEST_1C_HOST = "https://test.example.com/base/odata/standard.odata"
_TEST_WEBHOOK = "https://test.bitrix24.ru/rest/1/testtoken/"


def test_store_and_retrieve_1c(temp_vault: CredentialVault) -> None:
    """Store a 1C credential and retrieve it."""
    cred = OneCCredential(
        name="Тестовая база",
        host=_TEST_1C_HOST,
        username="test_user",
        password="test_value",  # noqa: S106 — test-only placeholder
        is_fresh=False,
    )
    temp_vault.store("test-1c", cred)

    retrieved = temp_vault.get("test-1c")
    assert retrieved is not None
    assert isinstance(retrieved, OneCCredential)
    assert retrieved.name == "Тестовая база"
    assert retrieved.host == _TEST_1C_HOST
    assert retrieved.username == "test_user"
    assert retrieved.is_fresh is False


def test_store_and_retrieve_bitrix(temp_vault: CredentialVault) -> None:
    """Store a Bitrix24 credential and retrieve it."""
    cred = Bitrix24Credential(
        name="Рабочий портал",
        webhook_url=_TEST_WEBHOOK,
    )
    temp_vault.store("test-bitrix", cred)

    retrieved = temp_vault.get("test-bitrix")
    assert retrieved is not None
    assert isinstance(retrieved, Bitrix24Credential)
    assert retrieved.webhook_url == _TEST_WEBHOOK


def test_list_connections(temp_vault: CredentialVault) -> None:
    """List all stored connections."""
    cred1 = OneCCredential(
        name="База 1", host="https://a.example.com",
        username="u", password="test_value",  # noqa: S106
    )
    cred2 = Bitrix24Credential(name="Портал", webhook_url=_TEST_WEBHOOK)

    temp_vault.store("conn-1", cred1)
    temp_vault.store("conn-2", cred2)

    connections = temp_vault.list_connections()
    assert len(connections) == 2
    assert connections[0]["service"] == "1c"
    assert connections[1]["service"] == "bitrix24"


def test_delete_connection(temp_vault: CredentialVault) -> None:
    """Delete a connection."""
    cred = OneCCredential(
        name="Удалить", host="https://x.example.com",
        username="u", password="test_value",  # noqa: S106
    )
    temp_vault.store("to-delete", cred)

    assert temp_vault.delete("to-delete") is True
    assert temp_vault.get("to-delete") is None
    assert temp_vault.delete("to-delete") is False


def test_get_nonexistent(temp_vault: CredentialVault) -> None:
    """Getting a nonexistent connection returns None."""
    assert temp_vault.get("does-not-exist") is None


def test_update_credential(temp_vault: CredentialVault) -> None:
    """Updating a credential overwrites the previous value."""
    cred1 = OneCCredential(
        name="v1", host="https://old.example.com",
        username="u", password="test_value_old",  # noqa: S106
    )
    cred2 = OneCCredential(
        name="v2", host="https://new.example.com",
        username="u", password="test_value_new",  # noqa: S106
    )

    temp_vault.store("update-me", cred1)
    temp_vault.store("update-me", cred2)

    retrieved = temp_vault.get("update-me")
    assert retrieved is not None
    assert isinstance(retrieved, OneCCredential)
    assert retrieved.name == "v2"
    assert retrieved.host == "https://new.example.com"
