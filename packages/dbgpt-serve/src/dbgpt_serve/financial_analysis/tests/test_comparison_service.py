from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from dbgpt_serve.session_file.api.endpoints import SessionFileApiError

from .conftest import wait_ready
from .fixtures import report_config


def create(service, files=None, config=None, run_id=None):
    run_id = run_id or str(uuid4())
    service.comparisons.create(
        "alice",
        "scope",
        files or ["a", "b"],
        run_id,
        config or report_config(),
        agent_model="synthetic-model",
    )
    return run_id


def test_durable_data_and_owner_session_member_boundaries(isolated_service):
    service, _, calls, _ = isolated_service
    run_id = create(service)
    assert wait_ready(service, run_id)["status"] == "completed"
    report = service.get("alice", "scope", run_id, report=True)
    assert report["mode"] == "comparison" and len(report["documents"]) == 2
    assert all(document["sizeBytes"] == 32 for document in report["documents"])
    assert sorted(calls) == ["a", "b"]
    for owner, scope in [("bob", "scope"), ("alice", "other")]:
        with pytest.raises(SessionFileApiError):
            service.get(owner, scope, run_id, report=True)
    with pytest.raises(SessionFileApiError):
        service.open_source("alice", "scope", run_id, "not-a-member")
    stream, record, _ = service.open_source(
        "alice", "scope", run_id, report["documents"][1]["id"]
    )
    stream.close()
    assert record.file_id == "b"


def test_idempotency_includes_parameters_and_display_order(isolated_service):
    service, _, calls, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    assert create(service, run_id=run_id) == run_id
    for files, config in [
        (["b", "a"], report_config()),
        (["a", "b"], report_config("trend")),
        (["a", "b"], report_config(baseline="b")),
    ]:
        with pytest.raises(SessionFileApiError) as error:
            create(service, files, config, run_id)
        assert error.value.err_code == "RUN_ID_CONFLICT"
    assert len(calls) == 2


def test_duplicate_hash_and_changed_source_cannot_reuse_another_attachment(
    isolated_service,
):
    service, payloads, calls, _ = isolated_service
    payloads["b"]["document"]["sha256"] = payloads["a"]["document"]["sha256"]
    with pytest.raises(SessionFileApiError) as error:
        create(service)
    assert error.value.err_code == "DUPLICATE_DOCUMENT" and not calls
    from .fixtures import extracted

    payloads["b"] = extracted("合成乙股份有限公司", token="b")
    original = service.registry.open_download

    def changed_source(**kwargs):
        stream, record = original(**kwargs)
        if kwargs["file_id"] == "b":
            record.sha256 = "f" * 64
        return stream, record

    service.registry.open_download = changed_source
    run_id = create(service)
    state = wait_ready(service, run_id)
    assert [m["status"] for m in state["members"]] == ["completed", "failed"]
    report = service.get("alice", "scope", run_id, report=True)
    assert not report["comparison"]["ready"] and calls == ["a"]


def test_partial_failure_retries_only_failed_member_even_with_one_worker(
    isolated_service,
):
    service, _, calls, _ = isolated_service
    service._executor.shutdown()
    service._executor = ThreadPoolExecutor(max_workers=1)
    original = service.extractor
    failing = {"c"}

    def extractor(path):
        file_id = path.read_text().rsplit(" ", 1)[1]
        if file_id in failing:
            calls.append(file_id)
            raise ValueError("synthetic failure")
        return original(path)

    service.extractor = extractor
    run_id = create(service, ["a", "b", "c"])
    state = wait_ready(service, run_id)
    assert state["status"] == "completed"
    assert [m["status"] for m in state["members"]] == [
        "completed",
        "completed",
        "failed",
    ]
    report = service.get("alice", "scope", run_id, report=True)
    assert report["comparison"]["ready"]
    failing.clear()
    service.comparisons.resume("alice", "scope", run_id, report["revision"])
    assert wait_ready(service, run_id)["status"] == "completed"
    assert calls.count("a") == calls.count("b") == 1 and calls.count("c") == 2


def test_one_valid_object_is_data_only_and_cannot_publish(isolated_service):
    service, _, _, _ = isolated_service
    original = service.extractor

    def extractor(path):
        if path.read_text().endswith("b"):
            raise ValueError("synthetic failure")
        return original(path)

    service.extractor = extractor
    run_id = create(service)
    wait_ready(service, run_id)
    report = service.get("alice", "scope", run_id, report=True)
    assert report["facts"] and not report["comparison"]["ready"]
    from dbgpt_serve.financial_analysis.workflow import publish

    with pytest.raises(SessionFileApiError):
        publish(report)


def test_ambiguity_resolution_reuses_extraction_and_configuration_keeps_old_version(
    isolated_service,
):
    service, payloads, calls, _ = isolated_service
    payloads["a"]["company_identity"] = {"candidates": ["合成甲", "合成丁"]}
    run_id = create(service)
    wait_ready(service, run_id)
    before = service.get("alice", "scope", run_id, report=True)
    assert before["comparison"]["clarifications"]
    service.comparisons.resume(
        "alice",
        "scope",
        run_id,
        before["revision"],
        {"a": {"company_name": "合成甲股份有限公司", "report_year": "2024"}},
    )
    wait_ready(service, run_id)
    resolved = service.get("alice", "scope", run_id, report=True)
    assert resolved["comparison"]["ready"] and len(calls) == 2
    after = service.comparisons.reconfigure(
        "alice", "scope", run_id, resolved["revision"], report_config(baseline="b")
    )
    assert (
        after["comparison"]["baselineEntityId"]
        != resolved["comparison"]["baselineEntityId"]
    )
    assert (
        service.get(
            "alice", "scope", run_id, report=True, revision=resolved["revision"]
        )
        == resolved
    )
    assert len(calls) == 2
