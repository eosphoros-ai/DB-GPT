import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

from dbgpt.util.json_utils import serialize


class Vis:
    def render_prompt(self):
        return None

    async def generate_param(self, **kwargs) -> Optional[str]:
        """
        Display corresponding content using vis protocol
        Args:
            **kwargs:

        Returns:
        vis protocol text
        """
        return kwargs["content"]

    async def display(self, **kwargs) -> Optional[str]:
        return f"```{self.vis_tag()}\n{json.dumps(await self.generate_param(**kwargs), default=serialize, ensure_ascii=False)}\n```"

    @classmethod
    def vis_tag(cls) -> str:
        """
        Current vis protocol module tag name
        Returns:

        """
