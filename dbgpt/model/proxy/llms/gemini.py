import os
from concurrent.futures import Executor
from typing import Any, Dict, Iterator, List, Optional, Tuple

from dbgpt.core import (
    MessageConverter,
    ModelMessage,
    ModelOutput,
    ModelRequest,
    ModelRequestContext,
)
from dbgpt.core.interface.message import parse_model_messages
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

GEMINI_DEFAULT_MODEL = "gemini-pro"

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


def gemini_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")
    client: GeminiLLMClient = model.proxy_llm_client
    context = ModelRequestContext(stream=True, user_name=params.get("user_name"))
    request = ModelRequest.build_request(
        client.default_model,
        messages=params["messages"],
        temperature=params.get("temperature"),
        context=context,
        max_new_tokens=params.get("max_new_tokens"),
        stop=params.get("stop"),
    )
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
        model_alias: Optional[str] = "gemini_proxyllm",
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
        self._api_key = api_key if api_key else os.getenv("GEMINI_PROXY_API_KEY")
        self._api_base = api_base if api_base else os.getenv("GEMINI_PROXY_API_BASE")
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
        model_params: ProxyModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "GeminiLLMClient":
        return cls(
            model=model_params.proxyllm_backend,
            api_key=model_params.proxy_api_key,
            api_base=model_params.proxy_api_base,
            model_alias=model_params.model_name,
            context_length=model_params.max_context_size,
            executor=default_executor,
        )

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
            return ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )
