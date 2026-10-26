"""Task-local durable extraction with explicit resume and bounded worker use."""

import hashlib
import json
import logging
import os
import time
from uuid import uuid4

from pydantic import ValidationError

from dbgpt_serve.session_file.api.endpoints import SessionFileApiError
from dbgpt_serve.session_file.domain import FileScope

from . import workflow
from .comparison_report import build_comparison
from .comparison_schema import (
    EXTRACTOR_VERSION,
    ComparisonConfig,
    ComparisonRequest,
    fingerprint,
    stable_id,
)
from .models import FinancialRunDocumentEntity as Member
from .models import FinancialRunEntity as Run
from .revisions import save_revision

logger = logging.getLogger(__name__)


class ComparisonRunner:
    def __init__(self, service):
        self.service = service
        self.session = service.session

    def _require_schema(self):
        if not self.service.comparison_schema_ready:
            raise SessionFileApiError(
                503,
                "COMPARISON_MIGRATION_REQUIRED",
                "财报对比需要管理员先显式迁移数据库并重启服务；单财报分析仍可使用。",
            )

    @staticmethod
    def member(row, *, extracted=False):
        result = {
            key: getattr(row, key)
            for key in (
                "file_id",
                "file_name",
                "status",
                "document_id",
                "sha256",
                "extractor_version",
                "error",
                "started_at",
                "completed_at",
            )
        }
        if extracted:
            result["extracted"] = (
                json.loads(row.extracted_json) if row.extracted_json else None
            )
        return result

    def members(self, run_id, *, extracted=False):
        self._require_schema()
        with self.session(commit=False) as session:
            return [
                self.member(row, extracted=extracted)
                for row in session.query(Member)
                .filter_by(run_id=run_id)
                .order_by(Member.position)
                .all()
            ]

    def create(self, owner, session_id, file_ids, run_id, config, *, agent_model=None):
        from .service import now

        self._require_schema()
        try:
            request = ComparisonRequest(file_ids=file_ids, comparison=config)
        except ValidationError as exc:
            raise SessionFileApiError(
                400, "INVALID_COMPARISON", "请提供不同的年度报告附件和有效的比较配置。"
            ) from exc
        config = request.comparison.model_dump()
        if not config["baseline_file_id"]:
            config["baseline_file_id"] = file_ids[0]
        try:
            maximum = max(2, min(5, int(os.getenv("DBGPT_COMPARISON_MAX_FILES", "5"))))
        except ValueError:
            maximum = 5
        if len(file_ids) > maximum:
            raise SessionFileApiError(
                400, "TOO_MANY_FILES", "超出当前对比附件数量限制。"
            )
        digest = fingerprint(file_ids, config)
        with self.service._lock:
            with self.session(commit=False) as session:
                previous = session.query(Run).filter_by(id=run_id).first()
                if previous:
                    if (
                        previous.owner_id,
                        previous.session_id,
                        previous.mode,
                        previous.request_fingerprint,
                    ) != (owner, session_id, "comparison", digest):
                        raise SessionFileApiError(
                            409, "RUN_ID_CONFLICT", "任务标识与参数冲突。"
                        )
                    return self.service._public(previous)
            records = []
            for file_id in file_ids:
                record = self.service.registry.get_file(
                    owner_id=owner, session_id=session_id, file_id=file_id
                )
                if not record:
                    raise SessionFileApiError(
                        404, "FILE_NOT_FOUND", "未找到当前会话的附件。"
                    )
                if not record.display_name.lower().endswith(
                    ".pdf"
                ) or record.media_type not in {
                    "application/pdf",
                    "application/octet-stream",
                }:
                    raise SessionFileApiError(
                        400, "PDF_REQUIRED", "仅支持 PDF 年度报告。"
                    )
                records.append(record)
            if len({r.sha256 for r in records}) != len(records):
                raise SessionFileApiError(
                    400,
                    "DUPLICATE_DOCUMENT",
                    "重复上传的同一文件不能作为多个比较对象。",
                )
            if not self.service._slots.acquire(blocking=False):
                raise SessionFileApiError(
                    429, "RUN_QUEUE_FULL", "分析队列已满，请稍后重试。"
                )
            try:
                with self.session() as session:
                    stamp = now()
                    row = Run(
                        id=run_id,
                        owner_id=owner,
                        session_id=session_id,
                        # Keep the legacy NOT NULL column as an attachment pointer;
                        # authorization always uses the member table in this mode.
                        file_id=config["baseline_file_id"],
                        mode="comparison",
                        config_json=json.dumps(
                            {
                                "comparison": config,
                                "resolutions": {},
                                "model": agent_model,
                            }
                        ),
                        request_fingerprint=digest,
                        status="pending",
                        stage="queued",
                        created_at=stamp,
                        updated_at=stamp,
                    )
                    session.add(row)
                    for position, record in enumerate(records):
                        session.add(
                            Member(
                                id=stable_id("member", run_id, record.file_id),
                                run_id=run_id,
                                file_id=record.file_id,
                                position=position,
                                file_name=record.display_name,
                                sha256=record.sha256,
                                status="pending",
                                extractor_version=EXTRACTOR_VERSION,
                            )
                        )
                    session.flush()
                    result = self.service._public(row)
                self.service._executor.submit(self.work, owner, session_id, run_id)
                return result
            except Exception:
                self.service._slots.release()
                self.service._update(
                    run_id,
                    status="failed",
                    stage="interrupted",
                    error="任务未启动，可显式继续。",
                )
                raise

    def resume(self, owner, session_id, run_id, revision=None, resolutions=None):
        self._require_schema()
        with self.service._lock:
            state = self.service.get(owner, session_id, run_id)
            if (
                state["mode"] != "comparison"
                or state["status"]
                in {
                    "running",
                    "pending",
                }
                or (
                    state["stage"] == "agent_topics"
                    and state.get("report_ready")
                    and self.service.get(owner, session_id, run_id, report=True)
                    .get("analysis", {})
                    .get("driver")
                    == "standalone"
                )
            ):
                raise SessionFileApiError(409, "RUN_BUSY", "任务类型不符或仍在执行。")
            if state["report_ready"]:
                report = self.service.get(owner, session_id, run_id, report=True)
                if report["revision"] != revision:
                    raise SessionFileApiError(
                        409, "REPORT_CHANGED", "请读取当前版本后继续。"
                    )
                self.service._check_parallel_idle(report)
            members = self.members(run_id)
            resume_only = (
                state["report_ready"]
                and not resolutions
                and all(m["status"] == "completed" for m in members)
            )
            if resume_only and report["workflow"]["status"] == "published":
                return state
            if not self.service._slots.acquire(blocking=False):
                raise SessionFileApiError(429, "RUN_QUEUE_FULL", "分析队列已满。")
            try:
                if (
                    resume_only
                    and self.service.analyzer
                    and report["analysis"].get("driver") == "standalone"
                ):
                    for topic in list(report["workflow"]["topics"]):
                        if topic["status"] == "failed":
                            report = workflow.start_topic(
                                report, topic["id"], retry=True
                            )
                with self.session() as session:
                    row = session.query(Run).filter_by(id=run_id).one()
                    stored = json.loads(row.config_json)
                    member_ids = {m["file_id"] for m in self.members(run_id)}
                    if resolutions:
                        if not set(resolutions) <= member_ids:
                            raise SessionFileApiError(
                                400, "INVALID_MEMBER", "澄清对象不属于此任务。"
                            )
                        stored["resolutions"].update(resolutions)
                        row.config_json = json.dumps(stored, ensure_ascii=False)
                    row.status, row.stage, row.error = "pending", "queued", None
                    if resume_only:
                        row.report_json = json.dumps(report, ensure_ascii=False)
                self.service._executor.submit(
                    self.work, owner, session_id, run_id, resume_only=resume_only
                )
            except Exception:
                self.service._slots.release()
                raise
        return self.service.get(owner, session_id, run_id)

    def _extract_member(self, owner, session_id, run_id, member):
        from .service import now

        with self.session() as session:
            row = (
                session.query(Member)
                .filter_by(run_id=run_id, file_id=member["file_id"])
                .one()
            )
            row.status, row.started_at, row.error = "running", now(), None
        try:
            opened = self.service.registry.open_download(
                owner_id=owner, session_id=session_id, file_id=member["file_id"]
            )
            if not opened:
                raise ValueError("来源文件已不可用；其他文件的提取结果仍保留。")
            stream, record = opened
            try:
                if record.sha256 != member["sha256"]:
                    raise ValueError("附件元信息与任务快照不一致。")
                with self.service.registry.materialize_local_file(
                    FileScope(owner_id=owner, session_id=session_id), stream, ".pdf"
                ) as path:
                    if (
                        hashlib.sha256(path.read_bytes()).hexdigest()
                        != member["sha256"]
                    ):
                        raise ValueError("附件内容哈希不一致。")
                    extracted = self.service.extractor(path)
            finally:
                stream.close()
            if extracted.get("document", {}).get("sha256") != member["sha256"]:
                raise ValueError("解析结果不属于此附件。")
            if extracted.get("_meta", {}).get("status") == "unsupported":
                raise ValueError("未识别到支持的文本年度财务表格。")
            extracted["document"]["sizeBytes"] = record.size_bytes
            content = json.dumps(extracted, ensure_ascii=False, allow_nan=False)
            with self.session() as session:
                row = (
                    session.query(Member)
                    .filter_by(run_id=run_id, file_id=member["file_id"])
                    .one()
                )
                row.extracted_json = content
                row.document_id = extracted["document"]["id"]
                row.status, row.completed_at = "completed", now()
        except Exception:
            # Do not persist provider/OS exception strings or paths.
            with self.session() as session:
                row = (
                    session.query(Member)
                    .filter_by(run_id=run_id, file_id=member["file_id"])
                    .one()
                )
                row.status, row.completed_at = "failed", now()
                row.error = (
                    "文件提取失败或来源不可用；可重试此文件，成功文件无需重解析。"
                )

    def work(self, owner, session_id, run_id, *, resume_only=False):
        from .service import now

        started, timer = now(), time.monotonic()
        try:
            if resume_only:
                report = self.service.get(owner, session_id, run_id, report=True)
                self.service._update(run_id, status="completed", stage="agent_topics")
                if (
                    report["analysis"].get("driver") == "standalone"
                    and self.service.analyzer
                    and report["comparison"]["ready"]
                ):
                    result = self.analyze(owner, session_id, run_id, report)
                    self.service._update(
                        run_id,
                        stage="completed"
                        if result["workflow"]["status"] == "published"
                        else "awaiting_revision",
                    )
                else:
                    self.service._update(run_id, stage="data_ready")
                return
            self.service._update(run_id, status="running", stage="extract")
            # Sequential document extraction is a deliberate budget of one per
            # run. No child jobs wait on the parent's bounded executor.
            for member in self.members(run_id):
                if member["status"] == "completed":
                    if member["extractor_version"] != EXTRACTOR_VERSION:
                        raise ValueError("提取版本不兼容，请创建新任务。")
                    continue
                self._extract_member(owner, session_id, run_id, member)
            extracted_ms = round((time.monotonic() - timer) * 1000)
            self.service._update(run_id, stage="align")
            with self.session(commit=False) as session:
                row = session.query(Run).filter_by(id=run_id).one()
                stored = json.loads(row.config_json)
            compute_timer = time.monotonic()
            report = build_comparison(
                self.members(run_id, extracted=True),
                {
                    "id": run_id,
                    "token": uuid4().hex[:12],
                    "started_at": started,
                    "completed_at": now(),
                    "model": stored.get("model"),
                },
                stored["comparison"],
                stored.get("resolutions"),
            )
            report["timings"] = {
                "extractionMs": extracted_ms,
                "alignmentCalculationMs": round(
                    (time.monotonic() - compute_timer) * 1000
                ),
            }
            report["analysis"] = {
                "status": "partial",
                "driver": "agent" if stored.get("model") else "standalone",
                "modelName": stored.get("model")
                or getattr(self.service.analyzer, "model", ""),
                "startedAt": now(),
                "completedAt": None,
                "rejectedCount": 0,
            }
            workflow.initialize(report)
            if not stored.get("model") and not self.service.analyzer:
                report["lifecycle"]["stage"] = "awaiting_analysis"
            with self.session() as session:
                row = session.query(Run).filter_by(id=run_id).one()
                if row.report_json:
                    save_revision(
                        session,
                        row,
                        json.loads(row.report_json),
                        timestamp=now(),
                        update_current=False,
                    )
                row.status, row.stage, row.completed_at = (
                    "completed",
                    "data_ready",
                    now(),
                )
                save_revision(session, row, report, timestamp=now())
            if (
                not stored.get("model")
                and self.service.analyzer
                and report["comparison"]["ready"]
            ):
                result = self.analyze(owner, session_id, run_id, report)
                self.service._update(
                    run_id,
                    stage="completed"
                    if result["workflow"]["status"] == "published"
                    else "awaiting_revision",
                )
        except Exception:
            logger.warning(
                "Comparison run %s interrupted; saved members retained", run_id
            )
            failure_values = {}
            if self.service.get(owner, session_id, run_id)["report_ready"]:
                retained = self.service.get(owner, session_id, run_id, report=True)
                if retained.get("workflow", {}).get("status") != "published":
                    workflow.changed(retained)
                    retained["lifecycle"]["stage"] = "interrupted"
                    retained["analysis"].update(status="partial", completedAt=now())
                    failure_values["report_json"] = json.dumps(
                        retained, ensure_ascii=False
                    )
            self.service._update(
                run_id,
                status="failed",
                stage="interrupted",
                completed_at=now(),
                error="对比处理已中断，已保存的文档与数据仍保留；请显式继续。",
                **failure_values,
            )
        finally:
            self.service._slots.release()

    def analyze(self, owner, session_id, run_id, report):
        """Standalone uses the same scoped save/review/publication transitions."""
        from copy import deepcopy

        timer = time.monotonic()
        self.service._update(run_id, stage="agent_topics")
        for topic_id in workflow.TOPICS:
            if workflow.topic(report, topic_id)["status"] in workflow.TERMINAL:
                continue
            report = self.service.update_agent_workflow(
                owner,
                session_id,
                run_id,
                report["revision"],
                "start",
                topic_id=topic_id,
            )
            report["lifecycle"]["stage"] = "analyzing"
            self.service._update(
                run_id, report_json=json.dumps(report, ensure_ascii=False)
            )
            context = workflow.topic_context(report, topic_id)
            for attempt in range(3):
                try:
                    if context["missingRequiredMetrics"]:
                        payload = {
                            "findings": [],
                            "missing_reason": (
                                "当前专题缺少可比较的输入或共同披露基础。"
                            ),
                        }
                    else:
                        scoped = deepcopy(report)
                        scoped["_activeTopic"] = topic_id
                        raw = self.service.analyzer(scoped, owner, session_id)
                        payload = json.loads(raw)
                    report = self.service.update_agent_workflow(
                        owner,
                        session_id,
                        run_id,
                        report["revision"],
                        "save",
                        topic_id=topic_id,
                        findings=payload.get("findings"),
                        missing_reason=payload.get("missing_reason", ""),
                    )
                    item = workflow.topic(report, topic_id)
                    if item["status"] in workflow.TERMINAL:
                        break
                except Exception:
                    current = self.service.get(owner, session_id, run_id, report=True)
                    if current["revision"] != report["revision"]:
                        return current
                    report = current
                    item = workflow.topic(report, topic_id)
                    item.update(
                        status="failed",
                        errorCode="MODEL_REQUEST_FAILED",
                        note="专题模型分析未完成；已保存数据和其他专题保留。",
                        failures=item["failures"] + 1,
                    )
                    workflow.changed(report)
                    self.service._update(
                        run_id, report_json=json.dumps(report, ensure_ascii=False)
                    )
                    break
        reviewer = getattr(self.service.analyzer, "review", None)
        review_issues = []
        if reviewer:
            for review_attempt in range(2):
                try:
                    review_input = deepcopy(report)
                    review_input["_reviewIssues"] = review_issues
                    reviews = reviewer(review_input, owner, session_id)
                    workflow.review_report(deepcopy(report), reviews)
                    break
                except SessionFileApiError as exc:
                    review_issues.append(exc.message)
                except Exception:
                    review_issues.append(
                        "复核请求或 JSON 格式未通过，请按复核协议重新返回。"
                    )
            else:
                report["analysis"]["reviewIssues"] = review_issues
                workflow.changed(report)
                report["lifecycle"]["stage"] = "awaiting_revision"
                report["timings"]["analysisMs"] = round(
                    (time.monotonic() - timer) * 1000
                )
                self.service._update(
                    run_id,
                    stage="awaiting_revision",
                    report_json=json.dumps(report, ensure_ascii=False),
                )
                return report
        else:
            reviews = None
        if reviews is None:
            reviews = [
                {
                    "topic_id": t["id"],
                    "verdict": "insufficient",
                    "directionChecked": True,
                    "scopeChecked": True,
                    "causalityChecked": True,
                    "note": "语义复核尚未完成；结构化引用已检查，结论仍待核对。",
                }
                for t in report["workflow"]["topics"]
            ]
        report["analysis"].pop("reviewIssues", None)
        report["timings"]["analysisMs"] = round((time.monotonic() - timer) * 1000)
        self.service._update(run_id, report_json=json.dumps(report, ensure_ascii=False))
        result = self.service.update_agent_workflow(
            owner, session_id, run_id, report["revision"], "review", reviews=reviews
        )
        if result["workflow"]["status"] != "published":
            result["lifecycle"]["stage"] = "awaiting_revision"
            self.service._update(
                run_id, report_json=json.dumps(result, ensure_ascii=False)
            )
        return result

    def reconfigure(self, owner, session_id, run_id, revision, config):
        self._require_schema()
        from .service import now

        config = ComparisonConfig.model_validate(config).model_dump()
        with self.service._lock:
            report = self.service.get(owner, session_id, run_id, report=True)
            state = self.service.get(owner, session_id, run_id)
            if (
                state["stage"] == "agent_topics"
                and report.get("analysis", {}).get("driver") == "standalone"
            ):
                raise SessionFileApiError(
                    409, "RUN_BUSY", "模型分析仍在执行，请完成后切换基准。"
                )
            self.service._check_parallel_idle(report)
            if report["revision"] != revision or report["mode"] != "comparison":
                raise SessionFileApiError(409, "REPORT_CHANGED", "请读取当前对比版本。")
            members = self.members(run_id, extracted=True)
            if config["baseline_file_id"] not in {m["file_id"] for m in members}:
                raise SessionFileApiError(
                    400, "INVALID_BASELINE", "基准必须属于任务成员。"
                )
            with self.session() as session:
                row = session.query(Run).filter_by(id=run_id).one()
                save_revision(
                    session, row, report, timestamp=now(), update_current=False
                )
                stored = json.loads(row.config_json)
                stored["comparison"] = config
                rebuilt = build_comparison(
                    members,
                    {
                        "id": run_id,
                        "token": uuid4().hex[:12],
                        "started_at": now(),
                        "completed_at": now(),
                    },
                    config,
                    stored.get("resolutions"),
                )
                rebuilt["analysis"] = dict(
                    report["analysis"],
                    status="partial",
                    completedAt=None,
                    rejectedCount=0,
                )
                workflow.initialize(rebuilt)
                rebuilt["lifecycle"]["stage"] = "awaiting_analysis"
                row.config_json = json.dumps(stored, ensure_ascii=False)
                row.stage = "data_ready"
                save_revision(session, row, rebuilt, timestamp=now())
            if (
                rebuilt["analysis"].get("driver") == "standalone"
                and self.service.analyzer
                and rebuilt["comparison"]["ready"]
            ):
                try:
                    self.resume(owner, session_id, run_id, rebuilt["revision"])
                except SessionFileApiError as exc:
                    if exc.err_code != "RUN_QUEUE_FULL":
                        raise
            return rebuilt

    def retry_topic(self, owner, session_id, run_id, revision, topic_id):
        """Explicit standalone retry keeps other topics and extracted members."""
        self._require_schema()
        with self.service._lock:
            state = self.service.get(owner, session_id, run_id)
            report = self.service.get(owner, session_id, run_id, report=True)
            if (
                state["mode"] != "comparison"
                or report["analysis"].get("driver") != "standalone"
                or state["stage"] == "agent_topics"
                or state["status"] in {"pending", "running"}
            ):
                raise SessionFileApiError(
                    409, "RUN_BUSY", "当前任务不支持独立页专题重试。"
                )
            if not report["comparison"]["ready"] or self.service.analyzer is None:
                raise SessionFileApiError(
                    409, "COMPARISON_NOT_READY", "请先确认比较对象和模型配置。"
                )
            if not self.service._slots.acquire(blocking=False):
                raise SessionFileApiError(429, "RUN_QUEUE_FULL", "分析任务较多。")
            try:
                self.service.update_agent_workflow(
                    owner,
                    session_id,
                    run_id,
                    revision,
                    "start",
                    topic_id=topic_id,
                    retry=True,
                )
                self.service._update(run_id, status="pending", stage="queued")
                self.service._executor.submit(
                    self.work, owner, session_id, run_id, resume_only=True
                )
            except Exception:
                self.service._slots.release()
                raise
            return self.service.get(owner, session_id, run_id)
