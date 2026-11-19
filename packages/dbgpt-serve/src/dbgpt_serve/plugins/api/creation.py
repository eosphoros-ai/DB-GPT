"""Application actions for suite creation; installation is never a model tool."""

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from dbgpt_serve.core import Result

from ..creation import SuiteCreationStore
from ..service.service import Service
from .endpoints import check_api_key, get_service

router = APIRouter(dependencies=[Depends(check_api_key)])


class DraftRequest(BaseModel):
    requirement: str = Field(default="", max_length=20000)
    conv_id: str = ""


class RevisionRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    source_artifact_id: str = ""


class EditRequest(RevisionRequest):
    files: Dict[str, str]


class InstallRequest(BaseModel):
    package_digest: str


class ConfigureRequest(BaseModel):
    database_name: str


def store() -> SuiteCreationStore:
    return SuiteCreationStore()


def action(fn, *args):
    try:
        return Result.succ(fn(*args))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/suite-drafts")
def create_draft(request: DraftRequest, drafts=Depends(store)):
    return action(drafts.create, request.requirement, request.conv_id)


@router.get("/suite-drafts/{draft_id}")
def read_draft(draft_id: str, drafts=Depends(store)):
    return action(drafts.read, draft_id)


@router.patch("/suite-drafts/{draft_id}")
def edit_draft(draft_id: str, request: EditRequest, drafts=Depends(store)):
    return action(drafts.write, draft_id, request.files, request.expected_revision)


@router.post("/suite-drafts/{draft_id}/validate")
def validate_draft(draft_id: str, request: RevisionRequest, drafts=Depends(store)):
    return action(drafts.validate, draft_id, request.expected_revision)


@router.post("/suite-drafts/{draft_id}/build")
def build_draft(draft_id: str, request: RevisionRequest, drafts=Depends(store)):
    return action(
        drafts.build,
        draft_id,
        request.expected_revision,
        request.source_artifact_id or None,
    )


@router.get("/suite-artifacts/{artifact_id}")
def get_artifact(artifact_id: str, drafts=Depends(store)):
    return action(
        lambda: {
            **drafts.artifact(artifact_id),
            "revisions": drafts.revisions(artifact_id),
            "configuration": drafts.configuration(
                drafts.artifact(artifact_id)["suite_name"]
            ),
        }
    )


@router.get("/suite-artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, drafts=Depends(store)):
    try:
        artifact = drafts.artifact(artifact_id)
        return FileResponse(
            drafts.download(artifact_id),
            media_type="application/zip",
            filename=f"{artifact['suite_name']}-{artifact['version']}.zip",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/suite-artifacts/{artifact_id}/installation")
def get_installation(
    artifact_id: str, drafts=Depends(store), service: Service = Depends(get_service)
):
    return action(drafts.installation, artifact_id, service)


@router.post("/suite-artifacts/{artifact_id}/install")
def install_artifact(
    artifact_id: str,
    request: InstallRequest,
    drafts=Depends(store),
    service: Service = Depends(get_service),
):
    return action(drafts.install, artifact_id, request.package_digest, service)


@router.post("/suite-artifacts/{artifact_id}/configure")
def configure_artifact(
    artifact_id: str,
    request: ConfigureRequest,
    drafts=Depends(store),
    service: Service = Depends(get_service),
):
    return action(drafts.configure, artifact_id, request.database_name, service)
