import errno
import hashlib

import pytest
from cryptography.fernet import Fernet

from dbgpt_app.openapi.api_v1.dashboard import share_vault
from dbgpt_app.openapi.api_v1.dashboard.live_share import LiveShareService
from dbgpt_app.openapi.api_v1.dashboard.share_vault import (
    DashboardShareSecretEntity,
    recover_share_token,
    remember_share_token,
)
from dbgpt_app.openapi.api_v1.dashboard.tests.test_feedback import (
    real_service as _real_service_fixture,
)

real_service = _real_service_fixture


@pytest.mark.parametrize("error_number", [errno.ENOTSUP, errno.EACCES])
def test_key_creation_failure_explains_configuration_and_removes_temporary_file(
    tmp_path, monkeypatch, error_number
):
    key_file = tmp_path / "share.key"
    monkeypatch.delenv("DBGPT_SHARE_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("DBGPT_SHARE_KEY_FILE", str(key_file))

    def reject_hard_link(*args):
        raise OSError(error_number, "fixture hard-link failure")

    monkeypatch.setattr(share_vault.os, "link", reject_hard_link)
    with pytest.raises(RuntimeError, match="DBGPT_SHARE_ENCRYPTION_KEY") as caught:
        share_vault.share_cipher()
    assert isinstance(caught.value.__cause__, OSError)
    assert not key_file.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_concurrent_key_creator_keeps_the_winning_key(tmp_path, monkeypatch):
    key_file = tmp_path / "share.key"
    winning_key = Fernet.generate_key()
    monkeypatch.delenv("DBGPT_SHARE_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("DBGPT_SHARE_KEY_FILE", str(key_file))

    def competing_creator(source, destination):
        destination.write_bytes(winning_key)
        raise FileExistsError("Another process already installed its key")

    monkeypatch.setattr(share_vault.os, "link", competing_creator)
    cipher = share_vault.share_cipher()
    assert key_file.read_bytes() == winning_key
    assert Fernet(winning_key).decrypt(cipher.encrypt(b"test")) == b"test"
    assert not list(tmp_path.glob("*.tmp"))


def test_configured_key_does_not_require_filesystem_hard_links(tmp_path, monkeypatch):
    key_file = tmp_path / "share.key"
    configured = Fernet.generate_key()
    monkeypatch.setenv("DBGPT_SHARE_ENCRYPTION_KEY", configured.decode())
    monkeypatch.setenv("DBGPT_SHARE_KEY_FILE", str(key_file))

    def reject_hard_link(*args):
        raise AssertionError("Configured key must bypass filesystem initialization")

    monkeypatch.setattr(share_vault.os, "link", reject_hard_link)
    assert (
        Fernet(configured).decrypt(share_vault.share_cipher().encrypt(b"test"))
        == b"test"
    )
    assert not key_file.exists()


def test_share_vault_uses_migrated_schema_without_runtime_create(
    real_service, monkeypatch
):
    service, _, _ = real_service
    monkeypatch.setenv("DBGPT_SHARE_ENCRYPTION_KEY", Fernet.generate_key().decode())

    def reject_runtime_ddl(*args, **kwargs):
        raise AssertionError("Request handling must not attempt to create tables")

    monkeypatch.setattr(
        DashboardShareSecretEntity.__table__, "create", reject_runtime_ddl
    )
    LiveShareService(service)
    token = "test-only-recoverable-token"
    remember_share_token(service.dao, token)
    digest = hashlib.sha256(token.encode()).hexdigest()
    assert recover_share_token(service.dao, digest) == token


def test_rotated_and_revoked_live_tokens_remove_encrypted_copies(
    real_service, monkeypatch
):
    service, record, _ = real_service
    monkeypatch.setenv("DBGPT_SHARE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    service.publish_dashboard(record.id, 1, {}, "alice")
    live = LiveShareService(service)
    first = live.create(record.id, "alice")["share_path"].rsplit("/", 1)[1]
    second = live.create(record.id, "alice")["share_path"].rsplit("/", 1)[1]
    first_digest = hashlib.sha256(first.encode()).hexdigest()
    second_digest = hashlib.sha256(second.encode()).hexdigest()
    assert recover_share_token(service.dao, first_digest) is None
    assert recover_share_token(service.dao, second_digest) == second
    live.revoke(record.id, "alice")
    assert recover_share_token(service.dao, second_digest) is None


def test_key_mismatch_logs_diagnostic_without_token_or_ciphertext(
    real_service, monkeypatch, caplog
):
    service, _, _ = real_service
    monkeypatch.setenv("DBGPT_SHARE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    token = "private-fixture-do-not-log"
    remember_share_token(service.dao, token)
    digest = hashlib.sha256(token.encode()).hexdigest()
    with service.dao.session(commit=False) as session:
        ciphertext = (
            session.query(DashboardShareSecretEntity)
            .filter_by(token_hash=digest)
            .one()
            .ciphertext
        )
    monkeypatch.setenv("DBGPT_SHARE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert recover_share_token(service.dao, digest) is None
    assert "check the configured encryption key" in caplog.text
    assert (
        token not in caplog.text
        and ciphertext not in caplog.text
        and digest not in caplog.text
    )
