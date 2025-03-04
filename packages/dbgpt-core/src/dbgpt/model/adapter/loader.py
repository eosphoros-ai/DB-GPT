#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from typing import Any, Dict, Optional, cast

from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.adapter.base import LLMModelAdapter
from dbgpt.util import get_gpu_memory
from dbgpt.util.parameter_utils import _genenv_ignoring_key_case

from .hf_adapter import HFLLMDeployModelParameters

logger = logging.getLogger(__name__)


def _check_multi_gpu_or_4bit_quantization(model_params: LLMDeployModelParameters):
    model_name = model_params.real_provider_model_name.lower()
    supported_models = ["llama", "baichuan", "vicuna"]
    return any(m in model_name for m in supported_models)


def _hf_check_quantization(model_params: HFLLMDeployModelParameters):
    model_name = model_params.real_provider_model_name.lower()
    has_quantization = model_params.quantization is not None
    if has_quantization:
        if model_params.real_device != "cuda":
            logger.warn(
                "8-bit quantization and 4-bit quantization just supported by cuda"
            )
            return False
        elif "chatglm" in model_name:
            if "int4" not in model_name:
                logger.warn(
                    "chatglm or chatglm2 not support quantization now, see: "
                    "https://github.com/huggingface/transformers/issues/25228"
                )
            return False
    return has_quantization


def _get_model_real_path(model_name, default_model_path) -> str:
    """Get model real path by model name
    priority from high to low:
    1. environment variable with key: {model_name}_model_path
    2. environment variable with key: model_path
    3. default_model_path
    """
    env_prefix = model_name + "_"
    env_prefix = env_prefix.replace("-", "_")
    env_model_path = _genenv_ignoring_key_case("model_path", env_prefix=env_prefix)
    if env_model_path:
        return env_model_path
    return _genenv_ignoring_key_case("model_path", default_value=default_model_path)


class ModelLoader:
    """Model loader is a class for model load."""

    def __init__(
        self,
        prompt_template: Optional[str] = None,
    ) -> None:
        self.prompt_template: Optional[str] = prompt_template

    def loader_with_params(
        self, model_params: LLMDeployModelParameters, llm_adapter: LLMModelAdapter
    ):
        """Load model with model parameters."""
        return llm_adapter.load_from_params(model_params)


