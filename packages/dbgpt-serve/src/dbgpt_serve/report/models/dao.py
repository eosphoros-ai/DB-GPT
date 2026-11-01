"""Transactional persistence for report snapshots and evidence indexes."""

import json
import math
import time
from collections.abc import Mapping
from typing import List, Optional
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from dbgpt.core.interface.report import (
    REPORT_SCHEMA_VERSION,
    Artifact,
    EvidenceReference,
    ReportDocument,
)
from dbgpt.storage.metadata import BaseDao

from ..domain import (
    ReportEvidenceDetail,
    ReportRunRecord,
    ReportRunSummary,
    ReportWriteConflictError,
)
from .models import (
    MAX_ARTIFACT_ID_LENGTH,
    MAX_BLOCK_ID_LENGTH,
    MAX_CONV_UID_LENGTH,
    MAX_MESSAGE_ID_LENGTH,
    MAX_OWNER_ID_LENGTH,
    MAX_REPORT_ID_LENGTH,
    MAX_REPORT_TITLE_LENGTH,
    MAX_RUN_ID_LENGTH,
    MAX_SECTION_ID_LENGTH,
    MAX_STEP_ID_LENGTH,
    MAX_TASK_ID_LENGTH,
    ReportArtifactDependencyEntity,
    ReportArtifactEntity,
    ReportEntity,
    ReportEvidenceEntity,
    ReportRunEntity,
)

_ARTIFACT_ADAPTER = TypeAdapter(Artifact)
_TRIGGER_TYPES = {"interactive", "refresh", "replay", "scheduled"}
_MAX_SAVE_ATTEMPTS = 3


