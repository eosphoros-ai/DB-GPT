"""Application service for owner-scoped report persistence."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from dbgpt.core.interface.report import (
    Artifact,
    ReportDocument,
    ReportPresentationBinding,
)
from dbgpt.core.interface.report_assembly import ReportAssembler
from dbgpt.core.interface.report_capture import (
    artifact_content_path,
    artifact_storage_root,
    sha256_json,
    store_artifact_json,
)

from .domain import ReportEvidenceDetail, ReportRunRecord, ReportRunSummary
from .models.dao import ReportDao


class ReportNotFoundError(LookupError):
    """The requested report run is not visible in the owner scope."""


class ReportBlockNotFoundError(LookupError):
    """The requested block is absent from an otherwise visible report run."""


class ReportService:
    """Thin orchestration layer above the transactional report DAO."""

    def __init__(
        self,
        dao: Optional[ReportDao] = None,
        assembler: Optional[ReportAssembler] = None,
    ) -> None:
        self._dao = dao or ReportDao()
        self._assembler = assembler or ReportAssembler()

    def save(
        self,
        *,
        owner_id: str,
        document: ReportDocument,
        trigger_type: str = "interactive",
        parent_run_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> ReportRunRecord:
        """Persist one immutable report revision."""
        kwargs: Dict[str, Any] = {
            "owner_id": owner_id,
            "trigger_type": trigger_type,
            "parent_run_id": parent_run_id,
        }
        if run_id is not None:
            kwargs["run_id"] = run_id
        return self._dao.save(document, **kwargs)

    def assemble_and_save(
        self,
        *,
        owner_id: str,
        report_id: str,
        title: str,
        conv_uid: str,
        final_content: str,
        artifacts: Sequence[Artifact],
        supporting_artifact_ids: Iterable[str] = (),
        presentation_bindings: Sequence[
            ReportPresentationBinding | Dict[str, Any]
        ] = (),
        presentation: Optional[Dict[str, Any]] = None,
        include_chart_blocks: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        trigger_type: str = "interactive",
        parent_run_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> ReportRunRecord:
        """Assemble one captured turn and persist it as an immutable revision."""
        document = self._assembler.assemble(
            report_id=report_id,
            title=title,
            conv_uid=conv_uid,
            final_content=final_content,
            artifacts=artifacts,
            supporting_artifact_ids=supporting_artifact_ids,
            presentation_bindings=presentation_bindings,
            presentation=presentation,
            include_chart_blocks=include_chart_blocks,
            created_at=created_at,
            metadata=metadata,
        )
        return self.save(
            owner_id=owner_id,
            document=document,
            trigger_type=trigger_type,
            parent_run_id=parent_run_id,
            run_id=run_id,
        )

    def get_latest(self, owner_id: str, report_id: str) -> ReportRunRecord:
        """Return the latest visible run or raise a domain not-found error."""
        record = self._dao.get_latest(owner_id, report_id)
        if record is None:
            raise ReportNotFoundError(report_id)
        return record

    def get_run(self, owner_id: str, report_id: str, run_id: str) -> ReportRunRecord:
        """Return one exact visible run or raise a domain not-found error."""
        record = self._dao.get_run(owner_id, report_id, run_id)
        if record is None:
            raise ReportNotFoundError(run_id)
        return record

    def list_runs(
        self,
        owner_id: str,
        report_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ReportRunSummary]:
        """List revisions only after verifying the report is owner-visible."""
        self.get_latest(owner_id, report_id)
        return self._dao.list_runs(owner_id, report_id, limit=limit, offset=offset)

    def artifact_content(self, owner_id, report_id, run_id, artifact_id, part):
        """Resolve only content attached to an owner-visible artifact."""
        run = self.get_run(owner_id, report_id, run_id)
        artifact = next(
            (a for a in run.document.artifacts if a.artifact_id == artifact_id), None
        )
        if artifact is None:
            raise ReportNotFoundError(artifact_id)
        if part == "source":
            content = artifact.metadata.get("content")
        elif part in {"renderer_template", "streams"}:
            content = artifact.metadata.get(part)
        else:
            value = getattr(artifact, part, None)
            content = value.model_dump(exclude_none=True) if value else None
            if (
                part == "output"
                and content
                and not str(content.get("uri", "")).startswith("artifact://")
            ):
                content = artifact.metadata.get("content")
        if not content or not content.get("uri"):
            raise ReportNotFoundError("Snapshot not captured")
        return artifact_content_path(content["uri"]), content.get(
            "media_type", "application/octet-stream"
        )

    def _observation_directory(self, owner_id, report_id, run_id) -> Path:
        self.get_run(owner_id, report_id, run_id)
        return (
            artifact_storage_root()
            / "observations"
            / sha256_json([owner_id, report_id, run_id])
        )

    def save_render_observation(self, owner_id, report_id, run_id, observation):
        """Append a browser measurement without changing the report revision."""
        run = self.get_run(owner_id, report_id, run_id)
        artifact = next(
            (
                a
                for a in run.document.artifacts
                if a.artifact_id == observation["artifact_id"]
            ),
            None,
        )
        if (
            artifact is None
            or artifact.type != "chart"
            or artifact.status != "succeeded"
        ):
            raise ValueError(
                "RENDER_OBSERVATION_ARTIFACT_INVALID: "
                "expected a successful chart in this run"
            )
        expected = (
            "image"
            if artifact.chart_type == "image"
            else "echarts"
            if artifact.spec.get("renderer") == "echarts"
            else "table"
            if artifact.chart_type == "response_table"
            else "g2"
        )
        if observation["renderer"] != expected:
            raise ValueError("RENDER_OBSERVATION_RENDERER_INVALID")
        options = observation.pop("options", None)
        if options is not None:
            encoded = json.dumps(options, ensure_ascii=False, allow_nan=False)
            if len(encoded.encode("utf-8")) > 4 * 1024 * 1024:
                raise ValueError("RENDER_OBSERVATION_OPTIONS_TOO_LARGE")
            observation["options_content"] = store_artifact_json(options).model_dump(
                exclude_none=True
            )
        observation["source"] = "browser"
        directory = self._observation_directory(owner_id, report_id, run_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (
            sha256_json([observation["observation_id"], observation["artifact_id"]])
            + ".json"
        )
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if {k: v for k, v in existing.items() if k != "received_at"} != observation:
                raise ValueError("RENDER_OBSERVATION_CONFLICT")
            return existing
        observation["received_at"] = datetime.now(timezone.utc).isoformat()
        with tempfile.NamedTemporaryFile(
            dir=directory, delete=False, suffix=".pending"
        ) as handle:
            temporary = Path(handle.name)
            handle.write(
                json.dumps(observation, ensure_ascii=False, allow_nan=False).encode(
                    "utf-8"
                )
            )
        try:
            # Publish complete bytes exclusively; preserve earlier observations.
            os.link(temporary, path)
        except FileExistsError:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if {k: v for k, v in existing.items() if k != "received_at"} != {
                k: v for k, v in observation.items() if k != "received_at"
            }:
                raise ValueError("RENDER_OBSERVATION_CONFLICT")
            return existing
        finally:
            temporary.unlink(missing_ok=True)
        return observation

    def list_render_observations(self, owner_id, report_id, run_id):
        directory = self._observation_directory(owner_id, report_id, run_id)
        if not directory.exists():
            return []
        paths = sorted(
            directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:100]
        return [json.loads(path.read_text(encoding="utf-8")) for path in paths]

    def render_observation_content(
        self, owner_id, report_id, run_id, artifact_id, observation_id
    ):
        directory = self._observation_directory(owner_id, report_id, run_id)
        path = directory / (sha256_json([observation_id, artifact_id]) + ".json")
        if not path.is_file():
            raise ReportNotFoundError(observation_id)
        observation = json.loads(path.read_text(encoding="utf-8"))
        content = observation.get("options_content")
        if not content:
            raise ReportNotFoundError("Render options not captured")
        return artifact_content_path(content["uri"]), "application/json"

    def get_block_evidence(
        self,
        owner_id: str,
        report_id: str,
        run_id: str,
        block_id: str,
        *,
        limit: int = 50,
    ) -> List[ReportEvidenceDetail]:
        """Return evidence while distinguishing missing and evidence-free blocks."""
        run = self.get_run(owner_id, report_id, run_id)
        if not any(
            block.block_id == block_id
            for section in run.document.sections
            for block in section.blocks
        ):
            raise ReportBlockNotFoundError(block_id)
        return self._dao.get_block_evidence(
            owner_id, report_id, run_id, block_id, limit=limit
        )
