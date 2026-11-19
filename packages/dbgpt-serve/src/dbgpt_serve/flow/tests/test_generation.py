"""Conversation generation invariants, including races and publish evidence."""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from dbgpt.core.interface.llm import ModelOutput
from dbgpt.storage.metadata import DatabaseManager
from dbgpt_app.operators.taskflow import build_step_marker

from ..api.generation import RunRequest, SaveRequest, debug, save
from ..config import ServeConfig
from ..models.models import ServeDao, ServeEntity
from ..service.generation_service import (
    DraftRequest,
    GenerationResult,
    GenerationService,
    MessageRequest,
    Scope,
    SessionStore,
    Snapshot,
    changes,
    fingerprint,
    validate_candidate,
)
from ..service.service import Service as FlowService

CATALOG = {
    "profiles": [{"id": "react_general"}],
    "models": ["test-model"],
    "tools": ["sql_query", "code"],
    "skills": [],
    "mcp": [],
    "datasources": ["sales"],
    "knowledge": ["manual"],
}
EMPTY = {
    "format": "taskflow/1",
    "nodes": [
        {"id": "s", "kind": "start", "config": {}},
        {"id": "o", "kind": "output", "config": {}},
    ],
    "edges": [["s", "o"]],
}


def agent_flow():
    result = copy.deepcopy(EMPTY)
    result["nodes"].insert(
        1,
        {
            "id": "a",
            "kind": "agent",
            "label": "分析",
            "config": {"goal": "分析输入并交付结论", "tools": []},
        },
    )
    result["edges"] = [["s", "a"], ["a", "o"]]
    return result


def response(source=None, **kwargs):
    return json.dumps(
        {
            "protocol": "generation_result/1",
            "type": "candidate",
            "summary": "已生成",
            "candidate_dsl": source or agent_flow(),
            **kwargs,
        }
    )


@pytest.fixture
def service(tmp_path):
    database = DatabaseManager()
    database.init_db(f"sqlite:///{tmp_path}/sessions.db")
    instance = GenerationService(None, Mock(), SessionStore(database))
    instance.catalog = AsyncMock(return_value=CATALOG)
    instance._model = AsyncMock(return_value=response())
    yield instance
    database.engine.dispose()


def create(service, source=None):
    return service.store.create(
        "owner", {"dsl": source or copy.deepcopy(EMPTY), "meta": {"label": "测试"}}
    )


async def generate(
    service,
    state,
    text="生成一个分析流程，根据用户输入的销售数据分析同比趋势并输出中文总结",
    **kwargs,
):
    request = MessageRequest(
        client_message_id=kwargs.pop("client_message_id", "message"),
        expected_draft_revision=state["draft_revision"],
        expected_context_revision=state["context_revision"],
        text=text,
        **kwargs,
    )
    result = await service.submit(state["session_id"], "owner", request)
    await service.tasks[result["request_id"]]
    return service.get(state["session_id"], "owner")


def test_store_owner_and_compare_and_swap(service):
    state = create(service)
    with pytest.raises(HTTPException) as exc:
        service.store.read(state["session_id"], "other")
    assert exc.value.status_code == 404
    latest, version = service.store.read(state["session_id"], "owner")
    service.store.write(latest, "owner", version)
    with pytest.raises(HTTPException) as exc:
        service.store.write(latest, "owner", version)
    assert exc.value.status_code == 409


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "branch",
        "missing_goal",
        "fake_db",
        "bash",
        "mcp",
        "skill",
        "unknown_config",
    ],
)
def test_invalid_candidates_never_compile(mutation):
    source = agent_flow()
    config = source["nodes"][1]["config"]
    if mutation == "duplicate":
        source["edges"].append(["s", "a"])
    elif mutation == "branch":
        source["edges"].append(["s", "o"])
    elif mutation == "missing_goal":
        config["goal"] = ""
    elif mutation == "fake_db":
        config["datasources"] = ["imaginary"]
    elif mutation == "bash":
        config["tools"] = ["bash"]
    elif mutation == "mcp":
        config["mcp"] = ["http:https://example.com"]
    elif mutation == "skill":
        config["skills"] = ["unverified"]
    else:
        config["parallel_with_prev"] = True
    with pytest.raises(ValueError):
        validate_candidate(source, EMPTY, Scope(), CATALOG)