def huggingface_loader(
    llm_adapter: LLMModelAdapter, model_params: LLMDeployModelParameters
):
    import torch

    from dbgpt.model.llm.compression import compress_module

    if not isinstance(model_params, HFLLMDeployModelParameters):
        raise ValueError(
            "Huggingface model loader only support HFLLMDeployModelParameters"
        )
    model_params = cast(HFLLMDeployModelParameters, model_params)
    model_path = model_params.real_model_path or model_params.real_provider_model_name

    device = model_params.real_device
    max_memory = None

    # if device is cpu or mps. gpu need to be zero
    num_gpus = 0

    parsed_torch_dtype = _parse_torch_dtype(model_params.torch_dtype)
    kwargs = {}
    if device == "cpu":
        default_torch_dtype = torch.float32
    elif device == "cuda":
        default_torch_dtype = torch.float16
        if model_params.num_gpus is not None:
            num_gpus = model_params.num_gpus
        else:
            num_gpus = torch.cuda.device_count()
        available_gpu_memory = get_gpu_memory(num_gpus)
        max_memory = {
            i: str(int(available_gpu_memory[i] * 0.85)) + "GiB" for i in range(num_gpus)
        }
        if num_gpus != 1:
            kwargs["device_map"] = "auto"
            if model_params.max_gpu_memory:
                logger.info(
                    "There has max_gpu_memory from config: "
                    f"{model_params.max_gpu_memory}"
                )
                max_memory = {i: model_params.max_gpu_memory for i in range(num_gpus)}
                kwargs["max_memory"] = max_memory
            else:
                kwargs["max_memory"] = max_memory
        logger.debug(f"max_memory: {max_memory}")

    elif device == "mps":
        default_torch_dtype = torch.float16

        import transformers

        version = tuple(int(v) for v in transformers.__version__.split("."))
        if version < (4, 35, 0):
            from dbgpt.model.llm.monkey_patch import (
                replace_llama_attn_with_non_inplace_operations,
            )

            # NOTE: Recent transformers library seems to fix the mps issue, also
            # it has made some changes causing compatibility issues with our
            # original patch. So we only apply the patch for older versions.
            # Avoid bugs in mps backend by not using in-place operations.
            replace_llama_attn_with_non_inplace_operations()

    else:
        raise ValueError(f"Invalid device: {device}")

    kwargs["torch_dtype"] = parsed_torch_dtype or default_torch_dtype
    if model_params.low_cpu_mem_usage is not None:
        kwargs["low_cpu_mem_usage"] = model_params.low_cpu_mem_usage
    if "device_map" in kwargs and "low_cpu_mem_usage" not in kwargs:
        # Must set low_cpu_mem_usage to True when device_map is set
        kwargs["low_cpu_mem_usage"] = True
    if model_params.attn_implementation:
        kwargs["attn_implementation"] = model_params.attn_implementation

    model, tokenizer = _hf_try_load_default_quantization_model(
        model_path, llm_adapter, device, num_gpus, model_params, kwargs
    )
    if model:
        return model, tokenizer

    can_quantization = _hf_check_quantization(model_params)
    is_load_8bits = (
        model_params.quantization and model_params.quantization._is_load_in_8bits
    )

    if can_quantization:
        try:
            # Try load quantization model
            return load_huggingface_quantization_model(
                model_path, llm_adapter, model_params, kwargs, max_memory
            )
        except Exception as e:
            logger.warning(
                f"Load quantization model failed, error: {str(e)}, try load default "
                "model"
            )
    # default loader
    model, tokenizer = llm_adapter.load(model_path, kwargs)

    if is_load_8bits and num_gpus == 1 and tokenizer:
        # Try to compress model with 8bit
        compress_module(model, device)

    return _hf_handle_model_and_tokenizer(
        model, tokenizer, device, num_gpus, model_params
    )


def _hf_try_load_default_quantization_model(
    model_path: str,
    llm_adapter: LLMModelAdapter,
    device: str,
    num_gpus: int,
    model_params: HFLLMDeployModelParameters,
    kwargs: Dict[str, Any],
):
    """Try load default quantization model(Support by huggingface default)"""
    cloned_kwargs = {k: v for k, v in kwargs.items()}
    model_name = model_params.name
    try:
        model, tokenizer = None, None
        if device != "cuda":
            # Just support cuda
            return None, None
        elif model_params.quantization and (
            llm_adapter.support_8bit or llm_adapter.support_4bit
        ):
            quantization_config = (
                model_params.quantization.generate_quantization_config()
            )
            if not quantization_config:
                logger.warning(
                    f"Generate quantization config failed, model: {model_name}"
                )
                return None, None
            logger.info(
                f"Load quantization model {model_name} with config: "
                f"{quantization_config}"
            )
            cloned_kwargs.update(quantization_config)
            model, tokenizer = llm_adapter.load(model_path, cloned_kwargs)
        if model:
            logger.info(f"Load default quantization model {model_name} success")
            return _hf_handle_model_and_tokenizer(
                model, tokenizer, device, num_gpus, model_params
            )
        return None, None
    except Exception as e:
        logger.warning(
            f"Load default quantization model {model_name} failed, error: {str(e)}"
        )
        return None, None


def _hf_handle_model_and_tokenizer(
    model,
    tokenizer,
    device: str,
    num_gpus: int,
    model_params: HFLLMDeployModelParameters,
):
    if (device == "cuda" and num_gpus == 1) or device == "mps" and tokenizer:
        # TODO: Check cpu_offloading
        try:
            model.to(device)
        except ValueError:
            pass
        except AttributeError:
            pass
    if model_params.verbose:
        print(model)
    return model, tokenizer


def _parse_torch_dtype(torch_dtype: Optional[str]):
    import torch  # noqa: F401

    if torch_dtype and torch_dtype in ["float16", "bfloat16", "float", "float32"]:
        try:
            return eval(f"torch.{torch_dtype}")
        except Exception as e:
            logger.warning(f"Parse torch dtype failed, error: {str(e)}")
            return None
    return torch_dtype


