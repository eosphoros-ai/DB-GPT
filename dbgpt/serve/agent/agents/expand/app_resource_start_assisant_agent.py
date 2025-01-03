import json
import logging
from typing import Any, Dict, List
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.agent import Action, ActionOutput, AgentResource, AgentMessage, ResourceType
from dbgpt.agent import (
    Agent,
    ConversableAgent,
    get_agent_manager,
)
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt.agent.resource.app import AppResource
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

logger = logging.getLogger(__name__)


class AppResourceInput(BaseModel):
    """Plugin input model."""

    app_name: str = Field(
        ...,
        description="The name of a application that can be used to answer the current question"
                    " or solve the current task.",
    )

    app_query: str = Field(
        ...,
        description="The query to the selected application",
    )


class AppResourceAction(Action[AppResourceInput]):
    """AppResource action class."""

    def __init__(self, **kwargs):
        """App action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisPlugin()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return ResourceType.App

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return self._render_protocol

    @property
    def out_model_type(self):
        """Return the output model type."""
        return AppResourceInput

    @property
    def ai_out_schema(self) -> Optional[str]:
        """Return the AI output schema."""
        out_put_schema = {
            "app_name": "the agent name you selected",
            "app_query": "the query to the selected agent, must input a str, base on the natural language "
        }

        return f"""Please response in the following json format:
        {json.dumps(out_put_schema, indent=2, ensure_ascii=False)}
        Make sure the response is correct json and can be parsed by Python json.loads.
        """

    async def run(
            self,
            ai_message: str,
            resource: Optional[AgentResource] = None,
            rely_action_out: Optional[ActionOutput] = None,
            need_vis_render: bool = True,
            **kwargs,
    ) -> ActionOutput:
        """Perform the plugin action.

        Args:
            ai_message (str): The AI message.
            resource (Optional[AgentResource], optional): The resource. Defaults to
                None.
            rely_action_out (Optional[ActionOutput], optional): The rely action output.
                Defaults to None.
            need_vis_render (bool, optional): Whether need visualization rendering.
                Defaults to True.
        """
        try:
            response_success = True
            err_msg = None
            app_result = None
            try:
                param: AppResourceInput = self._input_convert(ai_message, AppResourceInput)
            except Exception as e:
                logger.exception((str(e)))
                return ActionOutput(
                    is_exe_success=False,
                    content="The requested correctly structured answer could not be found.",
                )

            app_resource = self.__get_app_resource_of_app_name(param.app_name)
            try:
                user_input = param.app_query
                parent_agent = kwargs.get("parent_agent")
                app_result = await app_resource.async_execute(
                    user_input=user_input,
                    parent_agent=parent_agent,
                )
            except Exception as e:
                response_success = False
                err_msg = f"App [{param.app_name}] execute failed! {str(e)}"
                logger.exception(err_msg)

            return ActionOutput(
                is_exe_success=response_success,
                content=str(app_result),
                # view=self.__get_plugin_view(param, app_result, err_msg),
                view=str(app_result),
                observations=str(app_result),
            )
        except Exception as e:
            logger.exception("App Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"App action run failed!{str(e)}"
            )

    async def __get_plugin_view(self, param: AppResourceInput, app_result: Any, err_msg: str):
        if not self.render_protocol:
            return None
            # raise NotImplementedError("The render_protocol should be implemented.")
        plugin_param = {
            "name": param.tool_name,
            "args": param.args,
            "logo": None,
            "result": str(app_result),
            "err_msg": err_msg,
        }
        view = await self.render_protocol.display(content=plugin_param)

    def __get_app_resource_list(self) -> List[AppResource]:
        app_resource_list: List[AppResource] = []
        if self.resource.type() == ResourceType.Pack:
            for sub_resource in self.resource.sub_resources:
                if sub_resource.type() == ResourceType.App:
                    app_resource_list.extend(AppResource.from_resource(sub_resource))
        if self.resource.type() == ResourceType.App:
            app_resource_list.extend(AppResource.from_resource(self.resource))
        return app_resource_list

    def __get_app_resource_of_app_name(self, app_name: str):
        app_resource_list: List[AppResource] = self.__get_app_resource_list()
        if app_resource_list is None or len(app_resource_list) == 0:
            raise ValueError("No app resource was found！")

        for app_resource in app_resource_list:
            if app_resource._app_name == app_name:
                return app_resource

        raise ValueError(f"App {app_name} not found !")


class AppStarterAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "AppStarter",
            category="agent",
            key="dbgpt_ant_agent_agents_app_resource_starter_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "App Starter",
            category="agent",
            key="dbgpt_ant_agent_agents_app_resource_starter_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "根据用户的问题和提供的应用信息，从已知资源中选择一个合适的应用来解决和回答用户的问题,并提取用户输入的关键信息到应用意图的槽位中。",
            category="agent",
            key="dbgpt_ant_agent_agents_app_resource_starter_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "请一步一步思考参为用户问题选择一个最匹配的应用来进行用户问题回答，可参考给出示例的应用选择逻辑.",
                "请阅读用户问题，确定问题所属领域和问题意图，按领域和意图匹配应用,如果用户问题意图缺少操作类应用需要的参数，优先使用咨询类型应用，有明确操作目标才使用操作类应用.",
                "必须从已知的应用中选出一个可用的应用来进行回答，不要瞎编应用的名称",
                "仅选择可回答问题的应用即可，不要直接回答用户问题.",
                "如果用户的问题和提供的所有应用全都不相关，则应用code和name都输出为空",
                "注意应用意图定义中如果有槽位信息，再次阅读理解用户输入信息，将对应的内容填入对应槽位参数定义中.",
            ],
            category="agent",
            key="dbgpt_ant_agent_agents_app_resource_starter_assistant_agent_profile_constraints",
        ),
        desc=DynConfig(
            "根据用户问题匹配合适的应用来进行回答.",
            category="agent",
            key="dbgpt_ant_agent_agents_app_resource_starter_assistant_agent_profile_desc",
        ),
    )
    stream_out: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([AppResourceAction])

    def prepare_act_param(
            self,
            received_message: Optional[AgentMessage],
            sender: Agent,
            rely_messages: Optional[List[AgentMessage]] = None,
            **kwargs,
    ) -> Dict[str, Any]:
        return {
            "user_input": received_message.content,
            "conv_id": self.agent_context.conv_id,
            "parent_agent": self,
        }


agent_manage = get_agent_manager()
agent_manage.register_agent(AppStarterAgent)
