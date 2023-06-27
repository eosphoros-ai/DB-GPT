from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Union

from pilot.common.schema import ExampleType


class ExampleSelector(BaseModel, ABC):
    examples: List[List]
    use_example: bool = False
    type: str = ExampleType.ONE_SHOT.value

    def examples(self, count: int = 2):
        if ExampleType.ONE_SHOT.value == self.type:
            return self.__one_show_context()
        else:
            return self.__few_shot_context(count)

    def __few_shot_context(self, count: int = 2) -> List[List]:
        """
        Use 2 or more examples, default 2
        Returns: example text
        """
        if self.use_example:
            need_use = self.examples[:count]
            return need_use
        return None

    def __one_show_context(self) -> List:
        """
         Use one examples
        Returns:

        """
        if self.use_example:
            need_use = self.examples[:1]
            return need_use

        return None
