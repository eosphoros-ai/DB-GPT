"""Tests for the external ConnectorManager and credential store."""

import base64

import pytest

from dbgpt.agent.resource.connector.catalog import (
    AuthConfig,
    AuthField,
    ConnectorCatalogEntry,
    McpServerConfig,
)
from dbgpt.agent.resource.connector.credential import CredentialStore
from dbgpt.agent.resource.connector.manager import ConnectorManager, ConnectorStatus
from dbgpt.agent.resource.tool.pack import MCPToolPack
from dbgpt.component import SystemApp


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


def test_credential_store_uses_stable_encrypt_key_from_env(
    monkeypatch: pytest.MonkeyPatch,
):
    encrypt_key = base64.urlsafe_b64encode(b"connector-master-key-32-bytes!!").decode()
    monkeypatch.setenv("ENCRYPT_KEY", encrypt_key)

    store_a = CredentialStore()
    encrypted = store_a.encrypt({"token": "secret-value"}, salt="salt-1")

    store_b = CredentialStore()

    assert store_b.decrypt(encrypted, salt="salt-1") == {"token": "secret-value"}


def test_credential_store_prefers_system_app_encrypt_key(
    monkeypatch: pytest.MonkeyPatch,
):
    env_key = base64.urlsafe_b64encode(b"env-master-key-32-bytes-value!!!").decode()
    app_key = base64.urlsafe_b64encode(b"app-master-key-32-bytes-value!!!").decode()
    monkeypatch.setenv("ENCRYPT_KEY", env_key)

    system_app = SystemApp()
    system_app.config.set("dbgpt.app.global.encrypt_key", app_key)

    store_a = CredentialStore(system_app=system_app)
    encrypted = store_a.encrypt({"token": "secret-value"}, salt="salt-2")

    monkeypatch.setenv(
        "ENCRYPT_KEY",
        base64.urlsafe_b64encode(b"other-env-key-32-bytes-value!!!").decode(),
    )
    store_b = CredentialStore(system_app=system_app)

    assert store_b.decrypt(encrypted, salt="salt-2") == {"token": "secret-value"}


def test_get_catalog_returns_catalog_instance():
    """get_catalog() should expose the internal ConnectorCatalog."""
    manager = ConnectorManager()

    catalog = manager.get_catalog()

    assert catalog is manager._catalog
    assert catalog.list() == []


def test_get_catalog_after_load_returns_entries(tmp_path):
    """get_catalog() should reflect entries loaded via load_catalog()."""
    import json

    catalog_data = {
        "connectors": [
            {
                "type": "test_conn",
                "display_name": "Test Connector",
                "description": "A test connector",
                "icon": "test",
                "category": "testing",
                "mcp_server": {
                    "server_uri": "http://localhost:9999/sse",
                    "transport": "sse",
                },
                "auth": {
                    "type": "token",
                    "fields": [
                        {
                            "name": "token",
                            "label": "Token",
                            "type": "password",
                            "required": True,
                        }
                    ],
                    "header_mapping": {"token": "Authorization"},
                },
            }
        ]
    }

    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog_data))

    manager = ConnectorManager()
    manager.load_catalog(str(catalog_path))
    catalog = manager.get_catalog()

    assert len(catalog.list()) == 1
    assert catalog.list()[0].type == "test_conn"
    assert catalog.list()[0].display_name == "Test Connector"


# ---------------------------------------------------------------------------
# Task B – tool auto-prefix tests
# ---------------------------------------------------------------------------


def test_compute_tool_prefix_builtin_single():
    """Built-in type with no prior instances => prefix is just the type."""
    manager = ConnectorManager()
    prefix = manager.compute_tool_prefix("yuque", "My Yuque", "abc123")
    assert prefix == "yuque"


def test_compute_tool_prefix_builtin_multiple():
    """Built-in type with an existing instance => prefix includes slug of display_name."""
    manager = ConnectorManager()
    manager._connector_types["other-id"] = "yuque"
    prefix = manager.compute_tool_prefix("yuque", "Team Yuque", "new-id")
    assert prefix == "yuque-team-yuque"


def test_compute_tool_prefix_custom():
    """Custom connector type => prefix is slug of display_name only."""
    manager = ConnectorManager()
    prefix = manager.compute_tool_prefix("custom_mcp", "My Internal KB", "xyz789")
    assert prefix == "my-internal-kb"


def test_compute_tool_prefix_slug_fallback():
    """When slug is empty, fall back to first 6 chars of connector_id."""
    manager = ConnectorManager()
    prefix = manager.compute_tool_prefix("custom_mcp", "!!!", "abc1234567890")
    assert prefix == "abc123"


def test_apply_tool_prefix_renames_and_updates_map():
    """_apply_tool_prefix renames tools, updates tool_server_map, and annotates descriptions."""
    manager = ConnectorManager()

    pack = MCPToolPack(mcp_servers="http://example.com/sse", name="Yuque")
    pack.add_command(
        command_label="Create a doc",
        command_name="create_doc",
        args={},
        function=lambda: None,
    )
    pack.add_command(
        command_label="Delete a doc",
        command_name="delete_doc",
        args={},
        function=lambda: None,
    )
    pack.tool_server_map = {
        "create_doc": "http://example.com/sse",
        "delete_doc": "http://example.com/sse",
    }

    manager._apply_tool_prefix(pack, "yuque", "Yuque")

    tools = pack.sub_resources
    assert tools[0].name == "yuque_create_doc"
    assert tools[1].name == "yuque_delete_doc"
    assert pack.tool_server_map == {
        "yuque_create_doc": "http://example.com/sse",
        "yuque_delete_doc": "http://example.com/sse",
    }
    assert tools[0].description.endswith("(via Yuque)")
    assert tools[1].description.endswith("(via Yuque)")


def test_apply_tool_prefix_idempotent():
    """Calling _apply_tool_prefix twice with the same prefix doesn't double-prefix."""
    manager = ConnectorManager()

    pack = MCPToolPack(mcp_servers="http://example.com/sse", name="Yuque")
    pack.add_command(
        command_label="Create a doc",
        command_name="create_doc",
        args={},
        function=lambda: None,
    )
    pack.tool_server_map = {
        "create_doc": "http://example.com/sse",
    }

    manager._apply_tool_prefix(pack, "yuque", "Yuque")
    manager._apply_tool_prefix(pack, "yuque", "Yuque")

    tools = pack.sub_resources
    assert tools[0].name == "yuque_create_doc"
    assert pack.tool_server_map == {
        "yuque_create_doc": "http://example.com/sse",
    }
    assert tools[0].description.count("(via Yuque)") == 1


def test_remove_connector_clears_connector_types():
    """After remove_connector, _connector_types should not retain the entry.

    Otherwise compute_tool_prefix would treat re-created connectors as multi-instance.
    """
    manager = ConnectorManager()
    cid = "ghost-id"
    manager._connector_types[cid] = "yuque"
    manager._active_packs[cid] = MCPToolPack(
        mcp_servers="http://example.com/sse", name="Ghost"
    )
    manager._statuses[cid] = ConnectorStatus.active

    import asyncio

    asyncio.run(manager.remove_connector(cid))

    assert cid not in manager._connector_types
    assert not manager._has_multiple_instances_of_type("yuque")
