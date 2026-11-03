"""Revision writes and the mutable current pointer share one transaction."""

import hashlib
import json

from dbgpt_serve.session_file.api.endpoints import SessionFileApiError

from .comparison_schema import stable_id
from .models import FinancialReportRevisionEntity as Revision
from .workflow import public_snapshot


def save_revision(session, run, report, *, timestamp, update_current=True):
    if not run.supports_revisions:
        if update_current:
            run.report_json = json.dumps(report, ensure_ascii=False, allow_nan=False)
            run.updated_at = timestamp
        return
    snapshot = public_snapshot(report)
    content = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, allow_nan=False)
    digest = hashlib.sha256(content.encode()).hexdigest()
    existing = (
        session.query(Revision)
        .filter_by(run_id=run.id, revision=report["revision"])
        .first()
    )
    if existing:
        if existing.sha256 != digest:
            raise SessionFileApiError(
                409, "IMMUTABLE_REVISION", "此版本已保存，不能覆盖。"
            )
    else:
        session.add(
            Revision(
                id=stable_id("revision", run.id, report["revision"]),
                run_id=run.id,
                revision=report["revision"],
                report_json=content,
                published_at=timestamp,
                sha256=digest,
            )
        )
    if update_current:
        run.report_json = json.dumps(report, ensure_ascii=False, allow_nan=False)
        run.updated_at = timestamp


def read_revision(session, run, revision):
    if run.supports_revisions:
        row = (
            session.query(Revision).filter_by(run_id=run.id, revision=revision).first()
        )
        if row:
            return json.loads(row.report_json)
    # Legacy runs can supply only the snapshot that still exists.
    current = json.loads(run.report_json) if run.report_json else None
    if current and current["revision"] == revision:
        return current
    raise SessionFileApiError(404, "REVISION_NOT_FOUND", "未保存此报告版本。")
