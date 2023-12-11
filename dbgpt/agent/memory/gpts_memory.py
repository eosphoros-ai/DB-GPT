from __future__ import annotations
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

from .base import GptsPlansMemory, GptsPlan, GptsMessageMemory, GptsMessage
from .default_gpts_memory import DefaultGptsPlansMemory, DefaultGptsMessageMemory

class GptsMemory:
    def __init__(self, plans_memory: Optional[GptsPlansMemory]=None, message_memory: Optional[GptsMessageMemory]=None):
        self._plans_memory: GptsPlansMemory = plans_memory if plans_memory is not None else DefaultGptsPlansMemory()
        self._message_memory: GptsMessageMemory = message_memory if message_memory is not None else DefaultGptsMessageMemory()


    @property
    def plans_memory(self):
        return self._plans_memory


    @property
    def message_memory(self):
        return self._message_memory
