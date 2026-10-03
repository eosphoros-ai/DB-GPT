"""Generate a revision-bound proposal using real validation feedback.

Historical tool calls are not replayed.
"""

import asyncio
import json
import re
from typing import Optional

from pydantic import Field, ValidationError

from .annotations import resolve_stable_patch_operations
from .assistant_skills import dashboard_configuration_skill
from .collaboration import DashboardPatchError, apply_dashboard_patch
from .models import DashboardConflictError
from .schemas import (
    DashboardAction,
    DashboardAnnotationIntent,
    DashboardChangeProposalRequest,
    DashboardFilter,
    DashboardPublicationBinding,
    DashboardSchemaV1,
    StrictModel,
)
from .service import DashboardSchemaValidationError


class AnnotationGenerationRequest(StrictModel):
    model: Optional[str] = Field(default=None, max_length=256)
    user_prompt: Optional[str] = Field(default=None, max_length=20000)


def annotation_source_context(service, schema, actor):
    """Inspect only authorized connections; bound samples and categorical discovery."""
    import sqlglot

    source = schema.dashboard.data_source_id
    if service.authorization is not None:
        service.authorization.require_data_sources(service._owner(actor), [source])
    connector = service.query_executor._get_connector(source)
    dialect = service.query_executor._dialect(connector)

    def quote(name):
        return sqlglot.exp.to_identifier(str(name), quoted=True).sql(dialect=dialect)

    tables = []
    names = list(connector.get_table_names())
    if len(names) > 80:
        raise ValueError("当前数据源超过 80 张表，请连接要分析的表或视图后重试。")

    def read_rows(sql, columns, limit):
        sample = DashboardSchemaV1.model_validate(
            {
                "dashboard": {"title": "助手数据检查", "data_source_id": source},
                "widgets": [
                    {
                        "id": "sample",
                        "type": "table",
                        "title": "样本",
                        "query": {
                            "data_source_id": source,
                            "sql": sql,
                            "output_fields": [
                                {"name": name, "type": "unknown"} for name in columns
                            ],
                            "max_rows": limit,
                            "timeout_seconds": 10,
                        },
                        "encoding": {"columns": columns},
                    }
                ],
                "layouts": {
                    "desktop": [
                        {"widget_id": "sample", "x": 0, "y": 0, "w": 12, "h": 4}
                    ]
                },
            }
        )
        result = service.query_executor.execute_dashboard(sample, {})["sample"]
        if result.error:
            return {"error": result.error.message}
        return {
            "rows": [list(row) for row in result.rows],
            "truncated": result.truncated,
        }

    for index, table in enumerate(names):
        try:
            fields = connector.get_fields(table, source)
        except TypeError:
            fields = connector.get_fields(table)
        columns = [
            {
                "name": str(f.get("name", ""))
                if isinstance(f, dict)
                else service.query_executor._column_name(f),
                "type": str(f.get("type", ""))
                if isinstance(f, dict)
                else str(f[1] if len(f) > 1 else ""),
            }
            for f in fields
        ]
        entry = {"name": str(table), "columns": columns}
        # Keep dialect-specific metadata for every table; sampling is deliberately
        # limited to the installed SQLite sources rather than guessing other syntax.
        if index < 6 and columns and dialect in {"sqlite", "sqlite3"}:
            selected = [c["name"] for c in columns[:12]]
            entry["sample"] = read_rows(
                (
                    f"SELECT {','.join(quote(c) for c in selected)} FR"
                    f"OM {quote(table)} LIMIT 3"
                ),
                selected,
                3,
            )
            for column in columns[:12]:
                if not any(
                    token in column["type"].lower()
                    for token in ("char", "text", "bool")
                ):
                    continue
                name = column["name"]
                values = read_rows(
                    (
                        f"SELECT DISTINCT {quote(name)} FROM "
                        f"{quote(table)} WHERE {quote(name)} IS NOT NULL L"
                        f"IMIT 31"
                    ),
                    [name],
                    31,
                )
                if "error" not in values:
                    column["distinct_values"] = [row[0] for row in values["rows"][:30]]
                    column["values_truncated"] = (
                        len(values["rows"]) > 30 or values["truncated"]
                    )
        tables.append(entry)
    return {"data_source_id": source, "dialect": dialect, "tables": tables}


