import json
from typing import Dict, List
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
            config={"server_uri": "http://example.com/sse"},
        )
    )

    fake_manager.create_connector.assert_awaited_once()
    call_kwargs = fake_manager.create_connector.call_args.kwargs
    assert call_kwargs["connector_type"] == "github"
    assert call_kwargs["credentials"] == {"token": "secret-token"}
    assert call_kwargs["name"] == "GitHub Ops"
    assert call_kwargs["extra_config"] == {"server_uri": "http://example.com/sse"}
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
                config_json=json.dumps({"server_uri": "http://example.com/sse"}),
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
        extra_config={"server_uri": "http://example.com/sse"},
        connector_id="connector-1",
    )


def test_after_start_marks_legacy_connector_needs_reactivation(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """Phase 1 era connectors with NULL config_json should be flagged as
    needs_reactivation (not silently lost) after catalog downgrade."""
    store = CredentialStore(system_app=service.system_app)
    encryption_salt = store.generate_salt()
    encrypted_credentials = store.encrypt({"token": "old-token"}, encryption_salt)

    # Insert a legacy row: config_json is NULL (pre-1.5 era)
    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="legacy-conn-1",
                connector_type="github",
                display_name="Legacy GitHub",
                encrypted_credentials=encrypted_credentials,
                encryption_salt=encryption_salt,
                status="active",
                config_json=None,
            )
        )

    fake_manager = MagicMock()
    fake_manager.create_connector = AsyncMock(
        side_effect=ValueError(
            "Built-in connector type 'github' requires extra_config.server_uri"
        )
    )

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    # Should not raise
    service.after_start()

    # manager.create_connector was called with extra_config=None (the legacy state)
    fake_manager.create_connector.assert_awaited_once()
    call_kwargs = fake_manager.create_connector.call_args.kwargs
    assert call_kwargs["extra_config"] is None

    # DB row should now be marked as needs_reactivation
    with db.session() as session:
        entity = (
            session.query(ConnectorInstanceEntity)
            .filter(ConnectorInstanceEntity.connector_id == "legacy-conn-1")
            .first()
        )
        assert entity is not None
        assert entity.status == "needs_reactivation"

    # list_connectors must surface the needs_reactivation row (no silent filtering)
    connectors = service.list_connectors()
    assert any(c.status == "needs_reactivation" for c in connectors)


