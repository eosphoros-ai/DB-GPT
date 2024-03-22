from typing import Optional

from fastapi import APIRouter, Query

from dbgpt.serve.agent.db.gpts_app import (
    GptsApp,
    GptsAppCollectionDao,
    GptsAppDao,
    GptsAppQuery,
)
from dbgpt.serve.core import Result

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
):
    try:
        query = GptsAppQuery(
            page_no=page, page_size=page_size, is_collected=is_collected
        )
        return Result.succ(gpts_dao.app_list(query, True))
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"query app error: {ex}")


@router.get("/v2/serve/apps/{app_id}")
async def app_detail(app_id: str):
    try:
        return Result.succ(gpts_dao.app_detail(app_id))
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"query app error: {ex}")


@router.put("/v2/serve/apps/{app_id}")
async def app_update(app_id: str, gpts_app: GptsApp):
    try:
        return Result.succ(gpts_dao.edit(gpts_app))
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"edit app error: {ex}")


@router.post("/v2/serve/apps")
async def app_create(gpts_app: GptsApp):
    try:
        return Result.succ(gpts_dao.create(gpts_app))
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"edit app error: {ex}")


@router.delete("/v2/serve/apps/{app_id}")
async def app_delete(app_id: str, user_code: Optional[str], sys_code: Optional[str]):
    try:
        gpts_dao.delete(app_id, user_code, sys_code)
        return Result.succ([])
    except Exception as ex:
        return Result.failed(err_code="E000X", msg=f"delete app error: {ex}")
