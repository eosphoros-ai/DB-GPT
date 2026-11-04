"""Generated suites must remain immutable and recoverable before activation."""

import json
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from dbgpt.storage.metadata import db
from dbgpt_serve.plugins.config import ServeConfig
from dbgpt_serve.plugins.creation import SuiteCreationStore
from dbgpt_serve.plugins.loader import PLUGIN_MANIFEST_FILENAME, package_digest
from dbgpt_serve.plugins.models.models import SuiteDao, SuiteEventDao
from dbgpt_serve.plugins.registry import SuiteRegistry
from dbgpt_serve.plugins.service.service import Service


def package_files(database=False):
    return {
        PLUGIN_MANIFEST_FILENAME: json.dumps(
            {
                "name": "test-office",
                "version": "1.0.0",
                "displayNameCn": "测试办公专家",
                "description": "整理业务材料与周报",
                "skills": ["skills/report"],
                "dbgpt": {
                    "sop": "prompts/workflow.md",
                    "tools": {"allow": ["sql_query"] if database else []},
                    "context_defaults": {
                        "datasource": "required" if database else "optional"
                    },
                    "required_resources": ["database"] if database else [],
                    "artifacts": [{"type": "markdown", "name": "周报"}],
                    "output_contract": {"completion": "进展、风险、下一步完整且有依据"},
                },
            }
        ),
        "README.md": "# 周报专家\n根据业务材料整理周报与行动清单。",
        "prompts/workflow.md": "# 工作流程\n阅读材料，核实口径，生成周报，然后校验。",
        "skills/report/SKILL.md": (
            "---\nname: report\nname_zh: 周报\n"
            'description: "根据材料生成周报"\ncommand: /周报\n---\n'
            "# 周报技能\n阅读输入材料；按照进展、风险、责任人和下一步组织正文；"
            "逐条核对材料出处，缺失信息标记待补充，不编造事实。"
        ),
    }


@pytest.fixture
def store(tmp_path):
    return SuiteCreationStore(tmp_path / "creation")


def build(store, files=None):
    draft = store.create("create weekly report suite")
    draft = store.write(draft["draft_id"], files or package_files(), 0)
    return store.build(draft["draft_id"], draft["revision"])


@pytest.fixture
def service(tmp_path):
    db.init_db("sqlite:///:memory:")
    db.create_all()
    suites = tmp_path / "suites"
    suites.mkdir()
    # Use real DAOs and Service operations without a web application lifecycle.
    result = object.__new__(Service)
    result._dao = SuiteDao()
    result._event_dao = SuiteEventDao()
    result._registry = SuiteRegistry(result._dao, result._event_dao)
    result._serve_config = ServeConfig(suites_dir=str(suites))
    return result


def test_build_freezes_revision_and_zip(store):
    artifact = build(store)
    draft = store.read(artifact["draft_id"])
    store.write(draft["draft_id"], {"README.md": "# new contents"}, draft["revision"])
    assert (
        store.artifact(artifact["artifact_id"])["files"]["README.md"]
        == package_files()["README.md"]
    )
    assert artifact["validation"]["status"] == "ready"
    assert artifact["validation"]["trial_status"] == "not_run"
    with zipfile.ZipFile(store.download(artifact["artifact_id"])) as archive:
        assert "test-office/skills/report/SKILL.md" in archive.namelist()
    with pytest.raises(ValueError, match="revision conflict"):
        store.build(draft["draft_id"], draft["revision"])


@pytest.mark.parametrize(
    "path",
    [
        "../evil.md",
        "/tmp/evil.md",
        "a\\evil.md",
        "a/../evil.md",
        "a//evil.md",
        "script.py",
    ],
)
def test_unsafe_writes_never_mutate_draft(store, path):
    draft = store.create("test")
    with pytest.raises(ValueError):
        store.write(draft["draft_id"], {path: "bad"}, 0)
    assert store.read(draft["draft_id"])["revision"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_skill",
        "short_skill",
        "unknown_tool",
        "bad_command",
        "missing_reference",
        "escaped_reference",
        "missing_sop",
        "missing_contract",
        "null_manifest",
        "missing_readme",
    ],
)
def test_strict_validation_blocks_incomplete_suites(store, mutation):
    files = package_files()
    raw = json.loads(files[PLUGIN_MANIFEST_FILENAME])
    if mutation == "missing_skill":
        del files["skills/report/SKILL.md"]
    elif mutation == "short_skill":
        files["skills/report/SKILL.md"] = (
            "---\nname: report\ndescription: test\n---\nTODO"
        )
    elif mutation == "unknown_tool":
        raw["dbgpt"]["tools"]["allow"] = ["imaginary_tool"]
    elif mutation == "bad_command":
        raw["dbgpt"]["commands"] = [{"name": "/bad", "skill": "missing"}]
    elif mutation == "missing_reference":
        files["README.md"] += "\n[Reference](references/missing.md)"
    elif mutation == "escaped_reference":
        files["README.md"] += "\n[Reference](../../escape.md)"
    elif mutation == "missing_sop":
        del files["prompts/workflow.md"]
    elif mutation == "missing_contract":
        del raw["dbgpt"]["output_contract"]
    elif mutation == "missing_readme":
        del files["README.md"]
    files[PLUGIN_MANIFEST_FILENAME] = (
        "null" if mutation == "null_manifest" else json.dumps(raw)
    )
    draft = store.create("test")
    written = store.write(draft["draft_id"], files, 0)
    assert store.validate(draft["draft_id"], written["revision"])["status"] == "invalid"
    with pytest.raises(ValueError, match="validation failed"):
        store.build(draft["draft_id"], written["revision"])


