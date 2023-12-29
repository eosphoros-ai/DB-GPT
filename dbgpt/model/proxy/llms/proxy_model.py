from __future__ import annotations

from typing import Union, List, Optional, TYPE_CHECKING
import logging
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.model.utils.token_utils import ProxyTokenizerWrapper

if TYPE_CHECKING:
    from dbgpt.core.interface.message import ModelMessage, BaseMessage

logger = logging.getLogger(__name__)


class ProxyModel:
    def __init__(self, model_params: ProxyModelParameters) -> None:
        self._model_params = model_params
        self._tokenizer = ProxyTokenizerWrapper()

    def get_params(self) -> ProxyModelParameters:
        return self._model_params

    def count_token(
        self,
        messages: Union[str, BaseMessage, ModelMessage, List[ModelMessage]],
        model_name: Optional[int] = None,
    ) -> int:
        """Count token of given messages

        Args:
            messages (Union[str, BaseMessage, ModelMessage, List[ModelMessage]]): messages to count token
            model_name (Optional[int], optional): model name. Defaults to None.

        Returns:
            int: token count, -1 if failed
        """
        return self._tokenizer.count_token(messages, model_name)
