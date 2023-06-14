#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import warnings
from typing import Optional

import torch

from pilot.configs.model_config import DEVICE
from pilot.model.adapter import get_llm_model_adapter
from pilot.model.compression import compress_module
from pilot.model.llm.monkey_patch import replace_llama_attn_with_non_inplace_operations
from pilot.singleton import Singleton
from pilot.utils import get_gpu_memory


def raise_warning_for_incompatible_cpu_offloading_configuration(
    device: str, load_8bit: bool, cpu_offloading: bool
):
    if cpu_offloading:
        if not load_8bit:
            warnings.warn(
                "The cpu-offloading feature can only be used while also using 8-bit-quantization.\n"
                "Use '--load-8bit' to enable 8-bit-quantization\n"
                "Continuing without cpu-offloading enabled\n"
            )
            return False
        if not "linux" in sys.platform:
            warnings.warn(
                "CPU-offloading is only supported on linux-systems due to the limited compatability with the bitsandbytes-package\n"
                "Continuing without cpu-offloading enabled\n"
            )
            return False
        if device != "cuda":
            warnings.warn(
                "CPU-offloading is only enabled when using CUDA-devices\n"
                "Continuing without cpu-offloading enabled\n"
            )
            return False
    return cpu_offloading


class ModelLoader(metaclass=Singleton):
    """Model loader is a class for model load

      Args: model_path

    TODO: multi model support.
    """

    kwargs = {}

    def __init__(self, model_path) -> None:
        self.device = DEVICE
        self.model_path = model_path
        self.kwargs = {
            "torch_dtype": torch.float16,
            "device_map": "auto",
        }

    # TODO multi gpu support
    def loader(
        self,
        num_gpus,
        load_8bit=False,
        debug=False,
        cpu_offloading=False,
        max_gpu_memory: Optional[str] = None,
    ):
        if self.device == "cpu":
            kwargs = {"torch_dtype": torch.float32}

        elif self.device == "cuda":
            kwargs = {"torch_dtype": torch.float16}
            num_gpus = torch.cuda.device_count()

            if num_gpus != 1:
                kwargs["device_map"] = "auto"
                # if max_gpu_memory is None:
                #     kwargs["device_map"] = "sequential"

                available_gpu_memory = get_gpu_memory(num_gpus)
                kwargs["max_memory"] = {
                    i: str(int(available_gpu_memory[i] * 0.85)) + "GiB"
                    for i in range(num_gpus)
                }

            else:
                kwargs["max_memory"] = {i: max_gpu_memory for i in range(num_gpus)}

        elif self.device == "mps":
            kwargs = kwargs = {"torch_dtype": torch.float16}
            replace_llama_attn_with_non_inplace_operations()
        else:
            raise ValueError(f"Invalid device: {self.device}")

        # TODO when cpu loading,  need use quantization config

        llm_adapter = get_llm_model_adapter(self.model_path)
        model, tokenizer = llm_adapter.loader(self.model_path, kwargs)

        if load_8bit and tokenizer:
            if num_gpus != 1:
                warnings.warn(
                    "8-bit quantization is not supported for multi-gpu inference"
                )
            else:
                compress_module(model, self.device)

        if (
            (self.device == "cuda" and num_gpus == 1 and not cpu_offloading)
            or self.device == "mps"
            and tokenizer
        ):
            # 4-bit not support this
            try:
                model.to(self.device)
            except ValueError:
                pass
            except AttributeError:
                pass

        if debug:
            print(model)

        return model, tokenizer
