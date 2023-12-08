from datetime import datetime

from dbgpt.app.prompt.request.request import PromptManageRequest
from dbgpt.app.prompt.request.response import PromptQueryResponse
from dbgpt.app.prompt.prompt_manage_db import PromptManageDao, PromptManageEntity

prompt_manage_dao = PromptManageDao()


class PromptManageService:
    def __init__(self):
        pass

    """create prompt"""

    def create_prompt(self, request: PromptManageRequest):
        query = PromptManageRequest(
            prompt_name=request.prompt_name,
        )
        err_sys_str = ""
        if query.sys_code:
            query.sys_code = request.sys_code
            err_sys_str = f" and sys_code: {request.sys_code}"
        prompt_name = prompt_manage_dao.get_prompts(query)
        if len(prompt_name) > 0:
            raise Exception(
                f"prompt name: {request.prompt_name}{err_sys_str} have already named"
            )
        prompt_manage_dao.create_prompt(request)
        return True

    """get prompts"""

    def get_prompts(self, request: PromptManageRequest):
        query = PromptManageRequest(
            chat_scene=request.chat_scene,
            sub_chat_scene=request.sub_chat_scene,
            prompt_type=request.prompt_type,
            prompt_name=request.prompt_name,
            user_name=request.user_name,
            sys_code=request.sys_code,
        )
        responses = []
        prompts = prompt_manage_dao.get_prompts(query)
        for prompt in prompts:
            res = PromptQueryResponse()

            res.id = prompt.id
            res.chat_scene = prompt.chat_scene
            res.sub_chat_scene = prompt.sub_chat_scene
            res.prompt_type = prompt.prompt_type
            res.content = prompt.content
            res.user_name = prompt.user_name
            res.prompt_name = prompt.prompt_name
            res.gmt_created = prompt.gmt_created
            res.gmt_modified = prompt.gmt_modified
            responses.append(res)
        return responses

    """update prompt"""

    def update_prompt(self, request: PromptManageRequest):
        query = PromptManageEntity(prompt_name=request.prompt_name)
        prompts = prompt_manage_dao.get_prompts(query)
        if len(prompts) != 1:
            raise Exception(
                f"there are no or more than one space called {request.prompt_name}"
            )
        prompt = prompts[0]
        prompt.chat_scene = request.chat_scene
        prompt.sub_chat_scene = request.sub_chat_scene
        prompt.prompt_type = request.prompt_type
        prompt.content = request.content
        prompt.user_name = request.user_name
        prompt.gmt_modified = datetime.now()
        return prompt_manage_dao.update_prompt(prompt)

    """delete prompt"""

    def delete_prompt(self, prompt_name: str):
        query = PromptManageEntity(prompt_name=prompt_name)
        prompts = prompt_manage_dao.get_prompts(query)
        if len(prompts) == 0:
            raise Exception(f"delete error, no prompt name:{prompt_name} in database ")
        # delete prompt
        prompt = prompts[0]
        return prompt_manage_dao.delete_prompt(prompt)