def test_create_connector_builtin_without_server_uri_propagates_value_error(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """Service-layer create with built-in type but no config.server_uri
    should propagate the ValueError from manager."""
    fake_manager = MagicMock()
    fake_manager.create_connector = AsyncMock(
        side_effect=ValueError(
            "Built-in connector type 'github' requires extra_config.server_uri"
        )
    )

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    with pytest.raises(ValueError, match="requires extra_config.server_uri"):
        service.create_connector(
            ConnectorCreateRequest(
                connector_type="github",
                display_name="GitHub No URI",
                credentials={"token": "secret"},
                config=None,
            )
        )


def test_update_connector_merges_credentials_keeps_omitted_fields(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """P0-3: update with partial credentials merges into existing ones."""
    fake_manager = MagicMock()
    fake_manager.create_connector = AsyncMock()
    fake_manager.remove_connector = AsyncMock()

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    response = service.create_connector(
        ConnectorCreateRequest(
            connector_type="github",
            display_name="GitHub Ops",
            credentials={"github_token": "ghp_xxx", "username": "alice"},
            config={"server_uri": "http://example.com/sse"},
        )
    )

    # Reset mock call counts from create
    fake_manager.reset_mock()

    service.update_connector(
        response.connector_id,
        ConnectorUpdateRequest(credentials={"username": "bob"}),
    )

    with db.session() as session:
        entity = (
            session.query(ConnectorInstanceEntity)
            .filter(ConnectorInstanceEntity.connector_id == response.connector_id)
            .first()
        )
        assert entity is not None
        store = CredentialStore(system_app=service.system_app)
        decrypted = store.decrypt(entity.encrypted_credentials, entity.encryption_salt)
        assert decrypted == {"github_token": "ghp_xxx", "username": "bob"}

    # credentials_changed is True, so re-activation should be triggered
    fake_manager.remove_connector.assert_awaited_once_with(response.connector_id)
    fake_manager.create_connector.assert_awaited_once()


def test_update_connector_resets_needs_reactivation_status(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """P0-1: updating config on a needs_reactivation connector resets status
    to active and re-activates the manager."""
    store = CredentialStore(system_app=service.system_app)
    encryption_salt = store.generate_salt()
    encrypted_credentials = store.encrypt({"token": "old-token"}, encryption_salt)

    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="reactivate-conn-1",
                connector_type="github",
                display_name="Legacy GitHub",
                encrypted_credentials=encrypted_credentials,
                encryption_salt=encryption_salt,
                status="needs_reactivation",
                config_json=None,
            )
        )

    fake_manager = MagicMock()
    fake_manager.create_connector = AsyncMock()
    fake_manager.remove_connector = AsyncMock()

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = service.update_connector(
        "reactivate-conn-1",
        ConnectorUpdateRequest(config={"server_uri": "http://new.example.com/sse"}),
    )

    assert result.status == "active"

    fake_manager.remove_connector.assert_awaited_once_with("reactivate-conn-1")
    fake_manager.create_connector.assert_awaited_once()
    call_kwargs = fake_manager.create_connector.call_args.kwargs
    assert call_kwargs["extra_config"] == {"server_uri": "http://new.example.com/sse"}
    assert call_kwargs["connector_id"] == "reactivate-conn-1"


def test_update_connector_reactivation_failure_marks_error(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """When re-activation fails, the status should be set to 'error'."""
    store = CredentialStore(system_app=service.system_app)
    encryption_salt = store.generate_salt()
    encrypted_credentials = store.encrypt({"token": "test-token"}, encryption_salt)

    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="fail-conn-1",
                connector_type="github",
                display_name="Failing GitHub",
                encrypted_credentials=encrypted_credentials,
                encryption_salt=encryption_salt,
                status="needs_reactivation",
                config_json=None,
            )
        )

    fake_manager = MagicMock()
    fake_manager.remove_connector = AsyncMock()
    fake_manager.create_connector = AsyncMock(
        side_effect=RuntimeError("Connection refused")
    )

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = service.update_connector(
        "fail-conn-1",
        ConnectorUpdateRequest(config={"server_uri": "http://bad.example.com/sse"}),
    )

    assert result.status == "error"


# ---------------------------------------------------------------------------
# Phase 1.5 — test_connection tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_test_connection_returns_success_when_pack_active(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """test_connection returns success=True when pack exists and preload succeeds."""
    from dbgpt.agent.resource.tool.base import BaseTool

    # Create a connector row in DB
    response = service.create_connector(
        ConnectorCreateRequest(
            connector_type="github",
            display_name="GitHub Ops",
            credentials={"token": "secret-token"},
        )
    )
    cid = response.connector_id

    # Build mock pack with 3 tools
    mock_tool = MagicMock(spec=BaseTool)
    mock_pack = MagicMock()
    mock_pack.preload_resource = AsyncMock()
    mock_pack.sub_resources = [mock_tool, mock_tool, mock_tool]

    fake_manager = MagicMock()
    fake_manager.get_connector_tools = MagicMock(return_value=mock_pack)

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = await service.test_connection(cid)

    assert result["success"] is True
    assert "3 个工具" in result["message"]
    mock_pack.preload_resource.assert_awaited_once()


