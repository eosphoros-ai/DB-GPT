"""Stateful structured TaskFlow generation, independent of workflow execution.

The metadata database holds editing checkpoints and request results. Every write
uses compare-and-swap, including writes from late model responses. No candidate
is registered as a DAG. Deployments are explicit and require server run evidence.
"""

import asyncio
import copy
import hashlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

from fastapi import HTTPException
from sqlalchemy import Column, Integer, String, Text

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.storage.metadata import Model, db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def generation_budget(seconds: float):
    """Bound the whole turn, including catalog access, on Python 3.10+."""
    task = asyncio.current_task()
    timed_out = False

    def expire():
        nonlocal timed_out
        timed_out = True
        task.cancel()

    timer = asyncio.get_running_loop().call_later(seconds, expire)
    try:
        yield
    except asyncio.CancelledError:
        if timed_out:
            raise TimeoutError("生成超时，请缩小需求后重试") from None
        raise
    finally:
        timer.cancel()


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def flow_fingerprint(source: dict, meta: dict) -> str:
    """Stable saved definition identity, independent of lifecycle state."""
    return fingerprint(
        {
            "dsl": source,
            "meta": {key: meta.get(key) for key in ("name", "label", "description")},
        }
    )


def check_model_context(value: Any) -> None:
    """Refuse inline credentials; the generator only consumes resource refs."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {
                "api_key",
                "apikey",
                "password",
                "db_pwd",
                "token",
                "secret",
                "authorization",
            }:
                raise ValueError("流程含内联凭据，请移除凭据并使用资源引用")
            if key == "mcp" and isinstance(child, list):
                if any("?" in url or "@" in url for url in child):
                    raise ValueError("MCP URL 可能包含凭据，请使用无凭据的资源引用")
            check_model_context(child)
    elif isinstance(value, list):
        for child in value:
            check_model_context(child)


class GenerationSessionEntity(Model):
    __tablename__ = "taskflow_generation_session"

    id = Column(String(64), primary_key=True)
    owner = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=0)
    data = Column(Text, nullable=False)


class SessionStore:
    def __init__(self, database=None):
        self.database = database or db
        self._ready = False

    def ensure_table(self) -> None:
        if not self._ready:
            GenerationSessionEntity.__table__.create(
                self.database.engine, checkfirst=True
            )
            self._ready = True

    def create(self, owner: str, snapshot: dict) -> dict:
        self.ensure_table()
        state = {
            "session_id": uuid.uuid4().hex,
            "draft_revision": 0,
            "context_revision": 0,
            "snapshot": snapshot,
            "messages": [],
            "confirmed_turns": [],
            "questions": [],
            "requests": {},
            "candidate": None,
            "undo": None,
            "run": None,
            "dirty": False,
            "published": [],
            "flow_base_fingerprint": (
                flow_fingerprint(snapshot["dsl"], snapshot["meta"])
                if snapshot["meta"].get("uid")
                else None
            ),
        }
        with self.database.session() as session:
            session.add(
                GenerationSessionEntity(
                    id=state["session_id"],
                    owner=owner,
                    version=0,
                    data=json.dumps(state, ensure_ascii=False),
                )
            )
        return state

    def read(self, sid: str, owner: str) -> tuple:
        self.ensure_table()
        with self.database.session() as session:
            row = (
                session.query(GenerationSessionEntity)
                .filter_by(id=sid, owner=owner)
                .first()
            )
            if not row:
                raise HTTPException(404, "编辑会话不存在或无权访问")
            return json.loads(row.data), row.version

    def write(self, state: dict, owner: str, version: int) -> None:
        with self.database.session() as session:
            changed = (
                session.query(GenerationSessionEntity)
                .filter_by(id=state["session_id"], owner=owner, version=version)
                .update(
                    {
                        "data": json.dumps(state, ensure_ascii=False),
                        "version": version + 1,
                    },
                    synchronize_session=False,
                )
            )
            if changed != 1:
                raise HTTPException(409, "编辑版本已改变，请重试当前操作")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Snapshot(StrictModel):
    dsl: Dict[str, Any]
    meta: Dict[str, Any] = Field(default_factory=dict)


class DraftRequest(StrictModel):
    expected_draft_revision: int
    snapshot: Snapshot


class Scope(StrictModel):
    type: Literal["flow", "nodes"] = "flow"
    node_ids: List[str] = Field(default_factory=list)


class MessageRequest(StrictModel):
    client_message_id: str = Field(min_length=1, max_length=128)
    expected_draft_revision: int
    expected_context_revision: int
    text: str = Field(min_length=1, max_length=8000)
    model: Optional[str] = None
    scope: Scope = Field(default_factory=Scope)
    answers: Dict[str, str] = Field(default_factory=dict)
    replace_candidate: bool = False


class Question(StrictModel):
    question_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=1000)
    options: List[str] = Field(default_factory=list, max_length=6)


class Gap(StrictModel):
    node_id: str
    field: Literal["datasources", "knowledge"]
    message: str


class GenerationResult(StrictModel):
    # This version is negotiated by our output function, not inferred by the LLM.
    protocol: Literal["generation_result/1"] = "generation_result/1"
    type: Literal["clarification", "candidate", "failure"]
    summary: str = Field(min_length=1, max_length=3000)
    questions: List[Question] = Field(default_factory=list, max_length=3)
    candidate_dsl: Optional[Dict[str, Any]] = None
    flow_meta: Dict[str, str] = Field(default_factory=dict)
    assumptions: List[str] = Field(default_factory=list)
    missing_configuration: List[Gap] = Field(default_factory=list)


class NeedsResourceChoice(Exception):
    """A business question, not an invalid output to guess away in repairs."""

    def __init__(self, field: str, catalog: dict):
        label = "数据源" if field == "datasources" else "知识库"
        self.summary = f"需要先确认{label}，当前画布保持不变。"
        self.questions = [
            Question(
                question_id=f"resource_{field}",
                text=f"要使用哪个{label}？也可以说明只使用用户提供的数据。",
                options=[*catalog[field][:4], "只使用用户提供的数据"],
            )
        ]


SAFE_TOOLS = {
    "sql_query",
    "knowledge_retrieve",
    "code",
    "html_interpreter",
    "semantic_get_metadata",
    "semantic_search_business",
    "semantic_search_metrics",
    "semantic_get_metric",
}
AGENT_FIELDS = {
    "agent_profile",
    "goal",
    "model",
    "tools",
    "skills",
    "datasources",
    "knowledge",
    "mcp",
    "max_turns",
    "parallel_group",
}


def generation_schema() -> dict:
    """Constrain nested DSL/config too, not only the outer result envelope."""
    schema = GenerationResult.model_json_schema()
    config = {
        "type": "object",
        "additionalProperties": False,
        "required": ["goal"],
        "properties": {
            "goal": {"type": "string", "minLength": 1},
            "agent_profile": {"type": "string"},
            "model": {"type": "string"},
            "max_turns": {"type": "integer", "minimum": 1, "maximum": 30},
            "parallel_group": {"type": "string"},
            **{
                key: {"type": "array", "items": {"type": "string"}}
                for key in ("tools", "skills", "datasources", "knowledge", "mcp")
            },
        },
    }
    common = {
        "id": {"type": "string"},
        "label": {"type": "string"},
    }
    variants = [
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "kind", "config"],
            "properties": {
                **common,
                "kind": {"const": "agent"},
                "config": config,
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "kind", "config"],
            "properties": {
                **common,
                "kind": {"enum": ["start", "output"]},
                "config": {"type": "object"},
            },
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "kind", "config"],
            "properties": {
                **common,
                "kind": {
                    "enum": [
                        "db_query",
                        "file_data",
                        "ai_analysis",
                        "visualize",
                        "human_confirm",
                        "report",
                    ]
                },
                "config": {"type": "object"},
            },
            "description": "仅用于原样保留已有历史节点，禁止新增或修改。",
        },
    ]
    schema["properties"]["candidate_dsl"] = {
        "anyOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["format", "nodes", "edges"],
                "properties": {
                    "format": {"const": "taskflow/1"},
                    "nodes": {"type": "array", "items": {"oneOf": variants}},
                    "edges": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                    },
                    "viewport": {"type": "object"},
                },
            },
            {"type": "null"},
        ],
    }
    schema["properties"]["flow_meta"] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "label": {"type": "string"},
            "description": {"type": "string"},
        },
    }
    return schema


def validate_candidate(
    source: dict,
    before: dict,
    scope: Scope,
    catalog: dict,
    declared_gaps: Optional[List[dict]] = None,
) -> dict:
    """Validate references, staged Agent topology, scope and generation policy."""
    from ..taskflow.dsl import parse_dsl, topo_order, validate_dsl
    from ..taskflow.nodes import NODE_KINDS

    if set(source) - {"format", "nodes", "edges", "viewport"}:
        raise ValueError("流程包含未知字段")
    if source.get("format") != "taskflow/1":
        raise ValueError("流程格式必须是 taskflow/1")
    for raw in source.get("nodes", []):
        if set(raw) - {"id", "kind", "label", "config"}:
            raise ValueError("节点包含未知字段")
    dsl = parse_dsl(source)
    validate_dsl(dsl, NODE_KINDS)
    if len(dsl.nodes) > 32:
        raise ValueError("首版最多支持 32 个节点")
    if len(set(dsl.edges)) != len(dsl.edges):
        raise ValueError("不允许重复连线")
    order = topo_order(dsl)
    if set(dsl.edges) != set(zip(order, order[1:])):
        # Permit explicit Agent fork/join stages, never an accidental bypass.
        remaining = {node.id: node for node in dsl.nodes}
        completed = set()
        stages = {}
        stage = 0
        while remaining:
            ready = [
                node
                for node in remaining.values()
                if all(src in completed for src, tgt in dsl.edges if tgt == node.id)
            ]
            if not ready:
                raise ValueError("流程存在未满足的依赖")
            if len(ready) > 1 and (
                len(ready) != 2
                or any(node.kind != "agent" for node in ready)
                or not ready[0].config.get("parallel_group")
                or len({node.config.get("parallel_group") for node in ready}) != 1
            ):
                raise ValueError("并行阶段需要两个独立 Agent 使用相同的并行分组")
            if any(node.kind == "output" for node in ready) and len(remaining) != 1:
                raise ValueError("输出必须等待全部分支完成")
            for node in ready:
                stages[node.id] = stage
                completed.add(node.id)
                remaining.pop(node.id)
            stage += 1
        if any(stages[tgt] != stages[src] + 1 for src, tgt in dsl.edges):
            raise ValueError("连线不能绕过执行阶段，请使用完整的并行汇合结构")
    old = {n["id"]: n for n in before["nodes"]}
    new = {n["id"]: n for n in source["nodes"]}
    if scope.type == "nodes":
        selected = set(scope.node_ids)
        if not selected or not selected <= old.keys():
            raise ValueError("请先选择要修改的节点")
        if set(old) != set(new) or before["edges"] != source["edges"]:
            raise ValueError("局部修改不能增删节点或调整连线，请选择整个流程")
        for nid in old.keys() - selected:
            if old[nid] != new[nid]:
                raise ValueError(f"超出修改范围：{nid}")
    gaps = []
    profiles = {p["id"] for p in catalog["profiles"]}
    for node in source["nodes"]:
        unchanged = old.get(node["id"]) == node
        if node["kind"] not in {"start", "agent", "output"}:
            if not unchanged:
                raise ValueError("新增和修改的业务节点必须为 Agent")
            continue
        if node["kind"] != "agent":
            continue
        config = node.get("config", {})
        if not isinstance(config.get("goal"), str) or not config["goal"].strip():
            raise ValueError(f"{node['id']} 缺少 Agent 目标")
        if set(config) - AGENT_FIELDS and not unchanged:
            extra = sorted(set(config) - AGENT_FIELDS)
            raise ValueError(
                f"{node['id']}.config 未知字段 {extra}，请移除。"
                "名称用节点 label，画像用 agent_profile，目标和交接只写在 goal。"
            )
        if not unchanged:
            if config.get("skills") or config.get("mcp"):
                raise ValueError("首版生成暂不支持技能脚本或 MCP，请保留手动配置")
            if not set(config.get("tools", [])) <= SAFE_TOOLS:
                raise ValueError("首版生成只支持只读查询、检索、计算和报告工具")
        if config.get("agent_profile", "react_general") not in profiles:
            raise ValueError("Agent 画像不存在")
        if config.get("model") and config["model"] not in catalog["models"]:
            raise ValueError(f"模型不可用：{config['model']}")
        for field in ("tools", "skills", "mcp", "datasources", "knowledge"):
            values = config.get(field, [])
            if not isinstance(values, list) or any(
                not isinstance(value, str) for value in values
            ):
                raise ValueError(f"{node['id']}.{field} 必须是字符串数组")
        for field in ("datasources", "knowledge"):
            if not set(config.get(field, [])) <= set(catalog[field]):
                raise ValueError(f"{node['id']} 引用了不存在的 {field}")
        turns = config.get("max_turns", 10)
        if type(turns) is not int or not 1 <= turns <= 30:
            raise ValueError("max_turns 必须为 1–30 的整数")
        tools = set(config.get("tools", []))
        for tool, field in (
            ("sql_query", "datasources"),
            ("semantic_get_metadata", "datasources"),
            ("semantic_search_business", "datasources"),
            ("semantic_search_metrics", "datasources"),
            ("semantic_get_metric", "datasources"),
            ("knowledge_retrieve", "knowledge"),
        ):
            if (
                tool in tools
                and not config.get(field)
                and not any(
                    gap["node_id"] == node["id"] and gap["field"] == field
                    for gap in gaps
                )
            ):
                gaps.append(
                    {
                        "node_id": node["id"],
                        "field": field,
                        "message": f"{node.get('label') or node['id']}：请选择{field}",
                    }
                )
        if (
            any(tool.startswith("semantic_") for tool in tools)
            and len(config.get("datasources", [])) > 1
        ):
            raise ValueError(f"{node['id']} 的语义工具需要且只能选择一个数据源")
    for gap in declared_gaps or []:
        if gap["node_id"] not in new:
            raise ValueError("配置缺口引用了不存在的节点")
        required_tool = {
            "datasources": "sql_query",
            "knowledge": "knowledge_retrieve",
        }[gap["field"]]
        if required_tool not in new[gap["node_id"]].get("config", {}).get("tools", []):
            # The model may describe "no database needed" as a gap. Only
            # configured capabilities can make a resource mandatory.
            continue
        if not new[gap["node_id"]].get("config", {}).get(gap["field"]):
            if not any(
                g["node_id"] == gap["node_id"] and g["field"] == gap["field"]
                for g in gaps
            ):
                gaps.append(gap)
    from ..taskflow import compile_taskflow

    if not gaps:
        compile_taskflow(source)
    return {
        "structure": "valid",
        "resource_readiness": "incomplete" if gaps else "ready",
        "compile_readiness": "pending_configuration" if gaps else "valid",
        "missing_configuration": gaps,
    }


def changes(before: dict, after: dict) -> List[dict]:
    old = {n["id"]: n for n in before["nodes"]}
    new = {n["id"]: n for n in after["nodes"]}
    diff = []
    for nid in dict.fromkeys([*old, *new]):
        a, b = old.get(nid), new.get(nid)
        if a == b:
            continue
        fields = [
            key
            for key in set((a or {}).get("config", {}))
            | set((b or {}).get("config", {}))
            if (a or {}).get("config", {}).get(key)
            != (b or {}).get("config", {}).get(key)
        ]
        diff.append(
            {
                "node_id": nid,
                "label": (b or a).get("label") or nid,
                "type": "added" if a is None else "removed" if b is None else "updated",
                "fields": sorted(fields),
                "before": a,
                "after": b,
            }
        )
    if before["edges"] != after["edges"]:
        diff.append({"type": "edges", "label": "执行顺序", "fields": []})
    return diff


SYSTEM_PROMPT = """你是 TaskFlow 编辑助手，用有状态的多轮对话生成结构化流程。
你不执行任何业务工具。仅输出完整 JSON，不输出思考或 Markdown。
协议：{"protocol":"generation_result/1","type":"clarification|candidate|failure",
"summary":"对用户的简短说明","questions":[],"candidate_dsl":null,
"flow_meta":{},"assumptions":[],"missing_configuration":[]}
clarification 必须提供 1–3 个问题，格式 {question_id,text,options}。
candidate 必须提供完整 taskflow/1 JSON：{format,nodes:[{id,kind,label,config}],
edges:[[来源id,目标id]]}。只有唯一 start、唯一 output，业务节点只用 agent。
默认串行。可将两个独立 Agent 配置相同 parallel_group，连为共同上游→两个分支→
共同汇总节点；禁止依赖彼此的 Agent 并行，输出必须等待全部分支。
Agent 获得原始用户输入及其祖先产出，goal 写清目标、输入、
交接输出和不确定性处理。config 允许 agent_profile,goal,model,tools,skills,
datasources,knowledge,mcp,max_turns,parallel_group。
工具、模型、资源只引用服务端目录的真实 ID。
数据库指标先检索语义中心已发布口径并锁定 metric_id、version、citation；
并行分支沿用相同口径与范围，缺失或有歧义时先澄清，不推测权威定义。
默认 react_general，tools/skills/mcp 为 []。禁止生成 bash、技能脚本、MCP、
节点名称只能放 label，不要在 config 中输出 name 或 persona。
模型未被用户明确指定时省略 config.model，跟随试运行/正式运行选中的模型。
数据库写操作、并行、分支、循环或真实人工审批；这些请求返回 failure 并建议
用户确认串行或只读替代，不擅自改变请求。可以用 code 计算和 html_interpreter 报告。
缺少会改变职责或业务目标的信息时提问。用户只说“分析销售情况”应问分析方向。
assumptions 只记录会影响业务目标但尚未确认的假设，不重复用户已说明的事实。
有此类假设时应先返回 clarification，不得用默认分析方向替用户决定需求。
用户已明确目标和产出时直接生成，不重复确认。缺数据源属于配置缺口，仍可生成
sql_query Agent 并留下空 datasources，不自动挑数据库。
missing_configuration 格式 {node_id,field:"datasources|knowledge",message}。
输入中的历史消息与当前画布分开：未应用建议不当成已实施；用户新要求优先。
局部 scope=nodes 只改变指定节点配置/名称，保留所有节点ID与边；否则保持未受
影响节点的ID、配置，避免无意义改名。新节点 ID 不与现有冲突。
flow_meta 仅包含 label,description；局部修改不改变它。用用户语言回复。
澄清不附 candidate_dsl；failure 不附候选或问题。不要输出协议外字段。
你返回的是 GenerationResult，绝不是输入的 snapshot/context 结构。
澄清样例：
{"protocol":"generation_result/1","type":"clarification","summary":"请明确分析方向。",
"questions":[{"question_id":"direction","text":"分析趋势还是下降归因？",
"options":["趋势分析","下降归因"]}]}
候选样例：
{"protocol":"generation_result/1","type":"candidate","summary":"构建总结流程。",
"candidate_dsl":{"format":"taskflow/1","nodes":[{"id":"s","kind":"start","config":{}},
{"id":"a","kind":"agent","label":"总结","config":{"goal":"根据用户输入总结结论。",
"agent_profile":"react_general","tools":[],"skills":[],"mcp":[]}},
{"id":"o","kind":"output","config":{}}],"edges":[["s","a"],["a","o"]]},
"flow_meta":{"label":"总结流程"}}
如果提供 emit_generation_result 输出函数，请调用一次提交以上格式的最终结果；
这是结构化输出容器，不是业务工具，不进行任何业务操作。"""


class GenerationService:
    def __init__(self, system_app, flow_service, store=None):
        self.system_app = system_app
        self.flow_service = flow_service
        self.store = store or SessionStore()
        self.tasks: Dict[str, asyncio.Task] = {}
        self.runtime_revision = uuid.uuid4().hex

    async def catalog(self) -> dict:
        from dbgpt.model.cluster import WorkerManagerFactory
        from dbgpt.model.cluster.client import DefaultLLMClient
        from dbgpt_app.operators.agent_runner import list_agent_profiles
        from dbgpt_serve.datasource.service.service import Service as Datasources
        from dbgpt_serve.model.models.models import ModelProviderConfigEntity
        from dbgpt_serve.rag.service.service import Service as Knowledge
        from dbgpt_serve.rag.service.service import SpaceServeRequest

        client = DefaultLLMClient(
            WorkerManagerFactory.get_instance(self.system_app).create()
        )
        models = [m.model for m in await client.models()]
        # These services are instance-scoped in the existing API, not per-user.
        datasource_items = Datasources.get_instance(self.system_app).get_list()
        knowledge_items = Knowledge.get_instance(self.system_app).get_list(
            SpaceServeRequest()
        )
        datasources = [d.db_name for d in datasource_items if d.db_name]
        knowledge = [k.name for k in knowledge_items]
        with db.session() as session:
            provider_revisions = [
                [provider, str(modified)]
                for provider, modified in session.query(
                    ModelProviderConfigEntity.provider,
                    ModelProviderConfigEntity.gmt_modified,
                ).all()
            ]
        return {
            "profiles": list_agent_profiles(),
            "tools": sorted(SAFE_TOOLS),
            "skills": [],
            "mcp": [],
            "models": models,
            "datasources": datasources,
            "knowledge": knowledge,
            "resource_revisions": {
                "datasources": [
                    [d.db_name, fingerprint(d.params)] for d in datasource_items
                ],
                "knowledge": [
                    [k.name, str(getattr(k, "gmt_modified", ""))]
                    for k in knowledge_items
                ],
                "providers": provider_revisions,
                "runtime": self.runtime_revision,
            },
        }

    def get(self, sid: str, owner: str) -> dict:
        state, version = self.store.read(sid, owner)
        # Persisted deadlines recover requests after a process restart and do
        # not incorrectly cancel a request running in another API worker.
        changed = False
        for rid, req in state["requests"].items():
            if req["status"] == "running" and time.time() > req.get("expires_at", 0):
                req.update(status="failed", error="任务已超时或服务已重启，请重新生成")
                changed = True
        if changed:
            self.store.write(state, owner, version)
        return state

    def sync(self, sid: str, owner: str, request: DraftRequest) -> dict:
        state, version = self.store.read(sid, owner)
        if request.expected_draft_revision != state["draft_revision"]:
            raise HTTPException(409, "画布版本冲突，本地修改已保留，请刷新后核对")
        snapshot = request.snapshot.model_dump()
        if len(json.dumps(snapshot)) > 150000:
            raise HTTPException(422, "流程过大")
        # Client metadata must not switch the session to another published UID.
        for key in ("uid", "name", "state"):
            if key in state["snapshot"]["meta"]:
                snapshot["meta"][key] = state["snapshot"]["meta"][key]
            else:
                snapshot["meta"].pop(key, None)
        if snapshot != state["snapshot"]:
            state["snapshot"] = snapshot
            state["draft_revision"] += 1
            state["dirty"] = True
            state["run"] = None
            state["undo"] = None
            if state["candidate"] and state["candidate"]["status"] == "pending":
                state["candidate"]["status"] = "stale"
            elif state["candidate"] and state["candidate"]["status"] == "applied":
                by_id = {n["id"]: n for n in snapshot["dsl"]["nodes"]}
                state["candidate"]["missing_configuration"] = [
                    gap
                    for gap in state["candidate"]["missing_configuration"]
                    if not by_id.get(gap["node_id"], {})
                    .get("config", {})
                    .get(gap["field"])
                ]
            self.store.write(state, owner, version)
        return state

    async def submit(self, sid: str, owner: str, request: MessageRequest) -> dict:
        state, version = self.store.read(sid, owner)
        for req in state["requests"].values():
            if req["client_message_id"] == request.client_message_id:
                if req["input_fingerprint"] != fingerprint(request.model_dump()):
                    raise HTTPException(409, "重复请求 ID 对应不同内容")
                return req
        if (
            request.expected_draft_revision != state["draft_revision"]
            or request.expected_context_revision != state["context_revision"]
        ):
            raise HTTPException(409, "需求或画布已改变，请基于最新版本重新生成")
        if any(r["status"] == "running" for r in state["requests"].values()):
            raise HTTPException(409, "已有生成任务，请先取消")
        candidate = state["candidate"]
        if candidate and candidate["status"] == "pending":
            if not request.replace_candidate:
                raise HTTPException(409, "请先应用、放弃或选择替换候选")
            candidate["status"] = "discarded"
        question_ids = {q["question_id"] for q in state["questions"]}
        if not set(request.answers) <= question_ids:
            raise HTTPException(409, "回答引用了过期问题")
        if request.scope.type == "nodes":
            ids = {n["id"] for n in state["snapshot"]["dsl"]["nodes"]}
            if not request.scope.node_ids or not set(request.scope.node_ids) <= ids:
                raise HTTPException(422, "请选择有效的修改节点")
        rid = uuid.uuid4().hex
        req = {
            "request_id": rid,
            "client_message_id": request.client_message_id,
            "status": "running",
            "phase": "理解需求",
            "base_draft_revision": state["draft_revision"],
            "base_context_revision": state["context_revision"],
            "expires_at": time.time() + 185,
            "input_fingerprint": fingerprint(request.model_dump()),
        }
        state["requests"][rid] = req
        state["messages"].append({"role": "user", "text": request.text})
        state.setdefault("confirmed_turns", []).append(
            {"text": request.text, "answers": request.answers}
        )
        # Explicit user turns are authoritative requirements; guesses never are.
        state["context_revision"] += 1
        self.store.write(state, owner, version)
        self.tasks[rid] = asyncio.create_task(
            self._generate(sid, owner, rid, request, copy.deepcopy(state))
        )
        return req

    def _phase(self, sid: str, owner: str, rid: str, phase: str) -> None:
        state, version = self.store.read(sid, owner)
        if state["requests"][rid]["status"] != "running":
            raise asyncio.CancelledError()
        state["requests"][rid]["phase"] = phase
        self.store.write(state, owner, version)

    async def _model(self, model: str, context: dict) -> str:
        from dbgpt.core import ModelMessage, ModelRequest
        from dbgpt.model.cluster import WorkerManagerFactory
        from dbgpt.model.cluster.client import DefaultLLMClient

        client = DefaultLLMClient(
            WorkerManagerFactory.get_instance(self.system_app).create()
        )
        output = await client.generate(
            ModelRequest.build_request(
                model,
                messages=[
                    ModelMessage(role="system", content=SYSTEM_PROMPT),
                    ModelMessage(
                        role="human",
                        content=json.dumps(context, ensure_ascii=False),
                    ),
                ],
                temperature=0.1,
                max_new_tokens=6000,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "emit_generation_result",
                            "description": "提交澄清、完整流程候选或失败说明。",
                            "parameters": generation_schema(),
                        },
                    }
                ]
                if not model.startswith("deepseek-r1")
                else None,
                tool_choice={
                    "type": "function",
                    "function": {"name": "emit_generation_result"},
                }
                if not model.startswith("deepseek-r1")
                else None,
            )
        )
        if output.error_code:
            raise RuntimeError(output.text or "模型调用失败")
        if output.tool_calls:
            if len(output.tool_calls) != 1:
                raise ValueError("模型必须只提交一个结构化生成结果")
            function = output.tool_calls[0].get("function", {})
            if function.get("name") != "emit_generation_result":
                raise ValueError("模型返回了未授权的输出函数")
            return function["arguments"]
        return output.text

    async def _generate(
        self, sid: str, owner: str, rid: str, request: MessageRequest, base: dict
    ) -> None:
        try:
            async with generation_budget(180):
                catalog = await self.catalog()
                model = request.model or next(iter(catalog["models"]), None)
                if model not in catalog["models"]:
                    raise ValueError("请选择已启用的生成模型")
                check_model_context(base["snapshot"])
                context = {
                    "snapshot": base["snapshot"],
                    "history": base["messages"][-20:],
                    "explicit_requirements": [
                        m["text"] for m in base["messages"] if m["role"] == "user"
                    ],
                    "confirmed_turns": base.get("confirmed_turns", []),
                    "pending_questions": base["questions"],
                    "instruction": request.text,
                    "answers": request.answers,
                    "scope": request.scope.model_dump(),
                    "catalog": {
                        key: value
                        for key, value in catalog.items()
                        if key != "resource_revisions"
                    },
                }
                explicit_selection = "\n".join(context["explicit_requirements"])
                explicit_selection += json.dumps(
                    context["confirmed_turns"], ensure_ascii=False
                )
                for field in ("datasources", "knowledge"):
                    retained = {
                        value
                        for node in base["snapshot"]["dsl"]["nodes"]
                        for value in node.get("config", {}).get(field, [])
                    }
                    # Unselected resources are availability information, not
                    # default bindings offered to the generator.
                    context["catalog"][field] = [
                        value
                        for value in catalog[field]
                        if value in retained or value in explicit_selection
                    ]
                context["available_resource_counts"] = {
                    field: len(catalog[field]) for field in ("datasources", "knowledge")
                }
                retained_models = {
                    node.get("config", {}).get("model")
                    for node in base["snapshot"]["dsl"]["nodes"]
                }
                context["catalog"]["models"] = [
                    value
                    for value in catalog["models"]
                    if value == model
                    or value in retained_models
                    or value in explicit_selection
                ]
                if len(json.dumps(context)) > 100000:
                    raise ValueError("上下文过大，请缩小流程或修改范围")
                for attempt in range(3):
                    self._phase(
                        sid, owner, rid, "构建流程" if not attempt else "修正生成结果"
                    )
                    text = await self._model(model, context)
                    self._phase(sid, owner, rid, "校验流程")
                    try:
                        # Accept only a full JSON document (optional JSON fence).
                        clean = text.strip()
                        if clean.startswith("```json\n") and clean.endswith("```"):
                            clean = clean[8:-3].strip()
                        result = GenerationResult.model_validate(json.loads(clean))
                        if result.type == "candidate":
                            if result.questions or result.candidate_dsl is None:
                                raise ValueError("候选必须包含流程，不能同时返回问题")
                            if set(result.flow_meta) - {"label", "description"}:
                                raise ValueError("元信息只允许 label/description")
                            if request.scope.type == "nodes":
                                if any(
                                    value != base["snapshot"]["meta"].get(key)
                                    for key, value in result.flow_meta.items()
                                ):
                                    raise ValueError("局部修改不能改变流程元信息")
                                result.flow_meta = {}
                            if (
                                result.assumptions
                                and len(base.get("confirmed_turns", [])) == 1
                                and all(
                                    node["kind"] in {"start", "output"}
                                    for node in base["snapshot"]["dsl"]["nodes"]
                                )
                            ):
                                result = GenerationResult(
                                    protocol="generation_result/1",
                                    type="clarification",
                                    summary="需要先确认分析目标，当前画布保持不变。",
                                    questions=[
                                        Question(
                                            question_id="confirm_requirements",
                                            text="请确认或调整这些需求假设："
                                            + "；".join(result.assumptions)[:900],
                                            options=[
                                                "按以上方案继续",
                                                "我要调整分析目标",
                                            ],
                                        )
                                    ],
                                )
                                break
                            for node in result.candidate_dsl.get("nodes", []):
                                node_model = node.get("config", {}).get("model")
                                if (
                                    node_model
                                    and node_model not in context["catalog"]["models"]
                                ):
                                    raise ValueError(
                                        "不要自动切换模型，请省略 model"
                                        " 或使用用户选中的模型"
                                    )
                            # No arbitrary default database/knowledge binding:
                            # retain existing refs or require an explicit name
                            # in the user's confirmed turns.
                            explicit = "\n".join(context["explicit_requirements"])
                            explicit += json.dumps(
                                context["confirmed_turns"], ensure_ascii=False
                            )
                            for field in ("datasources", "knowledge"):
                                existing_refs = {
                                    value
                                    for node in base["snapshot"]["dsl"]["nodes"]
                                    for value in node.get("config", {}).get(field, [])
                                }
                                for node in result.candidate_dsl.get("nodes", []):
                                    for value in node.get("config", {}).get(field, []):
                                        if (
                                            value not in existing_refs
                                            and value not in explicit
                                        ):
                                            if value in catalog[field]:
                                                raise NeedsResourceChoice(
                                                    field, catalog
                                                )
                                            raise ValueError(f"资源不存在：{value}")
                            validation = validate_candidate(
                                result.candidate_dsl,
                                base["snapshot"]["dsl"],
                                request.scope,
                                catalog,
                                [g.model_dump() for g in result.missing_configuration],
                            )
                            if (
                                len(base.get("confirmed_turns", [])) == 1
                                and len(request.text.strip()) <= 20
                                and all(
                                    node["kind"] in {"start", "output"}
                                    for node in base["snapshot"]["dsl"]["nodes"]
                                )
                            ):
                                # A terse first instruction cannot silently
                                # authorize the model's expanded business scope.
                                proposed = "；".join(
                                    node.get("config", {}).get("goal", "")
                                    for node in result.candidate_dsl["nodes"]
                                    if node["kind"] == "agent"
                                )
                                result = GenerationResult(
                                    type="clarification",
                                    summary="请先确认具体目标，当前画布保持不变。",
                                    questions=[
                                        Question(
                                            question_id="confirm_requirements",
                                            text="希望完成什么具体目标、输出什么结果？"
                                            "当前建议：" + proposed[:700],
                                            options=[
                                                "按以上目标创建",
                                                "我要补充目标与输出",
                                            ],
                                        )
                                    ],
                                )
                                break
                        elif result.type == "clarification":
                            if not result.questions or result.candidate_dsl:
                                raise ValueError("澄清必须包含问题且不能包含流程")
                            ids = [q.question_id for q in result.questions]
                            if len(ids) != len(set(ids)):
                                raise ValueError("问题 ID 重复")
                        elif result.questions or result.candidate_dsl:
                            raise ValueError("失败不能附带流程或问题")
                        break
                    except NeedsResourceChoice as exc:
                        result = GenerationResult(
                            protocol="generation_result/1",
                            type="clarification",
                            summary=exc.summary,
                            questions=exc.questions,
                        )
                        break
                    except (ValueError, TypeError, KeyError) as exc:
                        if attempt == 2:
                            raise ValueError(f"生成结果校验失败：{exc}") from exc
                        context["repair"] = {
                            "invalid_response": text[:30000],
                            "error": str(exc)[:4000],
                            "instruction": "修正协议或结构，保留当前需求与修改范围。",
                        }
                state, version = self.store.read(sid, owner)
                req = state["requests"][rid]
                if req["status"] != "running":
                    return
                if (
                    state["draft_revision"] != base["draft_revision"]
                    or state["context_revision"] != base["context_revision"]
                ):
                    raise ValueError("生成期间画布或需求已改变，结果已过期，请重新生成")
                response = result.model_dump(exclude_none=True)
                if result.type == "candidate":
                    candidate = {
                        **response,
                        "candidate_id": uuid.uuid4().hex,
                        "base_draft_revision": state["draft_revision"],
                        "context_revision": state["context_revision"],
                        "catalog_version": fingerprint(catalog),
                        "change_summary": changes(
                            state["snapshot"]["dsl"], result.candidate_dsl
                        ),
                        "validation": validation,
                        "missing_configuration": validation["missing_configuration"],
                        "status": "pending",
                    }
                    state["candidate"] = candidate
                    response = candidate
                    # Empty creation uses the same application transaction.
                    if all(
                        n["kind"] in {"start", "output"}
                        for n in state["snapshot"]["dsl"]["nodes"]
                    ):
                        self._apply(state, candidate)
                        response["auto_applied"] = True
                    state["questions"] = []
                elif result.type == "clarification":
                    state["questions"] = response["questions"]
                state["messages"].append({"role": "assistant", "text": result.summary})
                req.update(status="succeeded", result=response, phase="完成")
                self.store.write(state, owner, version)
        except asyncio.CancelledError:
            # Cancellation is persisted before task.cancel(), so no late writes.
            pass
        except Exception as exc:
            logger.warning("TaskFlow generation %s failed: %s", rid, exc)
            state, version = self.store.read(sid, owner)
            if state["requests"][rid]["status"] == "running":
                state["requests"][rid].update(status="failed", error=str(exc)[:3000])
                self.store.write(state, owner, version)
        finally:
            self.tasks.pop(rid, None)

    def cancel(self, sid: str, owner: str, rid: str) -> dict:
        state, version = self.store.read(sid, owner)
        req = state["requests"].get(rid)
        if not req:
            raise HTTPException(404, "生成任务不存在")
        if req["status"] == "running":
            req["status"] = "cancelled"
            self.store.write(state, owner, version)
            if rid in self.tasks:
                self.tasks[rid].cancel()
        return state

    @staticmethod
    def _apply(state: dict, candidate: dict) -> None:
        state["undo"] = {
            "snapshot": copy.deepcopy(state["snapshot"]),
            "applied_revision": state["draft_revision"] + 1,
        }
        state["snapshot"]["dsl"] = candidate["candidate_dsl"]
        state["snapshot"]["meta"].update(candidate["flow_meta"])
        state["draft_revision"] += 1
        state["dirty"] = True
        state["run"] = None
        candidate["status"] = "applied"

    async def candidate_action(
        self, sid: str, owner: str, cid: str, action: str
    ) -> dict:
        state, version = self.store.read(sid, owner)
        candidate = state["candidate"]
        if not candidate or candidate["candidate_id"] != cid:
            raise HTTPException(404, "候选不存在")
        if candidate["status"] == ("applied" if action == "apply" else "discarded"):
            return state
        if candidate["status"] != "pending":
            raise HTTPException(409, "候选已过期")
        if action == "discard":
            candidate["status"] = "discarded"
        else:
            catalog = await self.catalog()
            # Re-read after awaiting resources to prevent overwriting edits.
            state, version = self.store.read(sid, owner)
            candidate = state["candidate"]
            if (
                candidate["status"] != "pending"
                or candidate["base_draft_revision"] != state["draft_revision"]
                or candidate["context_revision"] != state["context_revision"]
            ):
                raise HTTPException(409, "候选基础版本已改变")
            validate_candidate(
                candidate["candidate_dsl"],
                state["snapshot"]["dsl"],
                Scope(),
                catalog,
                candidate["missing_configuration"],
            )
            self._apply(state, candidate)
        self.store.write(state, owner, version)
        return state

    def undo(self, sid: str, owner: str) -> dict:
        state, version = self.store.read(sid, owner)
        undo = state["undo"]
        if not undo or undo["applied_revision"] != state["draft_revision"]:
            raise HTTPException(409, "应用后已手动编辑，无法直接撤销")
        if state["candidate"] and state["candidate"]["status"] == "pending":
            raise HTTPException(409, "请先放弃候选再撤销")
        state["snapshot"] = undo["snapshot"]
        # Undo content, never a saved workflow's stable identity.
        for key in ("uid", "name", "state"):
            if key in state.get("identity", {}):
                state["snapshot"]["meta"][key] = state["identity"][key]
        state["draft_revision"] += 1
        state["dirty"] = True
        state["undo"] = None
        state["run"] = None
        self.store.write(state, owner, version)
        return state
