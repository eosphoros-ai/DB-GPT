"""Bounded local background runs. No uploaded code or client paths are executed."""

import hashlib
import json
import logging
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from dbgpt_serve.session_file.api.endpoints import SessionFileApiError
from dbgpt_serve.session_file.domain import FileScope

from . import workflow
from .analysis import SECTIONS, InvalidFindings, apply_findings, validate_findings
from .exports import render_export
from .models import FinancialExportEntity as Export
from .models import FinancialRunEntity as Run
from .questions import question_context, reference_only_answer, validate_answer
from .report import build_report

logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).isoformat()


class FinancialAnalysisService:
    """Single-process local runner with durable completion and restart recovery.

    Uses the registry's own DB/session factory and owner-scoped materialization.
    The PDF is opened inside the worker and stays alive until extraction exits.
    """

    def __init__(
        self,
        registry,
        *,
        extractor=None,
        analyzer=None,
        answerer=None,
        export_runtime=None,
    ):
        self.registry = registry
        self.session = registry.dao.session
        self.extractor = extractor or self._extract
        self.analyzer = analyzer
        self.answerer = answerer
        self.export_runtime = export_runtime
        self._question_slots = threading.BoundedSemaphore(2)
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(4)
        self._preview_slots = threading.BoundedSemaphore(2)
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="financial"
        )
        with self.session(commit=False) as session:
            engine = session.get_bind()
        Run.__table__.create(bind=engine, checkfirst=True)
        Export.__table__.create(bind=engine, checkfirst=True)
        # This runner is intentionally for one local server process. Completed
        # snapshots survive restart; abandoned jobs are never left running.
        with self.session() as session:
            session.query(Run).filter(Run.status.in_(["pending", "running"])).update(
                {
                    Run.status: "failed",
                    Run.error: "服务重启，任务已中断，请重新分析。",
                    Run.updated_at: now(),
                    Run.completed_at: now(),
                },
                synchronize_session=False,
            )
            # Data snapshots are committed before model work. Preserve them if
            # the process exited during analysis; do not leave a perpetual spinner.
            for row in session.query(Run).filter_by(
                status="completed", stage="analyze"
            ):
                report = json.loads(row.report_json)
                self._finish_report_analysis(
                    report, "failed", "服务重启，模型分析已中断；财务数据仍可查看。"
                )
                row.report_json = json.dumps(
                    report, ensure_ascii=False, allow_nan=False
                )
                row.stage, row.updated_at = "completed", now()
            for row in session.query(Run).filter_by(
                status="completed", stage="agent_topics"
            ):
                report = json.loads(row.report_json)
                for item in report.get("workflow", {}).get("topics", []):
                    if item["status"] == "running":
                        item.update(
                            status="needs_revision",
                            note="服务重启，专题尚未保存；可继续分析，无需重新解析。",
                        )
                workflow.changed(report)
                row.report_json = json.dumps(
                    report, ensure_ascii=False, allow_nan=False
                )
                row.stage, row.updated_at = "completed", now()

    @staticmethod
    def _public(row):
        result = {
            key: getattr(row, key)
            for key in [
                "id",
                "session_id",
                "file_id",
                "status",
                "stage",
                "created_at",
                "updated_at",
                "completed_at",
                "error",
            ]
        }
        result["report_ready"] = bool(row.report_json)
        result["analysis_status"] = (
            json.loads(row.report_json).get("analysis", {}).get("status")
            if row.report_json
            else None
        )
        return result

    def get(self, owner, session_id, run_id, *, report=False):
        with self.session(commit=False) as session:
            row = (
                session.query(Run)
                .filter_by(id=run_id, owner_id=owner, session_id=session_id)
                .first()
            )
            if row is None:
                raise SessionFileApiError(404, "RUN_NOT_FOUND", "未找到分析任务。")
            if report:
                if row.status != "completed" or not row.report_json:
                    raise SessionFileApiError(409, "REPORT_NOT_READY", "报告尚未完成。")
                return json.loads(row.report_json)
            return self._public(row)

    def list_runs(self, owner, page=1, page_size=10):
        with self.session(commit=False) as session:
            query = session.query(Run).filter_by(owner_id=owner)
            total = query.count()
            rows = (
                query.order_by(Run.created_at.desc(), Run.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = []
            for row in rows:
                item = self._public(row)
                if row.report_json:
                    report = json.loads(row.report_json)
                    item.update(
                        title=report["report"]["companyName"],
                        fiscal_period=report["report"]["fiscalPeriod"],
                    )
                else:
                    record = self.registry.get_file(
                        owner_id=owner, session_id=row.session_id, file_id=row.file_id
                    )
                    item.update(
                        title=record.display_name if record else "财报分析任务",
                        fiscal_period=None,
                    )
                items.append(item)
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    @staticmethod
    def _export_public(row):
        return {
            key: getattr(row, key)
            for key in [
                "id",
                "run_id",
                "revision",
                "format",
                "file_name",
                "created_at",
                "size_bytes",
                "sha256",
            ]
        }

    def list_exports(self, owner, session_id, run_id):
        self.get(owner, session_id, run_id)
        with self.session(commit=False) as session:
            # Metadata only; do not load multi-megabyte HTML bodies to list files.
            rows = (
                session.query(
                    Export.id,
                    Export.run_id,
                    Export.revision,
                    Export.format,
                    Export.file_name,
                    Export.created_at,
                    Export.size_bytes,
                    Export.sha256,
                )
                .filter_by(run_id=run_id)
                .order_by(Export.created_at.desc(), Export.id.desc())
                .all()
            )
            return [self._export_public(row) for row in rows]

    def create_export(self, owner, session_id, run_id, revision, kind):
        report = self.get(owner, session_id, run_id, report=True)
        if report["revision"] != revision:
            raise SessionFileApiError(
                409, "REPORT_CHANGED", "报告已更新，请刷新后再导出。"
            )
        if report.get("analysis", {}).get("status") == "running":
            raise SessionFileApiError(
                409, "ANALYSIS_RUNNING", "模型分析仍在执行，请结束后再导出。"
            )
        if kind not in {"json", "html"}:
            raise SessionFileApiError(
                400, "EXPORT_FORMAT_INVALID", "不支持的导出格式。"
            )
        export_id = hashlib.sha256(f"{run_id}:{revision}:{kind}".encode()).hexdigest()
        with self._lock:
            with self.session() as session:
                row = session.query(Export).filter_by(id=export_id).first()
                if row is None:
                    content = render_export(report, kind, self.export_runtime)
                    encoded = content.encode("utf-8")
                    row = Export(
                        id=export_id,
                        run_id=run_id,
                        revision=revision,
                        format=kind,
                        file_name=f"financial-{run_id}.{kind}",
                        created_at=now(),
                        size_bytes=len(encoded),
                        sha256=hashlib.sha256(encoded).hexdigest(),
                        content=content,
                    )
                    session.add(row)
                    session.flush()
                return self._export_public(row)

    def download_export(self, owner, session_id, run_id, export_id):
        self.get(owner, session_id, run_id)
        with self.session(commit=False) as session:
            row = session.query(Export).filter_by(id=export_id, run_id=run_id).first()
            if row is None:
                raise SessionFileApiError(404, "EXPORT_NOT_FOUND", "未找到导出文件。")
            return row.content.encode("utf-8"), self._export_public(row)

    def ask(self, owner, session_id, run_id, revision, question):
        report = self.get(owner, session_id, run_id, report=True)
        if report["revision"] != revision:
            raise SessionFileApiError(
                409, "REPORT_CHANGED", "报告已更新，请刷新后重新提问。"
            )
        answerer = self.answerer
        if answerer is None:
            raise SessionFileApiError(
                503, "QUESTIONS_UNAVAILABLE", "追问服务尚未就绪，请稍后重试。"
            )
        if not self._question_slots.acquire(blocking=False):
            raise SessionFileApiError(
                429, "QUESTIONS_BUSY", "追问请求较多，请稍后重试。"
            )
        try:
            try:
                context = question_context(report, question)
                raw = answerer(report, question, owner, session_id)
                try:
                    answer = validate_answer(raw, context, report)
                    answer["answerMode"] = (
                        "insufficient" if not answer["citations"] else "validated"
                    )
                except ValueError:
                    answer = reference_only_answer(raw, context, report)
            except TimeoutError as exc:
                raise SessionFileApiError(
                    504, "QUESTION_TIMEOUT", "回答超时，请稍后重新发送问题。"
                ) from exc
            except ValueError as exc:
                raise SessionFileApiError(
                    502, "ANSWER_INVALID", "回答未通过数字或引用校验，请重新提问。"
                ) from exc
            except Exception as exc:
                raise SessionFileApiError(
                    503, "QUESTIONS_UNAVAILABLE", "追问暂不可用，请稍后重试。"
                ) from exc
            if self.get(owner, session_id, run_id, report=True)["revision"] != revision:
                raise SessionFileApiError(
                    409, "REPORT_CHANGED", "报告已更新，请刷新后重新提问。"
                )
            return dict(
                answer,
                runId=run_id,
                revision=revision,
                question=question,
                modelName=answerer.model,
            )
        finally:
            self._question_slots.release()

    def create(
        self, owner, session_id, file_id, run_id, *, agent_model=None, sectional=False
    ):
        with self._lock:
            # Idempotent request IDs prevent a retry/double click from queuing
            # the same file twice. A new ID explicitly creates another attempt.
            with self.session(commit=False) as session:
                existing = session.query(Run).filter_by(id=run_id).first()
                if existing is not None:
                    if (existing.owner_id, existing.session_id, existing.file_id) != (
                        owner,
                        session_id,
                        file_id,
                    ):
                        raise SessionFileApiError(
                            409, "RUN_ID_CONFLICT", "任务标识不可复用。"
                        )
                    return self._public(existing)
            record = self.registry.get_file(
                owner_id=owner, session_id=session_id, file_id=file_id
            )
            if record is None:
                raise SessionFileApiError(
                    404, "FILE_NOT_FOUND", "未找到当前会话的文件。"
                )
            if not record.display_name.lower().endswith(".pdf"):
                raise SessionFileApiError(400, "PDF_REQUIRED", "请上传 PDF 年度报告。")
            if not self._slots.acquire(blocking=False):
                raise SessionFileApiError(
                    429, "RUN_QUEUE_FULL", "分析任务较多，请稍后重试。"
                )
            try:
                stamp = now()
                with self.session() as session:
                    row = Run(
                        id=run_id,
                        owner_id=owner,
                        session_id=session_id,
                        file_id=file_id,
                        status="pending",
                        stage="queued",
                        created_at=stamp,
                        updated_at=stamp,
                    )
                    session.add(row)
                    session.flush()
                    result = self._public(row)
                self._executor.submit(
                    self._work,
                    owner,
                    session_id,
                    file_id,
                    run_id,
                    agent_model,
                    sectional,
                )
            except Exception:
                self._slots.release()
                self._update(
                    run_id,
                    status="failed",
                    error="无法启动分析任务，请重试。",
                    completed_at=now(),
                )
                raise
            return result

    def _update(self, run_id, **values):
        with self.session() as session:
            session.query(Run).filter_by(id=run_id).update(
                dict(values, updated_at=now()), synchronize_session=False
            )

    def _work(
        self, owner, session_id, file_id, run_id, agent_model=None, sectional=False
    ):
        try:
            started_at = now()
            read_start = time.monotonic()
            timings = {}
            self._update(run_id, status="running", stage="extract")
            opened = self.registry.open_download(
                owner_id=owner, session_id=session_id, file_id=file_id
            )
            if opened is None:
                raise ValueError("上传文件已不可用，请重新上传。")
            stream, record = opened
            try:
                scope = FileScope(owner_id=owner, session_id=session_id)
                with self.registry.materialize_local_file(
                    scope, stream, ".pdf"
                ) as path:
                    extract_start = time.monotonic()
                    extract_at = now()
                    timings["read"] = {
                        "startedAt": started_at,
                        "completedAt": extract_at,
                        "elapsedMs": round((extract_start - read_start) * 1000),
                    }
                    extracted = self.extractor(path)
                    timings["extract"] = {
                        "startedAt": extract_at,
                        "completedAt": now(),
                        "elapsedMs": round((time.monotonic() - extract_start) * 1000),
                    }
            finally:
                stream.close()
            if extracted.get("document", {}).get("sha256") != record.sha256:
                raise ValueError("解析文件与上传文件不一致，任务已停止。")
            self._update(run_id, stage="calculate")
            calculate_start = time.monotonic()
            calculate_at = now()
            completed_at = now()
            report = build_report(
                extracted, {"id": run_id, "completed_at": completed_at}, record
            )
            timings["calculate"] = {
                "startedAt": calculate_at,
                "completedAt": now(),
                "elapsedMs": round((time.monotonic() - calculate_start) * 1000),
            }
            report["report"]["run"]["startedAt"] = started_at
            for step in report["steps"]:
                step.update(timings.get(step["id"], {}))
            # Agent turns reuse deterministic extraction/calculation, but the
            # conversational agent supplies findings through publish_agent_report.
            analyzer = (
                SimpleNamespace(model=agent_model) if agent_model else self.analyzer
            )
            if analyzer is not None:
                report["analysis"] = {
                    "status": "running",
                    "modelName": analyzer.model,
                    "startedAt": now(),
                    "completedAt": None,
                    "error": None,
                    "rejectedCount": 0,
                }
                report["report"]["run"]["modelName"] = analyzer.model
                report["steps"].append(
                    {
                        "id": "analyze",
                        "order": len(report["steps"]) + 1,
                        "type": "analysis",
                        "title": "生成并校验模型分析",
                        "detail": "财务数据已保存，正在基于引用生成分析。",
                        "status": "running",
                        "capability": "existing",
                        "startedAt": report["analysis"]["startedAt"],
                    }
                )
                report["agent"]["groups"].append(
                    {
                        "id": "analysis",
                        "title": "模型分析",
                        "stepIds": ["analyze"],
                        "content": "基于已保存事实和计算，生成并校验引用。",
                    }
                )
                if agent_model:
                    report["analysis"].update(status="partial", driver="agent")
                    report["steps"][-1].update(
                        status="pending",
                        detail="财务数据已就绪，等待当前智能体提交分析。",
                    )
                    report["agent"]["summary"] = (
                        "财务数据已保存，智能体尚未提交分析结论。"
                    )
                    if sectional:
                        workflow.initialize(report)
            self._update(run_id, stage="save")
            save_start = time.monotonic()
            save_at = now()
            # Status and snapshot become visible in the same transaction.
            with self.session() as session:
                row = session.query(Run).filter_by(id=run_id).one()
                row.status = "completed"
                row.stage = (
                    "analyze"
                    if analyzer is not None and not agent_model
                    else "completed"
                )
                row.completed_at, row.updated_at = completed_at, now()
                row.report_json = json.dumps(
                    report, ensure_ascii=False, allow_nan=False
                )
                session.flush()
                # Measure serialization/DB write, excluding transaction commit.
                next(step for step in report["steps"] if step["id"] == "save").update(
                    startedAt=save_at,
                    completedAt=now(),
                    elapsedMs=round((time.monotonic() - save_start) * 1000),
                )
                row.report_json = json.dumps(
                    report, ensure_ascii=False, allow_nan=False
                )
            if analyzer is not None and not agent_model:
                self._analyze(run_id, report, analyzer, owner, session_id)
        except subprocess.TimeoutExpired:
            self._update(
                run_id,
                status="failed",
                error="PDF 解析超过 120 秒，请检查文件或缩小报告范围。",
                completed_at=now(),
            )
        except ValueError as exc:
            self._update(run_id, status="failed", error=str(exc), completed_at=now())
        except Exception:
            logger.exception("Financial analysis run %s failed", run_id)
            self._update(
                run_id,
                status="failed",
                error="财报处理失败，请检查文件后重新分析。",
                completed_at=now(),
            )
        finally:
            self._slots.release()

    @staticmethod
    def _finish_report_analysis(report, status, error=None, rejected=0):
        report["analysis"].update(
            status=status,
            error=error,
            completedAt=now(),
            rejectedCount=rejected,
        )
        report["revision"] = report["report"]["run"]["id"] + "-analysis-final"
        step = next(s for s in report["steps"] if s["id"] == "analyze")
        stamp = report["analysis"]["completedAt"]
        step["completedAt"] = stamp
        if report["analysis"].get("startedAt"):
            step["startedAt"] = report["analysis"]["startedAt"]
            step["elapsedMs"] = max(
                0,
                round(
                    (
                        datetime.fromisoformat(stamp)
                        - datetime.fromisoformat(step["startedAt"])
                    ).total_seconds()
                    * 1000
                ),
            )
        step["status"] = "failed" if status == "failed" else "completed"
        step["detail"] = error or (
            f"已保留 {len(report['findings'])} 条引用校验通过的分析；"
            f"{rejected} 条未通过校验。结论仍需人工核对。"
        )
        report["agent"]["summary"] = "财务事实、计算和原文已保存。\n\n" + step["detail"]

    def publish_agent_report(
        self, owner, session_id, run_id, revision, findings, *, rejected_count=0
    ):
        """Validate the current agent's conclusions against its saved snapshot.

        Publication is one-shot per run. Exports of the initial data revision
        remain immutable, and a second turn cannot overwrite a published report.
        """
        with self._lock:
            report = self.get(owner, session_id, run_id, report=True)
            if report.get("workflow"):
                if findings:
                    raise SessionFileApiError(
                        409,
                        "USE_TOPIC_TOOLS",
                        "请逐专题保存结论并复核，最终发布时省略 findings。",
                    )
                if report["revision"] != revision:
                    raise SessionFileApiError(
                        409, "REPORT_CHANGED", "报告已更新，请重新读取。"
                    )
                report = workflow.publish(report)
                self._update(
                    run_id,
                    stage="completed",
                    report_json=json.dumps(report, ensure_ascii=False, allow_nan=False),
                )
                return report
            analysis = report.get("analysis", {})
            if (
                report["revision"] != revision
                or analysis.get("driver") != "agent"
                or analysis.get("completedAt") is not None
            ):
                raise SessionFileApiError(
                    409, "REPORT_CHANGED", "报告已更新，请重新读取。"
                )
            if findings == []:
                accepted, rejected = [], rejected_count
            else:
                accepted, rejected = validate_findings(
                    json.dumps({"findings": findings}, ensure_ascii=False), report
                )
            report = apply_findings(report, accepted)
            complete = not rejected and {f["sectionKey"] for f in accepted} == set(
                SECTIONS
            )
            self._finish_report_analysis(
                report,
                "completed" if complete else "partial",
                rejected=rejected,
                error=(
                    "结论格式修正多次仍未通过校验，本次仅保留财务数据与原文依据。"
                    if not findings and rejected_count
                    else None
                ),
            )
            self._update(
                run_id,
                stage="completed",
                report_json=json.dumps(report, ensure_ascii=False, allow_nan=False),
            )
            return report

    def update_agent_workflow(
        self, owner, session_id, run_id, revision, action, **kwargs
    ):
        """Revision-checked topic mutations preserve the extraction and other topics."""
        with self._lock:
            report = self.get(owner, session_id, run_id, report=True)
            if report["revision"] != revision:
                raise SessionFileApiError(
                    409, "REPORT_CHANGED", "报告已更新，请重新读取。"
                )
            if not report.get("workflow"):
                raise SessionFileApiError(
                    409, "LEGACY_REPORT", "旧版报告请新建分析以启用专题流程。"
                )
            actions = {
                "start": workflow.start_topic,
                "save": workflow.save_topic,
                "review": workflow.review_report,
            }
            report = actions[action](report, **kwargs)
            self._update(
                run_id,
                stage="agent_topics",
                report_json=json.dumps(report, ensure_ascii=False, allow_nan=False),
            )
            return report

    def latest_agent_report(self, owner, session_id):
        """Find a report only within the authenticated conversation."""
        with self.session(commit=False) as session:
            rows = (
                session.query(Run)
                .filter_by(owner_id=owner, session_id=session_id)
                .order_by(Run.created_at.desc())
                .all()
            )
            for row in rows:
                if row.report_json:
                    report = json.loads(row.report_json)
                    if report.get("analysis", {}).get("driver") == "agent":
                        return report
        raise SessionFileApiError(
            404, "REPORT_NOT_FOUND", "当前对话还没有财报分析结果。"
        )

    def _analyze(self, run_id, report, analyzer, owner, session_id):
        # Catch model/validation failures here, separately from data processing.
        # Do not persist raw model output, provider errors, credentials or reasoning.
        rejected = 0
        try:
            raw = analyzer(report, owner, session_id)
            findings, rejected = validate_findings(raw, report)
            report = apply_findings(report, findings)
            covered = {f["sectionKey"] for f in findings}
            status = "partial" if rejected or covered != set(SECTIONS) else "completed"
            error = None
        except TimeoutError:
            status, error = "failed", "模型分析超时，财务数据和原文仍可查看。"
        except InvalidFindings as exc:
            rejected = exc.rejected_count
            logger.warning("Analysis rejected for run %s: %s", run_id, exc.issue_counts)
            status, error = "failed", "模型输出未通过数字或引用校验，财务数据仍可查看。"
        except ValueError:
            logger.warning("Analysis format invalid for run %s", run_id)
            status, error = (
                "failed",
                "模型输出未通过结构、数字或引用校验，财务数据仍可查看。",
            )
        except Exception:
            status, error = "failed", "模型分析暂不可用，财务数据和原文仍可查看。"
        self._finish_report_analysis(report, status, error, rejected)
        try:
            self._update(
                run_id,
                stage="completed",
                report_json=json.dumps(report, ensure_ascii=False, allow_nan=False),
            )
        except Exception:
            # The earlier data snapshot remains valid even if this write fails.
            logger.error("Could not persist analysis for run %s", run_id)

    @staticmethod
    def _extract(path):
        from dbgpt.configs.model_config import SKILLS_DIR

        script = (
            Path(SKILLS_DIR) / "financial-report-analyzer/scripts/extract_financials.py"
        )
        if not script.is_file():
            raise ValueError("财报提取脚本未安装，请检查 DBGPT_SKILLS_DIR 配置。")
        completed = subprocess.run(
            [sys.executable, str(script), json.dumps({"file_path": str(path)})],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            env=dict(os.environ, PYTHONIOENCODING="utf-8"),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if completed.returncode:
            raise ValueError("PDF 解析失败，文件可能损坏、加密或格式不受支持。")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("提取脚本返回格式无效。") from exc
        if not isinstance(result, dict) or result.get("error"):
            raise ValueError("PDF 提取未成功，请检查文件。")
        return result

    def open_source(self, owner, session_id, run_id, document_id):
        report = self.get(owner, session_id, run_id, report=True)
        document = next(
            (d for d in report["documents"] if d["id"] == document_id), None
        )
        run = self.get(owner, session_id, run_id)
        if not document or document.get("fileId") != run["file_id"]:
            raise SessionFileApiError(
                404, "SOURCE_NOT_FOUND", "未找到此报告的来源文件。"
            )
        opened = self.registry.open_download(
            owner_id=owner, session_id=session_id, file_id=document["fileId"]
        )
        if opened is None:
            raise SessionFileApiError(
                404, "SOURCE_NOT_FOUND", "原文件已不可用；已保存的摘录仍可查看。"
            )
        stream, record = opened
        if record.sha256 != document.get("sha256"):
            stream.close()
            raise SessionFileApiError(
                409, "SOURCE_CHANGED", "来源文件与报告快照不一致。"
            )
        return stream, record, document

    def render_source_page(self, owner, session_id, run_id, document_id, page_number):
        stream, record, document = self.open_source(
            owner, session_id, run_id, document_id
        )
        try:
            if not 1 <= page_number <= document.get("pageCount", 0):
                raise SessionFileApiError(
                    404, "PAGE_NOT_FOUND", "PDF 物理页码超出范围。"
                )
            if not self._preview_slots.acquire(blocking=False):
                raise SessionFileApiError(
                    429, "PREVIEW_BUSY", "页面正在加载，请稍后重试。"
                )
            try:
                scope = FileScope(owner_id=owner, session_id=session_id)
                with self.registry.materialize_local_file(
                    scope, stream, ".pdf"
                ) as path:
                    if hashlib.sha256(path.read_bytes()).hexdigest() != record.sha256:
                        raise SessionFileApiError(
                            409, "SOURCE_CHANGED", "来源文件内容校验失败。"
                        )
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(Path(__file__).with_name("render_pdf.py")),
                            str(path),
                            str(page_number),
                        ],
                        capture_output=True,
                        timeout=20,
                        creationflags=subprocess.CREATE_NO_WINDOW
                        if os.name == "nt"
                        else 0,
                    )
                    if completed.returncode == 2:
                        raise SessionFileApiError(
                            404, "PAGE_NOT_FOUND", "PDF 物理页码超出范围。"
                        )
                    if completed.returncode or not completed.stdout.startswith(
                        b"\x89PNG\r\n\x1a\n"
                    ):
                        raise SessionFileApiError(
                            422, "PREVIEW_FAILED", "此页无法预览，请下载原 PDF 核对。"
                        )
                    return completed.stdout
            except subprocess.TimeoutExpired as exc:
                raise SessionFileApiError(
                    504, "PREVIEW_TIMEOUT", "页面渲染超时，请重试或下载原 PDF。"
                ) from exc
            finally:
                self._preview_slots.release()
        finally:
            stream.close()

    def close(self):
        self._executor.shutdown(wait=True)