@pytest.mark.asyncio
async def test_test_connection_returns_failure_when_pack_missing(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """connector_id in DB but manager._active_packs has no entry -> success=False."""
    response = service.create_connector(
        ConnectorCreateRequest(
            connector_type="github",
            display_name="GitHub Ops",
            credentials={"token": "secret-token"},
        )
    )
    cid = response.connector_id

    fake_manager = MagicMock()
    fake_manager.get_connector_tools = MagicMock(return_value=None)

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = await service.test_connection(cid)

    assert result["success"] is False
    assert "未激活" in result["message"]


@pytest.mark.asyncio
async def test_test_connection_returns_failure_when_preload_throws(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """preload_resource raises network error -> success=False + error message."""
    response = service.create_connector(
        ConnectorCreateRequest(
            connector_type="github",
            display_name="GitHub Ops",
            credentials={"token": "secret-token"},
        )
    )
    cid = response.connector_id

    mock_pack = MagicMock()
    mock_pack.preload_resource = AsyncMock(side_effect=ConnectionError("timeout"))

    fake_manager = MagicMock()
    fake_manager.get_connector_tools = MagicMock(return_value=mock_pack)

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = await service.test_connection(cid)

    assert result["success"] is False
    assert "连接失败" in result["message"]


@pytest.mark.asyncio
async def test_test_connection_success_heals_error_status_to_active(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """A successful test_connection on an 'error' row should heal status
    back to 'active'.

    Why: status is only written on create/update/after_start. Once a transient
    re-activation failure stamps 'error', nothing else flips it back even after
    the remote recovers. test_connection succeeding is proof the connector works
    *now*, so we treat it as the self-heal trigger.
    """
    from dbgpt.agent.resource.tool.base import BaseTool

    store = CredentialStore(system_app=service.system_app)
    encryption_salt = store.generate_salt()
    encrypted_credentials = store.encrypt({"token": "tok"}, encryption_salt)

    # Seed a row already in the 'error' state (e.g., from a past PUT failure).
    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="heal-conn-1",
                connector_type="custom_mcp",
                display_name="ArXiv-Search",
                encrypted_credentials=encrypted_credentials,
                encryption_salt=encryption_salt,
                status="error",
                config_json=json.dumps({"server_uri": "http://example.com/sse"}),
            )
        )

    mock_tool = MagicMock(spec=BaseTool)
    mock_pack = MagicMock()
    mock_pack.preload_resource = AsyncMock()
    mock_pack.sub_resources = [mock_tool]

    fake_manager = MagicMock()
    fake_manager.get_connector_tools = MagicMock(return_value=mock_pack)

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = await service.test_connection("heal-conn-1")

    assert result["success"] is True

    with db.session() as session:
        entity = (
            session.query(ConnectorInstanceEntity)
            .filter(ConnectorInstanceEntity.connector_id == "heal-conn-1")
            .first()
        )
        assert entity is not None
        assert entity.status == "active"


@pytest.mark.asyncio
async def test_test_connection_failure_does_not_overwrite_status(
    service: ConnectorService, monkeypatch: pytest.MonkeyPatch
):
    """A failing test_connection must NOT mutate status — status only heals on
    real success, and a failed test does not prove the connector is broken
    (could be a transient network blip from the API server side)."""
    store = CredentialStore(system_app=service.system_app)
    encryption_salt = store.generate_salt()
    encrypted_credentials = store.encrypt({"token": "tok"}, encryption_salt)

    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="stable-conn-1",
                connector_type="custom_mcp",
                display_name="ArXiv-Search",
                encrypted_credentials=encrypted_credentials,
                encryption_salt=encryption_salt,
                status="active",
                config_json=json.dumps({"server_uri": "http://example.com/sse"}),
            )
        )

    mock_pack = MagicMock()
    mock_pack.preload_resource = AsyncMock(side_effect=ConnectionError("timeout"))

    fake_manager = MagicMock()
    fake_manager.get_connector_tools = MagicMock(return_value=mock_pack)

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = await service.test_connection("stable-conn-1")

    assert result["success"] is False

    with db.session() as session:
        entity = (
            session.query(ConnectorInstanceEntity)
            .filter(ConnectorInstanceEntity.connector_id == "stable-conn-1")
            .first()
        )
        assert entity is not None
        assert entity.status == "active"


