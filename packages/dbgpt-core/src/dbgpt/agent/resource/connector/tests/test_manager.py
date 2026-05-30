"""Tests for the external ConnectorManager and credential store."""

import asyncio
import base64
import json

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
                    "args": {},
                },
                {
                    "name": "list_issues",
                    "description": "List GitHub issues",
                    "args": {},
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
    assert tools[0].name == "mcp__yuque__create_doc"
    assert tools[1].name == "mcp__yuque__delete_doc"
    assert pack.tool_server_map == {
        "mcp__yuque__create_doc": "http://example.com/sse",
        "mcp__yuque__delete_doc": "http://example.com/sse",
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
    assert tools[0].name == "mcp__yuque__create_doc"
    assert pack.tool_server_map == {
        "mcp__yuque__create_doc": "http://example.com/sse",
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

    asyncio.run(manager.remove_connector(cid))

    assert cid not in manager._connector_types
    assert not manager._has_multiple_instances_of_type("yuque")


# ---------------------------------------------------------------------------
# Task F – custom_mcp branch + connector_id preservation
# ---------------------------------------------------------------------------


def _patch_preload_resource(monkeypatch):
    """Make MCPToolPack.preload_resource a no-op for tests."""
    from dbgpt.agent.resource.tool import pack as pack_mod

    async def _noop(self):
        return None

    monkeypatch.setattr(pack_mod.MCPToolPack, "preload_resource", _noop)


def test_create_connector_custom_mcp_bearer(monkeypatch: pytest.MonkeyPatch):
    """custom_mcp + auth_type=bearer should auto-prefix the token with 'Bearer '."""
    _patch_preload_resource(monkeypatch)
    manager = ConnectorManager()

    cid = asyncio.run(
        manager.create_connector(
            connector_type="custom_mcp",
            credentials={"token": "abc"},
            extra_config={"server_uri": "http://x", "auth_type": "bearer"},
            name="My MCP",
        )
    )

    pack = manager._active_packs[cid]
    assert pack._default_headers == {"Authorization": "Bearer abc"}
    assert manager._connector_types[cid] == "custom_mcp"
    assert manager._statuses[cid] == ConnectorStatus.active


def test_create_connector_custom_mcp_token(monkeypatch: pytest.MonkeyPatch):
    """custom_mcp + auth_type=token should use the raw token with a custom header name."""
    _patch_preload_resource(monkeypatch)
    manager = ConnectorManager()

    cid = asyncio.run(
        manager.create_connector(
            connector_type="custom_mcp",
            credentials={"token": "secret-value"},
            extra_config={
                "server_uri": "http://x",
                "auth_type": "token",
                "header_name": "X-Custom",
            },
            name="My MCP",
        )
    )

    pack = manager._active_packs[cid]
    assert pack._default_headers == {"X-Custom": "secret-value"}


def test_create_connector_custom_mcp_missing_server_uri_raises():
    manager = ConnectorManager()

    with pytest.raises(ValueError, match="custom_mcp requires extra_config.server_uri"):
        asyncio.run(
            manager.create_connector(
                connector_type="custom_mcp",
                credentials={},
                extra_config={},
            )
        )


def test_create_connector_preserves_provided_connector_id(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_preload_resource(monkeypatch)
    manager = ConnectorManager()

    cid = asyncio.run(
        manager.create_connector(
            connector_type="custom_mcp",
            credentials={},
            extra_config={"server_uri": "http://x", "auth_type": "none"},
            connector_id="fixed-id",
        )
    )

    assert cid == "fixed-id"
    assert "fixed-id" in manager._active_packs


def test_create_connector_unknown_type_message_mentions_custom_mcp():
    manager = ConnectorManager()

    with pytest.raises(ValueError, match="custom_mcp"):
        asyncio.run(
            manager.create_connector(
                connector_type="whatever",
                credentials={},
            )
        )


# ---------------------------------------------------------------------------
# Task G – catalog downgraded to template metadata
# ---------------------------------------------------------------------------


def test_create_connector_builtin_missing_server_uri_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """Built-in catalog types now require extra_config.server_uri (catalog downgrade)."""

    _patch_preload_resource(monkeypatch)

    catalog_data = {
        "connectors": [
            {
                "type": "github",
                "display_name": "GitHub",
                "description": "GitHub Issues, PR",
                "icon": "github",
                "category": "project",
                "mcp_server": {"transport": "sse"},
                "auth": {
                    "type": "token",
                    "fields": [
                        {
                            "name": "github_token",
                            "label": "Token",
                            "type": "password",
                            "required": True,
                        }
                    ],
                    "header_mapping": {"github_token": "Authorization"},
                },
            }
        ]
    }
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog_data))

    manager = ConnectorManager()
    manager.load_catalog(str(catalog_path))

    with pytest.raises(ValueError, match="requires extra_config.server_uri"):
        asyncio.run(
            manager.create_connector(
                connector_type="github",
                credentials={"github_token": "ghp_xxx"},
                # deliberately omit extra_config
            )
        )


def test_create_connector_builtin_with_server_uri_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """Built-in catalog type with extra_config.server_uri should activate normally."""

    _patch_preload_resource(monkeypatch)

    catalog_data = {
        "connectors": [
            {
                "type": "github",
                "display_name": "GitHub",
                "description": "GitHub Issues, PR",
                "icon": "github",
                "category": "project",
                "mcp_server": {"transport": "sse"},
                "auth": {
                    "type": "token",
                    "fields": [
                        {
                            "name": "github_token",
                            "label": "Token",
                            "type": "password",
                            "required": True,
                        }
                    ],
                    "header_mapping": {"github_token": "Authorization"},
                },
            }
        ]
    }
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog_data))

    manager = ConnectorManager()
    manager.load_catalog(str(catalog_path))

    cid = asyncio.run(
        manager.create_connector(
            connector_type="github",
            credentials={"github_token": "ghp_xxx"},
            extra_config={"server_uri": "http://example.com/sse"},
        )
    )

    assert manager._statuses[cid] == ConnectorStatus.active
    pack = manager._active_packs[cid]
    assert pack._mcp_servers == "http://example.com/sse"
    assert pack._default_headers == {"Authorization": "ghp_xxx"}