def proposal_messages(annotation, schema, source_context, user_prompt=None):
    from dbgpt.core import ModelMessage

    instruction = (
        "你是当前看板的修改方案生成器，只输出完整 JSON。\n"
        "本轮没有历史工具调用；只处理 annotation 中的当前"
        "要求。服务端绑定看板、批注和修订号，"
        "不要输出或猜测 dashboard_id、annotation_id，不调用工具，不输出 ReAct。\n"
        "user_request 是用户原始要求；annotation.prompt "
        "是前一步规划的参考，可能包含未经验证的 SQL 或范"
        "围推断。"
        "以原始要求和真实元数据为准，不沿用参考中臆造的参数语法或擅自缩小筛选范围。\n"
        "返回 {summary:中文修改说明,operations:[{op,path,"
        "value}],before:[原状],after:[结果]}。"
        "summary 用 2～4 句说明可见变化与业务口径，不堆砌内部 ID、JSON 路径或接口名；"
        "before/after 帮助用户比较影响范围。详细 SQL 放在 operations 中。"
        "operations 最多 50 项；op 只能 add/replace/remove。"
        "使用稳定 ID 路径，不使用数组下标；不改所有权、数据源、看板 ID 或修订号。"
        "新增筛选器必须用 add /filters/-，value 为含唯一 id 的完整筛选对象；"
        "新增图表必须用 add /widgets/- 并用 add /layouts/desktop/- 添加对应布局。"
        "by-id 和 by-widget-id 路径只能定位已有对象或本批"
        "次前面已创建的对象，不能直接创建不存在的 ID。"
        "操作按顺序执行：先创建，再绑定或修改；绑定筛选使"
        "用 /widgets/by-id/组件ID/query/filter_parameters"
        "/筛选ID。"
        "必要时整体替换 query/publication，减少相互依赖的零碎操作。"
        "JSON Pointer 的 replace 要求路径已经存在；新增 style 对象键用 add。"
        "提交的是待审阅方案，不是已应用结果。\n\n"
        "失败提案从未保存。每次修正都必须返回相对于 saved"
        "_schema 的完整累计 operations，"
        "保留上一轮已正确的操作，不能只返回错误字段的修补。\n\n"
        + dashboard_configuration_skill(annotation.target.kind.value)
    )
    payload = {
        "user_request": user_prompt or annotation.prompt,
        "annotation": {
            "target": annotation.target.model_dump(mode="json"),
            "prompt": annotation.prompt,
        },
        "saved_schema": schema.model_dump(mode="json", exclude_none=True),
        "source_context": source_context,
        "response_contract": DashboardChangeProposalRequest.model_json_schema(),
        "filter_contract": DashboardFilter.model_json_schema(),
        "publication_contract": DashboardPublicationBinding.model_json_schema(),
    }
    return [
        ModelMessage(role="system", content=instruction),
        ModelMessage(
            role="human", content=json.dumps(payload, ensure_ascii=False, default=str)
        ),
    ]


def _validate_configuration(
    service,
    dashboard_id,
    actor,
    schema,
    annotation,
    proposal,
    source_context=None,
    user_prompt=None,
):
    """Verify actual configuration and changed frozen datasets before persistence."""
    operations = resolve_stable_patch_operations(schema, proposal.operations)
    preview = DashboardSchemaV1.model_validate(
        apply_dashboard_patch(schema.model_dump(mode="json"), operations)
    )
    service.require_permission(dashboard_id, actor, DashboardAction.QUERY, preview)
    original = next(
        (w for w in schema.widgets if w.id == annotation.target.widget_id), None
    )
    configured = next(
        (w for w in preview.widgets if w.id == annotation.target.widget_id), None
    )
    if (
        original
        and configured
        and any(word in annotation.prompt.lower() for word in ("配置", "查询", "sql"))
    ):

        def placeholder(sql):
            return bool(re.search(r"\bWHERE\s+1\s*=\s*0\b", sql, re.I))

        if placeholder(original.query.sql) and placeholder(configured.query.sql):
            raise DashboardPatchError(
                (
                    "目标图表仍是未配置的占位查询。必须提供实际 query"
                    ".sql、字段映射及发布配置。失败方案没有保存，请返"
                    "回全部累计 operations，不要仅修补上一轮报错字段"
                    "。"
                )
            )
    changed = preview.model_copy(deep=True)
    originals = {w.id: w for w in schema.widgets}
    changed.widgets = [
        w
        for w in preview.widgets
        if w.publication
        and (w.id not in originals or w.publication != originals[w.id].publication)
    ]
    failures = service.publication_service.validate_materialization(
        changed, service.query_executor
    )
    if failures:
        raise DashboardPatchError(
            "发布查询验证失败：" + json.dumps(failures, ensure_ascii=False)
        )
    existing_filter_ids = {item.id for item in schema.filters}
    for selected in preview.filters:
        if selected.id not in existing_filter_ids or (
            annotation.target.kind.value == "filter"
            and selected.id == annotation.target.filter_id
        ):
            _validate_filter_configuration(
                service,
                schema,
                preview,
                selected,
                annotation,
                source_context,
                user_prompt,
            )


