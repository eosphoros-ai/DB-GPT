"""Financial run API reusing the session-file authentication and envelopes."""

from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.background import BackgroundTask

from dbgpt_serve.core import Result
from dbgpt_serve.session_file.api.endpoints import (
    _SessionFileApiRoute,
    get_authenticated_owner,
)

from .workflow import public_snapshot


class CreateRun(BaseModel):
    session_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_-]+$")
    file_ids: list[str] = Field(min_length=1, max_length=1)
    request_id: UUID = Field(default_factory=uuid4)


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
        return Result.succ(
            service.create(
                owner, body.session_id, body.file_ids[0], str(body.request_id)
            )
        )

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
        owner: str = Depends(get_authenticated_owner),
    ):
        return Result.succ(
            public_snapshot(service.get(owner, session_id, str(run_id), report=True))
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
                owner, body.session_id, str(run_id), body.revision, body.format
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
