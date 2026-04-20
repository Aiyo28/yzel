"""Encrypted credential vault — stores per-service auth securely.

Pattern: Airbyte's connection_id abstraction. Credentials stored AES-256
encrypted in SQLite. Encryption key from environment variable YZEL_KEY
or auto-generated on first run.
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from yzel.core.types import (
    AmoCRMCredential,
    Bitrix24Credential,
    IikoCredential,
    MoyskladCredential,
    OneCCredential,
    OzonCredential,
    ServiceCredential,
    ServiceType,
    TelegramCredential,
    WildberriesCredential,
)

_CREDENTIAL_CLASSES: dict[ServiceType, type[ServiceCredential]] = {
    ServiceType.ONEC: OneCCredential,
    ServiceType.BITRIX24: Bitrix24Credential,
    ServiceType.AMOCRM: AmoCRMCredential,
    ServiceType.MOYSKLAD: MoyskladCredential,
    ServiceType.WILDBERRIES: WildberriesCredential,
    ServiceType.OZON: OzonCredential,
    ServiceType.TELEGRAM: TelegramCredential,
    ServiceType.IIKO: IikoCredential,
}

_DEFAULT_DB_PATH = Path.home() / ".yzel" / "store.db"
_KEY_ENV = "YZEL_KEY"


class CredentialVault:
    """Encrypted credential storage backed by SQLite."""

    def __init__(self, db_path: Path | None = None, key: bytes | None = None) -> None:
        self._db_path = db_path or _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._key = key or self._load_or_generate_key()
        self._fernet = Fernet(self._key)
        self._init_db()

    def _load_or_generate_key(self) -> bytes:
        env_key = os.environ.get(_KEY_ENV)
        if env_key:
            return base64.urlsafe_b64decode(env_key)

        key_path = self._db_path.parent / "vault.key"
        if key_path.exists():
            return key_path.read_bytes()

        key = Fernet.generate_key()
        key_path.write_bytes(key)
        key_path.chmod(0o600)
        return key

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS connections (
                    id TEXT PRIMARY KEY,
                    service TEXT NOT NULL,
                    name TEXT NOT NULL,
                    encrypted_data BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def _encrypt(self, data: dict[str, Any]) -> bytes:
        return self._fernet.encrypt(json.dumps(data).encode())

    def _decrypt(self, encrypted: bytes) -> dict[str, Any]:
        return json.loads(self._fernet.decrypt(encrypted))

    def store(self, connection_id: str, credential: ServiceCredential) -> None:
        """Store or update a connection credential."""
        data = credential.model_dump()
        encrypted = self._encrypt(data)

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO connections (id, service, name, encrypted_data, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(id) DO UPDATE SET
                     encrypted_data = excluded.encrypted_data,
                     updated_at = CURRENT_TIMESTAMP""",
                (connection_id, credential.service.value, credential.name, encrypted),
            )

    def get(self, connection_id: str) -> ServiceCredential | None:
        """Retrieve and decrypt a connection credential."""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT service, encrypted_data FROM connections WHERE id = ?",
                (connection_id,),
            ).fetchone()

        if row is None:
            return None

        service = ServiceType(row[0])
        data = self._decrypt(row[1])
        cls = _CREDENTIAL_CLASSES[service]
        return cls(**data)

    def list_connections(self) -> list[dict[str, str]]:
        """List all stored connections (without decrypting secrets)."""
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT id, service, name, created_at, updated_at FROM connections"
            ).fetchall()

        return [
            {"id": r[0], "service": r[1], "name": r[2], "created_at": r[3], "updated_at": r[4]}
            for r in rows
        ]

    def delete(self, connection_id: str) -> bool:
        """Delete a connection. Returns True if it existed."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM connections WHERE id = ?", (connection_id,))
            return cursor.rowcount > 0
