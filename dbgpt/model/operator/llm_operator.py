import logging
from abc import ABC
from typing import Optional

from dbgpt.component import ComponentType
from dbgpt.core import LLMClient
from dbgpt.core.awel import BaseOperator
from dbgpt.core.operator import BaseLLM, BaseLLMOperator, BaseStreamingLLMOperator
from dbgpt.model.cluster import WorkerManagerFactory

logger = logging.getLogger(__name__)


class MixinLLMOperator(BaseLLM, BaseOperator, ABC):
    """Mixin class for LLM operator.

    This class extends BaseOperator by adding LLM capabilities.
    """

    def __init__(self, default_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(default_client)
        self._default_llm_client = default_client

    @property
    def llm_client(self) -> LLMClient:
        if not self._llm_client:
            worker_manager_factory: WorkerManagerFactory = (
                self.system_app.get_component(
                    ComponentType.WORKER_MANAGER_FACTORY,
                    WorkerManagerFactory,
                    default_component=None,
                )
            )
            if worker_manager_factory:
                from dbgpt.model.cluster.client import DefaultLLMClient

                self._llm_client = DefaultLLMClient(worker_manager_factory.create())
            else:
                if self._default_llm_client is None:
                    from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient

                    self._default_llm_client = OpenAILLMClient()
                logger.info(
                    f"Can't find worker manager factory, use default llm client {self._default_llm_client}."
                )
                self._llm_client = self._default_llm_client
        return self._llm_client


class LLMOperator(MixinLLMOperator, BaseLLMOperator):
    """Default LLM operator.

    Args:
        llm_client (Optional[LLMClient], optional): The LLM client. Defaults to None.
            If llm_client is None, we will try to connect to the model serving cluster deploy by DB-GPT,
            and if we can't connect to the model serving cluster, we will use the :class:`OpenAILLMClient` as the llm_client.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(llm_client)
        BaseLLMOperator.__init__(self, llm_client, **kwargs)


class StreamingLLMOperator(MixinLLMOperator, BaseStreamingLLMOperator):
    """Default streaming LLM operator.

    Args:
        llm_client (Optional[LLMClient], optional): The LLM client. Defaults to None.
            If llm_client is None, we will try to connect to the model serving cluster deploy by DB-GPT,
            and if we can't connect to the model serving cluster, we will use the :class:`OpenAILLMClient` as the llm_client.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, **kwargs):
        super().__init__(llm_client)
        BaseStreamingLLMOperator.__init__(self, llm_client, **kwargs)
