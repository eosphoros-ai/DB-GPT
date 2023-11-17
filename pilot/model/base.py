#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from enum import Enum
from typing import TypedDict, Optional, Dict, List, Any

from dataclasses import dataclass, asdict
import time
from datetime import datetime
from pilot.utils.parameter_utils import ParameterDescription


class Message(TypedDict):
    """LLM Message object containing usually like (role: content)"""

    role: str
    content: str


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
class ModelInferenceMetrics:
    """A class to represent metrics for assessing the inference performance of a LLM."""

    start_time_ms: Optional[int] = None
    """The timestamp (in milliseconds) when the model inference starts."""

    end_time_ms: Optional[int] = None
    """The timestamp (in milliseconds) when the model inference ends."""

    current_time_ms: Optional[int] = None
    """The current timestamp (in milliseconds) when the model inference return partially output(stream)."""

    first_token_time_ms: Optional[int] = None
    """The timestamp (in milliseconds) when the first token is generated."""

    first_completion_time_ms: Optional[int] = None
    """The timestamp (in milliseconds) when the first completion is generated."""

    first_completion_tokens: Optional[int] = None
    """The number of tokens when the first completion is generated."""

    prompt_tokens: Optional[int] = None
    """The number of tokens in the input prompt."""

    completion_tokens: Optional[int] = None
    """The number of tokens in the generated completion."""

    total_tokens: Optional[int] = None
    """The total number of tokens (prompt plus completion)."""

    speed_per_second: Optional[float] = None
    """The average number of tokens generated per second."""

    @staticmethod
    def create_metrics(
        last_metrics: Optional["ModelInferenceMetrics"] = None,
    ) -> "ModelInferenceMetrics":
        start_time_ms = last_metrics.start_time_ms if last_metrics else None
        first_token_time_ms = last_metrics.first_token_time_ms if last_metrics else None
        first_completion_time_ms = (
            last_metrics.first_completion_time_ms if last_metrics else None
        )
        first_completion_tokens = (
            last_metrics.first_completion_tokens if last_metrics else None
        )
        prompt_tokens = last_metrics.prompt_tokens if last_metrics else None
        completion_tokens = last_metrics.completion_tokens if last_metrics else None
        total_tokens = last_metrics.total_tokens if last_metrics else None
        speed_per_second = last_metrics.speed_per_second if last_metrics else None

        if not start_time_ms:
            start_time_ms = time.time_ns() // 1_000_000
        current_time_ms = time.time_ns() // 1_000_000
        end_time_ms = current_time_ms

        return ModelInferenceMetrics(
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            current_time_ms=current_time_ms,
            first_token_time_ms=first_token_time_ms,
            first_completion_time_ms=first_completion_time_ms,
            first_completion_tokens=first_completion_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            speed_per_second=speed_per_second,
        )

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ModelOutput:
    text: str
    error_code: int
    model_context: Dict = None
    finish_reason: str = None
    usage: Dict[str, Any] = None
    metrics: Optional[ModelInferenceMetrics] = None

    """Some metrics for model inference"""

    def to_dict(self) -> Dict:
        return asdict(self)


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