# ----------------------------------------------------------------------
# Tests added in v4: is_custom predicate, _tool_summary_for, list_tools
# ----------------------------------------------------------------------


def test_is_custom_connector_type_predicate():
    """The static predicate accepts only non-empty ``custom_<suffix>`` strings."""
    from dbgpt.agent.resource.connector.manager import ConnectorManager

    assert ConnectorManager.is_custom_connector_type("custom_mcp") is True
    assert ConnectorManager.is_custom_connector_type("custom_arxiv") is True
    assert ConnectorManager.is_custom_connector_type("custom_a") is True

    assert ConnectorManager.is_custom_connector_type("custom_") is False
    assert ConnectorManager.is_custom_connector_type("github") is False
    assert ConnectorManager.is_custom_connector_type("slack") is False
    assert ConnectorManager.is_custom_connector_type("") is False
    assert ConnectorManager.is_custom_connector_type(None) is False  # type: ignore[arg-type]
    assert ConnectorManager.is_custom_connector_type(123) is False  # type: ignore[arg-type]


def test_connector_response_is_custom_for_custom_mcp_entity(service: ConnectorService):
    """``ConnectorResponse.is_custom`` reflects the predicate on the type string."""
    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="custom-1",
                connector_type="custom_mcp",
                display_name="Custom MCP",
                status="active",
                config_json=json.dumps({"server_uri": "http://example.com/sse"}),
            )
        )

    response = service.get_connector("custom-1")
    assert response is not None
    assert response.is_custom is True
    assert response.connector_type == "custom_mcp"


def test_connector_response_is_custom_false_for_builtin_type(service: ConnectorService):
    """Built-in connector types must report ``is_custom=False``."""
    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="builtin-1",
                connector_type="github",
                display_name="GitHub",
                status="active",
            )
        )

    response = service.get_connector("builtin-1")
    assert response is not None
    assert response.is_custom is False


def test_tool_summary_for_returns_none_when_pack_absent():
    """``_tool_summary_for`` returns ``None`` when the connector_id is unknown."""
    from dbgpt.agent.resource.connector.manager import ConnectorManager

    manager = ConnectorManager()
    assert manager._tool_summary_for("missing-id") is None


def test_tool_summary_for_shape_matches_list_active_entry():
    """The helper output shape is identical to one ``list_active`` entry's tools."""
    from dbgpt.agent.resource.connector.manager import (
        ConnectorManager,
        ConnectorStatus,
    )
    from dbgpt.agent.resource.tool.base import BaseTool, ToolParameter

    class _StubTool(BaseTool):  # type: ignore[misc]
        @property
        def name(self) -> str:
            return "stub_tool"

        @property
        def description(self) -> str:
            return "stub tool"

        @property
        def args(self) -> Dict[str, ToolParameter]:
            return {
                "query": ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                    required=True,
                )
            }

        async def _arun(self, *args, **kwargs):  # pragma: no cover - unused path
            return None

        def _run(self, *args, **kwargs):  # pragma: no cover - unused path
            return None

    pack = MagicMock()
    pack.name = "stub-pack"
    pack.sub_resources = [_StubTool()]

    manager = ConnectorManager()
    manager._active_packs["c1"] = pack
    manager._statuses["c1"] = ConnectorStatus.active
    manager._connector_types["c1"] = "github"

    summary = manager._tool_summary_for("c1")
    list_active_entry = next(
        e for e in manager.list_active() if e["connector_id"] == "c1"
    )

    assert summary is not None
    assert summary == list_active_entry["tools"]
    assert summary[0]["name"] == "stub_tool"
    assert summary[0]["original_name"] == "stub_tool"  # no routing prefix
    assert summary[0]["args"]["query"]["required"] is True
    assert summary[0]["args"]["query"]["type"] == "string"