def test_create_connector_builtin_empty_server_uri_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """extra_config={'server_uri': ''} should be rejected the same as missing."""

    _patch_preload_resource(monkeypatch)

    catalog_data = {
        "connectors": [
            {
                "type": "github",
                "display_name": "GitHub",
                "description": "GitHub Issues, PR",
                "icon": "github",
                "category": "project",
                "mcp_server": {"transport": "sse"},
                "auth": {
                    "type": "token",
                    "fields": [
                        {
                            "name": "github_token",
                            "label": "Token",
                            "type": "password",
                            "required": True,
                        }
                    ],
                    "header_mapping": {"github_token": "Authorization"},
                },
            }
        ]
    }
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog_data))

    manager = ConnectorManager()
    manager.load_catalog(str(catalog_path))

    with pytest.raises(ValueError, match="requires extra_config.server_uri"):
        asyncio.run(
            manager.create_connector(
                connector_type="github",
                credentials={"github_token": "ghp_xxx"},
                extra_config={"server_uri": ""},
            )
        )


# ---------------------------------------------------------------------------
# Phase 1.5 — tool naming format tests
# ---------------------------------------------------------------------------


def test_tool_naming_uses_mcp_double_underscore_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """Tool names must follow mcp__<prefix>__<original_name> format."""
    _patch_preload_resource(monkeypatch)

    catalog_data = {
        "connectors": [
            {
                "type": "github",
                "display_name": "GitHub",
                "description": "GitHub Issues, PR",
                "icon": "github",
                "category": "project",
                "mcp_server": {"transport": "sse"},
                "auth": {
                    "type": "token",
                    "fields": [
                        {
                            "name": "github_token",
                            "label": "Token",
                            "type": "password",
                            "required": True,
                        }
                    ],
                    "header_mapping": {"github_token": "Authorization"},
                },
            }
        ]
    }
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps(catalog_data))

    manager = ConnectorManager()
    manager.load_catalog(str(catalog_path))

    cid = asyncio.run(
        manager.create_connector(
            connector_type="github",
            credentials={"github_token": "ghp_xxx"},
            extra_config={"server_uri": "http://example.com/sse"},
        )
    )

    pack = manager.get_connector_tools(cid)
    from dbgpt.agent.resource.tool.base import BaseTool

    for tool in pack.sub_resources:
        if isinstance(tool, BaseTool):
            parts = tool.name.split("__")
            assert len(parts) >= 3, (
                f"Tool name {tool.name!r} must have >=3 __-separated parts"
            )
            assert parts[0] == "mcp", (
                f"Tool name must start with 'mcp__': {tool.name!r}"
            )


