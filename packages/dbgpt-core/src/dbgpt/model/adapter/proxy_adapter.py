import logging
from abc import abstractmethod
from typing import Optional, Type

from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.adapter.base import LLMModelAdapter
from dbgpt.model.base import ModelType
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.proxy.llms.proxy_model import ProxyModel

logger = logging.getLogger(__name__)


class ProxyLLMModelAdapter(LLMModelAdapter):
    def model_type(self) -> str:
        return ModelType.PROXY

    def match(
        self,
        provider: str,
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
        self, params: LLMDeployModelParameters
    ) -> Optional[Type[ProxyLLMClient]]:
        """Get dynamic llm client class

        Parse the llm_client_class from params and return the class

        Args:
            params (LLMDeployModelParameters): proxy model parameters

        Returns:
            Optional[Type[ProxyLLMClient]]: llm client class
        """

        if hasattr(params, "llm_client_class") and params.llm_client_class:
            from dbgpt.util.module_utils import import_from_checked_string

            worker_cls: Type[ProxyLLMClient] = import_from_checked_string(
                params.llm_client_class, ProxyLLMClient
            )
            return worker_cls
        return None

    def get_llm_client_class(
        self, params: LLMDeployModelParameters
    ) -> Type[ProxyLLMClient]:
        """Get llm client class"""
        dynamic_llm_client_class = self.dynamic_llm_client_class(params)
        if dynamic_llm_client_class:
            return dynamic_llm_client_class
        raise NotImplementedError()

    def load_from_params(self, params: LLMDeployModelParameters):
        dynamic_llm_client_class = self.dynamic_llm_client_class(params)
        if not dynamic_llm_client_class:
            dynamic_llm_client_class = self.get_llm_client_class(params)
        logger.info(
            f"Load model from params: {params}llm client class: "
            f"{dynamic_llm_client_class}"
        )
        proxy_llm_client = dynamic_llm_client_class.new_client(params)
        model = ProxyModel(params, proxy_llm_client)
        return model, model
