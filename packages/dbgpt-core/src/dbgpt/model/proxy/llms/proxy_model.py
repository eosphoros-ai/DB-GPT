from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Union

from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.model.proxy.base import ProxyLLMClient
from dbgpt.model.utils.llm_utils import parse_model_request  # noqa: F401
from dbgpt.model.utils.token_utils import ProxyTokenizerWrapper

if TYPE_CHECKING:
    from dbgpt.core.interface.message import BaseMessage, ModelMessage

logger = logging.getLogger(__name__)


class ProxyModel:
    def __init__(
        self,
        model_params: LLMDeployModelParameters,
        proxy_llm_client: Optional[ProxyLLMClient] = None,
    ) -> None:
        self._model_params = model_params
        self._tokenizer = ProxyTokenizerWrapper()
        self.proxy_llm_client = proxy_llm_client

    def get_params(self) -> LLMDeployModelParameters:
        return self._model_params

    def count_token(
        self,
        messages: Union[str, BaseMessage, ModelMessage, List[ModelMessage]],
        model_name: Optional[int] = None,
    ) -> int:
        """Count token of given messages

        Args:
            messages (Union[str, BaseMessage, ModelMessage, List[ModelMessage]]):
                messages to count token
            model_name (Optional[int], optional): model name. Defaults to None.

        Returns:
            int: token count, -1 if failed
        """
        return self._tokenizer.count_token(messages, model_name)
