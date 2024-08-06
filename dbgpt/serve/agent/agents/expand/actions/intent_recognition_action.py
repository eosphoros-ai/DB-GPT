import json
import logging
from typing import Any, Dict, List, Optional, Union

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.agent import Action, ActionOutput, AgentResource, ResourceType
from dbgpt.vis.tags.vis_app_link import Vis, VisAppLink

logger = logging.getLogger(__name__)


class IntentRecognitionInput(BaseModel):
    intent: Optional[str] = Field(
        ...,
        description="The intent of user question.",
    )
    app_code: Optional[str] = Field(
        ...,
        description="The app code of intent.",
    )
    slots: Optional[dict] = Field(
        ...,
        description="The slots of user question.",
    )
    thought: Optional[str] = Field(
        ...,
        description="Logic and rationale for selecting the current application.",
    )
    ask_user: Optional[str] = Field(
        ...,
        description="Questions to users.",
    )
    user_input: Optional[str] = Field(
        ...,
        description="Instructions generated based on intent and slot.",
    )


class IntentRecognitionAction(Action[IntentRecognitionInput]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._render_protocal = VisAppLink()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        return ResourceType.Knowledge

    @property
    def render_protocal(self) -> Optional[Vis]:
        return self._render_protocal

    @property
    def out_model_type(self):
        return IntentRecognitionInput

    @property
    def ai_out_schema(self) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        out_put_schema = {
            "intent": "[意图占位符]",
            "thought": "你的推理思路",
            "app_code": "预定义意图的代码",
            "slots": {"意图定义中槽位属性1": "具体值", "意图定义中槽位属性2": "具体值"},
            "ask_user": "如果要用户补充槽位数据，向用户发起的问题",
            "user_input": "[根据意图和槽位生成的完整指令]",
        }

        return f"""请按如下JSON格式输出:
        {json.dumps(out_put_schema, indent=2, ensure_ascii=False)}
        确保只输出json，且可以被python json.loads加载.
        """

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
    ) -> ActionOutput:
        try:
            intent: IntentRecognitionInput = self._input_convert(
                ai_message, IntentRecognitionInput
            )
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content=ai_message,
                have_retry=False,
            )

        # 检查意图是否完整，是否需要向用户补充信息
        if intent.slots:
            for key, value in intent.slots.items():
                if not value or len(value) <= 0:
                    return ActionOutput(
                        is_exe_success=False,
                        content=json.dumps(intent.dict(), ensure_ascii=False),
                        view=intent.ask_user if intent.ask_user else ai_message,
                        have_retry=False,
                        ask_user=True,
                    )

        app_link_param = {
            "app_code": intent.app_code,
            "app_name": intent.intent,
            "app_desc": intent.user_input,
            "thought": intent.thought,
            "app_logo": "",
            "status": "TODO",
            "intent": json.dumps(intent.dict(), ensure_ascii=False),
        }
        return ActionOutput(
            is_exe_success=True,
            content=json.dumps(app_link_param, ensure_ascii=False),
            view=await self.render_protocal.display(content=app_link_param),
        )