def test_tool_summary_for_strips_routing_prefix():
    """Tools whose ``name`` carries the ``mcp__{prefix}__`` routing prefix
    expose the bare MCP name via ``original_name``."""
    from dbgpt.agent.resource.connector.manager import (
        ConnectorManager,
        ConnectorStatus,
    )
    from dbgpt.agent.resource.tool.base import BaseTool, ToolParameter

    class _PrefixedTool(BaseTool):  # type: ignore[misc]
        @property
        def name(self) -> str:
            return "mcp__arxiv-search__search_papers"

        @property
        def description(self) -> str:
            return "Search arXiv papers"

        @property
        def args(self) -> Dict[str, ToolParameter]:
            return {}

        async def _arun(self, *args, **kwargs):  # pragma: no cover
            return None

        def _run(self, *args, **kwargs):  # pragma: no cover
            return None

    pack = MagicMock()
    pack.name = "arxiv-search"
    pack.sub_resources = [_PrefixedTool()]

    manager = ConnectorManager()
    manager._active_packs["c-prefix"] = pack
    manager._statuses["c-prefix"] = ConnectorStatus.active
    manager._connector_types["c-prefix"] = "custom_mcp"

    summary = manager._tool_summary_for("c-prefix")
    assert summary is not None
    assert summary[0]["name"] == "mcp__arxiv-search__search_papers"
    assert summary[0]["original_name"] == "search_papers"


def test_tool_summary_for_dedups_duplicate_tools_by_original_name():
    """When ``_resources`` holds both prefixed and raw-name versions of the
    same logical tool (a real-world symptom of ``MCPToolPack.preload_resource``
    re-firing after ``_apply_tool_prefix``), the summary collapses them and
    keeps the prefixed entry — the canonical routing name LLMs invoke."""
    from dbgpt.agent.resource.connector.manager import (
        ConnectorManager,
        ConnectorStatus,
    )
    from dbgpt.agent.resource.tool.base import BaseTool, ToolParameter

    def _tool(name: str, desc: str) -> BaseTool:
        class _T(BaseTool):  # type: ignore[misc]
            @property
            def name(self_inner) -> str:
                return name

            @property
            def description(self_inner) -> str:
                return desc

            @property
            def args(self_inner) -> Dict[str, ToolParameter]:
                return {}

            async def _arun(self_inner, *a, **kw):  # pragma: no cover
                return None

            def _run(self_inner, *a, **kw):  # pragma: no cover
                return None

        return _T()

    pack = MagicMock()
    pack.name = "arxiv-search"
    # Two physical entries for the same logical tool — exactly what the
    # production bug produced (one prefixed via _apply_tool_prefix, one raw).
    pack.sub_resources = [
        _tool("mcp__arxiv-search__search_papers", "search (via ArXiv-Search)"),
        _tool("search_papers", "search"),
        _tool("mcp__arxiv-search__list_authors", "list authors (via ArXiv-Search)"),
        _tool("list_authors", "list authors"),
    ]

    manager = ConnectorManager()
    manager._active_packs["c-dup"] = pack
    manager._statuses["c-dup"] = ConnectorStatus.active
    manager._connector_types["c-dup"] = "custom_mcp"

    summary = manager._tool_summary_for("c-dup")
    assert summary is not None

    # Dedup: two logical tools, not four physical entries.
    assert len(summary) == 2

    # The prefixed (canonical routing) version wins.
    by_original = {t["original_name"]: t for t in summary}
    assert by_original["search_papers"]["name"] == "mcp__arxiv-search__search_papers"
    assert by_original["list_authors"]["name"] == "mcp__arxiv-search__list_authors"


