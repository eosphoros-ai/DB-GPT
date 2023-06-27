from abc import ABC, abstractmethod
from pydantic import BaseModel
from test_cls_base import TestBase
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Union

class Test2(TestBase):
    test_2_values:List = []
    mode:str = "789"
    def write(self):
        self.test_values.append(1)
        self.test_values.append(2)
        self.test_values.append(3)
        self.test_2_values.append("x")
        self.test_2_values.append("y")
        self.test_2_values.append("z")