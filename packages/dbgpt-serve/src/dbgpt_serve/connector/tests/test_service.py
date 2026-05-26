import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from dbgpt.agent.resource.connector.credential import CredentialStore
from dbgpt.component import SystemApp
from dbgpt.storage.metadata import db
from dbgpt_serve.core.tests.conftest import config, system_app  # noqa: F401

from ..config import ServeConfig
from ..models.models import ConnectorInstanceEntity
from ..service.service import (
    ConnectorCreateRequest,
    ConnectorService,
    ConnectorUpdateRequest,
)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield


@pytest.fixture
def service(system_app: SystemApp):
    system_app.config.set("dbgpt.app.global.encrypt_key", "test_encrypt_key")
    instance = ConnectorService(system_app, ServeConfig())
    instance.init_app(system_app)
    return instance


def test_create_connector_encrypts_credentials_before_persisting(
    service: ConnectorService,
):
    credentials = {"token": "secret-token"}
    response = service.create_connector(
        ConnectorCreateRequest(
            connector_type="github",
            display_name="GitHub Ops",
            credentials=credentials,
        )
    )

    with db.session() as session:
        entity = (
            session.query(ConnectorInstanceEntity)
            .filter(ConnectorInstanceEntity.connector_id == response.connector_id)
            .first()
        )
        assert entity is not None
        assert entity.encrypted_credentials != json.dumps(credentials)
        assert entity.encryption_salt
        store = CredentialStore(system_app=service.system_app)
        assert store.decrypt(entity.encrypted_credentials, entity.encryption_salt) == {
            "token": "secret-token"
        }


def test_update_connector_re_encrypts_credentials(service: ConnectorService):
    response = service.create_connector(
        ConnectorCreateRequest(
            connector_type="github",
            display_name="GitHub Ops",
            credentials={"token": "secret-token"},
        )
    )

    with db.session() as session:
        original_entity = (
            session.query(ConnectorInstanceEntity)
            .filter(ConnectorInstanceEntity.connector_id == response.connector_id)
            .first()
        )
        assert original_entity is not None
        original_ciphertext = original_entity.encrypted_credentials
        original_salt = original_entity.encryption_salt

    service.update_connector(
        response.connector_id,
        ConnectorUpdateRequest(credentials={"token": "new-secret-token"}),
    )

    with db.session() as session:
        entity = (
            session.query(ConnectorInstanceEntity)
            .filter(ConnectorInstanceEntity.connector_id == response.connector_id)
            .first()
        )
        assert entity is not None
        assert entity.encrypted_credentials != json.dumps({"token": "new-secret-token"})
        assert entity.encrypted_credentials != original_ciphertext
        assert entity.encryption_salt
        assert entity.encryption_salt != original_salt
        store = CredentialStore(system_app=service.system_app)
        assert store.decrypt(entity.encrypted_credentials, entity.encryption_salt) == {
            "token": "new-secret-token"
        }


def test_create_connector_activates_external_connector_manager(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    fake_manager = MagicMock()
    fake_manager.create_connector = AsyncMock(return_value="runtime-connector-id")

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    service.create_connector(
        ConnectorCreateRequest(
            connector_type="github",
            display_name="GitHub Ops",
            credentials={"token": "secret-token"},
        )
    )

    fake_manager.create_connector.assert_awaited_once()
    call_kwargs = fake_manager.create_connector.call_args.kwargs
    assert call_kwargs["connector_type"] == "github"
    assert call_kwargs["credentials"] == {"token": "secret-token"}
    assert call_kwargs["name"] == "GitHub Ops"
    assert call_kwargs["extra_config"] is None
    assert isinstance(call_kwargs["connector_id"], str)
    assert call_kwargs["connector_id"]


def test_after_start_rehydrates_active_connectors_with_decrypted_credentials(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    credentials = {"token": "secret-token"}
    store = CredentialStore(system_app=service.system_app)
    encryption_salt = store.generate_salt()
    encrypted_credentials = store.encrypt(credentials, encryption_salt)

    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="connector-1",
                connector_type="github",
                display_name="GitHub Ops",
                encrypted_credentials=encrypted_credentials,
                encryption_salt=encryption_salt,
                status="active",
            )
        )

    fake_manager = MagicMock()
    fake_manager.create_connector = AsyncMock()

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    service.after_start()

    fake_manager.create_connector.assert_awaited_once_with(
        connector_type="github",
        credentials=credentials,
        name="GitHub Ops",
        extra_config=None,
        connector_id="connector-1",
    )
