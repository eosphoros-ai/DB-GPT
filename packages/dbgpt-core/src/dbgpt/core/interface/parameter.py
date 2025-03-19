from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from dbgpt.configs.model_config import get_device
from dbgpt.util.configure import RegisterParameters
from dbgpt.util.i18n_utils import _
from dbgpt.util.parameter_utils import BaseParameters
from dbgpt.util.tracer import TracerParameters
from dbgpt.util.utils import LoggingParameters

if TYPE_CHECKING:
    from dbgpt.model.parameter import WorkerType


@dataclass
class BaseDeployModelParameters(BaseParameters):
    """Base deploy model parameters."""

    __type_field__ = "provider"

    name: str = field(
        metadata={
            "help": _("The name of the model."),
            "order": -1000,
        },
    )
    provider: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The provider of the model. If model is deployed in local, this is the "
                "inference type. If model is deployed in third-party service, this is "
                "platform name('proxy/<platform>')"
            ),
            "order": -900,
            "tags": "fixed",
            "valid_values": [
                "huggingface",
                "llama.cpp",
                "llama_cpp_server",
                "proxy/*",
                "vllm",
            ],
        },
    )
    verbose: Optional[bool] = field(
        default=False, metadata={"help": _("Show verbose output.")}
    )
    concurrency: Optional[int] = field(
        default=5, metadata={"help": _("Model concurrency limit")}
    )

    @property
    def real_provider_model_name(self) -> str:
        """Get the real provider model name."""
        return self.name

    @property
    def real_model_path(self) -> Optional[str]:
        """Get the real model path.

        If deploy model is not local, return None.
        """
        return None

    @property
    def real_device(self) -> Optional[str]:
        """Get the real device."""

        return get_device()


@dataclass
class LLMDeployModelParameters(BaseDeployModelParameters, RegisterParameters):
    """LLM deploy model parameters."""

    __cfg_type__ = "llm"

    backend: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The real model name to pass to the provider, default is None. If "
                "backend is None, use name as the real model name."
            ),
            "order": -700,
        },
    )
    prompt_template: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "Prompt template. If None, the prompt template is automatically "
                "determined from model. Just for local deployment."
            )
        },
    )
    context_length: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "The context length of the model. If None, it is automatically "
                "determined from model."
            )
        },
    )
    reasoning_model: Optional[bool] = field(
        default=None,
        metadata={
            "help": _(
                "Whether the model is a reasoning model. If None, it is "
                "automatically determined from model."
            )
        },
    )

    @property
    def real_provider_model_name(self) -> str:
        """Get the real provider model name."""
        return self.backend or self.name

    def _provider_to_model_type(self) -> Optional[str]:
        """Get the provider to model type."""
        if not self.provider:
            return None
        if self.provider.startswith("proxy/"):
            return "proxy"
        return self.provider

    @classmethod
    def worker_type(cls) -> "WorkerType":
        """Get the worker type."""
        from dbgpt.model.parameter import WorkerType

        return WorkerType.LLM


@dataclass
class EmbeddingDeployModelParameters(BaseDeployModelParameters, RegisterParameters):
    """Embedding deploy model parameters."""

    __cfg_type__ = "embedding"

    concurrency: Optional[int] = field(
        default=100, metadata={"help": _("Model concurrency limit")}
    )

    @classmethod
    def worker_type(cls) -> "WorkerType":
        """Get the worker type."""
        from dbgpt.model.parameter import WorkerType

        return WorkerType.TEXT2VEC


@dataclass
class RerankerDeployModelParameters(BaseDeployModelParameters, RegisterParameters):
    """Reranker deploy model parameters."""

    __cfg_type__ = "reranker"

    concurrency: Optional[int] = field(
        default=50, metadata={"help": _("Model concurrency limit")}
    )

    @classmethod
    def worker_type(cls) -> "WorkerType":
        """Get the worker type."""
        from dbgpt.model.parameter import WorkerType

        return WorkerType.RERANKER


@dataclass
class BaseHFQuantization(BaseParameters, RegisterParameters):
    """HF quantization parameters."""

    __cfg_type__ = "llm"

    def generate_quantization_config(self) -> Optional[Dict[str, Any]]:
        """Generate quantization config."""
        return None

    @property
    def _is_load_in_8bits(self) -> bool:
        """Check if load in 8 bits."""
        return False


@dataclass
class BitsandbytesQuantization(BaseHFQuantization):
    """Bits and bytes quantization parameters."""

    __type__ = "bitsandbytes"
    __config_type__ = "base"

    load_in_8bits: bool = field(
        default=False,
        metadata={
            "help": _(
                "Whether to load the model in 8 bits(LLM.int8() algorithm), default is "
                "False."
            ),
        },
    )
    load_in_4bits: bool = field(
        default=False,
        metadata={
            "help": _("Whether to load the model in 4 bits, default is False."),
        },
    )

    @classmethod
    def _from_dict_(
        cls, data: Dict, prepare_data_func, converter
    ) -> "BitsandbytesQuantization":
        load_in_8bits = data.get("load_in_8bits", False)
        load_in_4bits = data.get("load_in_4bits", False)
        real_cls = cls
        if load_in_8bits:
            real_cls = BitsandbytesQuantization8bits
            data["type"] = BitsandbytesQuantization8bits.__type__
        if load_in_4bits:
            real_cls = BitsandbytesQuantization4bits
            data["type"] = BitsandbytesQuantization4bits.__type__
        real_data = prepare_data_func(real_cls, data)
        return real_cls(**real_data)

    def generate_quantization_config(self) -> Optional[Dict[str, Any]]:
        """Generate quantization config."""
        if not self.load_in_4bits and not self.load_in_8bits:
            return None

        from transformers import BitsAndBytesConfig

        if self.load_in_4bits and self.load_in_8bits:
            raise ValueError(
                "[BitsandbytesQuantization] 4bits and 8bits cannot be enabled at the "
                "same time"
            )
        if self.load_in_4bits:
            return {"quantization_config": BitsAndBytesConfig(load_in_4bit=True)}
        if self.load_in_8bits:
            return {"quantization_config": BitsAndBytesConfig(load_in_8bit=True)}
        return None

    @property
    def _is_load_in_8bits(self) -> bool:
        """Check if load in 8 bits."""
        return self.load_in_8bits


