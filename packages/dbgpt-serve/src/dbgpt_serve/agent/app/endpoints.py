from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from dbgpt_serve.agent.db.gpts_app import (
    GptsApp,
    GptsAppCollectionDao,
    GptsAppDao,
    GptsAppQuery,
    GptsAppResponse,
)
from dbgpt_serve.auth.service.access import AccessService, get_access_service
from dbgpt_serve.core import Result
from dbgpt_serve.utils.auth import UserRequest, require_permission

router = APIRouter()
gpts_dao = GptsAppDao()
collection_dao = GptsAppCollectionDao()


@router.get("/v2/serve/apps")
async def app_list(
    user_name: Optional[str] = Query(default=None, description="user name"),
    sys_code: Optional[str] = Query(default=None, description="system code"),
    is_collected: Optional[str] = Query(default=None, description="system code"),
    page: int = Query(default=1, description="current page"),
    page_size: int = Query(default=20, description="page size"),
    operator: UserRequest = Depends(require_permission("AGENT_USE")),
    access: AccessService = Depends(get_access_service),
):
    allowed_ids = access.allowed_resource_ids(operator, "AGENT")
    if allowed_ids == set():
        return Result.succ(
            GptsAppResponse(
                total_count=0,
                total_page=0,
                current_page=page,
                app_list=[],
            )
        )
    try:
        query = GptsAppQuery(
            page_no=page, page_size=page_size, is_collected=is_collected
        )
        if allowed_ids is not None:
            query.app_codes = sorted(allowed_ids)
        return Result.succ(gpts_dao.app_list(query, True))
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"query app error: {ex}")


@router.get("/v2/serve/apps/{app_id}")
async def app_detail(
    app_id: str,
    operator: UserRequest = Depends(require_permission("AGENT_USE")),
    access: AccessService = Depends(get_access_service),
):
    access.require_resource_access(operator, "AGENT", app_id)
    try:
        return Result.succ(gpts_dao.app_detail(app_id))
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"query app error: {ex}")


@router.put("/v2/serve/apps/{app_id}")
async def app_update(
    app_id: str,
    gpts_app: GptsApp,
    operator: UserRequest = Depends(require_permission("AGENT_MANAGE")),
    access: AccessService = Depends(get_access_service),
):
    resource = access.require_resource_access(operator, "AGENT", app_id, manage=True)
    if gpts_app.account_set_id not in (None, resource.account_set_id):
        raise HTTPException(
            status_code=409,
            detail="Use the resource account-set impact and assignment APIs",
        )
    gpts_app.account_set_id = resource.account_set_id
    access.require_agent_definition_access(
        operator, gpts_app.account_set_id, gpts_app.details
    )
    try:
        return Result.succ(gpts_dao.edit(gpts_app))
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"edit app error: {ex}")


@router.post("/v2/serve/apps")
async def app_create(
    gpts_app: GptsApp,
    operator: UserRequest = Depends(require_permission("AGENT_MANAGE")),
    access: AccessService = Depends(get_access_service),
):
    if not gpts_app.account_set_id:
        raise HTTPException(status_code=422, detail="account_set_id is required")
    access.require_agent_definition_access(
        operator, gpts_app.account_set_id, gpts_app.details
    )
    try:
        return Result.succ(gpts_dao.create(gpts_app))
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"edit app error: {ex}")


@router.delete("/v2/serve/apps/{app_id}")
async def app_delete(
    app_id: str,
    user_code: Optional[str],
    sys_code: Optional[str],
    operator: UserRequest = Depends(require_permission("AGENT_MANAGE")),
    access: AccessService = Depends(get_access_service),
):
    access.require_resource_access(operator, "AGENT", app_id, manage=True)
    try:
        gpts_dao.delete(app_id, user_code, sys_code)
        return Result.succ([])
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"delete app error: {ex}")