def test_missing_resources_are_draft_gaps():
    source = agent_flow()
    source["nodes"][1]["config"]["tools"] = ["sql_query"]
    result = validate_candidate(source, EMPTY, Scope(), CATALOG)
    assert result["structure"] == "valid"
    assert result["compile_readiness"] == "pending_configuration"
    assert result["missing_configuration"][0]["field"] == "datasources"


def test_analysis_template_can_be_validated_for_save():
    from pathlib import Path

    source = json.loads(
        (
            Path(__file__).parents[1]
            / "templates/zh/taskflow-db-analysis-template.json"
        ).read_text()
    )["flow"]["taskflow_source"]
    for node in source["nodes"]:
        if "datasources" in node["config"]:
            node["config"]["datasources"] = ["Walmart_Sales"]
    catalog = {
        **CATALOG,
        "profiles": [{"id": "react_data"}, {"id": "react_general"}],
        "datasources": ["Walmart_Sales"],
        "tools": [
            *CATALOG["tools"],
            "html_interpreter",
            "semantic_get_metadata",
            "semantic_search_business",
            "semantic_search_metrics",
            "semantic_get_metric",
        ],
    }
    result = validate_candidate(source, EMPTY, Scope(), catalog)
    assert result["compile_readiness"] == "valid"
    assert result["missing_configuration"] == []


def test_unbound_analysis_template_is_saveable_draft_with_gaps():
    from pathlib import Path

    source = json.loads(
        (
            Path(__file__).parents[1]
            / "templates/zh/taskflow-db-analysis-template.json"
        ).read_text()
    )["flow"]["taskflow_source"]
    result = validate_candidate(
        source,
        source,
        Scope(),
        {**CATALOG, "profiles": [{"id": "react_data"}, {"id": "react_general"}]},
    )
    assert result["compile_readiness"] == "pending_configuration"
    assert len(result["missing_configuration"]) == 5


def test_semantic_tools_require_one_database_and_report_draft_gap():
    source = agent_flow()
    source["nodes"][1]["config"]["tools"] = ["semantic_get_metric"]
    result = validate_candidate(source, EMPTY, Scope(), CATALOG)
    assert result["missing_configuration"][0]["field"] == "datasources"
    source["nodes"][1]["config"]["datasources"] = ["a", "b"]
    with pytest.raises(ValueError, match="只能选择一个"):
        validate_candidate(
            source, EMPTY, Scope(), {**CATALOG, "datasources": ["a", "b"]}
        )


def test_model_cannot_make_resources_required_for_text_only_agent():
    result = validate_candidate(
        agent_flow(),
        EMPTY,
        Scope(),
        CATALOG,
        [{"node_id": "a", "field": "datasources", "message": "仅使用用户输入"}],
    )
    assert result["resource_readiness"] == "ready"
    assert result["missing_configuration"] == []


def test_local_scope_preserves_unselected_nodes():
    original = agent_flow()
    changed = copy.deepcopy(original)
    changed["nodes"][0]["label"] = "偷偷修改"
    with pytest.raises(ValueError, match="超出修改范围"):
        validate_candidate(
            changed, original, Scope(type="nodes", node_ids=["a"]), CATALOG
        )


@pytest.mark.asyncio
async def test_first_candidate_auto_apply_and_monotonic_undo(service):
    state = await generate(service, create(service))
    assert state["candidate"]["status"] == "applied"
    assert state["draft_revision"] == 1
    result = service.undo(state["session_id"], "owner")
    assert result["snapshot"]["dsl"] == EMPTY
    assert result["draft_revision"] == 2
    assert result["context_revision"] == 1


