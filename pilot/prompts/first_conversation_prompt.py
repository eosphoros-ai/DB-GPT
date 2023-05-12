from pilot.prompts.generator import PromptGenerator
from typing import Any, Optional, Type
import os
import platform
from pathlib import Path

import distro
import yaml
from pilot.configs.config import Config
from pilot.prompts.prompt import build_default_prompt_generator


class FirstPrompt:
    """

    """
    def __init__(
        self,
        ai_goals: list | None = None,
    ) -> None:
        """
        Initialize a class instance

        Parameters:
            ai_name (str): The name of the AI.
            ai_role (str): The description of the AI's role.
            ai_goals (list): The list of objectives the AI is supposed to complete.
            api_budget (float): The maximum dollar value for API calls (0.0 means infinite)
        Returns:
            None
        """
        if ai_goals is None:
            ai_goals = []
        self.ai_goals = ai_goals
        self.prompt_generator = None
        self.command_registry = None


    def construct_first_prompt(
            self,
            command_registry: [] = None,
            fisrt_message: [str]=[],
            prompt_generator: Optional[PromptGenerator] = None
    ) -> str:
        """
        基于用户输入的初始对话信息构建完整的prompt信息
        Args:
            self:
            prompt_generator:

        Returns:

        """
        prompt_start = (
            "Your decisions must always be made independently without"
            " seeking user assistance. Play to your strengths as an LLM and pursue"
            " simple strategies with no legal complications."
            ""
        )




        if prompt_generator is None:
            prompt_generator = build_default_prompt_generator()
        prompt_generator.goals = fisrt_message
        prompt_generator.command_registry = command_registry
        # 加载插件中可用命令
        cfg = Config()
        for plugin in cfg.plugins:
            if not plugin.can_handle_post_prompt():
                continue
            prompt_generator = plugin.post_prompt(prompt_generator)
        if cfg.execute_local_commands:
            # add OS info to prompt
            os_name = platform.system()
            os_info = (
                platform.platform(terse=True)
                if os_name != "Linux"
                else distro.name(pretty=True)
            )

            prompt_start += f"\nThe OS you are running on is: {os_info}"

        # Construct full prompt
        full_prompt = f"{prompt_start}\n\nGOALS:\n\n"

        if not self.ai_goals :
            self.ai_goals = fisrt_message
        for i, goal in enumerate(self.ai_goals):
            full_prompt += f"{i+1}. {goal}\n"
        # if self.api_budget > 0.0:
        #     full_prompt += f"\nIt takes money to let you run. Your API budget is ${self.api_budget:.3f}"
        self.prompt_generator = prompt_generator
        full_prompt += f"\n\n{prompt_generator.generate_prompt_string()}"
        return full_prompt