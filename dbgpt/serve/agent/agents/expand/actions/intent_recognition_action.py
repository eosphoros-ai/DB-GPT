import json
import logging
from typing import Any, Dict, List, Optional, Union

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict
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
        None,
        description="The slots of user question.",
    )
    ask_user: Optional[str] = Field(
        None,
        description="Questions to users.",
    )
    user_input: Optional[str] = Field(
        None,
        description="Generate new complete user instructions based on current intent and all slot information.",
    )

    def to_dict(self):
        return model_to_dict(self)


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
    def ai_out_schema(self) -> Optional[str]:
        out_put_schema = {
            "intent": "[The recognized intent is placed here]",
            "app_code": "[App code in selected intent]",
            "slots": {"意图定义中槽位属性1": "具体值", "意图定义中槽位属性2": "具体值"},
            "ask_user": "If you want the user to supplement slot data, ask the user a question",
            "user_input": "[Complete instructions generated based on intent and slot]",
        }
        if self.language == "en":
            return f"""Please reply in the following json format:
                {json.dumps(out_put_schema, indent=2, ensure_ascii=False)}
            Make sure the output is only json and can be parsed by Python json.loads."""  # noqa: E501
        else:
            return f"""请按如下JSON格式输出:
            {json.dumps(out_put_schema, indent=2, ensure_ascii=False)}
            确保输出只有json，且可以被python json.loads加载."""

    def _get_default_next_speakers(self):
        next_speakers = []
        from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent

        next_speakers.append(SummaryAssistantAgent().role)

        from dbgpt.agent.expand.simple_assistant_agent import SimpleAssistantAgent

        next_speakers.append(SimpleAssistantAgent().role)

        return next_speakers

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        next_speakers = self._get_default_next_speakers()
        try:
            intent: IntentRecognitionInput = self._input_convert(
                ai_message, IntentRecognitionInput
            )
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content="Error:The answer is not output in the required format.",
                have_retry=True,
                next_speakers=next_speakers,
            )

        # Check whether the message is complete and whether additional information needs to be provided to the user
        if intent.slots:
            for key, value in intent.slots.items():
                if not value or len(value) <= 0:
                    logger.info("slots check, need additional information!")
                    return ActionOutput(
                        is_exe_success=False,
                        content=json.dumps(intent.to_dict(), ensure_ascii=False),
                        view=intent.ask_user if intent.ask_user else ai_message,
                        have_retry=False,
                        ask_user=True,
                        next_speakers=next_speakers,
                    )

        if intent.app_code and len(intent.app_code) > 0:
            from dbgpt.serve.agent.agents.expand.app_start_assisant_agent import (
                StartAppAssistantAgent,
            )

            next_speakers = [StartAppAssistantAgent().role]

        app_link_param = {
            "app_code": intent.app_code,
            "app_name": intent.intent,
            "app_desc": intent.user_input,
        }

        return ActionOutput(
            is_exe_success=True,
            content=json.dumps(app_link_param, ensure_ascii=False),
            view=await self.render_protocal.display(
                content={
                    "app_code": intent.app_code,
                    "app_name": intent.intent,
                    "app_desc": intent.user_input,
                    "app_logo": "",
                    "status": "TODO",
                }
            ),
            next_speakers=next_speakers,
        )
