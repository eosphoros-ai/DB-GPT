from typing import List, Dict
import logging

from dbgpt.app.scene import BaseChat, ChatScene
from dbgpt._private.config import Config
from dbgpt.agent.commands.command_mange import ApiCall
from dbgpt.agent import PluginPromptGenerator
from dbgpt.component import ComponentType
from dbgpt.agent.controller import ModuleAgent
from dbgpt.util.tracer import root_tracer, trace

CFG = Config()

logger = logging.getLogger("chat_agent")


class ChatAgent(BaseChat):
    """Chat With Agent through plugin"""

    chat_scene: str = ChatScene.ChatAgent.value()
    chat_retention_rounds = 0

    def __init__(self, chat_param: Dict):
        """Chat Agent Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) agent plugin
        """
        if not chat_param["select_param"]:
            raise ValueError("Please select a Plugin!")
        self.select_plugins = chat_param["select_param"].split(",")

        chat_param["chat_mode"] = ChatScene.ChatAgent
        super().__init__(chat_param=chat_param)
        self.plugins_prompt_generator = PluginPromptGenerator()
        self.plugins_prompt_generator.command_registry = CFG.command_registry

        # load  select plugin
        agent_module = CFG.SYSTEM_APP.get_component(
            ComponentType.AGENT_HUB, ModuleAgent
        )
        self.plugins_prompt_generator = agent_module.load_select_plugin(
            self.plugins_prompt_generator, self.select_plugins
        )

        self.api_call = ApiCall(plugin_generator=self.plugins_prompt_generator)

    @trace()
    async def generate_input_values(self) -> Dict[str, str]:
        input_values = {
            "user_goal": self.current_user_input,
            "expand_constraints": self.__list_to_prompt_str(
                list(self.plugins_prompt_generator.constraints)
            ),
            "tool_list": self.plugins_prompt_generator.generate_commands_string(),
        }
        return input_values

    def stream_plugin_call(self, text):
        text = (
            text.replace("\\n", " ")
            .replace("\n", " ")
            .replace("\_", "_")
            .replace("\\", " ")
        )
        with root_tracer.start_span(
            "ChatAgent.stream_plugin_call.api_call", metadata={"text": text}
        ):
            return self.api_call.run(text)

    def __list_to_prompt_str(self, list: List) -> str:
        return "\n".join(f"{i + 1 + 1}. {item}" for i, item in enumerate(list))
