#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

from typing import Any, Optional, Type
from dataclasses import dataclass, field, fields

from pilot.model.conversation import conv_templates

suported_prompt_templates = ",".join(conv_templates.keys())


def _genenv_ignoring_key_case(env_key: str, env_prefix: str = None, default_value=None):
    """Get the value from the environment variable, ignoring the case of the key"""
    if env_prefix:
        env_key = env_prefix + env_key
    return os.getenv(
        env_key, os.getenv(env_key.upper(), os.getenv(env_key.lower(), default_value))
    )


class EnvArgumentParser:
    def parse_args_into_dataclass(
        self, dataclass_type: Type, env_prefix: str = None, **kwargs
    ) -> Any:
        for field in fields(dataclass_type):
            env_var_value = _genenv_ignoring_key_case(field.name, env_prefix)
            if env_var_value:
                env_var_value = env_var_value.strip()
                if field.type is int or field.type == Optional[int]:
                    env_var_value = int(env_var_value)
                elif field.type is float or field.type == Optional[float]:
                    env_var_value = float(env_var_value)
                elif field.type is bool or field.type == Optional[bool]:
                    env_var_value = env_var_value.lower() == "true"
                elif field.type is str or field.type == Optional[str]:
                    pass
                else:
                    raise ValueError(f"Unsupported parameter type {field.type}")
                kwargs[field.name] = env_var_value
        return dataclass_type(**kwargs)


@dataclass
class ModelParameters:
    device: str = field(metadata={"help": "Device to run model"})
    model_name: str = field(metadata={"help": "Model name"})
    model_path: str = field(metadata={"help": "Model path"})
    model_type: Optional[str] = field(
        default="huggingface", metadata={"help": "Model type, huggingface or llama.cpp"}
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
    # "bfloat16", "float16", "float32"
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
