"""Example selector base class"""

from abc import ABC
from enum import Enum
from typing import List, Optional

from dbgpt._private.pydantic import BaseModel


class ExampleType(Enum):
    """Example type"""

    ONE_SHOT = "one_shot"
    FEW_SHOT = "few_shot"


class ExampleSelector(BaseModel, ABC):
    """Example selector base class"""

    examples_record: List[dict]
    use_example: bool = False
    type: str = ExampleType.ONE_SHOT.value

    def examples(self, count: int = 2):
        """Return examples"""
        if ExampleType.ONE_SHOT.value == self.type:
            return self.__one_shot_context()
        else:
            return self.__few_shot_context(count)

    def __few_shot_context(self, count: int = 2) -> Optional[List[dict]]:
        """
        Use 2 or more examples, default 2
        Returns: example text
        """
        if self.use_example:
            need_use = self.examples_record[:count]
            return need_use
        return None

    def __one_shot_context(self) -> Optional[dict]:
        """
         Use one examples
        Returns:

        """
        if self.use_example:
            need_use = self.examples_record[-1]
            return need_use

        return None
