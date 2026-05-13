"""Tests for the external ConnectorManager and credential store."""

import base64

import pytest

from dbgpt.component import SystemApp
from dbgpt.agent.resource.connector.catalog import (
    AuthConfig,
    AuthField,
    ConnectorCatalogEntry,
    McpServerConfig,
)
from dbgpt.agent.resource.connector.credential import CredentialStore
from dbgpt.agent.resource.connector.manager import ConnectorManager, ConnectorStatus
from dbgpt.agent.resource.tool.pack import MCPToolPack


def test_list_active_returns_prompt_ready_connector_summaries():
    manager = ConnectorManager()
    connector_id = "conn-1"
    pack = MCPToolPack(mcp_servers="http://example.com/sse", name="GitHub Ops")
    pack.add_command(
        command_label="Create a GitHub issue",
        command_name="create_issue",
        args={},
        function=lambda: None,
    )
    pack.add_command(
        command_label="List GitHub issues",
        command_name="list_issues",
        args={},
        function=lambda: None,
    )

    manager._connector_types[connector_id] = "github"
    manager._statuses[connector_id] = ConnectorStatus.active
    manager._active_packs[connector_id] = pack
    manager._catalog._entries["github"] = ConnectorCatalogEntry(
        type="github",
        display_name="GitHub",
        description="GitHub workspace connector",
        icon="github",
        category="productivity",
        mcp_server=McpServerConfig(
            server_uri="http://example.com/sse",
            transport="sse",
        ),
        auth=AuthConfig(
            type="token",
            fields=[
                AuthField(
                    name="token",
                    label="Token",
                    type="password",
                    required=True,
                )
            ],
            header_mapping={"token": "Authorization"},
        ),
    )

    summaries = manager.list_active()

    assert summaries == [
        {
            "connector_id": "conn-1",
            "name": "GitHub Ops",
            "connector_type": "github",
            "description": "GitHub workspace connector",
            "status": "active",
            "tools": [
                {
                    "name": "create_issue",
                    "description": "Create a GitHub issue",
                },
                {
                    "name": "list_issues",
                    "description": "List GitHub issues",
                },
            ],
        }
    ]


def test_credential_store_uses_stable_encrypt_key_from_env(monkeypatch: pytest.MonkeyPatch):
    encrypt_key = base64.urlsafe_b64encode(b"connector-master-key-32-bytes!!").decode()
    monkeypatch.setenv("ENCRYPT_KEY", encrypt_key)

    store_a = CredentialStore()
    encrypted = store_a.encrypt({"token": "secret-value"}, salt="salt-1")

    store_b = CredentialStore()

    assert store_b.decrypt(encrypted, salt="salt-1") == {"token": "secret-value"}


def test_credential_store_prefers_system_app_encrypt_key(monkeypatch: pytest.MonkeyPatch):
    env_key = base64.urlsafe_b64encode(b"env-master-key-32-bytes-value!!!").decode()
    app_key = base64.urlsafe_b64encode(b"app-master-key-32-bytes-value!!!").decode()
    monkeypatch.setenv("ENCRYPT_KEY", env_key)

    system_app = SystemApp()
    system_app.config.set("dbgpt.app.global.encrypt_key", app_key)

    store_a = CredentialStore(system_app=system_app)
    encrypted = store_a.encrypt({"token": "secret-value"}, salt="salt-2")

    monkeypatch.setenv("ENCRYPT_KEY", base64.urlsafe_b64encode(b"other-env-key-32-bytes-value!!!").decode())
    store_b = CredentialStore(system_app=system_app)

    assert store_b.decrypt(encrypted, salt="salt-2") == {"token": "secret-value"}