@dataclass
class BitsandbytesQuantization8bits(BitsandbytesQuantization):
    """Bits and bytes quantization 8 bits parameters."""

    __type__ = "bitsandbytes_8bits"

    load_in_8bits: bool = field(
        default=True,
        metadata={
            "help": _("Whether to load the model in 8 bits(LLM.int8() algorithm)."),
        },
    )

    llm_int8_enable_fp32_cpu_offload: bool = field(
        default=False,
        metadata={
            "help": _(
                "8-bit models can offload weights between the CPU and GPU to support "
                "fitting very large models into memory. The weights dispatched to the "
                "CPU are actually stored in float32, and aren’t converted to 8-bit. "
            ),
        },
    )
    llm_int8_threshold: float = field(
        default=6.0,
        metadata={
            "help": _(
                "An “outlier” is a hidden state value greater than a certain threshold,"
                " and these values are computed in fp16. While the values are usually "
                "normally distributed ([-3.5, 3.5]), this distribution can be very "
                "different for large models ([-60, 6] or [6, 60]). 8-bit quantization "
                "works well for values ~5, but beyond that, there is a significant "
                "performance penalty. A good default threshold value is 6, but a lower "
                "threshold may be needed for more unstable models "
                "(small models or finetuning)."
            ),
        },
    )
    llm_int8_skip_modules: List[str] = field(
        default_factory=list,
        metadata={
            "help": _(
                "An explicit list of the modules that we do not want to convert in "
                "8-bit. This is useful for models such as Jukebox that has several "
                "heads in different places and not necessarily at the last position. "
                "For example for `CausalLM` models, the last `lm_head` is kept in its "
                "original `dtype`"
            ),
        },
    )

    def generate_quantization_config(self) -> Optional[Dict[str, Any]]:
        """Generate quantization config."""
        if not self.load_in_8bits:
            return None
        from transformers import BitsAndBytesConfig

        return {
            "quantization_config": BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_enable_fp32_cpu_offload=self.llm_int8_enable_fp32_cpu_offload,
                llm_int8_threshold=self.llm_int8_threshold,
                llm_int8_skip_modules=self.llm_int8_skip_modules or None,
            )
        }


@dataclass
class BitsandbytesQuantization4bits(BitsandbytesQuantization):
    """Bits and bytes quantization 4 bits parameters."""

    __type__ = "bitsandbytes_4bits"
    load_in_4bits: bool = field(
        default=True,
        metadata={
            "help": _("Whether to load the model in 4 bits."),
        },
    )

    bnb_4bit_compute_dtype: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "To speedup computation, you can change the data type from float32 "
                "(the default value) to bfloat16"
            ),
            "valid_values": [
                "bfloat16",
                "float16",
                "float32",
            ],
        },
    )
    bnb_4bit_quant_type: str = field(
        default="nf4",
        metadata={
            "valid_values": ["nf4", "fp4"],
            "help": _(
                "Quantization datatypes, `fp4` (four bit float) and `nf4` "
                "(normal four bit float), only valid when load_4bit=True"
            ),
        },
    )
    bnb_4bit_use_double_quant: bool = field(
        default=True,
        metadata={
            "help": _(
                "Nested quantization is a technique that can save additional memory at "
                "no additional performance cost. This feature performs a second "
                "quantization of the already quantized weights to save an additional "
                "0.4 bits/parameter. "
            )
        },
    )

    def generate_quantization_config(self) -> Optional[Dict[str, Any]]:
        """Generate quantization config."""
        if not self.load_in_4bits:
            return None
        import torch  # noqa: F401
        from transformers import BitsAndBytesConfig

        if self.bnb_4bit_compute_dtype and self.bnb_4bit_compute_dtype not in [
            "bfloat16",
            "float16",
            "float32",
        ]:
            raise ValueError(
                f"[BitsandbytesQuantization4bits] bnb_4bit_compute_dtype must be "
                f"bfloat16, float16 or float32, but got {self.bnb_4bit_compute_dtype}"
            )
        compute_dtype = None
        if self.bnb_4bit_compute_dtype:
            compute_dtype = eval("torch.{}".format(self.bnb_4bit_compute_dtype))

        return {
            "quantization_config": BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_quant_type=self.bnb_4bit_quant_type,
                bnb_4bit_use_double_quant=self.bnb_4bit_use_double_quant,
            )
        }


@dataclass
class BaseServerParameters(BaseParameters):
    __cfg_type__ = "service"

    host: Optional[str] = field(
        default="0.0.0.0", metadata={"help": _("The host IP address to bind to.")}
    )
    port: Optional[int] = field(
        default=None, metadata={"help": _("The port number to bind to.")}
    )
    daemon: Optional[bool] = field(
        default=False, metadata={"help": _("Run the server as a daemon.")}
    )
    log: LoggingParameters = field(
        default_factory=LoggingParameters,
        metadata={
            "help": _("Logging configuration"),
        },
    )
    trace: Optional[TracerParameters] = field(
        default=None,
        metadata={
            "help": _("Tracer configuration"),
        },
    )
