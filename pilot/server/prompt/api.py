from fastapi import APIRouter, File, UploadFile, Form, Depends

from pilot.openapi.api_view_model import Result
from pilot.server.prompt.service import PromptManageService
from pilot.server.prompt.request.request import PromptManageRequest
from pilot.user import UserRequest, get_user_from_headers

router = APIRouter()

prompt_manage_service = PromptManageService()


@router.post("/prompt/add")
def prompt_add(request: PromptManageRequest, user_token: UserRequest = Depends(get_user_from_headers)):
    print(f"/prompt/add params: {request}")
    request.user_id = user_token.user_id
    try:
        prompt_manage_service.create_prompt(request)
        return Result.succ([])
    except Exception as e:
        return Result.failed(code="E010X", msg=f"prompt add error {e}")


@router.post("/prompt/list")
def prompt_list(request: PromptManageRequest, user_token: UserRequest = Depends(get_user_from_headers)):
    print(f"/prompt/list params:  {request}")
    try:
        request.user_id = user_token.user_id
        return Result.succ(prompt_manage_service.get_prompts(request))
    except Exception as e:
        return Result.failed(code="E010X", msg=f"prompt list error {e}")


@router.post("/prompt/update")
def prompt_update(request: PromptManageRequest, user_token: UserRequest = Depends(get_user_from_headers)):
    print(f"/prompt/update params:  {request}")
    request.user_id = user_token.user_id
    try:
        return Result.succ(prompt_manage_service.update_prompt(request))
    except Exception as e:
        return Result.failed(code="E010X", msg=f"prompt update error {e}")


@router.post("/prompt/delete")
def prompt_delete(request: PromptManageRequest, user_token: UserRequest = Depends(get_user_from_headers)):
    print(f"/prompt/delete params: {request}")
    try:
        return Result.succ(prompt_manage_service.delete_prompt(request.prompt_name, user_token.user_id))
    except Exception as e:
        return Result.failed(code="E010X", msg=f"prompt delete error {e}")
