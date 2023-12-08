#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import Enum
from typing import TypedDict, Optional, Dict, List, Any

from dataclasses import dataclass, asdict
import time
from datetime import datetime
from dbgpt.util.parameter_utils import ParameterDescription
from dbgpt.util.model_utils import GPUInfo


class ModelType:
    """ "Type of model"""

    HF = "huggingface"
    LLAMA_CPP = "llama.cpp"
    PROXY = "proxy"
    VLLM = "vllm"
    # TODO, support more model type


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
class WorkerApplyOutput:
    message: str
    success: Optional[bool] = True
    # The seconds cost to apply some action to worker instances
    timecost: Optional[int] = -1

    @staticmethod
    def reduce(outs: List["WorkerApplyOutput"]) -> "WorkerApplyOutput":
        """Merge all outputs

        Args:
            outs (List["WorkerApplyOutput"]): The list of WorkerApplyOutput
        """
        if not outs:
            return WorkerApplyOutput("Not outputs")
        combined_success = all(out.success for out in outs)
        max_timecost = max(out.timecost for out in outs)
        combined_message = ", ".join(out.message for out in outs)
        return WorkerApplyOutput(combined_message, combined_success, max_timecost)


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
