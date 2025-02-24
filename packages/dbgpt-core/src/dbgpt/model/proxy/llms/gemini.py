import os
from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple, Type, Union

from dbgpt.core import (
    MessageConverter,
    ModelMessage,
    ModelMetadata,
    ModelOutput,
    ModelRequest,
)
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.core.interface.message import parse_model_messages
from dbgpt.model.proxy.base import (
    AsyncGenerateStreamFunction,
    GenerateStreamFunction,
    ProxyLLMClient,
    register_proxy_model_adapter,
)
from dbgpt.model.proxy.llms.proxy_model import ProxyModel, parse_model_request
from dbgpt.util.i18n_utils import _

from .chatgpt import OpenAICompatibleDeployModelParameters

GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
]


@auto_register_resource(
    label=_("Gemini Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Google Gemini proxy LLM configuration."),
    documentation_url="https://ai.google.dev/gemini-api/docs",
    show_in_ui=False,
)
@dataclass
class GeminiDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Gemini."""

    provider: str = "proxy/gemini"

    api_base: Optional[str] = field(
        default="${env:GEMINI_PROXY_API_BASE}",
        metadata={
            "help": _("The base url of the gemini API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:GEMINI_PROXY_API_KEY}",
        metadata={
            "help": _("The API key of the gemini API."),
            "tags": "privacy",
        },
    )


def gemini_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")
    client: GeminiLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    for r in client.sync_generate_stream(request):
        yield r


def _transform_to_gemini_messages(
    messages: List[ModelMessage],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Transform messages to gemini format

    See https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/getting-started/intro_gemini_python.ipynb

    Args:
        messages (List[ModelMessage]): messages

    Returns:
        Tuple[str, List[Dict[str, Any]]]: user_prompt, gemini_hist

    Examples:
        .. code-block:: python

            messages = [
                ModelMessage(role="human", content="Hello"),
                ModelMessage(role="ai", content="Hi there!"),
                ModelMessage(role="human", content="How are you?"),
            ]
            user_prompt, gemini_hist = _transform_to_gemini_messages(messages)
            assert user_prompt == "How are you?"
            assert gemini_hist == [
                {"role": "user", "parts": {"text": "Hello"}},
                {"role": "model", "parts": {"text": "Hi there!"}},
            ]
    """
    # TODO raise error if messages has system message
    user_prompt, system_messages, history_messages = parse_model_messages(messages)
    if system_messages:
        raise ValueError("Gemini does not support system role")
    gemini_hist = []
    if history_messages:
        for user_message, model_message in history_messages:
            gemini_hist.append({"role": "user", "parts": {"text": user_message}})
            gemini_hist.append({"role": "model", "parts": {"text": model_message}})
    return user_prompt, gemini_hist


class GeminiLLMClient(ProxyLLMClient):
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_alias: Optional[str] = "gemini-2.0-flash",
        context_length: Optional[int] = 8192,
        executor: Optional[Executor] = None,
    ):
        try:
            import google.generativeai as genai

        except ImportError as exc:
            raise ValueError(
                "Could not import python package: generativeai "
                "Please install dashscope by command `pip install google-generativeai"
            ) from exc
        if not model:
            model = GEMINI_DEFAULT_MODEL
        api_key = api_key if api_key else os.getenv("GEMINI_PROXY_API_KEY")
        api_base = api_base if api_base else os.getenv("GEMINI_PROXY_API_BASE")
        self._api_key = self._resolve_env_vars(api_key)
        self._api_base = self._resolve_env_vars(api_base)
        self._model = model
        if not self._api_key:
            raise RuntimeError("api_key can't be empty")

        if self._api_base:
            from google.api_core import client_options

            client_opts = client_options.ClientOptions(api_endpoint=self._api_base)
            genai.configure(
                api_key=self._api_key, transport="rest", client_options=client_opts
            )
        else:
            genai.configure(api_key=self._api_key)
        super().__init__(
            model_names=[model, model_alias],
            context_length=context_length,
            executor=executor,
        )

    @classmethod
    def new_client(
        cls,
        model_params: GeminiDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "GeminiLLMClient":
        return cls(
            api_key=model_params.api_key,
            api_base=model_params.api_base,
            model=model_params.real_provider_model_name,
            model_alias=model_params.real_provider_model_name,
            context_length=model_params.context_length,
            executor=default_executor,
        )

    @classmethod
    def param_class(cls) -> Type[GeminiDeployModelParameters]:
        """Return the parameter class for the client."""
        return GeminiDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get the generate stream function."""
        return gemini_generate_stream

    @property
    def default_model(self) -> str:
        return self._model

    def sync_generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> Iterator[ModelOutput]:
        request = self.local_covert_message(request, message_converter)
        try:
            import google.generativeai as genai

            generation_config = {
                "temperature": request.temperature,
                "top_p": 1,
                "top_k": 1,
                "max_output_tokens": request.max_new_tokens,
            }
            model = genai.GenerativeModel(
                model_name=self._model,
                generation_config=generation_config,
                safety_settings=safety_settings,
            )
            user_prompt, gemini_hist = _transform_to_gemini_messages(request.messages)
            chat = model.start_chat(history=gemini_hist)
            response = chat.send_message(user_prompt, stream=True)
            text = ""
            for chunk in response:
                text += chunk.text
                yield ModelOutput(text=text, error_code=0)
        except Exception as e:
            yield ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )


register_proxy_model_adapter(
    GeminiLLMClient,
    supported_models=[
        ModelMetadata(
            model=["gemini-2.0-flash", "gemini-2.0-flash-lite-preview-02-05"],
            context_length=1048576,
            max_output_length=8 * 1024,
            description="Gemini-2.0 by Google",
            link="https://ai.google.dev/gemini-api/docs/models/gemini#gemini-2.0-flash",
            function_calling=True,
        ),
        ModelMetadata(
            model=[
                "gemini-1.5-flash-latest",
                "gemini-1.5-flash",
                "gemini-1.5-flash-001",
                "gemini-1.5-flash-002",
            ],
            context_length=1048576,
            max_output_length=8 * 1024,
            description="Gemini-1.5 by Google",
            link="https://ai.google.dev/gemini-api/docs/models/gemini#gemini-1.5-flash",
            function_calling=True,
        ),
    ],
)