def load_huggingface_quantization_model(
    model_path: str,
    llm_adapter: LLMModelAdapter,
    model_params: HFLLMDeployModelParameters,
    kwargs: Dict,
    max_memory: Dict[int, str],
):
    import torch

    try:
        import transformers
        from accelerate import init_empty_weights
        from accelerate.utils import infer_auto_device_map
        from transformers import (
            AutoConfig,
            AutoModel,
            AutoModelForCausalLM,
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            LlamaForCausalLM,
            LlamaTokenizer,
        )
    except ImportError as exc:
        raise ValueError(
            "Could not import depend python package "
            "Please install it with `pip install transformers` "
            "`pip install bitsandbytes``pip install accelerate`."
        ) from exc

    if not model_params.quantization:
        raise ValueError("Quantization config is required")

    # It will be return a dict with keys: quantization_config
    quantization_config = model_params.quantization.generate_quantization_config()
    is_load_8bits = (
        model_params.quantization and model_params.quantization._is_load_in_8bits
    )

    model_name = model_params.real_provider_model_name.lower()
    if "llama-2" in model_name and not transformers.__version__ >= "4.31.0":
        raise ValueError(
            "Llama-2 quantization require transformers.__version__>=4.31.0"
        )
    if "low_cpu_mem_usage" in kwargs and kwargs["low_cpu_mem_usage"] is False:
        logger.warning(
            "low_cpu_mem_usage setting is False, it dose not support for "
            "quantization model, will set it to True"
        )
    params = {"low_cpu_mem_usage": True, "device_map": "auto"}
    torch_dtype = kwargs.get("torch_dtype")
    params["torch_dtype"] = torch_dtype if torch_dtype else torch.float16
    params["max_memory"] = max_memory
    params.update(quantization_config)

    if "chatglm" in model_name:
        LoaderClass = AutoModel
    else:
        config = AutoConfig.from_pretrained(
            model_path, trust_remote_code=model_params.trust_remote_code
        )
        if config.to_dict().get("is_encoder_decoder", False):
            LoaderClass = AutoModelForSeq2SeqLM
        else:
            LoaderClass = AutoModelForCausalLM

    if is_load_8bits and max_memory is not None:
        config = AutoConfig.from_pretrained(
            model_path, trust_remote_code=model_params.trust_remote_code
        )
        with init_empty_weights():
            model = LoaderClass.from_config(
                config, trust_remote_code=model_params.trust_remote_code
            )

        model.tie_weights()
        params["device_map"] = infer_auto_device_map(
            model,
            dtype=torch.int8,
            max_memory=params["max_memory"].copy(),
            no_split_module_classes=model._no_split_modules,
        )
    try:
        if model_params.trust_remote_code:
            params["trust_remote_code"] = True
        logger.info(f"params: {params}")
        model = LoaderClass.from_pretrained(model_path, **params)
    except Exception as e:
        logger.error(
            f"Load quantization model failed, error: {str(e)}, params: {params}"
        )
        raise e

    # Loading the tokenizer
    if type(model) is LlamaForCausalLM:
        logger.info(
            "Current model is type of: LlamaForCausalLM, load tokenizer by "
            "LlamaTokenizer"
        )
        tokenizer = LlamaTokenizer.from_pretrained(
            model_path, clean_up_tokenization_spaces=True
        )
        # Leaving this here until the LLaMA tokenizer gets figured out.
        # For some people this fixes things, for others it causes an error.
        try:
            tokenizer.eos_token_id = 2
            tokenizer.bos_token_id = 1
            tokenizer.pad_token_id = 0
        except Exception as e:
            logger.warn(f"{str(e)}")
    else:
        logger.info(
            "Current model type is not LlamaForCausalLM, load tokenizer by "
            "AutoTokenizer"
        )
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=model_params.trust_remote_code,
            use_fast=llm_adapter.use_fast_tokenizer(),
        )

    return model, tokenizer