@pytest.mark.asyncio
async def test_clarification_keeps_canvas_and_validates_answer_id(service):
    service._model.return_value = json.dumps(
        {
            "protocol": "generation_result/1",
            "type": "clarification",
            "summary": "需要明确方向",
            "questions": [
                {
                    "question_id": "direction",
                    "text": "分析什么方向？",
                    "options": ["趋势", "归因"],
                }
            ],
        }
    )
    state = await generate(service, create(service))
    assert state["snapshot"]["dsl"] == EMPTY
    assert state["questions"][0]["question_id"] == "direction"
    with pytest.raises(HTTPException) as exc:
        await service.submit(
            state["session_id"],
            "owner",
            MessageRequest(
                client_message_id="answer",
                expected_draft_revision=0,
                expected_context_revision=1,
                text="趋势",
                answers={"obsolete": "趋势"},
            ),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_existing_flow_preview_apply_is_idempotent(service):
    state = create(service, agent_flow())
    source = agent_flow()
    source["nodes"][1]["config"]["goal"] = "额外标注证据"
    service._model.return_value = response(source)
    state = await generate(service, state)
    assert state["candidate"]["status"] == "pending"
    assert state["draft_revision"] == 0
    cid = state["candidate"]["candidate_id"]
    applied = await service.candidate_action(state["session_id"], "owner", cid, "apply")
    repeated = await service.candidate_action(
        state["session_id"], "owner", cid, "apply"
    )
    assert applied["draft_revision"] == repeated["draft_revision"] == 1
    assert applied["snapshot"]["dsl"] == source


@pytest.mark.asyncio
async def test_manual_edit_invalidates_candidate_and_undo(service):
    state = await generate(service, create(service, agent_flow()))
    snapshot = copy.deepcopy(state["snapshot"])
    snapshot["dsl"]["nodes"][1]["config"]["goal"] = "手动编辑"
    synced = service.sync(
        state["session_id"],
        "owner",
        DraftRequest(
            expected_draft_revision=0,
            snapshot=Snapshot(**snapshot),
        ),
    )
    assert synced["candidate"]["status"] == "stale"
    with pytest.raises(HTTPException):
        await service.candidate_action(
            state["session_id"], "owner", state["candidate"]["candidate_id"], "apply"
        )
    with pytest.raises(HTTPException):
        service.undo(state["session_id"], "owner")


@pytest.mark.asyncio
async def test_two_repairs_then_success(service):
    service._model.side_effect = ["bad JSON", response({"format": "wrong"}), response()]
    state = await generate(service, create(service))
    assert service._model.await_count == 3
    assert state["candidate"]["status"] == "applied"


@pytest.mark.asyncio
async def test_repair_exhaustion_preserves_canvas(service):
    service._model.return_value = "broken"
    state = await generate(service, create(service))
    assert service._model.await_count == 3
    assert state["snapshot"]["dsl"] == EMPTY
    assert next(iter(state["requests"].values()))["status"] == "failed"


@pytest.mark.asyncio
async def test_cancel_rejects_late_model_result(service):
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(*args):
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            # Simulate a provider that cannot abort its upstream HTTP call.
            return response()
        return response()

    service._model.side_effect = slow
    state = create(service)
    req = await service.submit(
        state["session_id"],
        "owner",
        MessageRequest(
            client_message_id="cancel",
            expected_draft_revision=0,
            expected_context_revision=0,
            text="生成",
        ),
    )
    await started.wait()
    task = service.tasks[req["request_id"]]
    service.cancel(state["session_id"], "owner", req["request_id"])
    release.set()
    await task
    state = service.get(state["session_id"], "owner")
    assert state["candidate"] is None
    assert state["snapshot"]["dsl"] == EMPTY
    assert state["requests"][req["request_id"]]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_edit_during_generation_rejects_late_result(service):
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(*args):
        started.set()
        await release.wait()
        return response()

    service._model.side_effect = slow
    state = create(service)
    req = await service.submit(
        state["session_id"],
        "owner",
        MessageRequest(
            client_message_id="race",
            expected_draft_revision=0,
            expected_context_revision=0,
            text="生成",
        ),
    )
    await started.wait()
    task = service.tasks[req["request_id"]]
    snapshot = copy.deepcopy(state["snapshot"])
    snapshot["meta"]["label"] = "我的新标题"
    service.sync(
        state["session_id"],
        "owner",
        DraftRequest(
            expected_draft_revision=0,
            snapshot=Snapshot(**snapshot),
        ),
    )
    release.set()
    await task
    latest = service.get(state["session_id"], "owner")
    assert latest["candidate"] is None
    assert latest["snapshot"]["meta"]["label"] == "我的新标题"
    assert latest["requests"][req["request_id"]]["status"] == "failed"


@pytest.mark.asyncio
async def test_publish_requires_server_evidence(service):
    state = create(service, agent_flow())
    with pytest.raises(HTTPException) as exc:
        await save(
            state["session_id"],
            SaveRequest(
                expected_draft_revision=0,
                publish=True,
            ),
            "owner",
            service,
        )
    assert exc.value.status_code == 409
    service.flow_service.update_flow.assert_not_called()


@pytest.mark.asyncio
async def test_formal_draft_save_with_real_dao(service):
    database = service.store.database
    ServeEntity.__table__.create(database.engine, checkfirst=True)
    dao = ServeDao(ServeConfig())
    dao._db_manager = database
    service.flow_service.dao = dao
    service.flow_service.get.side_effect = dao.get_one
    service.flow_service._maybe_compile_taskflow.side_effect = lambda flow: (
        FlowService._maybe_compile_taskflow(service.flow_service, flow)
    )
    state = create(service, agent_flow())
    result = await save(
        state["session_id"], SaveRequest(expected_draft_revision=0), "owner", service
    )
    saved = result.data
    uid = saved["snapshot"]["meta"]["uid"]
    assert uid
    assert saved["dirty"] is False
    assert dao.get_one({"uid": uid}).taskflow_source == agent_flow()
    service.flow_service.create_and_save_dag.assert_not_called()
    service.flow_service.update_flow.assert_not_called()


@pytest.mark.asyncio
async def test_save_published_draft_does_not_touch_live_definition(service):
    state = create(service, agent_flow())
    service.flow_service.get.return_value = SimpleNamespace(
        uid="live",
        name="flow",
        state="running",
    )
    await save(
        state["session_id"],
        SaveRequest(
            expected_draft_revision=0,
        ),
        "owner",
        service,
    )
    service.flow_service.update_flow.assert_not_called()
    service.flow_service.create_and_save_dag.assert_not_called()
    service.flow_service.dao.update.assert_not_called()


def test_change_summary_is_computed_on_server():
    source = agent_flow()
    diff = changes(EMPTY, source)
    assert [item["type"] for item in diff] == ["added", "edges"]
    assert fingerprint(source) == fingerprint(copy.deepcopy(source))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["success", "provider_error", "running_only", "failed_marker", "no_marker"]
)
async def test_debug_requires_real_terminal_and_successful_steps(service, mode):
    state = create(service, agent_flow())

    async def outputs(*args, **kwargs):
        if mode != "no_marker":
            status = {
                "success": "success",
                "provider_error": "success",
                "running_only": "running",
                "failed_marker": "failed",
            }[mode]
            yield ModelOutput(
                error_code=0, text=build_step_marker("a", "分析", "agent", status)
            )
        yield ModelOutput(
            error_code=1 if mode == "provider_error" else 0,
            text="provider failed" if mode == "provider_error" else "分析结果",
        )

    service.flow_service.debug_flow = outputs
    response = await debug(
        state["session_id"],
        RunRequest(expected_draft_revision=0, model="test-model", question="分析"),
        "owner",
        service,
    )
    events = [chunk async for chunk in response.body_iterator]
    latest = service.get(state["session_id"], "owner")
    assert latest["run"]["status"] == ("success" if mode == "success" else "failed")
    assert '"run_completed": true' in events[-1]


