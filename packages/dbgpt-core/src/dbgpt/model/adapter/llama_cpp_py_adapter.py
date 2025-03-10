import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Type

from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.adapter.base import (
    ConversationAdapter,
    LLMModelAdapter,
    register_model_adapter,
)
from dbgpt.model.adapter.model_metadata import COMMON_LLAMA_CPP_MODELS
from dbgpt.model.base import ModelType
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


@dataclass
class LlamaCppModelParameters(LLMDeployModelParameters):
    provider: str = ModelType.LLAMA_CPP
    path: Optional[str] = field(
        default=None,
        metadata={
            "order": -800,
            "help": _("The path of the model, if you want to deploy a local model."),
        },
    )
    device: Optional[str] = field(
        default=None,
        metadata={
            "order": -700,
            "help": _(
                "Device to run model. If None, the device is automatically determined"
            ),
        },
    )
    seed: Optional[int] = field(
        default=-1,
        metadata={"help": _("Random seed for llama-cpp models. -1 for random")},
    )
    n_threads: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Number of threads to use. If None, the number of threads is "
                "automatically determined"
            )
        },
    )
    n_batch: Optional[int] = field(
        default=512,
        metadata={
            "help": _(
                "Maximum number of prompt tokens to batch together when calling "
                "llama_eval"
            )
        },
    )
    n_gpu_layers: Optional[int] = field(
        default=1000000000,
        metadata={
            "help": _(
                "Number of layers to offload to the GPU, Set this to 1000000000 to "
                "offload all layers to the GPU."
            )
        },
    )
    n_gqa: Optional[int] = field(
        default=None,
        metadata={"help": _("Grouped-query attention. Must be 8 for llama-2 70b.")},
    )
    rms_norm_eps: Optional[float] = field(
        default=5e-06, metadata={"help": _("5e-6 is a good value for llama-2 models.")}
    )
    cache_capacity: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "Maximum cache capacity. Examples: 2000MiB, 2GiB. When provided "
                "without units, bytes will be assumed. "
            )
        },
    )
    prefer_cpu: Optional[bool] = field(
        default=False,
        metadata={
            "help": _(
                "If a GPU is available, it will be preferred by default, unless "
                "prefer_cpu=False is configured."
            )
        },
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


class LLamaCppModelAdapter(LLMModelAdapter):
    def model_type(self) -> str:
        return ModelType.LLAMA_CPP

    def model_param_class(
        self, model_type: str = None
    ) -> Type[LlamaCppModelParameters]:
        return LlamaCppModelParameters

    def match(
        self,
        provider: str,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> bool:
        if provider != ModelType.LLAMA_CPP:
            return False
        model_name = model_name.lower() if model_name else None
        model_path = model_path.lower() if model_path else None
        return self.do_match(model_name) or self.do_match(model_path)

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path and "gguf" in lower_model_name_or_path

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> Optional[ConversationAdapter]:
        return None

    def load_from_params(self, params: LlamaCppModelParameters):
        try:
            from dbgpt.model.llm.llama_cpp.llama_cpp import LlamaCppModel
        except ImportError as exc:
            raise ValueError(
                "Could not import python package: llama-cpp-python "
                "Please install it by `pip install llama-cpp-python`"
            ) from exc
        model_path = params.real_model_path
        model, tokenizer = LlamaCppModel.from_pretrained(model_path, params)
        return model, tokenizer

    def get_generate_stream_function(
        self, model, deploy_model_params: LLMDeployModelParameters
    ):
        return generate_stream


def generate_stream(model, tokenizer, params: Dict, device: str, context_len: int):
    # Just support LlamaCppModel
    return model.generate_streaming(params=params, context_len=context_len)


register_model_adapter(LLamaCppModelAdapter, supported_models=COMMON_LLAMA_CPP_MODELS)
