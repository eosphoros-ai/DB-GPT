#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import Enum
from typing import TypedDict, Optional, Dict
from dataclasses import dataclass
from datetime import datetime


class Message(TypedDict):
    """LLM Message object containing usually like (role: content)"""

    role: str
    content: str


@dataclass
class ModelInstance:
    """Model instance info"""

    model_name: str
    host: str
    port: int
    weight: Optional[float] = 1.0
    check_healthy: Optional[bool] = True
    healthy: Optional[bool] = False
    enabled: Optional[bool] = True
    prompt_template: Optional[str] = None
    last_heartbeat: Optional[datetime] = None


class WorkerApplyType(str, Enum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    UPDATE_PARAMS = "update_params"


@dataclass
class ModelOutput:
    text: str
    error_code: int
    model_context: Dict = None


@dataclass
class WorkerApplyOutput:
    message: str
    # The seconds cost to apply some action to worker instances
    timecost: Optional[int] = -1
