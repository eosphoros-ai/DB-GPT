from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Union


class TestBase(BaseModel, ABC):
    test_values: List = []


    def test(self):
        print(self.__class__.__name__ + ":" )
        print(self.test_values)