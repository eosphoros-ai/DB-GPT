"""llama.cpp server adapter.

See more details:
https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md

**Features:**
 * LLM inference of F16 and quantized models on GPU and CPU
 * Parallel decoding with multi-user support
 * Continuous batching

The llama.cpp server is pure C++ server, we need to use the llama-cpp-server-py-core
to interact with it.
"""

import logging
from dataclasses import dataclass, field, fields
from typing import List, Optional, Type

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


_DEFAULT_HF_REPO = "ggml-org/models"
_DEFAULT_HF_FILE = "tinyllamas/stories260K.gguf"
_DEFAULT_MODEL_ALIAS = "tinyllama-2"


@dataclass
class LlamaServerParameters(LLMDeployModelParameters):
    provider: str = ModelType.LLAMA_CPP_SERVER

    path: Optional[str] = field(
        default=None,
        metadata={
            "order": -800,
            "help": _("Local model file path"),
        },
    )
    # Model configuration
    model_hf_repo: Optional[str] = field(
        default=None,
        metadata={"help": _("Hugging Face repository for model download")},
    )

    model_hf_file: Optional[str] = field(
        default=None,
        metadata={"help": _("Model file name in the Hugging Face repository")},
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

    # Server configuration
    server_bin_path: Optional[str] = field(
        default=None, metadata={"help": _("Path to the server binary executable")}
    )

    server_host: str = field(
        default="127.0.0.1", metadata={"help": _("Host address to bind the server")}
    )

    server_port: int = field(
        default=0,
        metadata={"help": _("Port to bind the server. 0 for random available port")},
    )

    # Model parameters
    temperature: float = field(
        default=0.8, metadata={"help": _("Sampling temperature for text generation")}
    )

    seed: int = field(
        default=42, metadata={"help": _("Random seed for reproducibility")}
    )

    debug: bool = field(default=False, metadata={"help": _("Enable debug mode")})

    # Optional model sources
    model_url: Optional[str] = field(
        default=None,
        metadata={"help": _("Model download URL (env: LLAMA_ARG_MODEL_URL)")},
    )

    model_draft: Optional[str] = field(
        default=None, metadata={"help": _("Draft model file path")}
    )

    # Performance settings
    threads: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Number of threads to use during generation (default: -1) "
                "(env: LLAMA_ARG_THREADS)"
            )
        },
    )

    n_gpu_layers: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Number of layers to store in VRAM (env: LLAMA_ARG_N_GPU_LAYERS), set"
                " 1000000000 to use all layers"
            )
        },
    )

    batch_size: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Logical maximum batch size (default: 2048) (env: LLAMA_ARG_BATCH)"
            )
        },
    )

    ubatch_size: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Physical maximum batch size (default: 512) (env: LLAMA_ARG_UBATCH)"
            )
        },
    )

    # Context settings
    ctx_size: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Size of the prompt context (default: 4096, 0 = loaded from model) "
                "(env: LLAMA_ARG_CTX_SIZE)"
            )
        },
    )

    grp_attn_n: Optional[int] = field(
        default=None, metadata={"help": _("Group-attention factor (default: 1)")}
    )

    grp_attn_w: Optional[int] = field(
        default=None, metadata={"help": _("Group-attention width (default: 512)")}
    )

    # Generation settings
    n_predict: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Number of tokens to predict (default: -1, -1 = infinity, -2 = until "
                "context filled) (env: LLAMA_ARG_N_PREDICT)"
            )
        },
    )

    # Cache settings
    slot_save_path: Optional[str] = field(
        default=None,
        metadata={"help": _("Path to save slot kv cache (default: disabled)")},
    )

    n_slots: Optional[int] = field(
        default=None, metadata={"help": _("Number of slots for KV cache")}
    )

    # Feature flags
    cont_batching: bool = field(
        default=False,
        metadata={"help": _("Enable continuous batching (a.k.a dynamic batching)")},
    )

    embedding: bool = field(
        default=False,
        metadata={
            "help": _(
                "Restrict to only support embedding use case; use only with dedicated "
                "embedding models (env: LLAMA_ARG_EMBEDDINGS)"
            )
        },
    )

    reranking: bool = field(
        default=False,
        metadata={
            "help": _("Enable reranking endpoint on server (env: LLAMA_ARG_RERANKING)")
        },
    )

    metrics: bool = field(
        default=False,
        metadata={
            "help": _(
                "Enable prometheus compatible metrics endpoint "
                "(env: LLAMA_ARG_ENDPOINT_METRICS)"
            )
        },
    )

    slots: bool = field(
        default=False,
        metadata={
            "help": _(
                "Enable slots monitoring endpoint (env: LLAMA_ARG_ENDPOINT_SLOTS)"
            )
        },
    )

    # Draft settings
    draft: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Number of tokens to draft for speculative decoding (default: 16) "
                "(env: LLAMA_ARG_DRAFT_MAX)"
            )
        },
    )

    draft_max: Optional[int] = field(
        default=None, metadata={"help": _("Same as draft")}
    )

    draft_min: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Minimum number of draft tokens to use for speculative decoding "
                "(default: 5)"
            )
        },
    )

    # Authentication
    api_key: Optional[str] = field(
        default=None,
        metadata={"help": _("API key to use for authentication (env: LLAMA_API_KEY)")},
    )

    # Model adaptation
    lora_files: List[str] = field(
        default_factory=list,
        metadata={
            "help": _("Path to LoRA adapter (can be repeated to use multiple adapters)")
        },
    )

    # Additional settings
    no_context_shift: bool = field(
        default=False,
        metadata={"help": _("Disables context shift on infinite text generation")},
    )

    no_webui: Optional[bool] = field(
        default=None, metadata={"help": _("Disable web UI")}
    )
    startup_timeout: Optional[int] = field(
        default=None, metadata={"help": _("Server startup timeout in seconds")}
    )

    concurrency: Optional[int] = field(
        default=20, metadata={"help": _("Model concurrency limit")}
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

    def generate_server_config(self):
        from llama_cpp_server_py_core import ServerConfig

        curr_config = self.to_dict()
        config_dict = {}
        for fd in fields(ServerConfig):
            if fd.name in curr_config:
                config_dict[fd.name] = curr_config[fd.name]

        if (
            self.real_device
            and self.real_device == "cuda"
            and ("n_gpu_layers" not in config_dict or not config_dict["n_gpu_layers"])
        ):
            # Set n_gpu_layers to a large number to use all layers
            logger.info("Set n_gpu_layers to a large number to use all layers")
            config_dict["n_gpu_layers"] = 1000000000
        config_dict["model_alias"] = self.name
        config_dict["model_file"] = self._resolve_root_path(self.path)
        model_file = config_dict.get("model_file")
        model_url = config_dict.get("model_url")
        model_hf_repo = config_dict.get("model_hf_repo")
        if not model_file and not model_url and not model_hf_repo:
            # Default to use Hugging Face repository
            config_dict["model_hf_repo"] = _DEFAULT_HF_REPO
            config_dict["model_hf_file"] = _DEFAULT_HF_FILE
        return ServerConfig(**config_dict)


class LLamaServerModelAdapter(LLMModelAdapter):
    def match(
        self,
        provider: str,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> bool:
        return provider == ModelType.LLAMA_CPP_SERVER

    def model_type(self) -> str:
        return ModelType.LLAMA_CPP_SERVER

    def model_param_class(self, model_type: str = None) -> Type[LlamaServerParameters]:
        return LlamaServerParameters

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> Optional[ConversationAdapter]:
        return None

    def load_from_params(self, params: LlamaServerParameters):
        """Load model from parameters."""
        try:
            from llama_cpp_server_py_core import LlamaCppServer, ServerProcess
        except ImportError:
            logger.error(
                "Failed to import llama_cpp_server_py_core, please install it first by "
                "`pip install llama-cpp-server-py`"
            )
            raise

        server_config = params.generate_server_config()
        server = ServerProcess(server_config)
        server.start(params.startup_timeout or 300)
        model_server = LlamaCppServer(server, server_config)
        return model_server, model_server

    def support_generate_function(self) -> bool:
        return True

    def get_generate_stream_function(
        self, model, deploy_model_params: LLMDeployModelParameters
    ):
        from dbgpt.model.llm.llama_cpp.llama_cpp_server import generate_stream

        return generate_stream

    def get_generate_function(
        self, model, deploy_model_params: LLMDeployModelParameters
    ):
        from dbgpt.model.llm.llama_cpp.llama_cpp_server import generate

        return generate


register_model_adapter(
    LLamaServerModelAdapter, supported_models=COMMON_LLAMA_CPP_MODELS
)
