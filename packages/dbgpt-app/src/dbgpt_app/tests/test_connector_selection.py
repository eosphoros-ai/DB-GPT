"""Unit tests for connector selection helpers in agentic_data_api.

Tests ``_parse_connector_ids`` and ``_select_connector_packs`` which are
extracted helpers that ``_react_agent_stream`` delegates to.
"""

from typing import Any, Dict
from unittest.mock import MagicMock

from dbgpt_app.openapi.api_v1.agentic_data_api import (
    _parse_connector_ids,
    _select_connector_packs,
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
# _select_connector_packs
# ---------------------------------------------------------------------------


def _make_manager(packs: Dict[str, Any]) -> MagicMock:
    """Create a mock ConnectorManager with the given id->pack mapping."""
    mgr = MagicMock()
    mgr.get_connector_tools.side_effect = lambda cid: packs.get(cid)
    return mgr


class TestSelectConnectorPacks:
    """Verify filtered connector pack selection."""

    def test_empty_ids_returns_empty(self):
        mgr = _make_manager({"id1": "pack1"})
        packs, missing = _select_connector_packs([], mgr)
        assert packs == []
        assert missing == []

    def test_none_manager_returns_empty(self):
        packs, missing = _select_connector_packs(["id1"], None)
        assert packs == []
        assert missing == []

    def test_both_active(self):
        mgr = _make_manager({"id1": "pack1", "id2": "pack2"})
        packs, missing = _select_connector_packs(["id1", "id2"], mgr)
        assert packs == ["pack1", "pack2"]
        assert missing == []

    def test_one_missing(self):
        mgr = _make_manager({"id1": "pack1"})
        packs, missing = _select_connector_packs(["id1", "missing"], mgr)
        assert packs == ["pack1"]
        assert missing == ["missing"]

    def test_all_missing(self):
        mgr = _make_manager({})
        packs, missing = _select_connector_packs(["a", "b"], mgr)
        assert packs == []
        assert missing == ["a", "b"]

    def test_single_id(self):
        mgr = _make_manager({"solo": "solo-pack"})
        packs, missing = _select_connector_packs(["solo"], mgr)
        assert packs == ["solo-pack"]
        assert missing == []

    def test_preserves_order(self):
        mgr = _make_manager({"c": "pc", "a": "pa", "b": "pb"})
        packs, missing = _select_connector_packs(["a", "b", "c"], mgr)
        assert packs == ["pa", "pb", "pc"]
        assert missing == []
