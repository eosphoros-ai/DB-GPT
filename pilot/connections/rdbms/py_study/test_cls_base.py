from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Union


class TestBase(BaseModel, ABC):
    test_values: List = []
    mode:str = "123"

    def test(self):
        print(self.__class__.__name__ + ":" )
        print(self.test_values)
        print(self.mode)