from enum import auto, Enum
from typing import List, Any


class SeparatorStyle(Enum):
    SINGLE = "###"
    TWO = "</s>"
    THREE = auto()
    FOUR = auto()


class ExampleType(Enum):
    ONE_SHOT = "one_shot"
    FEW_SHOT = "few_shot"