def test_tool_summary_for_keeps_raw_when_only_raw_present():
    """If only the raw (unprefixed) version exists, it's still surfaced."""
    from dbgpt.agent.resource.connector.manager import (
        ConnectorManager,
        ConnectorStatus,
    )
    from dbgpt.agent.resource.tool.base import BaseTool, ToolParameter

    class _Raw(BaseTool):  # type: ignore[misc]
        @property
        def name(self) -> str:
            return "search_papers"

        @property
        def description(self) -> str:
            return "raw"

        @property
        def args(self) -> Dict[str, ToolParameter]:
            return {}

        async def _arun(self, *a, **kw):  # pragma: no cover
            return None

        def _run(self, *a, **kw):  # pragma: no cover
            return None

    pack = MagicMock()
    pack.name = "x"
    pack.sub_resources = [_Raw()]
    manager = ConnectorManager()
    manager._active_packs["c-raw"] = pack
    manager._statuses["c-raw"] = ConnectorStatus.active
    manager._connector_types["c-raw"] = "custom_mcp"

    summary = manager._tool_summary_for("c-raw")
    assert summary == [
        {
            "name": "search_papers",
            "original_name": "search_papers",
            "description": "raw",
            "args": {},
        }
    ]


def test_strip_routing_prefix_unit():
    """The ``_strip_routing_prefix`` helper correctly peels ``mcp__{prefix}__``."""
    from dbgpt.agent.resource.connector.manager import _strip_routing_prefix

    assert _strip_routing_prefix("mcp__github__create_issue") == "create_issue"
    assert _strip_routing_prefix("mcp__github-acme__create_issue") == "create_issue"
    assert _strip_routing_prefix("mcp__my-arxiv__search_papers") == "search_papers"
    # Tool name with underscores survives (split with maxsplit=2).
    assert (
        _strip_routing_prefix("mcp__svc__a_long_tool_name_with_underscores")
        == "a_long_tool_name_with_underscores"
    )
    # No prefix → unchanged.
    assert _strip_routing_prefix("search_papers") == "search_papers"
    # Looks-like but malformed → unchanged.
    assert _strip_routing_prefix("mcp__") == "mcp__"
    assert _strip_routing_prefix("mcp__only_one_segment") == "mcp__only_one_segment"