def _validate_filter_configuration(
    service, schema, preview, selected, annotation, source_context, user_prompt
):
    """Apply the same scope and selection checks to configured and new filters."""
    explicit_scope = any(
        word in (user_prompt or annotation.prompt)
        for word in (
            "只影响",
            "仅影响",
            "仅作用",
            "只绑定",
            "仅绑定",
            "只联动",
            "仅联动",
            "只对",
            "仅对",
            "不影响",
            "排除",
        )
    ) or bool(
        re.search(r"\b(only|exclude|except)\b", user_prompt or annotation.prompt, re.I)
    )
    # A new global filter covers compatible metrics on the same base table,
    # even when their current projection has not selected the new dimension.
    was_bound = any(selected.id in w.query.filter_parameters for w in schema.widgets)
    if source_context and not was_bound and not explicit_scope:
        import sqlglot

        tables = {
            table["name"]: {c["name"] for c in table["columns"]}
            for table in source_context["tables"]
        }
        available = {
            name
            for name, fields in tables.items()
            if selected.field.split(".")[-1] in fields
        }
        missing = []
        for original_widget in schema.widgets:
            if (
                original_widget.query.federation
                or original_widget.query.data_source_id
                != source_context["data_source_id"]
            ):
                continue
            try:
                tree = sqlglot.parse_one(
                    original_widget.query.sql, read=source_context["dialect"]
                )
                physical_tables = {
                    table.name for table in tree.find_all(sqlglot.exp.Table)
                } & tables.keys()
            except sqlglot.errors.ParseError:
                continue
            candidate = next(
                (w for w in preview.widgets if w.id == original_widget.id), None
            )
            if (
                len(physical_tables) == 1
                and physical_tables <= available
                and candidate
                and selected.id not in candidate.query.filter_parameters
            ):
                missing.append(original_widget.id)
        if missing:
            raise DashboardPatchError(
                "新全局筛选遗漏了可联动组件："
                + ", ".join(missing)
                + "。这些组件的同源基础表确实包含字段 "
                + selected.field
                + (
                    "，请在聚合前加入维度及参数，并同步发布映射。用户"
                    "没有限定局部范围，前置规划的部分组件列表不构成限"
                    "制。"
                )
            )
    # Equivalent metrics shown as a KPI and a gauge must keep the same scope.
    if not explicit_scope:
        groups = {}
        for widget in schema.widgets:
            key = (widget.query.data_source_id, re.sub(r"\s+", "", widget.query.sql))
            groups.setdefault(key, []).append(widget.id)
        for ids in groups.values():
            bindings = {
                w.id: selected.id in w.query.filter_parameters
                for w in preview.widgets
                if w.id in ids
            }
            if bindings and any(bindings.values()) and not all(bindings.values()):
                raise DashboardPatchError(
                    "同一查询的组件必须保持一致的筛选范围："
                    + ", ".join(ids)
                    + "。请同时绑定这些组件及其发布字段，避免 KPI 与仪表盘数值不一致。"
                )
    if selected.type.value != "multi_select":
        return
    values = [item.value for item in selected.options[:2]]
    for selection in [[], values[:1], values]:
        validation = service.validate_schema(
            preview, execute_queries=True, filters={selected.id: selection}
        )
        if not validation.valid:
            raise DashboardSchemaValidationError(validation.issues)


