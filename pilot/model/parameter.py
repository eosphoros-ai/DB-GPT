#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass, field, fields, MISSING
from enum import Enum
from typing import Any, Dict, Optional

from pilot.model.conversation import conv_templates
from pilot.utils.parameter_utils import BaseParameters

suported_prompt_templates = ",".join(conv_templates.keys())


class WorkerType(str, Enum):
    LLM = "llm"
    TEXT2VEC = "text2vec"

    @staticmethod
    def values():
        return [item.value for item in WorkerType]


@dataclass
class ModelControllerParameters(BaseParameters):
    host: Optional[str] = field(
        default="0.0.0.0", metadata={"help": "Model Controller deploy host"}
    )
    port: Optional[int] = field(
        default=8000, metadata={"help": "Model Controller deploy port"}
    )


@dataclass
class ModelWorkerParameters(BaseParameters):
    model_name: str = field(metadata={"help": "Model name", "tags": "fixed"})
    model_path: str = field(metadata={"help": "Model path", "tags": "fixed"})
    worker_type: Optional[str] = field(
        default=None,
        metadata={"valid_values": WorkerType.values(), "help": "Worker type"},
    )
    worker_class: Optional[str] = field(
        default=None,
        metadata={
            "help": "Model worker class, pilot.model.worker.default_worker.DefaultModelWorker"
        },
    )
    host: Optional[str] = field(
        default="0.0.0.0", metadata={"help": "Model worker deploy host"}
    )

    port: Optional[int] = field(
        default=8000, metadata={"help": "Model worker deploy port"}
    )
    limit_model_concurrency: Optional[int] = field(
        default=5, metadata={"help": "Model concurrency limit"}
    )
    standalone: Optional[bool] = field(
        default=False,
        metadata={"help": "Standalone mode. If True, embedded Run ModelController"},
    )
    register: Optional[bool] = field(
        default=True, metadata={"help": "Register current worker to model controller"}
    )
    worker_register_host: Optional[str] = field(
        default=None,
        metadata={
            "help": "The ip address of current worker to register to ModelController. If None, the address is automatically determined"
        },
    )
    controller_addr: Optional[str] = field(
        default=None, metadata={"help": "The Model controller address to register"}
    )
    send_heartbeat: Optional[bool] = field(
        default=True, metadata={"help": "Send heartbeat to model controller"}
    )
    heartbeat_interval: Optional[int] = field(
        default=20, metadata={"help": "The interval for sending heartbeats (seconds)"}
    )


@dataclass
class EmbeddingModelParameters(BaseParameters):
    model_name: str = field(metadata={"help": "Model name", "tags": "fixed"})
    model_path: str = field(metadata={"help": "Model path", "tags": "fixed"})
    device: Optional[str] = field(
        default=None,
        metadata={
            "help": "Device to run model. If None, the device is automatically determined"
        },
    )

    normalize_embeddings: Optional[bool] = field(
        default=None,
        metadata={
            "help": "Determines whether the model's embeddings should be normalized."
        },
    )

    def build_kwargs(self, **kwargs) -> Dict:
        model_kwargs, encode_kwargs = None, None
        if self.device:
            model_kwargs = {"device": self.device}
        if self.normalize_embeddings:
            encode_kwargs = {"normalize_embeddings": self.normalize_embeddings}
        if model_kwargs:
            kwargs["model_kwargs"] = model_kwargs
        if encode_kwargs:
            kwargs["encode_kwargs"] = encode_kwargs
        return kwargs


@dataclass
class ModelParameters(BaseParameters):
    model_name: str = field(metadata={"help": "Model name", "tags": "fixed"})
    model_path: str = field(metadata={"help": "Model path", "tags": "fixed"})
    device: Optional[str] = field(
        default=None,
        metadata={
            "help": "Device to run model. If None, the device is automatically determined"
        },
    )
    model_type: Optional[str] = field(
        default="huggingface",
        metadata={"help": "Model type, huggingface or llama.cpp", "tags": "fixed"},
    )
    prompt_template: Optional[str] = field(
        default=None,
        metadata={
            "help": f"Prompt template. If None, the prompt template is automatically determined from model path, supported template: {suported_prompt_templates}"
        },
    )
    max_context_size: Optional[int] = field(
        default=4096, metadata={"help": "Maximum context size"}
    )

    num_gpus: Optional[int] = field(
        default=None,
        metadata={
            "help": "The number of gpus you expect to use, if it is empty, use all of them as much as possible"
        },
    )
    max_gpu_memory: Optional[str] = field(
        default=None,
        metadata={
            "help": "The maximum memory limit of each GPU, only valid in multi-GPU configuration"
        },
    )
    cpu_offloading: Optional[bool] = field(
        default=False, metadata={"help": "CPU offloading"}
    )
    load_8bit: Optional[bool] = field(
        default=False, metadata={"help": "8-bit quantization"}
    )
    load_4bit: Optional[bool] = field(
        default=False, metadata={"help": "4-bit quantization"}
    )
    quant_type: Optional[str] = field(
        default="nf4",
        metadata={
            "valid_values": ["nf4", "fp4"],
            "help": "Quantization datatypes, `fp4` (four bit float) and `nf4` (normal four bit float), only valid when load_4bit=True",
        },
    )
    use_double_quant: Optional[bool] = field(
        default=True,
        metadata={"help": "Nested quantization, only valid when load_4bit=True"},
    )
    compute_dtype: Optional[str] = field(
        default=None,
        metadata={
            "valid_values": ["bfloat16", "float16", "float32"],
            "help": "Model compute type",
        },
    )
    trust_remote_code: Optional[bool] = field(
        default=True, metadata={"help": "Trust remote code"}
    )
    verbose: Optional[bool] = field(
        default=False, metadata={"help": "Show verbose output."}
    )


@dataclass
class LlamaCppModelParameters(ModelParameters):
    seed: Optional[int] = field(
        default=-1, metadata={"help": "Random seed for llama-cpp models. -1 for random"}
    )
    n_threads: Optional[int] = field(
        default=None,
        metadata={
            "help": "Number of threads to use. If None, the number of threads is automatically determined"
        },
    )
    n_batch: Optional[int] = field(
        default=512,
        metadata={
            "help": "Maximum number of prompt tokens to batch together when calling llama_eval"
        },
    )
    n_gpu_layers: Optional[int] = field(
        default=1000000000,
        metadata={
            "help": "Number of layers to offload to the GPU, Set this to 1000000000 to offload all layers to the GPU."
        },
    )
    n_gqa: Optional[int] = field(
        default=None,
        metadata={"help": "Grouped-query attention. Must be 8 for llama-2 70b."},
    )
    rms_norm_eps: Optional[float] = field(
        default=5e-06, metadata={"help": "5e-6 is a good value for llama-2 models."}
    )
    cache_capacity: Optional[str] = field(
        default=None,
        metadata={
            "help": "Maximum cache capacity. Examples: 2000MiB, 2GiB. When provided without units, bytes will be assumed. "
        },
    )
    prefer_cpu: Optional[bool] = field(
        default=False,
        metadata={
            "help": "If a GPU is available, it will be preferred by default, unless prefer_cpu=False is configured."
        },
    )