def test_list_tools_unknown_connector_id_raises_404(service: ConnectorService):
    """Querying tools for a non-existent connector raises ``HTTPException(404)``."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        service.list_tools("non-existent-id")
    assert exc_info.value.status_code == 404


def test_list_tools_inactive_when_pack_not_in_manager(
    service: ConnectorService, monkeypatch
):
    """Connector exists in DB but no live pack -> ``state="inactive"``, empty tools."""
    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="inactive-1",
                connector_type="github",
                display_name="Inactive Conn",
                status="disconnected",
            )
        )

    fake_manager = MagicMock()
    fake_manager._tool_summary_for = MagicMock(return_value=None)
    fake_manager._statuses = {}

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = service.list_tools("inactive-1")
    assert result.connector_id == "inactive-1"
    assert result.state == "inactive"
    assert result.tools == []


def test_list_tools_inactive_when_manager_unavailable(
    service: ConnectorService, monkeypatch
):
    """Manager component missing -> still returns ``state="inactive"`` (no crash)."""
    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="no-manager-1",
                connector_type="github",
                display_name="Conn",
                status="active",
            )
        )

    def _fake_get_component(name, component_type, default_component=None):
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = service.list_tools("no-manager-1")
    assert result.state == "inactive"
    assert result.tools == []


def test_list_tools_active_returns_tools_when_pack_present(
    service: ConnectorService, monkeypatch
):
    """Active pack + active status -> ``state="active"`` with tool list."""
    from dbgpt.agent.resource.connector.manager import ConnectorStatus

    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="active-1",
                connector_type="github",
                display_name="Active Conn",
                status="active",
            )
        )

    fake_manager = MagicMock()
    fake_manager._tool_summary_for = MagicMock(
        return_value=[
            {
                "name": "github_search",
                "description": "Search GitHub",
                "args": {
                    "query": {
                        "type": "string",
                        "required": True,
                        "description": "search query",
                    }
                },
            }
        ]
    )
    fake_manager._statuses = {"active-1": ConnectorStatus.active}

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = service.list_tools("active-1")
    assert result.state == "active"
    assert len(result.tools) == 1
    assert result.tools[0]["name"] == "github_search"
    assert result.tools[0]["args"]["query"]["required"] is True


def test_list_tools_pack_present_but_status_not_active_is_inactive(
    service: ConnectorService, monkeypatch
):
    """Pack registered but ``_statuses`` reports non-active -> ``state="inactive"``."""
    from dbgpt.agent.resource.connector.manager import ConnectorStatus

    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="degraded-1",
                connector_type="github",
                display_name="Degraded",
                status="error",
            )
        )

    fake_manager = MagicMock()
    fake_manager._tool_summary_for = MagicMock(
        return_value=[{"name": "x", "description": "y", "args": {}}]
    )
    fake_manager._statuses = {"degraded-1": ConnectorStatus.error}

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = service.list_tools("degraded-1")
    # Pack is present so tools are returned, but status is not "active".
    assert result.state == "inactive"
    assert len(result.tools) == 1


def test_list_tools_truncates_args_over_8kb(service: ConnectorService, monkeypatch):
    """Tools whose args JSON exceeds 8KB are replaced with the truncation marker."""
    from dbgpt.agent.resource.connector.manager import ConnectorStatus

    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="huge-1",
                connector_type="github",
                display_name="Huge",
                status="active",
            )
        )

    huge_args = {
        f"arg_{i}": {
            "type": "string",
            "required": False,
            "description": "x" * 200,
        }
        for i in range(60)
    }

    fake_manager = MagicMock()
    fake_manager._tool_summary_for = MagicMock(
        return_value=[{"name": "huge_tool", "description": "huge", "args": huge_args}]
    )
    fake_manager._statuses = {"huge-1": ConnectorStatus.active}

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    result = service.list_tools("huge-1")
    assert result.state == "active"
    assert len(result.tools) == 1
    args = result.tools[0]["args"]
    assert args.get("_truncated") is True
    assert args.get("byte_count", 0) > 8192


def test_list_tools_p95_latency_under_100ms_for_50_tools(
    service: ConnectorService, monkeypatch
):
    """End-to-end p95 latency for a 50-tool synthetic pack stays under 100ms."""
    import time

    from dbgpt.agent.resource.connector.manager import ConnectorStatus

    with db.session() as session:
        session.add(
            ConnectorInstanceEntity(
                connector_id="perf-1",
                connector_type="github",
                display_name="Perf",
                status="active",
            )
        )

    fifty_tools = [
        {
            "name": f"tool_{i}",
            "description": f"description {i}",
            "args": {
                f"arg_{j}": {
                    "type": "string",
                    "required": j == 0,
                    "description": f"arg {j} of tool {i}",
                }
                for j in range(5)
            },
        }
        for i in range(50)
    ]

    fake_manager = MagicMock()
    fake_manager._tool_summary_for = MagicMock(return_value=fifty_tools)
    fake_manager._statuses = {"perf-1": ConnectorStatus.active}

    def _fake_get_component(name, component_type, default_component=None):
        if name == "connector_manager":
            return fake_manager
        return default_component

    monkeypatch.setattr(service.system_app, "get_component", _fake_get_component)

    samples_ms: List[float] = []
    for _ in range(50):
        # Fresh copy each iteration; the service mutates the args dict in place
        # when applying the 8KB cap, so reusing the same list across calls would
        # also work but copying keeps the test self-contained.
        fake_manager._tool_summary_for = MagicMock(
            return_value=[dict(t, args=dict(t["args"])) for t in fifty_tools]
        )
        start = time.perf_counter()
        service.list_tools("perf-1")
        samples_ms.append((time.perf_counter() - start) * 1000.0)

    samples_ms.sort()
    p95 = samples_ms[int(len(samples_ms) * 0.95) - 1]
    assert p95 < 100.0, f"p95={p95:.2f}ms exceeds 100ms budget"
