import requests
import datetime
from urllib.parse import urljoin
from typing import List
import traceback

from pilot.scene.base_chat import BaseChat, logger, headers
from pilot.scene.message import OnceConversation
from pilot.scene.base import ChatScene
from pilot.configs.config import Config
from pilot.commands.command import execute_command
from pilot.prompts.generator import PluginPromptGenerator
from pilot.scene.chat_execution.prompt import prompt

CFG = Config()


class ChatWithPlugin(BaseChat):
    chat_scene: str = ChatScene.ChatExecution.value()
    plugins_prompt_generator: PluginPromptGenerator
    select_plugin: str = None

    def __init__(
        self,
        chat_session_id,
        user_input,
        plugin_selector: str = None,
    ):
        super().__init__(
            chat_mode=ChatScene.ChatExecution,
            chat_session_id=chat_session_id,
            current_user_input=user_input,
        )
        self.plugins_prompt_generator = PluginPromptGenerator()
        self.plugins_prompt_generator.command_registry = CFG.command_registry
        # 加载插件中可用命令
        self.select_plugin = plugin_selector
        if self.select_plugin:
            for plugin in CFG.plugins:
                if plugin._name == plugin_selector:
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

    def generate_input_values(self):
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
