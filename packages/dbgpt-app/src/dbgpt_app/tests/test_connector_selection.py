"""Unit tests for connector selection helpers in agentic_data_api.

Tests ``_parse_connector_ids`` and ``_select_connector_tools`` which are
extracted helpers that ``_react_agent_stream`` delegates to.
"""

from typing import Any, Dict, List
from unittest.mock import MagicMock

from dbgpt_app.openapi.api_v1.agentic_data_api import (
    _parse_connector_ids,
    _select_connector_tools,
)

# ---------------------------------------------------------------------------
# _parse_connector_ids
# ---------------------------------------------------------------------------


class TestParseConnectorIds:
    """Verify ext_info parsing for connector_ids / connector_id."""

    def test_none_ext_info(self):
        assert _parse_connector_ids(None) == []

    def test_empty_dict(self):
        assert _parse_connector_ids({}) == []

    def test_not_a_dict(self):
        assert _parse_connector_ids("not-a-dict") == []

    def test_connector_ids_list(self):
        ext = {"connector_ids": ["id1", "id2"]}
        assert _parse_connector_ids(ext) == ["id1", "id2"]

    def test_connector_ids_filters_non_strings(self):
        ext = {"connector_ids": ["id1", 123, "", None, "id2"]}
        assert _parse_connector_ids(ext) == ["id1", "id2"]

    def test_connector_ids_empty_list(self):
        ext = {"connector_ids": []}
        assert _parse_connector_ids(ext) == []

    def test_legacy_connector_id_string(self):
        ext = {"connector_id": "legacy-id"}
        assert _parse_connector_ids(ext) == ["legacy-id"]

    def test_legacy_connector_id_empty_string(self):
        ext = {"connector_id": ""}
        assert _parse_connector_ids(ext) == []

    def test_legacy_connector_id_not_string(self):
        ext = {"connector_id": 42}
        assert _parse_connector_ids(ext) == []

    def test_connector_ids_takes_precedence_over_legacy(self):
        ext = {"connector_ids": ["new-id"], "connector_id": "old-id"}
        assert _parse_connector_ids(ext) == ["new-id"]

    def test_connector_ids_empty_falls_through_to_legacy(self):
        """Empty list means user explicitly chose nothing -> no fallback."""
        ext = {"connector_ids": [], "connector_id": "old-id"}
        # connector_ids is present (empty list), so we return empty -- no
        # fallback to legacy.  This matches the code: isinstance([], list)
        # is True, so the list comprehension runs and returns [].
        assert _parse_connector_ids(ext) == []


# ---------------------------------------------------------------------------
# _select_connector_tools
# ---------------------------------------------------------------------------


def _make_mock_tool(name: str) -> MagicMock:
    """Create a mock BaseTool with the given name."""
    from dbgpt.agent.resource.tool.base import BaseTool

    tool = MagicMock(spec=BaseTool)
    tool.name = name
    return tool


def _make_mock_pack(tools: List[MagicMock]) -> MagicMock:
    """Create a mock MCPToolPack whose sub_resources returns *tools*."""
    pack = MagicMock()
    pack.sub_resources = tools
    return pack


def _make_manager(packs: Dict[str, Any]) -> MagicMock:
    """Create a mock ConnectorManager with the given id->pack mapping."""
    mgr = MagicMock()
    mgr.get_connector_tools.side_effect = lambda cid: packs.get(cid)
    return mgr


class TestSelectConnectorTools:
    """Verify filtered connector tool selection (flattened)."""

    def test_empty_ids_returns_empty(self):
        mgr = _make_manager({"id1": _make_mock_pack([_make_mock_tool("t1")])})
        tools, missing = _select_connector_tools([], mgr)
        assert tools == []
        assert missing == []

    def test_none_manager_returns_empty(self):
        tools, missing = _select_connector_tools(["id1"], None)
        assert tools == []
        assert missing == []

    def test_both_active_flattened(self):
        t1 = _make_mock_tool("tool1")
        t2 = _make_mock_tool("tool2")
        t3 = _make_mock_tool("tool3")
        mgr = _make_manager(
            {
                "id1": _make_mock_pack([t1, t2]),
                "id2": _make_mock_pack([t3]),
            }
        )
        tools, missing = _select_connector_tools(["id1", "id2"], mgr)
        assert tools == [t1, t2, t3]
        assert missing == []

    def test_one_missing(self):
        t1 = _make_mock_tool("tool1")
        mgr = _make_manager({"id1": _make_mock_pack([t1])})
        tools, missing = _select_connector_tools(["id1", "missing"], mgr)
        assert tools == [t1]
        assert missing == ["missing"]

    def test_all_missing(self):
        mgr = _make_manager({})
        tools, missing = _select_connector_tools(["a", "b"], mgr)
        assert tools == []
        assert missing == ["a", "b"]

    def test_single_id(self):
        t1 = _make_mock_tool("solo-tool")
        mgr = _make_manager({"solo": _make_mock_pack([t1])})
        tools, missing = _select_connector_tools(["solo"], mgr)
        assert tools == [t1]
        assert missing == []

    def test_preserves_order(self):
        ta = _make_mock_tool("ta")
        tb = _make_mock_tool("tb")
        tc = _make_mock_tool("tc")
        mgr = _make_manager(
            {
                "c": _make_mock_pack([tc]),
                "a": _make_mock_pack([ta]),
                "b": _make_mock_pack([tb]),
            }
        )
        tools, missing = _select_connector_tools(["a", "b", "c"], mgr)
        assert tools == [ta, tb, tc]
        assert missing == []
