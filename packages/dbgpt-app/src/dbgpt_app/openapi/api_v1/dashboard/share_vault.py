"""Recover public grants for their authorized publisher without storing plaintext."""

import logging
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import Column, String

from dbgpt.storage.metadata import Model

logger = logging.getLogger(__name__)


class DashboardShareSecretEntity(Model):
    __tablename__ = "dbgpt_dashboard_share_secret"
    token_hash = Column(String(64), primary_key=True)
    ciphertext = Column(String(512), nullable=False)


def share_cipher():
    configured = os.getenv("DBGPT_SHARE_ENCRYPTION_KEY")
    if configured:
        return Fernet(configured.encode())
    path = Path(
        os.getenv("DBGPT_SHARE_KEY_FILE", "pilot/meta_data/dashboard-share.key")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
        try:
            with os.fdopen(
                os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
            ) as stream:
                stream.write(Fernet.generate_key())
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
            except OSError as exc:
                raise RuntimeError(
                    "Cannot atomically create the dashboard share encryption key "
                    "on this filesystem. Check filesystem permissions and hard "
                    "link support, or explicitly configure "
                    "DBGPT_SHARE_ENCRYPTION_KEY."
                ) from exc
        finally:
            temporary.unlink(missing_ok=True)
    return Fernet(path.read_bytes().strip())


def public_origin():
    value = os.getenv("DBGPT_PUBLIC_DASHBOARD_ORIGIN", "").strip().rstrip("/")
    origin_file = os.getenv("DBGPT_PUBLIC_DASHBOARD_ORIGIN_FILE")
    if not value and origin_file and Path(origin_file).is_file():
        value = Path(origin_file).read_text(encoding="utf-8-sig").strip().rstrip("/")
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    return (
        value
        if parsed.scheme == "https"
        and parsed.netloc
        and not parsed.path
        and not parsed.username
        else ""
    )


def remember_share_token(dao, token):
    import hashlib

    digest = hashlib.sha256(token.encode()).hexdigest()
    with dao.session() as session:
        if (
            not session.query(DashboardShareSecretEntity)
            .filter_by(token_hash=digest)
            .first()
        ):
            session.add(
                DashboardShareSecretEntity(
                    token_hash=digest,
                    ciphertext=share_cipher().encrypt(token.encode()).decode(),
                )
            )


def recover_share_token(dao, digest):
    with dao.session(commit=False) as session:
        row = (
            session.query(DashboardShareSecretEntity)
            .filter_by(token_hash=digest)
            .first()
        )
        if row:
            try:
                return share_cipher().decrypt(row.ciphertext.encode()).decode()
            except Exception as exc:
                logger.warning(
                    "Unable to recover a dashboard share link; check the "
                    "configured encryption key (%s).",
                    type(exc).__name__,
                )
                return None
    return None
