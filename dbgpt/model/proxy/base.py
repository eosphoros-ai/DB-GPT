from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from concurrent.futures import Executor, ThreadPoolExecutor
from functools import cache
from typing import TYPE_CHECKING, AsyncIterator, Iterator, List, Optional

from dbgpt.core import (
    LLMClient,
    MessageConverter,
    ModelMetadata,
    ModelOutput,
    ModelRequest,
)
from dbgpt.model.parameter import ProxyModelParameters
from dbgpt.util.executor_utils import blocking_func_to_async

if TYPE_CHECKING:
    from tiktoken import Encoding

logger = logging.getLogger(__name__)


class ProxyTokenizer(ABC):
    @abstractmethod
    def count_token(self, model_name: str, prompts: List[str]) -> List[int]:
        """Count token of given prompts.
        Args:
            model_name (str): model name
            prompts (List[str]): prompts to count token

        Returns:
            List[int]: token count, -1 if failed
        """


class TiktokenProxyTokenizer(ProxyTokenizer):
    def __init__(self):
        self._cache = {}

    def count_token(self, model_name: str, prompts: List[str]) -> List[int]:
        encoding_model = self._get_or_create_encoding_model(model_name)
        if not encoding_model:
            return [-1] * len(prompts)
        return [
            len(encoding_model.encode(prompt, disallowed_special=()))
            for prompt in prompts
        ]

    def _get_or_create_encoding_model(self, model_name: str) -> Optional[Encoding]:
        if model_name in self._cache:
            return self._cache[model_name]
        encoding_model = None
        try:
            import tiktoken

            logger.info(
                "tiktoken installed, using it to count tokens, tiktoken will download tokenizer from network, "
                "also you can download it and put it in the directory of environment variable TIKTOKEN_CACHE_DIR"
            )
        except ImportError:
            self._support_encoding = False
            logger.warn("tiktoken not installed, cannot count tokens")
            return None
        try:
            if not model_name:
                model_name = "gpt-3.5-turbo"
            encoding_model = tiktoken.model.encoding_for_model(model_name)
        except KeyError:
            logger.warning(
                f"{model_name}'s tokenizer not found, using cl100k_base encoding."
            )
        if encoding_model:
            self._cache[model_name] = encoding_model
        return encoding_model


class ProxyLLMClient(LLMClient):
    """Proxy LLM client base class"""

    executor: Executor
    model_names: List[str]

    def __init__(
        self,
        model_names: List[str],
        context_length: int = 4096,
        executor: Optional[Executor] = None,
        proxy_tokenizer: Optional[ProxyTokenizer] = None,
    ):
        self.model_names = model_names
        self.context_length = context_length
        self.executor = executor or ThreadPoolExecutor()
        self.proxy_tokenizer = proxy_tokenizer or TiktokenProxyTokenizer()

    @classmethod
    @abstractmethod
    def new_client(
        cls,
        model_params: ProxyModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "ProxyLLMClient":
        """Create a new client instance from model parameters.

        Args:
            model_params (ProxyModelParameters): model parameters
            default_executor (Executor): default executor, If your model is blocking,
                you should pass a ThreadPoolExecutor.
        """

    async def generate(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> ModelOutput:
        """Generate model output from model request.

        We strongly recommend you to implement this method instead of sync_generate for high performance.

        Args:
            request (ModelRequest): model request
            message_converter (Optional[MessageConverter], optional): message converter. Defaults to None.

        Returns:
            ModelOutput: model output
        """
        return await blocking_func_to_async(
            self.executor, self.sync_generate, request, message_converter
        )

    def sync_generate(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> ModelOutput:
        """Generate model output from model request.

        Args:
            request (ModelRequest): model request
            message_converter (Optional[MessageConverter], optional): message converter. Defaults to None.

        Returns:
            ModelOutput: model output
        """
        output = None
        for out in self.sync_generate_stream(request, message_converter):
            output = out
        return output

    async def generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> AsyncIterator[ModelOutput]:
        """Generate model output stream from model request.

        We strongly recommend you to implement this method instead of sync_generate_stream for high performance.

        Args:
            request (ModelRequest): model request
            message_converter (Optional[MessageConverter], optional): message converter. Defaults to None.

        Returns:
            AsyncIterator[ModelOutput]: model output stream
        """
        from starlette.concurrency import iterate_in_threadpool

        async for output in iterate_in_threadpool(
            self.sync_generate_stream(request, message_converter)
        ):
            yield output

    def sync_generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> Iterator[ModelOutput]:
        """Generate model output stream from model request.

        Args:
            request (ModelRequest): model request
            message_converter (Optional[MessageConverter], optional): message converter. Defaults to None.

        Returns:
            Iterator[ModelOutput]: model output stream
        """

        raise NotImplementedError()

    async def models(self) -> List[ModelMetadata]:
        """Get model metadata list

        Returns:
            List[ModelMetadata]: model metadata list
        """
        return self._models()

    @property
    def default_model(self) -> str:
        """Get default model name

        Returns:
            str: default model name
        """
        return self.model_names[0]

    @cache
    def _models(self) -> List[ModelMetadata]:
        results = []
        for model in self.model_names:
            results.append(
                ModelMetadata(model=model, context_length=self.context_length)
            )
        return results

    def local_covert_message(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> ModelRequest:
        """Convert message locally

        Args:
            request (ModelRequest): model request
            message_converter (Optional[MessageConverter], optional): message converter. Defaults to None.

        Returns:
            ModelRequest: converted model request
        """
        if not message_converter:
            return request
        metadata = self._models[0].ext_metadata
        new_request = request.copy()
        new_messages = message_converter.convert(request.messages, metadata)
        new_request.messages = new_messages
        return new_request

    async def count_token(self, model: str, prompt: str) -> int:
        """Count token of given prompt

        Args:
            model (str): model name
            prompt (str): prompt to count token

        Returns:
            int: token count, -1 if failed
        """
        counts = await blocking_func_to_async(
            self.executor, self.proxy_tokenizer.count_token, model, [prompt]
        )
        return counts[0]
