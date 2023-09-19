#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import Enum
from typing import TypedDict, Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime
from pilot.utils.parameter_utils import ParameterDescription


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
    success: Optional[bool] = True
    # The seconds cost to apply some action to worker instances
    timecost: Optional[int] = -1


@dataclass
class SupportedModel:
    model: str
    path: str
    worker_type: str
    path_exist: bool
    proxy: bool
    enabled: bool
    params: List[ParameterDescription]

    @classmethod
    def from_dict(cls, model_data: Dict) -> "SupportedModel":
        params = model_data.get("params", [])
        if params:
            params = [ParameterDescription(**param) for param in params]
        model_data["params"] = params
        return cls(**model_data)


@dataclass
class WorkerSupportedModel:
    host: str
    port: int
    models: List[SupportedModel]

    @classmethod
    def from_dict(cls, worker_data: Dict) -> "WorkerSupportedModel":
        models = [
            SupportedModel.from_dict(model_data) for model_data in worker_data["models"]
        ]
        worker_data["models"] = models
        return cls(**worker_data)


@dataclass
class FlatSupportedModel(SupportedModel):
    """For web"""

    host: str
    port: int

    @staticmethod
    def from_supports(
        supports: List[WorkerSupportedModel],
    ) -> List["FlatSupportedModel"]:
        results = []
        for s in supports:
            host, port, models = s.host, s.port, s.models
            for m in models:
                kwargs = asdict(m)
                kwargs["host"] = host
                kwargs["port"] = port
                results.append(FlatSupportedModel(**kwargs))
        return results
