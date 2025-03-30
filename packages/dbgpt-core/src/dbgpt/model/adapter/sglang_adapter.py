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
class SGlangDeployModelParameters(LLMDeployModelParameters):
    """SGlang deploy model parameters"""

    provider: str = "sglang"

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
                "The device to run the model, 'auto' means using the default device."
            ),
        },
    )

    concurrency: Optional[int] = field(
        default=100, metadata={"help": _("Model concurrency limit")}
    )

    @property
    def real_model_path(self) -> Optional[str]:
        """Get the real model path

        If deploy model is not local, return None
        """
        return self._resolve_root_path(self.path)

    @property
    def real_device(self) -> Optional[str]:
        """Get the real device"""

        return self.device or super().real_device

    def to_sglang_params(
        self, sglang_config_cls: Optional[Type] = None
    ) -> Dict[str, Any]:
        """Convert to sglang deploy model parameters"""

        data = self.to_dict()
        model = data.get("path", None)
        if not model:
            model = data.get("name", None)
        if not model:
            raise ValueError(
                _("Model is required, please pecify the model path or name.")
            )

        copy_data = data.copy()
        real_params = {}
        extra_params = copy_data.get("extras", {})
        if sglang_config_cls and is_dataclass(sglang_config_cls):
            for fd in fields(sglang_config_cls):
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
                "buggingface."
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
                '* "half" for FP16.\n'
                '* "float16" is the same as "half".\n'
                '* "bfloat16" for a balance between precision and range.\n'
                '* "float" is shorthand for FP32 precision.\n'
                '* "float32" for FP32 precision.'
            ),
            "valid_values": ["auto", "half", "float16", "bfloat16", "float", "float32"],
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
    tensor_parallel_size: int = field(
        default=1,
        metadata={
            "help": _("Number of tensor parallel replicas."),
        },
    )
    max_num_seqs: Optional[int] = field(
        default=None,
        metadata={
            "help": _("Maximum number of sequences per iteration."),
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
            "valid_values": ["awq", "gptq", "int8"],
        },
    )
    gpu_memory_utilization: float = field(
        default=0.90,
        metadata={
            "help": _("The fraction of GPU memory to be used for the model."),
        },
    )
    extras: Optional[Dict] = field(
        default=None,
        metadata={
            "help": _("Extra parameters, it will be passed to the sglang engine.")
        },
    )


class SGLangModelAdapterWrapper(LLMModelAdapter):
    """Wrapping sglang engine"""

    def __init__(self, conv_factory: Optional[ConversationAdapterFactory] = None):
        if not conv_factory:
            from dbgpt.model.adapter.model_adapter import (
                DefaultConversationAdapterFactory,
            )

            conv_factory = DefaultConversationAdapterFactory()

        self.conv_factory = conv_factory

    def new_adapter(self, **kwargs) -> "SGLangModelAdapterWrapper":
        new_obj = super().new_adapter(**kwargs)
        new_obj.conv_factory = self.conv_factory
        return new_obj  # type: ignore

    def model_type(self) -> str:
        return ModelType.SGLANG

    def model_param_class(
        self, model_type: str = None
    ) -> Type[SGlangDeployModelParameters]:
        """Get model parameters class."""
        return SGlangDeployModelParameters

    def match(
        self,
        provider: str,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> bool:
        return provider == ModelType.SGLANG

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
        convert_to_compatible_format: bool = False,
    ) -> Optional[str]:
        if not tokenizer:
            raise ValueError("tokenizer is None")

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

    def load_from_params(self, params: SGlangDeployModelParameters):
        try:
            import sglang as sgl
            from sglang.srt.entrypoints.engine import Engine as AsyncLLMEngine
        except ImportError:
            raise ImportError("Please install sglang first: pip install sglang")

        logger.info(
            f" Start SGLang AsyncLLMEngine with args: \
                {_get_dataclass_print_str(params)}"
        )

        sglang_args_dict = params.to_sglang_params()
        model_path = sglang_args_dict.pop("model")

        # Create sglang config args
        server_config = sgl.ServerArgs(
            model=model_path,
            tensor_parallel_size=params.tensor_parallel_size,
            max_model_len=params.max_model_len or 4096,
            dtype=params.dtype if params.dtype != "auto" else None,
            quantization=params.quantization,
            gpu_memory_utilization=params.gpu_memory_utilization,
            **sglang_args_dict.get("extras", {}),
        )

        # Create sglang engine
        engine = AsyncLLMEngine(server_config)
        tokenizer = engine.tokenizer_manager.tokenizer
        return engine, tokenizer

    def support_async(self) -> bool:
        return True

    def get_async_generate_stream_function(
        self, model, deploy_model_params: LLMDeployModelParameters
    ):
        from dbgpt.model.llm.llm_out.sglang_llm import generate_stream

        return generate_stream

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> ConversationAdapter:
        return self.conv_factory.get_by_model(model_name, model_path)

    def __str__(self) -> str:
        return "{}.{}".format(self.__class__.__module__, self.__class__.__name__)


register_model_adapter(SGLangModelAdapterWrapper, supported_models=COMMON_HF_MODELS)
