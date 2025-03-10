import logging
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Dict, List, Optional, Type

from dbgpt.core import ModelMessage
from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.adapter.base import LLMModelAdapter, register_model_adapter
from dbgpt.model.adapter.model_metadata import COMMON_HF_MODELS
from dbgpt.model.adapter.template import ConversationAdapter, ConversationAdapterFactory
from dbgpt.model.base import ModelType
from dbgpt.util.i18n_utils import _
from dbgpt.util.parameter_utils import (
    _get_dataclass_print_str,
)

logger = logging.getLogger(__name__)


@dataclass
class VLLMDeployModelParameters(LLMDeployModelParameters):
    """Local deploy model parameters."""

    provider: str = "vllm"

    path: Optional[str] = field(
        default=None,
        metadata={
            "order": -800,
            "help": _("The path of the model, if you want to deploy a local model."),
        },
    )
    device: Optional[str] = field(
        default="auto",
        metadata={
            "order": -700,
            "help": _(
                "Device to run model. If None, the device is automatically determined"
            ),
        },
    )

    concurrency: Optional[int] = field(
        default=100, metadata={"help": _("Model concurrency limit")}
    )

    @property
    def real_model_path(self) -> Optional[str]:
        """Get the real model path.

        If deploy model is not local, return None.
        """
        return self._resolve_root_path(self.path)

    @property
    def real_device(self) -> Optional[str]:
        """Get the real device."""
        return self.device or super().real_device

    def to_vllm_params(self, vllm_config_cls: Optional[Type] = None) -> Dict[str, Any]:
        """Convert to vllm parameters."""
        data = self.to_dict()
        model = data.get("path", None)
        if not model:
            model = data.get("name", None)
        else:
            # Path is specified, so we use it as the model
            model = self._resolve_root_path(model)
        if not model:
            raise ValueError(
                "Model is required, please specify the model path or name."
            )
        copy_data = data.copy()
        real_params = {}
        extra_params = copy_data.get("extras", {})
        if vllm_config_cls and is_dataclass(vllm_config_cls):
            for fd in fields(vllm_config_cls):
                if fd.name in copy_data:
                    real_params[fd.name] = copy_data[fd.name]
        else:
            for k, v in copy_data.items():
                if k in [
                    "provider",
                    "path",
                    "name",
                    "extras",
                    "verbose",
                    "backend",
                    "prompt_template",
                    "context_length",
                ]:
                    continue
                real_params[k] = v
        real_params["model"] = model
        if extra_params and isinstance(extra_params, dict):
            real_params.update(extra_params)
        return real_params

    trust_remote_code: Optional[bool] = field(
        default=True, metadata={"help": _("Trust remote code or not.")}
    )
    download_dir: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "Directory to download and load the weights, "
                "default to the default cache dir of "
                "huggingface."
            )
        },
    )
    load_format: Optional[str] = field(
        default="auto",
        metadata={
            "help": _(
                "The format of the model weights to load.\n\n"
                '* "auto" will try to load the weights in the safetensors format '
                "and fall back to the pytorch bin format if safetensors format "
                "is not available.\n"
                '* "pt" will load the weights in the pytorch bin format.\n'
                '* "safetensors" will load the weights in the safetensors format.\n'
                '* "npcache" will load the weights in pytorch format and store '
                "a numpy cache to speed up the loading.\n"
                '* "dummy" will initialize the weights with random values, '
                "which is mainly for profiling.\n"
                '* "tensorizer" will load the weights using tensorizer from '
                "CoreWeave. See the Tensorize vLLM Model script in the Examples "
                "section for more information.\n"
                '* "runai_streamer" will load the Safetensors weights using Run:ai'
                "Model Streamer \n"
                '* "bitsandbytes" will load the weights using bitsandbytes '
                "quantization.\n"
            ),
            "valid_values": [
                "auto",
                "pt",
                "safetensors",
                "npcache",
                "dummy",
                "tensorizer",
                "runai_streamer",
                "bitsandbytes",
                "sharded_state",
                "gguf",
                "mistral",
            ],
        },
    )
    config_format: Optional[str] = field(
        default="auto",
        metadata={
            "help": _(
                "The format of the model config to load.\n\n"
                '* "auto" will try to load the config in hf format '
                "if available else it will try to load in mistral format "
            ),
            "valid_values": [
                "auto",
                "hf",
                "mistral",
            ],
        },
    )
    dtype: Optional[str] = field(
        default="auto",
        metadata={
            "help": _(
                "Data type for model weights and activations.\n\n"
                '* "auto" will use FP16 precision for FP32 and FP16 models, and '
                "BF16 precision for BF16 models.\n"
                '* "half" for FP16. Recommended for AWQ quantization.\n'
                '* "float16" is the same as "half".\n'
                '* "bfloat16" for a balance between precision and range.\n'
                '* "float" is shorthand for FP32 precision.\n'
                '* "float32" for FP32 precision.'
            ),
            "valid_values": ["auto", "half", "float16", "bfloat16", "float", "float32"],
        },
    )
    kv_cache_dtype: str = field(
        default="auto",
        metadata={
            "help": _(
                'Data type for kv cache storage. If "auto", will use model '
                "data type. CUDA 11.8+ supports fp8 (=fp8_e4m3) and fp8_e5m2. "
                "ROCm (AMD GPU) supports fp8 (=fp8_e4m3)"
            ),
            "valid_values": ["auto", "fp8", "fp8_e5m2", "fp8_e4m3"],
        },
    )
    seed: int = field(
        default=0,
        metadata={
            "help": _("Random seed for operations."),
        },
    )
    max_model_len: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Model context length. If unspecified, will be automatically derived "
                "from the model config."
            ),
        },
    )
    distributed_executor_backend: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "Backend to use for distributed model "
                'workers, either "ray" or "mp" (multiprocessing). If the product '
                "of pipeline_parallel_size and tensor_parallel_size is less than "
                'or equal to the number of GPUs available, "mp" will be used to '
                "keep processing on a single host. Otherwise, this will default "
                'to "ray" if Ray is installed and fail otherwise. Note that tpu '
                "only supports Ray for distributed inference."
            ),
            "valid_values": ["ray", "mp", "uni", "external_launcher"],
        },
    )
    pipeline_parallel_size: int = field(
        default=1,
        metadata={
            "help": _("Number of pipeline stages."),
        },
    )
    tensor_parallel_size: int = field(
        default=1,
        metadata={
            "help": _("Number of tensor parallel replicas."),
        },
    )
    max_parallel_loading_workers: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Load model sequentially in multiple batches, to avoid RAM OOM when "
                "using tensor parallel and large models."
            ),
        },
    )
    block_size: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Token block size for contiguous chunks of tokens. This is ignored on "
                "neuron devices and set to ``--max-model-len``. On CUDA devices, only "
                "block sizes up to 32 are supported. On HPU devices, block size "
                "defaults to 128."
            ),
            "valid_values": [8, 16, 32, 64, 128],
        },
    )
    enable_prefix_caching: Optional[bool] = field(
        default=None,
        metadata={
            "help": _("Enables automatic prefix caching. "),
        },
    )
    swap_space: float = field(
        default=4,
        metadata={
            "help": _("CPU swap space size (GiB) per GPU."),
        },
    )
    cpu_offload_gb: float = field(
        default=0,
        metadata={
            "help": _(
                "The space in GiB to offload to CPU, per GPU. "
                "Default is 0, which means no offloading. Intuitively, "
                "this argument can be seen as a virtual way to increase "
                "the GPU memory size. For example, if you have one 24 GB "
                "GPU and set this to 10, virtually you can think of it as "
                "a 34 GB GPU. Then you can load a 13B model with BF16 weight, "
                "which requires at least 26GB GPU memory. Note that this "
                "requires fast CPU-GPU interconnect, as part of the model is "
                "loaded from CPU memory to GPU memory on the fly in each "
                "model forward pass."
            ),
        },
    )
    gpu_memory_utilization: float = field(
        default=0.90,
        metadata={
            "help": _(
                "The fraction of GPU memory to be used for the model "
                "executor, which can range from 0 to 1. For example, a value of "
                "0.5 would imply 50%% GPU memory utilization. If unspecified, "
                "will use the default value of 0.9. This is a per-instance "
                "limit, and only applies to the current vLLM instance."
                "It does not matter if you have another vLLM instance running "
                "on the same GPU. For example, if you have two vLLM instances "
                "running on the same GPU, you can set the GPU memory utilization "
                "to 0.5 for each instance."
            ),
        },
    )
    max_num_batched_tokens: Optional[int] = field(
        default=None,
        metadata={
            "help": _("Maximum number of batched tokens per iteration."),
        },
    )
    max_num_seqs: Optional[int] = field(
        default=None,
        metadata={
            "help": _("Maximum number of sequences per iteration."),
        },
    )
    max_logprobs: int = field(
        default=20,
        metadata={
            "help": _(
                "Max number of log probs to return logprobs is specified in"
                " SamplingParams."
            ),
        },
    )
    revision: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The specific model version to use. It can be a branch "
                "name, a tag name, or a commit id. If unspecified, will use "
                "the default version."
            ),
        },
    )
    code_revision: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The specific revision to use for the model code on "
                "Hugging Face Hub. It can be a branch name, a tag name, or a "
                "commit id. If unspecified, will use the default version."
            ),
        },
    )
    tokenizer_revision: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "Revision of the huggingface tokenizer to use. "
                "It can be a branch name, a tag name, or a commit id. "
                "If unspecified, will use the default version."
            ),
        },
    )
    tokenizer_mode: str = field(
        default="auto",
        metadata={
            "help": _(
                'The tokenizer mode.\n\n* "auto" will use the '
                'fast tokenizer if available.\n* "slow" will '
                "always use the slow tokenizer. \n* "
                '"mistral" will always use the `mistral_common` tokenizer.'
            ),
            "valid_values": ["auto", "slow", "mistral"],
        },
    )
    quantization: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "Method used to quantize the weights. If "
                "None, we first check the `quantization_config` "
                "attribute in the model config file. If that is "
                "None, we assume the model weights are not "
                "quantized and use `dtype` to determine the data "
                "type of the weights."
            ),
            "valid_values": [
                "aqlm",
                "awq",
                "deepspeedfp",
                "tpu_int8",
                "fp8",
                "ptpc_fp8",
                "fbgemm_fp8",
                "modelopt",
                "marlin",
                "gguf",
                "gptq_marlin_24",
                "gptq_marlin",
                "awq_marlin",
                "gptq",
                "compressed-tensors",
                "bitsandbytes",
                "qqq",
                "hqq",
                "experts_int8",
                "neuron_quant",
                "ipex",
                "quark",
                "moe_wna16",
            ],
        },
    )
    max_seq_len_to_capture: int = field(
        default=8192,
        metadata={
            "help": _(
                "Maximum sequence length covered by CUDA "
                "graphs. When a sequence has context length "
                "larger than this, we fall back to eager mode. "
                "Additionally for encoder-decoder models, if the "
                "sequence length of the encoder input is larger "
                "than this, we fall back to the eager mode."
            ),
        },
    )
    worker_cls: str = field(
        default="auto",
        metadata={"help": _("The worker class to use for distributed execution.")},
    )
    extras: Optional[Dict] = field(
        default=None,
        metadata={"help": _("Extra parameters, it will be passed to the vllm engine.")},
    )