async def generate_annotation_proposal(
    annotation_service,
    dashboard_id,
    annotation_id,
    actor,
    request,
    llm_client=None,
    *,
    cancelled=None,
):
    from dbgpt.core import ModelMessage, ModelRequest

    service = annotation_service.dashboard_service
    record = service.get_dashboard(dashboard_id, actor)
    service.require_permission(dashboard_id, actor, DashboardAction.EDIT)
    annotation = annotation_service._to_record(
        annotation_service._get(dashboard_id, annotation_id)
    )
    if annotation.intent != DashboardAnnotationIntent.MODIFY:
        raise DashboardPatchError("解释与异常分析批注不能生成修改提案。")
    if annotation.base_revision != record.current_revision:
        raise DashboardConflictError("看板已变更，请基于当前版本重新发送批注。")
    if annotation.status.value in {"applied", "rejected"}:
        raise DashboardConflictError("此批注已经处理，请重新发送当前修改要求。")
    if annotation.status.value == "proposed" and annotation.proposal:
        return annotation
    service.require_permission(
        dashboard_id, actor, DashboardAction.QUERY, record.schema_payload
    )
    context = await asyncio.to_thread(
        annotation_source_context, service, record.schema_payload, actor
    )
    messages = proposal_messages(
        annotation, record.schema_payload, context, request.user_prompt
    )
    if llm_client is None:
        from dbgpt._private.config import Config
        from dbgpt.component import ComponentType
        from dbgpt.model.cluster import WorkerManagerFactory
        from dbgpt.model.cluster.client import DefaultLLMClient

        manager = (
            Config()
            .SYSTEM_APP.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            )
            .create()
        )
        llm_client = DefaultLLMClient(manager, auto_convert_message=True)
    model = request.model
    if not model:
        models = await llm_client.models()
        if not models:
            raise ValueError("请先配置可用模型。")
        model = models[0].model
    for attempt in range(3):
        if cancelled and await cancelled():
            raise asyncio.CancelledError()
        output = await asyncio.wait_for(
            llm_client.generate(
                ModelRequest.build_request(
                    model=model,
                    messages=messages,
                    temperature=0,
                    max_new_tokens=16000,
                )
            ),
            timeout=120,
        )
        if output.error_code:
            raise ValueError("修改方案生成服务暂不可用，请重试。")
        try:
            raw = output.text.strip()
            if raw.startswith("```") and raw.endswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            proposal = DashboardChangeProposalRequest.model_validate(json.loads(raw))
            await asyncio.to_thread(
                _validate_configuration,
                service,
                dashboard_id,
                actor,
                record.schema_payload,
                annotation,
                proposal,
                context,
                request.user_prompt,
            )
            if cancelled and await cancelled():
                raise asyncio.CancelledError()
            # The service rechecks the revision and permissions, validates the full
            # schema and executes queries. Only a successful proposal is persisted.
            return await asyncio.to_thread(
                annotation_service.propose_change,
                dashboard_id,
                annotation_id,
                proposal,
                actor,
            )
        except (
            ValidationError,
            DashboardPatchError,
            DashboardSchemaValidationError,
            ValueError,
        ) as error:
            if isinstance(error, DashboardSchemaValidationError):
                detail = "; ".join(
                    f"{i.path} [{i.code}]: {i.message}" for i in error.issues
                )
            else:
                detail = str(error)
            if attempt == 2:
                raise ValueError(
                    "修改方案未通过验证，批注已保留。具体原因：" + detail[:2200]
                ) from error
            messages.extend(
                [
                    ModelMessage(role="ai", content=output.text),
                    ModelMessage(
                        role="human",
                        content="validation_feedback："
                        + detail[:5000]
                        + (
                            "\n失败提案没有保存；请保留之前正确的修改，返回相"
                            "对于 saved_schema 的完整累计 operations JSON，不"
                            "能仅返回错误字段的修补。不要改动其他目标。"
                        ),
                    ),
                ]
            )