@pytest.mark.asyncio
async def test_terse_first_request_cannot_auto_apply_expanded_scope(service):
    state = await generate(service, create(service), text="分析销售情况")
    assert state["snapshot"]["dsl"] == EMPTY
    assert state["candidate"] is None
    assert state["questions"][0]["question_id"] == "confirm_requirements"
    assert service._model.await_count == 1


@pytest.mark.asyncio
async def test_local_result_can_echo_unchanged_metadata(service):
    state = create(service, agent_flow())
    source = agent_flow()
    source["nodes"][1]["config"]["goal"] = "添加行动建议"
    result = json.loads(response(source, flow_meta={"label": "测试"}))
    result.pop("protocol")
    service._model.return_value = json.dumps(result)
    latest = await generate(service, state, scope=Scope(type="nodes", node_ids=["a"]))
    assert latest["candidate"]["status"] == "pending"
    assert latest["candidate"]["flow_meta"] == {}
    assert latest["snapshot"] == state["snapshot"]
    assert service._model.await_count == 1
    with pytest.raises(ValueError):
        GenerationResult.model_validate({**result, "protocol": "unknown/2"})


@pytest.mark.asyncio
async def test_generator_cannot_switch_to_unselected_model(service):
    catalog = copy.deepcopy(CATALOG)
    catalog["models"].append("other-model")
    service.catalog.return_value = catalog
    source = agent_flow()
    source["nodes"][1]["config"]["model"] = "other-model"
    service._model.side_effect = [response(source), response()]
    state = await generate(service, create(service), model="test-model")
    assert state["candidate"]["status"] == "applied"
    assert service._model.await_count == 2
    assert "model" not in state["snapshot"]["dsl"]["nodes"][1]["config"]
    context = service._model.call_args_list[0].args[1]
    assert context["catalog"]["models"] == ["test-model"]


