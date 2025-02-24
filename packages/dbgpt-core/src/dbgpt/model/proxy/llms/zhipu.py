import logging
import os
from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import Iterator, Optional, Type, Union

from dbgpt.core import MessageConverter, ModelMetadata, ModelOutput, ModelRequest
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.proxy.base import (
    AsyncGenerateStreamFunction,
    GenerateStreamFunction,
    ProxyLLMClient,
    register_proxy_model_adapter,
)
from dbgpt.model.proxy.llms.proxy_model import ProxyModel, parse_model_request
from dbgpt.util.i18n_utils import _

from .chatgpt import OpenAICompatibleDeployModelParameters

_DEFAULT_MODEL = "glm-4-plus"

logger = logging.getLogger(__name__)


@auto_register_resource(
    label=_("Zhipu Proxy LLM"),
    category=ResourceCategory.LLM_CLIENT,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Zhipu proxy LLM configuration."),
    documentation_url="https://open.bigmodel.cn/dev/api/normal-model/glm-4#overview",
    show_in_ui=False,
)
@dataclass
class ZhipuDeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy model parameters for Zhipu."""

    provider: str = "proxy/zhipu"

    api_base: Optional[str] = field(
        default="${env:ZHIPUAI_BASE_URL:-https://open.bigmodel.cn/api/paas/v4}",
        metadata={
            "help": _("The base url of the Zhipu API."),
        },
    )

    api_key: Optional[str] = field(
        default="${env:ZHIPUAI_API_KEY}",
        metadata={
            "help": _("The API key of the Zhipu API."),
            "tags": "privacy",
        },
    )


def zhipu_generate_stream(
    model: ProxyModel, tokenizer, params, device, context_len=2048
):
    """Zhipu ai, see: https://open.bigmodel.cn/dev/api#overview"""
    model_params = model.get_params()
    print(f"Model: {model}, model_params: {model_params}")

    # TODO: Support convert_to_compatible_format config, zhipu not support system
    #  message
    # convert_to_compatible_format = params.get("convert_to_compatible_format", False)
    # history, systems = __convert_2_zhipu_messages(messages)
    client: ZhipuLLMClient = model.proxy_llm_client
    request = parse_model_request(params, client.default_model, stream=True)
    for r in client.sync_generate_stream(request):
        yield r


class ZhipuLLMClient(ProxyLLMClient):
    def __init__(
        self,
        model: Optional[str] = _DEFAULT_MODEL,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_alias: Optional[str] = _DEFAULT_MODEL,
        context_length: Optional[int] = 8192,
        executor: Optional[Executor] = None,
    ):
        try:
            from zhipuai import ZhipuAI

        except ImportError as exc:
            if (
                "No module named" in str(exc)
                or "cannot find module" in str(exc).lower()
            ):
                raise ValueError(
                    "The python package 'zhipuai' is not installed. "
                    "Please install it by running `pip install zhipuai`."
                ) from exc
            else:
                raise ValueError(
                    "Could not import python package: zhipuai "
                    "This may be due to a version that is too low. "
                    "Please upgrade the zhipuai package by running "
                    "`pip install --upgrade zhipuai`."
                ) from exc
        if not model:
            model = _DEFAULT_MODEL
        if not api_key:
            # Compatible with DB-GPT's config
            api_key = os.getenv("ZHIPU_PROXY_API_KEY")

        api_key = self._resolve_env_vars(api_key)
        api_base = self._resolve_env_vars(api_base)
        self._model = model
        self.client = ZhipuAI(api_key=api_key, base_url=api_base)

        super().__init__(
            model_names=[model, model_alias],
            context_length=context_length,
            executor=executor,
        )

    @classmethod
    def new_client(
        cls,
        model_params: ZhipuDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "ZhipuLLMClient":
        return cls(
            model=model_params.real_provider_model_name,
            api_key=model_params.api_key,
            api_base=model_params.api_base,
            model_alias=model_params.real_provider_model_name,
            context_length=model_params.context_length,
            executor=default_executor,
        )

    @classmethod
    def param_class(cls) -> Type[LLMDeployModelParameters]:
        return ZhipuDeployModelParameters

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        return zhipu_generate_stream

    @property
    def default_model(self) -> str:
        return self._model

    def sync_generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> Iterator[ModelOutput]:
        request = self.local_covert_message(request, message_converter)

        messages = request.to_common_messages(support_system_role=False)

        model = request.model or self._model
        try:
            logger.debug(
                f"Send request to zhipu ai, model: {model}, request: {request}"
            )
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_new_tokens,
                top_p=request.top_p,
                stream=True,
            )
            partial_text = ""
            for chunk in response:
                if not chunk.choices or not chunk.choices[0].delta:
                    continue
                delta_content = chunk.choices[0].delta.content
                finish_reason = chunk.choices[0].finish_reason
                partial_text += delta_content
                if logger.isEnabledFor(logging.DEBUG):
                    print(delta_content, end="")
                yield ModelOutput(
                    text=partial_text, error_code=0, finish_reason=finish_reason
                )
            if not partial_text:
                yield ModelOutput(text="**LLMServer Generate Empty.**", error_code=1)

        except Exception as e:
            yield ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )


register_proxy_model_adapter(
    ZhipuLLMClient,
    supported_models=[
        ModelMetadata(
            model=["glm-4-plus", "glm-4-air", "glm-4-air-0111"],
            context_length=128 * 1024,
            max_output_length=4 * 1024,
            description="GLM-4 by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-4-long"],
            context_length=1000 * 1024,
            max_output_length=4 * 1024,
            description="Long context GLM-4 by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-4-flash", "glm-4-flashx"],
            context_length=128 * 1024,
            max_output_length=4 * 1024,
            description="Flash version of GLM-4 by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-4-airx"],
            context_length=8 * 1024,
            max_output_length=4 * 1024,
            description="Quick response reasoning model by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
        ModelMetadata(
            model=["glm-zero-preview"],
            context_length=16 * 1024,
            max_output_length=12 * 1024,
            description="Reasoning model by Zhipu AI",
            link="https://bigmodel.cn/dev/howuse/model",
            function_calling=True,
        ),
    ],
)
