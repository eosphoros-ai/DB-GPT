from abc import ABC, abstractmethod
from pydantic import BaseModel
from test_cls_base import TestBase


class Test1(TestBase):
    mode:str = "456"
    def write(self):
        self.test_values.append("x")
        self.test_values.append("y")
        self.test_values.append("g")

