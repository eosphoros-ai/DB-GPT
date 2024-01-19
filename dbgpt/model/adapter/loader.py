#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from typing import Any, Dict, Optional

from dbgpt.configs.model_config import get_device
from dbgpt.model.adapter.base import LLMModelAdapter
from dbgpt.model.adapter.model_adapter import get_llm_model_adapter
from dbgpt.model.base import ModelType
from dbgpt.model.parameter import (
    LlamaCppModelParameters,
    ModelParameters,
    ProxyModelParameters,
)
from dbgpt.util import get_gpu_memory
from dbgpt.util.parameter_utils import EnvArgumentParser, _genenv_ignoring_key_case

logger = logging.getLogger(__name__)


def _check_multi_gpu_or_4bit_quantization(model_params: ModelParameters):
    # TODO: vicuna-v1.5 8-bit quantization info is slow
    # TODO: support wizardlm quantization, see: https://huggingface.co/WizardLM/WizardLM-13B-V1.2/discussions/5
    # TODO: support internlm quantization
    model_name = model_params.model_name.lower()
    supported_models = ["llama", "baichuan", "vicuna"]
    return any(m in model_name for m in supported_models)


def _check_quantization(model_params: ModelParameters):
    model_name = model_params.model_name.lower()
    has_quantization = any([model_params.load_8bit or model_params.load_4bit])
    if has_quantization:
        if model_params.device != "cuda":
            logger.warn(
                "8-bit quantization and 4-bit quantization just supported by cuda"
            )
            return False
        elif "chatglm" in model_name:
            if "int4" not in model_name:
                logger.warn(
                    "chatglm or chatglm2 not support quantization now, see: https://github.com/huggingface/transformers/issues/25228"
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
    """Model loader is a class for model load

      Args: model_path

    TODO: multi model support.
    """

    def __init__(self, model_path: str, model_name: str = None) -> None:
        self.device = get_device()
        self.model_path = model_path
        self.model_name = model_name
        self.prompt_template: str = None

    # TODO multi gpu support
    def loader(
        self,
        load_8bit=False,
        load_4bit=False,
        debug=False,
        cpu_offloading=False,
        max_gpu_memory: Optional[str] = None,
    ):
        llm_adapter = get_llm_model_adapter(self.model_name, self.model_path)
        model_type = llm_adapter.model_type()
        param_cls = llm_adapter.model_param_class(model_type)

        args_parser = EnvArgumentParser()
        # Read the parameters of the model from the environment variable according to the model name prefix, which currently has the highest priority
        # vicuna_13b_max_gpu_memory=13Gib or VICUNA_13B_MAX_GPU_MEMORY=13Gib
        env_prefix = self.model_name + "_"
        env_prefix = env_prefix.replace("-", "_")
        model_params = args_parser.parse_args_into_dataclass(
            param_cls,
            env_prefixes=[env_prefix],
            device=self.device,
            model_path=self.model_path,
            model_name=self.model_name,
            max_gpu_memory=max_gpu_memory,
            cpu_offloading=cpu_offloading,
            load_8bit=load_8bit,
            load_4bit=load_4bit,
            verbose=debug,
        )
        self.prompt_template = model_params.prompt_template

        logger.info(f"model_params:\n{model_params}")

        if model_type == ModelType.HF:
            return huggingface_loader(llm_adapter, model_params)
        elif model_type == ModelType.LLAMA_CPP:
            return llamacpp_loader(llm_adapter, model_params)
        else:
            raise Exception(f"Unkown model type {model_type}")

    def loader_with_params(
        self, model_params: ModelParameters, llm_adapter: LLMModelAdapter
    ):
        model_type = llm_adapter.model_type()
        self.prompt_template = model_params.prompt_template
        if model_type == ModelType.HF:
            return huggingface_loader(llm_adapter, model_params)
        elif model_type == ModelType.LLAMA_CPP:
            return llamacpp_loader(llm_adapter, model_params)
        elif model_type == ModelType.PROXY:
            # return proxyllm_loader(llm_adapter, model_params)
            return llm_adapter.load_from_params(model_params)
        elif model_type == ModelType.VLLM:
            return llm_adapter.load_from_params(model_params)
        else:
            raise Exception(f"Unkown model type {model_type}")


def huggingface_loader(llm_adapter: LLMModelAdapter, model_params: ModelParameters):
    import torch

    from dbgpt.model.llm.compression import compress_module

    device = model_params.device
    max_memory = None

    # if device is cpu or mps. gpu need to be zero
    num_gpus = 0

    if device == "cpu":
        kwargs = {"torch_dtype": torch.float32}
    elif device == "cuda":
        kwargs = {"torch_dtype": torch.float16}
        num_gpus = torch.cuda.device_count()
        available_gpu_memory = get_gpu_memory(num_gpus)
        max_memory = {
            i: str(int(available_gpu_memory[i] * 0.85)) + "GiB" for i in range(num_gpus)
        }
        if num_gpus != 1:
            kwargs["device_map"] = "auto"
            if model_params.max_gpu_memory:
                logger.info(
                    f"There has max_gpu_memory from config: {model_params.max_gpu_memory}"
                )
                max_memory = {i: model_params.max_gpu_memory for i in range(num_gpus)}
                kwargs["max_memory"] = max_memory
            else:
                kwargs["max_memory"] = max_memory
        logger.debug(f"max_memory: {max_memory}")

    elif device == "mps":
        kwargs = {"torch_dtype": torch.float16}

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

    model, tokenizer = _try_load_default_quantization_model(
        llm_adapter, device, num_gpus, model_params, kwargs
    )
    if model:
        return model, tokenizer

    can_quantization = _check_quantization(model_params)

    if can_quantization and (num_gpus > 1 or model_params.load_4bit):
        if _check_multi_gpu_or_4bit_quantization(model_params):
            return load_huggingface_quantization_model(
                llm_adapter, model_params, kwargs, max_memory
            )
        else:
            logger.warn(
                f"Current model {model_params.model_name} not supported quantization"
            )
    # default loader
    model, tokenizer = llm_adapter.load(model_params.model_path, kwargs)

    if model_params.load_8bit and num_gpus == 1 and tokenizer:
        # TODO merge current code into `load_huggingface_quantization_model`
        compress_module(model, model_params.device)

    return _handle_model_and_tokenizer(model, tokenizer, device, num_gpus, model_params)


def _try_load_default_quantization_model(
    llm_adapter: LLMModelAdapter,
    device: str,
    num_gpus: int,
    model_params: ModelParameters,
    kwargs: Dict[str, Any],
):
    """Try load default quantization model(Support by huggingface default)"""
    cloned_kwargs = {k: v for k, v in kwargs.items()}
    try:
        model, tokenizer = None, None
        if device != "cuda":
            return None, None
        elif model_params.load_8bit and llm_adapter.support_8bit:
            cloned_kwargs["load_in_8bit"] = True
            model, tokenizer = llm_adapter.load(model_params.model_path, cloned_kwargs)
        elif model_params.load_4bit and llm_adapter.support_4bit:
            cloned_kwargs["load_in_4bit"] = True
            model, tokenizer = llm_adapter.load(model_params.model_path, cloned_kwargs)
        if model:
            logger.info(
                f"Load default quantization model {model_params.model_name} success"
            )
            return _handle_model_and_tokenizer(
                model, tokenizer, device, num_gpus, model_params
            )
        return None, None
    except Exception as e:
        logger.warning(
            f"Load default quantization model {model_params.model_name} failed, error: {str(e)}"
        )
        return None, None


def _handle_model_and_tokenizer(
    model, tokenizer, device: str, num_gpus: int, model_params: ModelParameters
):
    if (
        (device == "cuda" and num_gpus == 1 and not model_params.cpu_offloading)
        or device == "mps"
        and tokenizer
    ):
        try:
            model.to(device)
        except ValueError:
            pass
        except AttributeError:
            pass
    if model_params.verbose:
        print(model)
    return model, tokenizer


def load_huggingface_quantization_model(
    llm_adapter: LLMModelAdapter,
    model_params: ModelParameters,
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
            BitsAndBytesConfig,
            LlamaForCausalLM,
            LlamaTokenizer,
        )
    except ImportError as exc:
        raise ValueError(
            "Could not import depend python package "
            "Please install it with `pip install transformers` "
            "`pip install bitsandbytes``pip install accelerate`."
        ) from exc
    if (
        "llama-2" in model_params.model_name.lower()
        and not transformers.__version__ >= "4.31.0"
    ):
        raise ValueError(
            "Llama-2 quantization require transformers.__version__>=4.31.0"
        )
    params = {"low_cpu_mem_usage": True}
    params["low_cpu_mem_usage"] = True
    params["device_map"] = "auto"

    torch_dtype = kwargs.get("torch_dtype")

    if model_params.load_4bit:
        compute_dtype = None
        if model_params.compute_dtype and model_params.compute_dtype in [
            "bfloat16",
            "float16",
            "float32",
        ]:
            compute_dtype = eval("torch.{}".format(model_params.compute_dtype))

        quantization_config_params = {
            "load_in_4bit": True,
            "bnb_4bit_compute_dtype": compute_dtype,
            "bnb_4bit_quant_type": model_params.quant_type,
            "bnb_4bit_use_double_quant": model_params.use_double_quant,
        }
        logger.warn(
            "Using the following 4-bit params: " + str(quantization_config_params)
        )
        params["quantization_config"] = BitsAndBytesConfig(**quantization_config_params)
    elif model_params.load_8bit and max_memory:
        params["quantization_config"] = BitsAndBytesConfig(
            load_in_8bit=True, llm_int8_enable_fp32_cpu_offload=True
        )
    elif model_params.load_in_8bit:
        params["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    params["torch_dtype"] = torch_dtype if torch_dtype else torch.float16
    params["max_memory"] = max_memory

    if "chatglm" in model_params.model_name.lower():
        LoaderClass = AutoModel
    else:
        config = AutoConfig.from_pretrained(
            model_params.model_path, trust_remote_code=model_params.trust_remote_code
        )
        if config.to_dict().get("is_encoder_decoder", False):
            LoaderClass = AutoModelForSeq2SeqLM
        else:
            LoaderClass = AutoModelForCausalLM

    if model_params.load_8bit and max_memory is not None:
        config = AutoConfig.from_pretrained(
            model_params.model_path, trust_remote_code=model_params.trust_remote_code
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
        model = LoaderClass.from_pretrained(model_params.model_path, **params)
    except Exception as e:
        logger.error(
            f"Load quantization model failed, error: {str(e)}, params: {params}"
        )
        raise e

    # Loading the tokenizer
    if type(model) is LlamaForCausalLM:
        logger.info(
            f"Current model is type of: LlamaForCausalLM, load tokenizer by LlamaTokenizer"
        )
        tokenizer = LlamaTokenizer.from_pretrained(
            model_params.model_path, clean_up_tokenization_spaces=True
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
            f"Current model type is not LlamaForCausalLM, load tokenizer by AutoTokenizer"
        )
        tokenizer = AutoTokenizer.from_pretrained(
            model_params.model_path,
            trust_remote_code=model_params.trust_remote_code,
            use_fast=llm_adapter.use_fast_tokenizer(),
        )

    return model, tokenizer


def llamacpp_loader(
    llm_adapter: LLMModelAdapter, model_params: LlamaCppModelParameters
):
    try:
        from dbgpt.model.llm.llama_cpp.llama_cpp import LlamaCppModel
    except ImportError as exc:
        raise ValueError(
            "Could not import python package: llama-cpp-python "
            "Please install db-gpt llama support with `cd $DB-GPT-DIR && pip install .[llama_cpp]` "
            "or install llama-cpp-python with `pip install llama-cpp-python`"
        ) from exc
    model_path = model_params.model_path
    model, tokenizer = LlamaCppModel.from_pretrained(model_path, model_params)
    return model, tokenizer


def proxyllm_loader(llm_adapter: LLMModelAdapter, model_params: ProxyModelParameters):
    from dbgpt.model.proxy.llms.proxy_model import ProxyModel

    logger.info("Load proxyllm")
    model = ProxyModel(model_params)
    return model, model