class ReportDao(BaseDao[ReportEntity, dict, dict]):
    """Owner-scoped DAO whose save operation is one atomic transaction."""

    def from_request(self, request):
        request_dict = request if isinstance(request, dict) else request.model_dump()
        return ReportEntity(**request_dict)

    def to_request(self, entity: ReportEntity) -> dict:
        return {"owner_id": entity.owner_id, "report_id": entity.report_id}

    def to_response(self, entity: ReportEntity) -> dict:
        return {
            "report_id": entity.report_id,
            "title": entity.title,
            "conv_uid": entity.conv_uid,
            "latest_run_id": entity.latest_run_id,
            "latest_revision": entity.latest_revision,
        }

    def save(
        self,
        document: ReportDocument,
        *,
        owner_id: str,
        trigger_type: str = "interactive",
        parent_run_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> ReportRunRecord:
        """Append an immutable run and all query indexes atomically."""
        owner_id = self._require_identifier(owner_id, "owner_id", MAX_OWNER_ID_LENGTH)
        run_id = self._require_identifier(
            run_id or str(uuid4()), "run_id", MAX_RUN_ID_LENGTH
        )
        if parent_run_id is not None:
            self._require_identifier(parent_run_id, "parent_run_id", MAX_RUN_ID_LENGTH)
        if trigger_type not in _TRIGGER_TYPES:
            raise ValueError(f"unsupported trigger_type: {trigger_type}")

        # Produce one finite, canonical JSON snapshot and re-parse it before
        # opening the transaction. ReportDocument instances are mutable, so
        # this is the trust boundary that reruns all protocol validators. Every
        # normalized row below is derived from this validated copy.
        self._assert_finite(document.model_dump(mode="python", warnings="none"))
        document_json = self._canonical_json(
            document.model_dump(mode="json", warnings="none")
        )
        try:
            document = ReportDocument.model_validate_json(document_json)
        except ValueError as error:
            raise ValueError(f"invalid ReportDocument JSON: {error}") from error
        document_json = self._canonical_json(
            document.model_dump(mode="json", warnings="none")
        )
        self._validate_storage_lengths(document)
        for attempt in range(_MAX_SAVE_ATTEMPTS):
            try:
                return self._save_once(
                    document=document,
                    document_json=document_json,
                    owner_id=owner_id,
                    run_id=run_id,
                    trigger_type=trigger_type,
                    parent_run_id=parent_run_id,
                )
            except IntegrityError as error:
                if self._run_id_exists(run_id):
                    raise ValueError(f"run_id already exists: {run_id}") from error
                if not self._is_revision_conflict(error):
                    raise
                self._retry_or_raise(attempt, error)
            except OperationalError as error:
                if not self._is_retryable_operational_error(error):
                    raise
                self._retry_or_raise(attempt, error)
        raise AssertionError("unreachable report save retry state")

    def _save_once(
        self,
        *,
        document: ReportDocument,
        document_json: str,
        owner_id: str,
        run_id: str,
        trigger_type: str,
        parent_run_id: Optional[str],
    ) -> ReportRunRecord:
        """Execute one report-save transaction; callers handle contention."""
        artifact_rows = [
            self._artifact_entity(run_id, item) for item in document.artifacts
        ]
        dependency_rows = [
            ReportArtifactDependencyEntity(
                run_id=run_id,
                artifact_id=artifact.artifact_id,
                input_artifact_id=input_id,
            )
            for artifact in document.artifacts
            for input_id in dict.fromkeys(artifact.input_artifact_ids)
        ]
        evidence_rows = [
            ReportEvidenceEntity(
                run_id=run_id,
                section_id=section.section_id,
                block_id=block.block_id,
                ordinal=ordinal,
                artifact_id=evidence.artifact_id,
                role=evidence.role,
                selector_json=self._canonical_json(evidence.selector),
                target_selector_json=self._canonical_json(evidence.target_selector),
            )
            for section in document.sections
            for block in section.blocks
            for ordinal, evidence in enumerate(block.evidence)
        ]

        with self.session() as session:
            if (
                session.query(ReportRunEntity)
                .filter(ReportRunEntity.run_id == run_id)
                .first()
                is not None
            ):
                raise ValueError(f"run_id already exists: {run_id}")
            if parent_run_id is not None and (
                self._run_query(
                    session,
                    owner_id,
                    document.report_id,
                    parent_run_id,
                ).first()
                is None
            ):
                raise ValueError(
                    "parent_run_id must identify a run in the same report scope"
                )

            report = (
                session.query(ReportEntity)
                .filter(
                    ReportEntity.owner_id == owner_id,
                    ReportEntity.report_id == document.report_id,
                )
                .with_for_update()
                .first()
            )
            if report is None:
                revision = 1
                report = ReportEntity(
                    report_id=document.report_id,
                    owner_id=owner_id,
                    title=document.title,
                    conv_uid=document.conv_uid,
                    latest_run_id=run_id,
                    latest_revision=revision,
                )
                session.add(report)
            else:
                if report.conv_uid != document.conv_uid:
                    raise ValueError("conv_uid cannot change between report revisions")
                revision = report.latest_revision + 1
                report.title = document.title
                report.latest_run_id = run_id
                report.latest_revision = revision

            self._before_flush(document.report_id, revision)
            run = ReportRunEntity(
                run_id=run_id,
                report_id=document.report_id,
                owner_id=owner_id,
                revision=revision,
                schema_version=document.schema_version,
                trigger_type=trigger_type,
                parent_run_id=parent_run_id,
                status="completed",
                document_json=document_json,
            )
            session.add(run)
            session.add_all(artifact_rows)
            session.add_all(dependency_rows)
            session.add_all(evidence_rows)
            session.flush()
            return self._run_record(run)

    def _run_id_exists(self, run_id: str) -> bool:
        with self.session(commit=False) as session:
            return (
                session.query(ReportRunEntity)
                .filter(ReportRunEntity.run_id == run_id)
                .first()
                is not None
            )

    @staticmethod
    def _before_flush(report_id: str, revision: int) -> None:
        """Concurrency-test seam invoked after revision allocation, before writes."""

    @staticmethod
    def _is_revision_conflict(error: IntegrityError) -> bool:
        message = str(error.orig).lower()
        return any(
            token in message
            for token in (
                "uk_report_owner_report",
                "uk_report_run_owner_report_revision",
                "dbgpt_report.owner_id, dbgpt_report.report_id",
                "dbgpt_report_run.owner_id, dbgpt_report_run.report_id",
            )
        )

    @staticmethod
    def _is_retryable_operational_error(error: OperationalError) -> bool:
        message = str(error.orig).lower()
        code = error.orig.args[0] if getattr(error.orig, "args", ()) else None
        return code in (1205, 1213, "40001", "40P01") or any(
            token in message
            for token in (
                "database is locked",
                "deadlock",
                "lock wait timeout",
                "could not serialize",
                "serialization failure",
            )
        )

    @staticmethod
    def _retry_or_raise(attempt: int, error: Exception) -> None:
        if attempt + 1 >= _MAX_SAVE_ATTEMPTS:
            raise ReportWriteConflictError(
                "concurrent report save could not be serialized"
            ) from error
        time.sleep(0.01 * (2**attempt))

    def get_latest(self, owner_id: str, report_id: str) -> Optional[ReportRunRecord]:
        """Return the latest owner-visible snapshot."""
        with self.session(commit=False) as session:
            report = (
                session.query(ReportEntity)
                .filter(
                    ReportEntity.owner_id == owner_id,
                    ReportEntity.report_id == report_id,
                )
                .first()
            )
            if report is None:
                return None
            run = (
                session.query(ReportRunEntity)
                .filter(ReportRunEntity.run_id == report.latest_run_id)
                .first()
            )
            return self._run_record(run) if run is not None else None

    def get_run(
        self, owner_id: str, report_id: str, run_id: str
    ) -> Optional[ReportRunRecord]:
        """Return an exact immutable snapshot in the owner/report scope."""
        with self.session(commit=False) as session:
            run = self._run_query(session, owner_id, report_id, run_id).first()
            return self._run_record(run) if run is not None else None

    def list_runs(
        self, owner_id: str, report_id: str, *, limit: int = 50, offset: int = 0
    ) -> List[ReportRunSummary]:
        """List owner-visible revisions newest first."""
        if limit < 1 or limit > 200 or offset < 0:
            raise ValueError("invalid report run pagination")
        with self.session(commit=False) as session:
            runs = (
                session.query(ReportRunEntity)
                .filter(
                    ReportRunEntity.owner_id == owner_id,
                    ReportRunEntity.report_id == report_id,
                )
                .order_by(ReportRunEntity.revision.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [self._run_summary(run) for run in runs]

    def get_block_evidence(
        self,
        owner_id: str,
        report_id: str,
        run_id: str,
        block_id: str,
        *,
        limit: int = 50,
    ) -> List[ReportEvidenceDetail]:
        """Return indexed evidence only if its run is owner-visible."""
        if limit < 1 or limit > 200:
            raise ValueError("invalid evidence limit")
        with self.session(commit=False) as session:
            if self._run_query(session, owner_id, report_id, run_id).first() is None:
                return []
            rows = (
                session.query(ReportEvidenceEntity, ReportArtifactEntity)
                .join(
                    ReportArtifactEntity,
                    (ReportArtifactEntity.run_id == ReportEvidenceEntity.run_id)
                    & (
                        ReportArtifactEntity.artifact_id
                        == ReportEvidenceEntity.artifact_id
                    ),
                )
                .filter(
                    ReportEvidenceEntity.run_id == run_id,
                    ReportEvidenceEntity.block_id == block_id,
                )
                .order_by(ReportEvidenceEntity.ordinal)
                .limit(limit)
                .all()
            )
            return [
                self._evidence_detail(evidence, artifact) for evidence, artifact in rows
            ]

    @staticmethod
    def _run_query(session: Session, owner_id: str, report_id: str, run_id: str):
        return session.query(ReportRunEntity).filter(
            ReportRunEntity.owner_id == owner_id,
            ReportRunEntity.report_id == report_id,
            ReportRunEntity.run_id == run_id,
        )

    @staticmethod
    def _artifact_entity(run_id: str, artifact: Artifact) -> ReportArtifactEntity:
        execution = artifact.execution
        return ReportArtifactEntity(
            run_id=run_id,
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.type,
            conv_uid=execution.conv_uid,
            step_id=execution.step_id,
            message_id=execution.message_id,
            task_id=execution.task_id,
            execution_run_id=execution.run_id,
            artifact_json=ReportDao._canonical_json(artifact.model_dump(mode="json")),
        )

    @staticmethod
    def _run_summary(entity: ReportRunEntity) -> ReportRunSummary:
        return ReportRunSummary(
            run_id=entity.run_id,
            report_id=entity.report_id,
            revision=entity.revision,
            schema_version=REPORT_SCHEMA_VERSION,
            trigger_type=entity.trigger_type,
            parent_run_id=entity.parent_run_id,
            status=entity.status,
            created_at=entity.created_at,
        )

    @classmethod
    def _run_record(cls, entity: ReportRunEntity) -> ReportRunRecord:
        summary = cls._run_summary(entity)
        return ReportRunRecord(
            **summary.__dict__,
            document=ReportDocument.model_validate_json(entity.document_json),
        )

    @staticmethod
    def _evidence_detail(
        evidence: ReportEvidenceEntity, artifact: ReportArtifactEntity
    ) -> ReportEvidenceDetail:
        reference = EvidenceReference(
            artifact_id=evidence.artifact_id,
            role=evidence.role,
            selector=json.loads(evidence.selector_json),
            target_selector=json.loads(evidence.target_selector_json),
        )
        return ReportEvidenceDetail(
            section_id=evidence.section_id,
            block_id=evidence.block_id,
            ordinal=evidence.ordinal,
            evidence=reference,
            artifact=_ARTIFACT_ADAPTER.validate_json(artifact.artifact_json),
        )

    @staticmethod
    def _require_identifier(value: str, name: str, max_length: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must not be blank")
        if len(value) > max_length:
            raise ValueError(f"{name} exceeds {max_length} characters")
        return value

    @classmethod
    def _validate_storage_lengths(cls, document: ReportDocument) -> None:
        cls._require_identifier(document.report_id, "report_id", MAX_REPORT_ID_LENGTH)
        cls._require_identifier(document.title, "title", MAX_REPORT_TITLE_LENGTH)
        cls._require_identifier(document.conv_uid, "conv_uid", MAX_CONV_UID_LENGTH)
        for section in document.sections:
            cls._require_identifier(
                section.section_id, "section_id", MAX_SECTION_ID_LENGTH
            )
            for block in section.blocks:
                cls._require_identifier(block.block_id, "block_id", MAX_BLOCK_ID_LENGTH)
        for artifact in document.artifacts:
            cls._require_identifier(
                artifact.artifact_id, "artifact_id", MAX_ARTIFACT_ID_LENGTH
            )
            for input_id in artifact.input_artifact_ids:
                cls._require_identifier(
                    input_id, "input_artifact_id", MAX_ARTIFACT_ID_LENGTH
                )
            execution = artifact.execution
            cls._require_identifier(
                execution.conv_uid, "execution.conv_uid", MAX_CONV_UID_LENGTH
            )
            cls._require_identifier(
                execution.step_id, "execution.step_id", MAX_STEP_ID_LENGTH
            )
            for value, name, max_length in (
                (execution.message_id, "execution.message_id", MAX_MESSAGE_ID_LENGTH),
                (execution.task_id, "execution.task_id", MAX_TASK_ID_LENGTH),
                (execution.run_id, "execution.run_id", MAX_RUN_ID_LENGTH),
            ):
                if value is not None:
                    cls._require_identifier(value, name, max_length)

    @staticmethod
    def _canonical_json(value) -> str:
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"report data must be finite JSON: {error}") from error

    @classmethod
    def _assert_finite(cls, value) -> None:
        """Reject values that Pydantic's JSON mode would silently coerce to null."""
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("report data must be finite JSON")
        if isinstance(value, Mapping):
            for item in value.values():
                cls._assert_finite(item)
        elif isinstance(value, (list, tuple, set, frozenset)):
            for item in value:
                cls._assert_finite(item)
