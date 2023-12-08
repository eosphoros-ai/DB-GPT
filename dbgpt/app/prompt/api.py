from fastapi import APIRouter

from dbgpt.app.openapi.api_view_model import Result
from dbgpt.app.prompt.service import PromptManageService
from dbgpt.app.prompt.request.request import PromptManageRequest

router = APIRouter()

prompt_manage_service = PromptManageService()


@router.post("/prompt/add")
def prompt_add(request: PromptManageRequest):
    print(f"/prompt/add params: {request}")
    try:
        prompt_manage_service.create_prompt(request)
        return Result.succ([])
    except Exception as e:
        return Result.failed(code="E010X", msg=f"prompt add error {e}")


@router.post("/prompt/list")
def prompt_list(request: PromptManageRequest):
    print(f"/prompt/list params:  {request}")
    try:
        return Result.succ(prompt_manage_service.get_prompts(request))
    except Exception as e:
        return Result.failed(code="E010X", msg=f"prompt list error {e}")


@router.post("/prompt/update")
def prompt_update(request: PromptManageRequest):
    print(f"/prompt/update params:  {request}")
    try:
        return Result.succ(prompt_manage_service.update_prompt(request))
    except Exception as e:
        return Result.failed(code="E010X", msg=f"prompt update error {e}")


@router.post("/prompt/delete")
def prompt_delete(request: PromptManageRequest):
    print(f"/prompt/delete params: {request}")
    try:
        return Result.succ(prompt_manage_service.delete_prompt(request.prompt_name))
    except Exception as e:
        return Result.failed(code="E010X", msg=f"prompt delete error {e}")
