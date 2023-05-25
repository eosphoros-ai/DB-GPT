from typing import Optional

from pilot.configs.config import Config
from pilot.prompts.generator import PromptGenerator
from pilot.prompts.prompt import build_default_prompt_generator


class CommandsLoad:
    """
    Load Plugins Commands Info , help build system prompt!
    """

    def __init__(self) -> None:
        self.command_registry = None

    def getCommandInfos(
        self, prompt_generator: Optional[PromptGenerator] = None
    ) -> str:
        cfg = Config()
        if prompt_generator is None:
            prompt_generator = build_default_prompt_generator()
        for plugin in cfg.plugins:
            if not plugin.can_handle_post_prompt():
                continue
            prompt_generator = plugin.post_prompt(prompt_generator)
        self.prompt_generator = prompt_generator
        command_infos = ""
        command_infos += f"\n\n{prompt_generator.commands()}"
        return command_infos
