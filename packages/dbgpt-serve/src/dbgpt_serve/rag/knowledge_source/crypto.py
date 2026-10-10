"""AES-256-GCM credential encryption for knowledge source bindings.

Key resolution order (first match wins):
1. env ``DB_GPT_KS_ENCRYPT_KEY``
2. toml ``[rag.knowledge_source] encrypt_key``
3. **auto-provisioned**: a random key generated once and stored in the
   metadata DB (``knowledge_source_keystore``) — the zero-config product
   default.

Trade-off of option 3 (logged loudly on first generation): credentials are
encrypted at rest against backups/logs/casual reading, but a full DB dump
contains both ciphertext and key — pin an explicit key (options 1/2) in
production environments where DBA-level confidentiality matters.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

_cached_auto_key: Optional[str] = None


class KeyNotConfiguredError(Exception):
    pass


def _load_key(system_app=None) -> bytes:
    raw = os.environ.get("DB_GPT_KS_ENCRYPT_KEY")
    if not raw and system_app is not None:
        try:
            rag_cfg = system_app.config.configs.get("app_config").rag
            raw = getattr(
                getattr(rag_cfg, "knowledge_source", None), "encrypt_key", None
            )
        except Exception:  # noqa: BLE001 - config shape differences are non-fatal
            raw = None
    if not raw:
        raw = _auto_key(system_app)
    return hashlib.sha256(raw.encode("utf-8")).digest()  # 32 bytes for AES-256


def _auto_key(system_app=None) -> str:
    """Zero-config fallback: get-or-create the keystore key (cached)."""
    global _cached_auto_key
    if _cached_auto_key:
        return _cached_auto_key
    from dbgpt_serve.rag.knowledge_source.models import KnowledgeSourceKeyDao

    raw = KnowledgeSourceKeyDao().get_or_create()
    if not raw:
        raise KeyNotConfiguredError(
            "keystore row empty; set DB_GPT_KS_ENCRYPT_KEY or "
            "[rag.knowledge_source] encrypt_key"
        )
    logger.warning(
        "knowledge-source encrypt key auto-provisioned in the metadata DB "
        "(zero-config mode). Credentials are encrypted at rest against "
        "backups/logs, but a full DB dump contains both ciphertext and "
        "key. Set DB_GPT_KS_ENCRYPT_KEY or [rag.knowledge_source] "
        "encrypt_key for stronger confidentiality — note that existing "
        "bindings must be re-created after switching keys."
    )
    _cached_auto_key = raw
    return raw


def encrypt_config(plain: dict, system_app=None) -> str:
    import json
    import secrets

    key = _load_key(system_app)
    nonce = secrets.token_bytes(12)
    data = json.dumps(plain, ensure_ascii=False).encode("utf-8")
    ct = AESGCM(key).encrypt(nonce, data, None)
    return base64.b64encode(nonce + ct).decode("utf-8")


def decrypt_config(token: str, system_app=None) -> dict:
    import json

    key = _load_key(system_app)
    raw = base64.b64decode(token)
    nonce, ct = raw[:12], raw[12:]
    data = AESGCM(key).decrypt(nonce, ct, None)
    return json.loads(data)
