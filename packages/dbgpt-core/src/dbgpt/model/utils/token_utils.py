from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Union

if TYPE_CHECKING:
    from dbgpt.core.interface.message import BaseMessage, ModelMessage

logger = logging.getLogger(__name__)


class ProxyTokenizerWrapper:
    def __init__(self) -> None:
        self._support_encoding = True
        self._encoding_model = None

    def count_token(
        self,
        messages: Union[str, BaseMessage, ModelMessage, List[ModelMessage]],
        model_name: Optional[str] = None,
    ) -> int:
        """Count token of given messages

        Args:
            messages (Union[str, BaseMessage, ModelMessage, List[ModelMessage]]): messages to count token
            model_name (Optional[str], optional): model name. Defaults to None.

        Returns:
            int: token count, -1 if failed
        """
        if not self._support_encoding:
            logger.warning(
                "model does not support encoding model, can't count token, returning -1"
            )
            return -1
        encoding = self._get_or_create_encoding_model(model_name)
        cnt = 0
        if isinstance(messages, str):
            cnt = len(encoding.encode(messages, disallowed_special=()))
        elif isinstance(messages, BaseMessage):
            cnt = len(encoding.encode(messages.content, disallowed_special=()))
        elif isinstance(messages, ModelMessage):
            cnt = len(encoding.encode(messages.content, disallowed_special=()))
        elif isinstance(messages, list):
            for message in messages:
                cnt += len(encoding.encode(message.content, disallowed_special=()))
        else:
            logger.warning(
                "unsupported type of messages, can't count token, returning -1"
            )
            return -1
        return cnt

    def _get_or_create_encoding_model(self, model_name: Optional[str] = None):
        """Get or create encoding model for given model name
        More detail see: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        """
        if self._encoding_model:
            return self._encoding_model
        try:
            import tiktoken

            logger.info(
                "tiktoken installed, using it to count tokens, tiktoken will download tokenizer from network, "
                "also you can download it and put it in the directory of environment variable TIKTOKEN_CACHE_DIR"
            )
        except ImportError:
            self._support_encoding = False
            logger.warn("tiktoken not installed, cannot count tokens, returning -1")
            return -1
        try:
            if not model_name:
                model_name = "gpt-3.5-turbo"
            self._encoding_model = tiktoken.model.encoding_for_model(model_name)
        except KeyError:
            logger.warning(
                f"{model_name}'s tokenizer not found, using cl100k_base encoding."
            )
            self._encoding_model = tiktoken.get_encoding("cl100k_base")
        return self._encoding_model