def test_concurrent_edits_do_not_overwrite(store):
    draft = store.create("test")

    def write(name):
        try:
            return store.write(draft["draft_id"], {name: "content"}, 0)
        except ValueError:
            return None

    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(write, ["first.md", "second.md"]))
    assert sum(result is not None for result in results) == 1
    assert len(store.read(draft["draft_id"])["files"]) == 1


def test_install_idempotent_and_real_registry(store, service):
    artifact = build(store)
    first = store.install(artifact["artifact_id"], artifact["package_digest"], service)
    second = store.install(artifact["artifact_id"], artifact["package_digest"], service)
    assert first.id == second.id
    assert first.status == "enabled"
    assert (
        service.get("test-office").manifest_snapshot["commands"][0]["skill"] == "report"
    )
    assert len(service.list_events("test-office")) == 1
    assert store.installation(artifact["artifact_id"], service).id == first.id


def test_required_database_installs_disabled(store, service):
    artifact = build(store, package_files(database=True))
    installed = store.install(
        artifact["artifact_id"], artifact["package_digest"], service
    )
    assert installed.status == "disabled"
    assert installed.manifest_snapshot["required_resources"] == ["database"]
    with pytest.raises(ValueError, match="数据库配置"):
        service.enable(installed.name)


def test_same_name_conflict_preserves_installed_contents(store, service):
    artifact = build(store)
    original = store.install(
        artifact["artifact_id"], artifact["package_digest"], service
    )
    files = package_files()
    files["README.md"] += "\nchanged"
    changed = build(store, files)
    with pytest.raises(ValueError, match="same-name conflict"):
        store.install(changed["artifact_id"], changed["package_digest"], service)
    assert package_digest(original.package_path) == artifact["package_digest"]
    assert len(service.list_events(original.name)) == 1


def test_failed_registration_recovers_files(store, service):
    artifact = build(store)
    real_register = service.install_generated_package
    service.install_generated_package = Mock(
        side_effect=RuntimeError("registration failed")
    )
    with pytest.raises(RuntimeError, match="registration failed"):
        store.install(artifact["artifact_id"], artifact["package_digest"], service)
    assert service.get("test-office") is None
    assert not Path(service.config.suites_dir, "test-office").exists()
    service.install_generated_package = real_register
    assert (
        store.install(
            artifact["artifact_id"], artifact["package_digest"], service
        ).status
        == "enabled"
    )


def test_tampering_and_wrong_digest_block_install(store, service):
    artifact = build(store)
    with pytest.raises(ValueError, match="digest mismatch"):
        store.install(artifact["artifact_id"], "wrong", service)
    path = store._dir("artifacts", artifact["artifact_id"]) / "package" / "README.md"
    path.write_text("changed", "utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        store.install(artifact["artifact_id"], artifact["package_digest"], service)
    assert service.get("test-office") is None


def test_later_artifact_link_does_not_change_original(store):
    original = build(store)
    draft = store.create("revision")
    written = store.write(draft["draft_id"], package_files(), 0)
    child = store.build(draft["draft_id"], written["revision"], original["artifact_id"])
    assert store.revisions(original["artifact_id"]) == [child["artifact_id"]]
    assert store.artifact(original["artifact_id"]) == original


def test_valid_relative_skill_reference(store):
    files = package_files()
    files["references/check.md"] = "# Check\nVerify weekly facts."
    files["skills/report/SKILL.md"] += "\n[Checklist](../../references/check.md)"
    assert store.validate_files(files)["status"] == "ready"


def test_audit_failure_rolls_back_registration_and_files(store, service):
    from sqlalchemy import event

    from dbgpt_serve.plugins.models.models import SuiteEventEntity

    artifact = build(store)

    def fail_audit(*args):
        raise RuntimeError("audit unavailable")

    event.listen(SuiteEventEntity, "before_insert", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            store.install(artifact["artifact_id"], artifact["package_digest"], service)
    finally:
        event.remove(SuiteEventEntity, "before_insert", fail_audit)
    assert service.get("test-office") is None
    assert not Path(service.config.suites_dir, "test-office").exists()
    assert (
        store.install(
            artifact["artifact_id"], artifact["package_digest"], service
        ).status
        == "enabled"
    )


def test_crash_orphan_is_not_activated_by_startup_scan(store, service, monkeypatch):
    monkeypatch.setenv("DBGPT_SUITE_CREATION_DIR", str(store.root))
    artifact = build(store, package_files(database=True))
    source = store._dir("artifacts", artifact["artifact_id"]) / "package"
    target = Path(service.config.suites_dir, artifact["suite_name"])
    shutil.copytree(source, target)
    store._save(
        store.root / "installations" / "test-office.json",
        {
            "artifact_id": artifact["artifact_id"],
            "status": "installing",
        },
    )
    service.sync_official_on_start()
    assert service.get("test-office") is None
    installed = store.install(
        artifact["artifact_id"], artifact["package_digest"], service
    )
    assert installed.status == "disabled"
