from typing import List, Dict

from dbgpt.app.scene import BaseChat, ChatScene
from dbgpt._private.config import Config
from dbgpt.agent.commands.command import execute_command
from dbgpt.agent import PluginPromptGenerator
from dbgpt.util.tracer import trace

CFG = Config()


class ChatWithPlugin(BaseChat):
    """Chat With Plugin"""

    chat_scene: str = ChatScene.ChatExecution.value()
    plugins_prompt_generator: PluginPromptGenerator
    select_plugin: str = None

    def __init__(self, chat_param: Dict):
        """Chat Dashboard Module Initialization
        Args:
           - chat_param: Dict
            - chat_session_id: (str) chat session_id
            - current_user_input: (str) current user input
            - model_name:(str) llm model name
            - select_param:(str) plugin selector
        """
        self.plugin_selector = chat_param["select_param"]
        chat_param["chat_mode"] = ChatScene.ChatExecution
        super().__init__(chat_param=chat_param)
        self.plugins_prompt_generator = PluginPromptGenerator()
        self.plugins_prompt_generator.command_registry = CFG.command_registry
        # 加载插件中可用命令
        self.select_plugin = self.plugin_selector
        if self.select_plugin:
            for plugin in CFG.plugins:
                if plugin._name == self.plugin_selector:
                    if not plugin.can_handle_post_prompt():
                        continue
                    self.plugins_prompt_generator = plugin.post_prompt(
                        self.plugins_prompt_generator
                    )

        else:
            for plugin in CFG.plugins:
                if not plugin.can_handle_post_prompt():
                    continue
                self.plugins_prompt_generator = plugin.post_prompt(
                    self.plugins_prompt_generator
                )

    @trace()
    async def generate_input_values(self) -> Dict:
        input_values = {
            "input": self.current_user_input,
            "constraints": self.__list_to_prompt_str(
                list(self.plugins_prompt_generator.constraints)
            ),
            "commands_infos": self.plugins_prompt_generator.generate_commands_string(),
        }
        return input_values

    def do_action(self, prompt_response):
        print(f"do_action:{prompt_response}")
        ## plugin command run
        return execute_command(
            str(prompt_response.command.get("name")),
            prompt_response.command.get("args", {}),
            self.plugins_prompt_generator,
        )

    def chat_show(self):
        super().chat_show()

    def __list_to_prompt_str(self, list: List) -> str:
        return "\n".join(f"{i + 1 + 1}. {item}" for i, item in enumerate(list))

    def generate(self, p) -> str:
        return super().generate(p)

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatExecution.value