def test_flattened_mcp_tools_lookupable_in_outer_toolpack(
    monkeypatch: pytest.MonkeyPatch,
):
    """Regression for Bug 2: after flattening MCPToolPack, the prefixed tool
    names should be directly look-up-able from a parent ToolPack (no nesting)."""
    from dbgpt.agent.resource.tool.base import BaseTool
    from dbgpt.agent.resource.tool.pack import ToolPack

    manager = ConnectorManager()

    pack = MCPToolPack(mcp_servers="http://example.com/sse", name="GitHub")
    pack.add_command(
        command_label="Create issue",
        command_name="create_issue",
        args={},
        function=lambda: None,
    )
    pack.add_command(
        command_label="List issues",
        command_name="list_issues",
        args={},
        function=lambda: None,
    )
    pack.tool_server_map = {
        "create_issue": "http://example.com/sse",
        "list_issues": "http://example.com/sse",
    }

    manager._apply_tool_prefix(pack, "github", "GitHub")

    # Flatten: extract BaseTool instances (mirrors _select_connector_tools)
    flat_tools = [t for t in pack.sub_resources if isinstance(t, BaseTool)]
    assert len(flat_tools) == 2

    # Simulate agentic_data_api caller: outer ToolPack with flat tools
    outer = ToolPack(flat_tools)

    # Each prefixed name should be a direct key in outer._resources
    for t in flat_tools:
        assert t.name.startswith("mcp__github__"), f"Bad prefix on {t.name}"
        assert t.name in outer._resources, (
            f"Flattened tool {t.name} not found in outer ToolPack._resources"
        )


# ---------------------------------------------------------------------------
# Fix 5a – list_active returns args schema
# ---------------------------------------------------------------------------


def test_list_active_returns_tools_with_args_schema():
    """list_active() should include args schema (not just name+description)."""
    manager = ConnectorManager()
    connector_id = "conn-args"
    pack = MCPToolPack(mcp_servers="http://example.com/sse", name="ArXiv Search")
    pack.add_command(
        command_label="Search papers on ArXiv",
        command_name="search_papers",
        args={
            "query": {
                "type": "string",
                "description": "Search query for papers",
                "required": True,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results",
                "required": False,
            },
        },
        function=lambda query, max_results=10: None,
    )

    manager._connector_types[connector_id] = "arxiv"
    manager._statuses[connector_id] = ConnectorStatus.active
    manager._active_packs[connector_id] = pack
    manager._catalog._entries["arxiv"] = ConnectorCatalogEntry(
        type="arxiv",
        display_name="ArXiv",
        description="ArXiv paper search",
        icon="arxiv",
        category="research",
        mcp_server=McpServerConfig(
            server_uri="http://example.com/sse",
            transport="sse",
        ),
        auth=AuthConfig(
            type="none",
            fields=[],
        ),
    )

    summaries = manager.list_active()
    assert len(summaries) == 1

    tools = summaries[0]["tools"]
    assert len(tools) == 1

    tool = tools[0]
    assert tool["name"] == "search_papers"
    assert "args" in tool
    assert isinstance(tool["args"], dict)

    # Verify args schema contains expected fields
    assert "query" in tool["args"]
    assert tool["args"]["query"]["type"] == "string"
    assert tool["args"]["query"]["required"] is True
    assert "max_results" in tool["args"]
    assert tool["args"]["max_results"]["type"] == "integer"
    assert tool["args"]["max_results"]["required"] is False