class VLLMModelAdapterWrapper(LLMModelAdapter):
    """Wrapping vllm engine"""

    def __init__(self, conv_factory: Optional[ConversationAdapterFactory] = None):
        if not conv_factory:
            from dbgpt.model.adapter.model_adapter import (
                DefaultConversationAdapterFactory,
            )

            conv_factory = DefaultConversationAdapterFactory()
        self.conv_factory = conv_factory

    def new_adapter(self, **kwargs) -> "VLLMModelAdapterWrapper":
        new_obj = super().new_adapter(**kwargs)
        new_obj.conv_factory = self.conv_factory
        return new_obj  # type: ignore

    def model_type(self) -> str:
        return ModelType.VLLM

    def model_param_class(
        self, model_type: str = None
    ) -> Type[VLLMDeployModelParameters]:
        """Get model parameters class."""
        return VLLMDeployModelParameters

    def match(
        self,
        provider: str,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> bool:
        return provider == ModelType.VLLM

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
        convert_to_compatible_format: bool = False,
    ) -> Optional[str]:
        if not tokenizer:
            raise ValueError("tokenizer is is None")
        if hasattr(tokenizer, "apply_chat_template"):
            messages = self.transform_model_messages(
                messages, convert_to_compatible_format
            )
            logger.debug(f"The messages after transform: \n{messages}")
            str_prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            return str_prompt
        return None

    def load_from_params(self, params: VLLMDeployModelParameters):
        from vllm import AsyncLLMEngine
        from vllm.engine.arg_utils import AsyncEngineArgs

        logger.info(
            f"Start vllm AsyncLLMEngine with args: {_get_dataclass_print_str(params)}"
        )

        vllm_engine_args_dict = params.to_vllm_params(AsyncEngineArgs)
        # Set the attributes from the parsed arguments.
        engine_args = AsyncEngineArgs(**vllm_engine_args_dict)
        engine = AsyncLLMEngine.from_engine_args(engine_args)
        tokenizer = engine.engine.tokenizer
        if hasattr(tokenizer, "tokenizer"):
            # vllm >= 0.2.7
            tokenizer = tokenizer.tokenizer
        return engine, tokenizer

    def support_async(self) -> bool:
        return True

    def get_async_generate_stream_function(
        self, model, deploy_model_params: LLMDeployModelParameters
    ):
        from dbgpt.model.llm.llm_out.vllm_llm import generate_stream

        return generate_stream

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> ConversationAdapter:
        return self.conv_factory.get_by_model(model_name, model_path)

    def __str__(self) -> str:
        return "{}.{}".format(self.__class__.__module__, self.__class__.__name__)


register_model_adapter(VLLMModelAdapterWrapper, supported_models=COMMON_HF_MODELS)
