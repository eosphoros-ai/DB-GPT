import textwrap

import pytest

from dbgpt.storage.metadata import db
from dbgpt_serve.plugins.loader import load_suite_dir
from dbgpt_serve.plugins.models.models import SuiteDao, SuiteEventDao
from dbgpt_serve.plugins.registry import (
    STATUS_DISABLED,
    STATUS_ENABLED,
    SuiteRegistry,
)

MANIFEST = textwrap.dedent(
    """
    kind: scenario-suite
    name: demo-query
    display: 智能取数
    version: {version}
    scenario_id: query
    skills: []
    """
)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield


@pytest.fixture
def registry():
    return SuiteRegistry(SuiteDao(), SuiteEventDao())


def _pkg(tmp_path, version="1.0.0"):
    pkg_dir = tmp_path / "demo-query"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "suite.yaml").write_text(
        MANIFEST.format(version=version), encoding="utf-8"
    )
    return load_suite_dir(pkg_dir)


def test_sync_installs_then_stays_unchanged(tmp_path, registry):
    pkg = _pkg(tmp_path)
    first = registry.sync_official([pkg])
    assert first.installed == ["demo-query"]
    assert first.upgraded == []

    second = registry.sync_official([pkg])
    assert second.unchanged == ["demo-query"]
    assert second.installed == []

    row = registry.get("demo-query")
    assert row is not None
    assert row.status == STATUS_ENABLED
    assert row.source == "official"
    assert row.version == "1.0.0"
    assert row.manifest_snapshot["scenario_id"] == "query"


def test_sync_version_bump_writes_upgrade_event(tmp_path, registry):
    registry.sync_official([_pkg(tmp_path, "1.0.0")])
    summary = registry.sync_official([_pkg(tmp_path, "1.1.0")])
    assert summary.upgraded == ["demo-query"]
    assert registry.get("demo-query").version == "1.1.0"
    events = registry.list_events("demo-query")
    assert events[0].event_type == "upgrade"
    assert events[0].from_version == "1.0.0"
    assert events[0].to_version == "1.1.0"


def test_missing_package_degrades_to_disabled(tmp_path, registry):
    registry.sync_official([_pkg(tmp_path)])
    summary = registry.sync_official([])
    assert summary.disabled_missing == ["demo-query"]
    assert registry.get("demo-query").status == STATUS_DISABLED
    events = registry.list_events("demo-query")
    assert events[0].event_type == "disable"
    assert events[0].detail["reason"] == "package_missing"


def test_enable_disable_roundtrip_and_events(tmp_path, registry):
    registry.sync_official([_pkg(tmp_path)])
    disabled = registry.set_enabled("demo-query", False, user_name="ckt")
    assert disabled.status == STATUS_DISABLED
    enabled = registry.set_enabled("demo-query", True, user_name="ckt")
    assert enabled.status == STATUS_ENABLED
    types = [e.event_type for e in registry.list_events("demo-query")]
    assert types[:3] == ["enable", "disable", "install"]


def test_set_enabled_unknown_suite_raises(registry):
    with pytest.raises(ValueError):
        registry.set_enabled("nope", True)


def test_list_suites_orders_enabled_first(tmp_path, registry):
    registry.sync_official([_pkg(tmp_path)])
    other = tmp_path / "demo-ops"
    other.mkdir()
    (other / "suite.yaml").write_text(
        MANIFEST.format(version="1.0.0").replace("demo-query", "demo-ops"),
        encoding="utf-8",
    )
    registry.sync_official([load_suite_dir(other)])
    registry.set_enabled("demo-query", False)
    names = [s.name for s in registry.list_suites()]
    assert names == ["demo-ops", "demo-query"]


def test_record_pin_bumps_use_count_and_event(tmp_path, registry):
    registry.sync_official([_pkg(tmp_path)])
    registry.record_pin("conv-1", "demo-query", "1.0.0")
    row = registry.get("demo-query")
    assert row.use_count == 1
    assert registry.list_events("demo-query")[0].event_type == "pin"
    assert registry.list_events("demo-query")[0].conv_uid == "conv-1"
