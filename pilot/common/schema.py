from enum import auto, Enum
from typing import List, Any


class SeparatorStyle(Enum):
    SINGLE = "###"
    TWO = "</s>"
    THREE = auto()
    FOUR = auto()
