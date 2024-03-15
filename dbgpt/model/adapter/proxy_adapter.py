import logging
from abc import abstractmethod
from typing import Optional, Type

from dbgpt.model.adapter.base import LLMModelAdapter, register_model_adapter
from dbgpt.model.base import ModelType
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

logger = logging.getLogger(__name__)


class ProxyLLMModelAdapter(LLMModelAdapter):
    def new_adapter(self, **kwargs) -> "LLMModelAdapter":
        return self.__class__()

    def model_type(self) -> str:
        return ModelType.PROXY

    def match(
        self,
        model_type: str,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> bool:
        model_name = model_name.lower() if model_name else None
        model_path = model_path.lower() if model_path else None
        return self.do_match(model_name) or self.do_match(model_path)

    @abstractmethod
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        raise NotImplementedError()

    def dynamic_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Optional[Type[ProxyLLMClient]]:
        """Get dynamic llm client class

        Parse the llm_client_class from params and return the class

        Args:
            params (ProxyModelParameters): proxy model parameters

        Returns:
            Optional[Type[ProxyLLMClient]]: llm client class
        """

        if params.llm_client_class:
            from dbgpt.util.module_utils import import_from_checked_string

            worker_cls: Type[ProxyLLMClient] = import_from_checked_string(
                params.llm_client_class, ProxyLLMClient
            )
            return worker_cls
        return None

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        """Get llm client class"""
        dynamic_llm_client_class = self.dynamic_llm_client_class(params)
        if dynamic_llm_client_class:
            return dynamic_llm_client_class
        raise NotImplementedError()

    def load_from_params(self, params: ProxyModelParameters):
        dynamic_llm_client_class = self.dynamic_llm_client_class(params)
        if not dynamic_llm_client_class:
            dynamic_llm_client_class = self.get_llm_client_class(params)
        logger.info(
            f"Load model from params: {params}, llm client class: {dynamic_llm_client_class}"
        )
        proxy_llm_client = dynamic_llm_client_class.new_client(params)
        model = ProxyModel(params, proxy_llm_client)
        return model, model


class OpenAIProxyLLMModelAdapter(ProxyLLMModelAdapter):
    def support_async(self) -> bool:
        return True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path in ["chatgpt_proxyllm", "proxyllm"]

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        """Get llm client class"""
        from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient

        return OpenAILLMClient

    def get_async_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.proxy.llms.chatgpt import chatgpt_generate_stream

        return chatgpt_generate_stream


class TongyiProxyLLMModelAdapter(ProxyLLMModelAdapter):
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path == "tongyi_proxyllm"

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        from dbgpt.model.proxy.llms.tongyi import TongyiLLMClient

        return TongyiLLMClient

    def get_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.proxy.llms.tongyi import tongyi_generate_stream

        return tongyi_generate_stream


class ZhipuProxyLLMModelAdapter(ProxyLLMModelAdapter):
    support_system_message = False

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path == "zhipu_proxyllm"

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        from dbgpt.model.proxy.llms.zhipu import ZhipuLLMClient

        return ZhipuLLMClient

    def get_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.proxy.llms.zhipu import zhipu_generate_stream

        return zhipu_generate_stream


class WenxinProxyLLMModelAdapter(ProxyLLMModelAdapter):
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path == "wenxin_proxyllm"

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        from dbgpt.model.proxy.llms.wenxin import WenxinLLMClient

        return WenxinLLMClient

    def get_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.proxy.llms.wenxin import wenxin_generate_stream

        return wenxin_generate_stream


class GeminiProxyLLMModelAdapter(ProxyLLMModelAdapter):
    support_system_message = False

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path == "gemini_proxyllm"

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        from dbgpt.model.proxy.llms.gemini import GeminiLLMClient

        return GeminiLLMClient

    def get_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.proxy.llms.gemini import gemini_generate_stream

        return gemini_generate_stream


class SparkProxyLLMModelAdapter(ProxyLLMModelAdapter):
    support_system_message = False

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path == "spark_proxyllm"

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        from dbgpt.model.proxy.llms.spark import SparkLLMClient

        return SparkLLMClient

    def get_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.proxy.llms.spark import spark_generate_stream

        return spark_generate_stream


class BardProxyLLMModelAdapter(ProxyLLMModelAdapter):
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path == "bard_proxyllm"

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        """Get llm client class"""
        # TODO: Bard proxy LLM not support ProxyLLMClient now, we just return OpenAILLMClient
        from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient

        return OpenAILLMClient

    def get_async_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.proxy.llms.bard import bard_generate_stream

        return bard_generate_stream


class BaichuanProxyLLMModelAdapter(ProxyLLMModelAdapter):
    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path == "bc_proxyllm"

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        """Get llm client class"""
        # TODO: Baichuan proxy LLM not support ProxyLLMClient now, we just return OpenAILLMClient
        from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient

        return OpenAILLMClient

    def get_async_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.proxy.llms.baichuan import baichuan_generate_stream

        return baichuan_generate_stream


class YiProxyLLMModelAdapter(ProxyLLMModelAdapter):
    """Yi proxy LLM model adapter.

    See Also: `Yi Documentation <https://platform.lingyiwanwu.com/docs/>`_
    """

    def support_async(self) -> bool:
        return True

    def do_match(self, lower_model_name_or_path: Optional[str] = None):
        return lower_model_name_or_path in ["yi_proxyllm"]

    def get_llm_client_class(
        self, params: ProxyModelParameters
    ) -> Type[ProxyLLMClient]:
        """Get llm client class"""
        from dbgpt.model.proxy.llms.yi import YiLLMClient

        return YiLLMClient

    def get_async_generate_stream_function(self, model, model_path: str):
        from dbgpt.model.proxy.llms.yi import yi_generate_stream

        return yi_generate_stream


register_model_adapter(OpenAIProxyLLMModelAdapter)
register_model_adapter(TongyiProxyLLMModelAdapter)
register_model_adapter(ZhipuProxyLLMModelAdapter)
register_model_adapter(WenxinProxyLLMModelAdapter)
register_model_adapter(GeminiProxyLLMModelAdapter)
register_model_adapter(SparkProxyLLMModelAdapter)
register_model_adapter(BardProxyLLMModelAdapter)
register_model_adapter(BaichuanProxyLLMModelAdapter)
register_model_adapter(YiProxyLLMModelAdapter)
