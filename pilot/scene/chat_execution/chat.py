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

CFG = Config()

class ChatWithPlugin(BaseChat):
    chat_scene: str = ChatScene.ChatExecution.value
    plugins_prompt_generator:PluginPromptGenerator
    select_plugin: str = None

    def __init__(self, chat_mode, chat_session_id, current_user_input, select_plugin:str=None):
        super().__init__(chat_mode, chat_session_id, current_user_input)
        self.plugins_prompt_generator = PluginPromptGenerator()
        self.plugins_prompt_generator.command_registry = self.command_registry
        # 加载插件中可用命令
        self.select_plugin = select_plugin
        if self.select_plugin:
            for plugin in CFG.plugins:
                if plugin.
        else:
            for plugin in CFG.plugins:
                if not plugin.can_handle_post_prompt():
                    continue
                self.plugins_prompt_generator = plugin.post_prompt(self.plugins_prompt_generator)




    def generate_input_values(self):
        input_values = {
            "input": self.current_user_input,
            "constraints": self.__list_to_prompt_str(self.plugins_prompt_generator.constraints),
            "commands_infos":  self.plugins_prompt_generator.generate_commands_string()
        }
        return input_values

    def do_with_prompt_response(self, prompt_response):
        ## plugin command run
        return execute_command(str(prompt_response), self.plugins_prompt_generator)


    # def call(self):
    #     input_values = {
    #         "input": self.current_user_input,
    #         "constraints": self.__list_to_prompt_str(self.plugins_prompt_generator.constraints),
    #         "commands_infos":  self.__get_comnands_promp_info()
    #     }
    #
    #     ### Chat sequence advance
    #     self.current_message.chat_order = len(self.history_message) + 1
    #     self.current_message.add_user_message(self.current_user_input)
    #     self.current_message.start_date = datetime.datetime.now()
    #     # TODO
    #     self.current_message.tokens = 0
    #
    #     current_prompt = self.prompt_template.format(**input_values)
    #
    #     ### 构建当前对话， 是否安第一次对话prompt构造？ 是否考虑切换库
    #     if self.history_message:
    #         ## TODO 带历史对话记录的场景需要确定切换库后怎么处理
    #         logger.info(
    #             f"There are already {len(self.history_message)} rounds of conversations!"
    #         )
    #
    #     self.current_message.add_system_message(current_prompt)
    #
    #     payload = {
    #         "model": self.llm_model,
    #         "prompt": self.generate_llm_text(),
    #         "temperature": float(self.temperature),
    #         "max_new_tokens": int(self.max_new_tokens),
    #         "stop": self.prompt_template.sep,
    #     }
    #     logger.info(f"Requert: \n{payload}")
    #     ai_response_text = ""
    #     try:
    #         ### 走非流式的模型服务接口
    #
    #         response = requests.post(
    #             urljoin(CFG.MODEL_SERVER, "generate"),
    #             headers=headers,
    #             json=payload,
    #             timeout=120,
    #         )
    #         ai_response_text = (
    #             self.prompt_template.output_parser.parse_model_server_out(response)
    #         )
    #         self.current_message.add_ai_message(ai_response_text)
    #         prompt_define_response =  self.prompt_template.output_parser.parse_prompt_response(ai_response_text)
    #
    #
    #         ## plugin command run
    #         result = execute_command(prompt_define_response, self.plugins_prompt_generator)
    #
    #         if hasattr(prompt_define_response, "thoughts"):
    #             if prompt_define_response.thoughts.get("speak"):
    #                 self.current_message.add_view_message(
    #                     self.prompt_template.output_parser.parse_view_response(
    #                         prompt_define_response.thoughts.get("speak"), result
    #                     )
    #                 )
    #             elif prompt_define_response.thoughts.get("reasoning"):
    #                 self.current_message.add_view_message(
    #                     self.prompt_template.output_parser.parse_view_response(
    #                         prompt_define_response.thoughts.get("reasoning"), result
    #                     )
    #                 )
    #             else:
    #                 self.current_message.add_view_message(
    #                     self.prompt_template.output_parser.parse_view_response(
    #                         prompt_define_response.thoughts, result
    #                     )
    #                 )
    #         else:
    #             self.current_message.add_view_message(
    #                 self.prompt_template.output_parser.parse_view_response(
    #                     prompt_define_response, result
    #                 )
    #             )
    #
    #     except Exception as e:
    #         print(traceback.format_exc())
    #         logger.error("model response parase faild！" + str(e))
    #         self.current_message.add_view_message(
    #             f"""<span style=\"color:red\">ERROR!</span>{str(e)}\n  {ai_response_text} """
    #         )
    #     ### 对话记录存储
    #     self.memory.append(self.current_message)

    def chat_show(self):
        super().chat_show()


    def __list_to_prompt_str(list: List) -> str:
        if not list:
            separator = '\n'
            return separator.join(list)
        else:
            return ""

    def generate(self, p) -> str:
        return super().generate(p)

    @property
    def chat_type(self) -> str:
        return ChatScene.ChatExecution.value
