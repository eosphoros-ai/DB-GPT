"""Credential store — encrypts and decrypts connector credentials."""

import json
import logging
import os
import secrets
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = frozenset({"password", "token", "secret", "api_key", "github_token"})


class CredentialStore:
    def __init__(self, system_app: Optional[Any] = None) -> None:
        self._system_app = system_app
        self._master_key = self._resolve_master_key()
        self._fernet = self._build_fernet(self._master_key)

    def _resolve_master_key(self) -> bytes:
        config_key: Optional[str] = None
        if self._system_app is not None and getattr(self._system_app, "config", None):
            config_key = self._system_app.config.get("dbgpt.app.global.encrypt_key")
        raw_key = config_key or os.environ.get("ENCRYPT_KEY")
        if raw_key:
            return raw_key.encode()
        logger.warning(
            "CredentialStore falling back to ephemeral master key because no "
            "dbgpt.app.global.encrypt_key or ENCRYPT_KEY was provided. "
            "Encrypted connector credentials will not survive process restarts."
        )
        return secrets.token_bytes(32)

    def _build_fernet(self, key: bytes):
        from dbgpt.core.interface.variables import FernetEncryption

        return FernetEncryption(key=key)

    def generate_salt(self) -> str:
        return secrets.token_hex(32)

    def encrypt(self, credentials: Dict[str, str], salt: str) -> str:
        plaintext = json.dumps(credentials, ensure_ascii=False)
        return self._fernet.encrypt(plaintext, salt)

    def decrypt(self, encrypted: str, salt: str) -> Dict[str, str]:
        try:
            plaintext = self._fernet.decrypt(encrypted, salt)
        except Exception as exc:
            raise ValueError(f"Credential decryption failed: {exc}") from exc
        try:
            result = json.loads(plaintext)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Decrypted payload is not valid JSON: {exc}") from exc
        if not isinstance(result, dict):
            raise ValueError("Decrypted credentials must be a JSON object")
        return result