@pytest.mark.asyncio
async def test_unconfirmed_initial_assumptions_require_clarification(service):
    service._model.return_value = response(assumptions=["默认按地区分析下降原因"])
    state = await generate(service, create(service), text="分析销售情况")
    assert state["snapshot"]["dsl"] == EMPTY
    assert state["candidate"] is None
    assert state["questions"][0]["question_id"] == "confirm_requirements"
    assert service._model.await_count == 1
    service._model.return_value = response(assumptions=["用户输入提供数据"])
    continued = await generate(
        service,
        state,
        text="分析同比趋势",
        client_message_id="answer",
        answers={"confirm_requirements": "分析同比趋势"},
    )
    assert continued["candidate"]["status"] == "applied"


@pytest.mark.asyncio
async def test_model_cannot_autoselect_database(service):
    source = agent_flow()
    source["nodes"][1]["config"].update(tools=["sql_query"], datasources=["sales"])
    service._model.return_value = response(source)
    state = await generate(service, create(service), text="分析销售趋势")
    assert state["candidate"] is None
    assert state["snapshot"]["dsl"] == EMPTY
    assert state["questions"][0]["question_id"] == "resource_datasources"
    assert service._model.await_count == 1


@pytest.mark.asyncio
async def test_inline_credentials_never_reach_model(service):
    source = agent_flow()
    source["nodes"][1]["config"]["api_key"] = "a-secret-for-test"
    state = await generate(service, create(service, source))
    service._model.assert_not_awaited()
    assert state["snapshot"]["dsl"] == source


@pytest.mark.asyncio
async def test_edit_invalidates_successful_run(service):
    state = create(service, agent_flow())
    stored, version = service.store.read(state["session_id"], "owner")
    stored["run"] = {
        "status": "success",
        "draft_revision": 0,
        "snapshot_fingerprint": fingerprint(stored["snapshot"]),
        "catalog_version": fingerprint(CATALOG),
    }
    service.store.write(stored, "owner", version)
    snapshot = copy.deepcopy(state["snapshot"])
    snapshot["meta"]["label"] = "新版本"
    service.sync(
        state["session_id"],
        "owner",
        DraftRequest(
            expected_draft_revision=0,
            snapshot=Snapshot(**snapshot),
        ),
    )
    with pytest.raises(HTTPException) as exc:
        await save(
            state["session_id"],
            SaveRequest(
                expected_draft_revision=1,
                publish=True,
            ),
            "owner",
            service,
        )
    assert exc.value.status_code == 409
