"""Financial run API reusing the session-file authentication and envelopes."""

from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.background import BackgroundTask

from dbgpt_serve.core import Result
from dbgpt_serve.session_file.api.endpoints import (
    SessionFileApiError,
    _SessionFileApiRoute,
    get_authenticated_owner,
)

from .comparison_schema import ComparisonConfig, ComparisonRequest
from .workflow import public_snapshot


class CreateRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    file_ids: list[str] = Field(min_length=1, max_length=5)
    request_id: UUID = Field(default_factory=uuid4)
    mode: Literal["report", "comparison"] = "report"
    comparison: ComparisonConfig | None = None

    @model_validator(mode="after")
    def validate_mode(self):
        if self.mode == "report":
            if len(self.file_ids) != 1 or self.comparison is not None:
                raise ValueError("Single report requires exactly one file")
        else:
            if self.comparison is None:
                raise ValueError("Comparison configuration required")
            ComparisonRequest(file_ids=self.file_ids, comparison=self.comparison)
        return self


class IdentityResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str = Field(min_length=2, max_length=120)
    report_year: str = Field(pattern=r"^20\d{2}$")


class ResumeRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    revision: str | None = Field(default=None, max_length=255)
    resolutions: dict[str, IdentityResolution] = Field(
        default_factory=dict, max_length=5
    )


class ReconfigureRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    revision: str = Field(min_length=1, max_length=255)
    comparison: ComparisonConfig


class RetryTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    revision: str = Field(min_length=1, max_length=255)
    topic_id: str = Field(min_length=1, max_length=40)


class AskQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    revision: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Question is empty")
        return value


class CreateExport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    revision: str = Field(min_length=1, max_length=255)
    format: Literal["json", "html"]
    language: Literal["zh", "en"] = "zh"


def make_router(service):
    router = APIRouter(route_class=_SessionFileApiRoute)

    @router.get("/runs")
    def list_runs(
        page: int = Query(default=1, ge=1, le=100000),
        page_size: int = Query(default=10, ge=1, le=30),
        owner: str = Depends(get_authenticated_owner),
    ):
        return Result.succ(service.list_runs(owner, page, page_size))

    @router.post("/runs", status_code=202)
    def create_run(body: CreateRun, owner: str = Depends(get_authenticated_owner)):
        if body.mode == "comparison":
            return Result.succ(
                service.comparisons.create(
                    owner,
                    body.session_id,
                    body.file_ids,
                    str(body.request_id),
                    body.comparison.model_dump(),
                )
            )
        return Result.succ(
            service.create(
                owner, body.session_id, body.file_ids[0], str(body.request_id)
            )
        )

    @router.get("/runs/latest")
    def latest_report(
        session_id: str = Query(
            min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$"
        ),
        owner: str = Depends(get_authenticated_owner),
    ):
        try:
            report = service.latest_agent_report(owner, session_id)
        except SessionFileApiError as exc:
            if exc.err_code != "REPORT_NOT_FOUND":
                raise
            return Result.succ(None)
        return Result.succ(public_snapshot(report))

    @router.get("/runs/{run_id}")
    def get_run(
        run_id: UUID,
        session_id: str = Query(min_length=1, max_length=255),
        owner: str = Depends(get_authenticated_owner),
    ):
        return Result.succ(service.get(owner, session_id, str(run_id)))

    @router.get("/runs/{run_id}/report")
    def get_report(
        run_id: UUID,
        session_id: str = Query(min_length=1, max_length=255),
        revision: str | None = Query(default=None, min_length=1, max_length=255),
        owner: str = Depends(get_authenticated_owner),
    ):
        return Result.succ(
            public_snapshot(
                service.get(
                    owner, session_id, str(run_id), report=True, revision=revision
                )
            )
        )

    @router.get("/runs/{run_id}/revisions")
    def list_revisions(
        run_id: UUID,
        session_id: str = Query(min_length=1, max_length=255),
        owner: str = Depends(get_authenticated_owner),
    ):
        return Result.succ(service.list_revisions(owner, session_id, str(run_id)))

    @router.post("/runs/{run_id}/resume")
    def resume_run(
        run_id: UUID, body: ResumeRun, owner: str = Depends(get_authenticated_owner)
    ):
        return Result.succ(
            service.comparisons.resume(
                owner,
                body.session_id,
                str(run_id),
                body.revision,
                {key: value.model_dump() for key, value in body.resolutions.items()},
            )
        )

    @router.post("/runs/{run_id}/configuration")
    def reconfigure_run(
        run_id: UUID,
        body: ReconfigureRun,
        owner: str = Depends(get_authenticated_owner),
    ):
        return Result.succ(
            public_snapshot(
                service.comparisons.reconfigure(
                    owner,
                    body.session_id,
                    str(run_id),
                    body.revision,
                    body.comparison.model_dump(),
                )
            )
        )

    @router.post("/runs/{run_id}/topics/retry", status_code=202)
    def retry_topic(
        run_id: UUID, body: RetryTopic, owner: str = Depends(get_authenticated_owner)
    ):
        return Result.succ(
            service.comparisons.retry_topic(
                owner, body.session_id, str(run_id), body.revision, body.topic_id
            )
        )

    @router.get("/runs/{run_id}/exports")
    def list_exports(
        run_id: UUID,
        session_id: str = Query(min_length=1, max_length=255),
        owner: str = Depends(get_authenticated_owner),
    ):
        return Result.succ(service.list_exports(owner, session_id, str(run_id)))

    @router.post("/runs/{run_id}/exports")
    def create_export(
        run_id: UUID, body: CreateExport, owner: str = Depends(get_authenticated_owner)
    ):
        return Result.succ(
            service.create_export(
                owner,
                body.session_id,
                str(run_id),
                body.revision,
                body.format,
                language=body.language,
            )
        )

    @router.get("/runs/{run_id}/exports/{export_id}")
    def download_export(
        run_id: UUID,
        export_id: str = Path(pattern=r"^[a-f0-9]{64}$"),
        session_id: str = Query(min_length=1, max_length=255),
        owner: str = Depends(get_authenticated_owner),
    ):
        content, record = service.download_export(
            owner, session_id, str(run_id), export_id
        )
        return Response(
            content,
            media_type="application/json"
            if record["format"] == "json"
            else "text/html",
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(record["file_name"]),
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post("/runs/{run_id}/questions")
    def ask_question(
        run_id: UUID, body: AskQuestion, owner: str = Depends(get_authenticated_owner)
    ):
        return Result.succ(
            service.ask(
                owner, body.session_id, str(run_id), body.revision, body.question
            )
        )

    @router.get("/runs/{run_id}/documents/{document_id}/pages/{page_number}")
    def source_page(
        run_id: UUID,
        document_id: str,
        page_number: int = Path(ge=1),
        session_id: str = Query(min_length=1, max_length=255),
        owner: str = Depends(get_authenticated_owner),
    ):
        png = service.render_source_page(
            owner, session_id, str(run_id), document_id, page_number
        )
        return Response(
            png,
            media_type="image/png",
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/runs/{run_id}/documents/{document_id}/download")
    def source_download(
        run_id: UUID,
        document_id: str,
        session_id: str = Query(min_length=1, max_length=255),
        owner: str = Depends(get_authenticated_owner),
    ):
        stream, record, _ = service.open_source(
            owner, session_id, str(run_id), document_id
        )

        def chunks():
            try:
                while chunk := stream.read(1024 * 1024):
                    yield chunk
            finally:
                stream.close()

        return StreamingResponse(
            chunks(),
            media_type="application/pdf",
            background=BackgroundTask(stream.close),
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(record.display_name),
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
