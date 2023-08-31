#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

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
    @staticmethod
    def get_env_prefix(env_key: str) -> str:
        if not env_key:
            return None
        env_key = env_key.replace("-", "_")
        return env_key + "_"

    def parse_args_into_dataclass(
        self,
        dataclass_type: Type,
        env_prefix: str = None,
        command_args: List[str] = None,
        **kwargs,
    ) -> Any:
        """Parse parameters from environment variables and command lines and populate them into data class"""
        parser = argparse.ArgumentParser()
        for field in fields(dataclass_type):
            env_var_value = _genenv_ignoring_key_case(field.name, env_prefix)
            if not env_var_value:
                # Read without env prefix
                env_var_value = _genenv_ignoring_key_case(field.name)

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
            if not env_var_value:
                env_var_value = kwargs.get(field.name)
            if not env_var_value:
                env_var_value = field.default

            # Add a command-line argument for this field
            help_text = field.metadata.get("help", "")
            valid_values = field.metadata.get("valid_values", None)
            parser.add_argument(
                f"--{field.name}",
                type=self._get_argparse_type(field.type),
                help=help_text,
                choices=valid_values,
                default=env_var_value,
            )

        # Parse the command-line arguments
        cmd_args, cmd_argv = parser.parse_known_args(args=command_args)
        print(f"cmd_args: {cmd_args}")
        for field in fields(dataclass_type):
            # cmd_line_value = getattr(cmd_args, field.name)
            if field.name in cmd_args:
                cmd_line_value = getattr(cmd_args, field.name)
                if cmd_line_value is not None:
                    kwargs[field.name] = cmd_line_value

        return dataclass_type(**kwargs)

    @staticmethod
    def _get_argparse_type(field_type: Type) -> Type:
        # Return the appropriate type for argparse to use based on the field type
        if field_type is int or field_type == Optional[int]:
            return int
        elif field_type is float or field_type == Optional[float]:
            return float
        elif field_type is bool or field_type == Optional[bool]:
            return bool
        elif field_type is str or field_type == Optional[str]:
            return str
        else:
            raise ValueError(f"Unsupported parameter type {field_type}")

    @staticmethod
    def _get_argparse_type_str(field_type: Type) -> str:
        argparse_type = EnvArgumentParser._get_argparse_type(field_type)
        if argparse_type is int:
            return "int"
        elif argparse_type is float:
            return "float"
        elif argparse_type is bool:
            return "bool"
        else:
            return "str"


@dataclass
class ParameterDescription:
    param_name: str
    param_type: str
    description: str
    default_value: Optional[Any]
    valid_values: Optional[List[Any]]


def _get_parameter_descriptions(dataclass_type: Type) -> List[ParameterDescription]:
    descriptions = []
    for field in fields(dataclass_type):
        descriptions.append(
            ParameterDescription(
                param_name=field.name,
                param_type=EnvArgumentParser._get_argparse_type_str(field.type),
                description=field.metadata.get("help", None),
                default_value=field.default,  # TODO handle dataclasses._MISSING_TYPE
                valid_values=field.metadata.get("valid_values", None),
            )
        )
    return descriptions


class WorkerType(str, Enum):
    LLM = "llm"
    TEXT2VEC = "text2vec"

    @staticmethod
    def values():
        return [item.value for item in WorkerType]


@dataclass
class BaseParameters:
    def update_from(self, source: Union["BaseParameters", dict]) -> bool:
        """
        Update the attributes of this object using the values from another object (of the same or parent type) or a dictionary.
        Only update if the new value is different from the current value and the field is not marked as "fixed" in metadata.

        Args:
            source (Union[BaseParameters, dict]): The source to update from. Can be another object of the same type or a dictionary.

        Returns:
            bool: True if at least one field was updated, otherwise False.
        """
        updated = False  # Flag to indicate whether any field was updated
        if isinstance(source, (BaseParameters, dict)):
            for field_info in fields(self):
                # Check if the field has a "fixed" tag in metadata
                tags = field_info.metadata.get("tags")
                tags = [] if not tags else tags.split(",")
                if tags and "fixed" in tags:
                    continue  # skip this field
                # Get the new value from source (either another BaseParameters object or a dict)
                new_value = (
                    getattr(source, field_info.name)
                    if isinstance(source, BaseParameters)
                    else source.get(field_info.name, None)
                )

                # If the new value is not None and different from the current value, update the field and set the flag
                if new_value is not None and new_value != getattr(
                    self, field_info.name
                ):
                    setattr(self, field_info.name, new_value)
                    updated = True
        else:
            raise ValueError(
                "Source must be an instance of BaseParameters (or its derived class) or a dictionary."
            )

        return updated

    def __str__(self) -> str:
        class_name = self.__class__.__name__
        parameters = [
            f"\n\n=========================== {class_name} ===========================\n"
        ]
        for field_info in fields(self):
            value = getattr(self, field_info.name)
            parameters.append(f"{field_info.name}: {value}")
        parameters.append(
            "\n======================================================================\n\n"
        )
        return "\n".join(parameters)


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
            "help": "Model worker deploy host, pilot.model.worker.default_worker.DefaultModelWorker"
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
        default=True, metadata={"help": "8-bit quantization"}
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
