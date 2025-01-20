"""Application Resources for the agent."""

import uuid
from typing import List, Optional

from dbgpt.agent import AgentMessage, ConversableAgent
from dbgpt.agent.resource.app import AppInfo, AppResource
from dbgpt_serve.agent.agents.app_agent_manage import get_app_manager


class GptAppResource(AppResource):
    """AppResource resource class."""

    def __init__(self, name: str, app_code: str, **kwargs):
        """Initialize AppResource resource."""
        super().__init__(name, **kwargs)

        self._app_code = app_code

        self.gpt_app = get_app_manager().get_app(self._app_code)
        self._app_name = self.gpt_app.app_name
        self._app_desc = self.gpt_app.app_describe

    @property
    def app_desc(self):
        """Return the app description."""
        return self._app_desc

    @property
    def app_name(self):
        """Return the app name."""
        return self._app_name

    @classmethod
    def _get_app_list(cls) -> List[AppInfo]:
        from dbgpt_serve.agent.agents.app_agent_manage import get_app_manager

        # Only call this function when the system app is initialized
        apps = get_app_manager().get_dbgpts()
        app_list = []
        for app in apps:
            app_list.append(
                AppInfo(name=app.app_name, code=app.app_code, desc=app.app_describe)
            )
        return app_list

    async def _start_app(
        self,
        user_input: str,
        sender: ConversableAgent,
        conv_uid: Optional[str] = None,
    ) -> AgentMessage:
        """Start App By AppResource."""
        conv_uid = str(uuid.uuid4()) if conv_uid is None else conv_uid
        gpts_app = get_app_manager().get_app(self._app_code)
        app_agent = await get_app_manager().create_agent_by_app_code(
            gpts_app, conv_uid=conv_uid
        )

        agent_message = AgentMessage(
            content=user_input,
            current_goal=user_input,
            context={
                "conv_uid": conv_uid,
            },
            rounds=0,
        )
        reply_message: AgentMessage = await app_agent.generate_reply(
            received_message=agent_message, sender=sender
        )

        return reply_message
