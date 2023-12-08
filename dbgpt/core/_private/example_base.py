from abc import ABC
from typing import List
from enum import Enum
from dbgpt._private.pydantic import BaseModel


class ExampleType(Enum):
    ONE_SHOT = "one_shot"
    FEW_SHOT = "few_shot"


class ExampleSelector(BaseModel, ABC):
    examples_record: List[dict]
    use_example: bool = False
    type: str = ExampleType.ONE_SHOT.value

    def examples(self, count: int = 2):
        if ExampleType.ONE_SHOT.value == self.type:
            return self.__one_show_context()
        else:
            return self.__few_shot_context(count)

    def __few_shot_context(self, count: int = 2) -> List[dict]:
        """
        Use 2 or more examples, default 2
        Returns: example text
        """
        if self.use_example:
            need_use = self.examples_record[:count]
            return need_use
        return None

    def __one_show_context(self) -> dict:
        """
         Use one examples
        Returns:

        """
        if self.use_example:
            need_use = self.examples_record[:1]
            return need_use

        return None
