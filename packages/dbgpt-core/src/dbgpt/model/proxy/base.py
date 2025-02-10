import logging
from abc import ABC, abstractmethod
from concurrent.futures import Executor, ThreadPoolExecutor
from functools import cache
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    Optional,
    Type,
    Union,
)

from dbgpt.core import (
    LLMClient,
    MessageConverter,
    ModelMetadata,
    ModelOutput,
    ModelRequest,
)
from dbgpt.core.interface.parameter import LLMDeployModelParameters
from dbgpt.util.executor_utils import blocking_func_to_async

if TYPE_CHECKING:
    from tiktoken import Encoding

    from .llms.proxy_model import ProxyModel

logger = logging.getLogger(__name__)

GenerateStreamFunction = Callable[
    ["ProxyModel", Any, Dict[str, Any], str, int], AsyncGenerator[ModelOutput, None]
]
AsyncGenerateStreamFunction = Callable[
    ["ProxyModel", Any, Dict[str, Any], str, int],
    Generator[ModelOutput, None, None],
]
GenerateFunction = Callable[["ProxyModel", Any, Dict[str, Any], str, int], ModelOutput]
AsyncGenerateFunction = Callable[
    ["ProxyModel", Any, Dict[str, Any], str, int],
    ModelOutput,
]


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

    def support_async(self) -> bool:
        """Check if the tokenizer supports asynchronous counting token.

        Returns:
            bool: True if supports, False otherwise
        """
        return False

    async def count_token_async(self, model_name: str, prompts: List[str]) -> List[int]:
        """Count token of given prompts asynchronously.
        Args:
            model_name (str): model name
            prompts (List[str]): prompts to count token

        Returns:
            List[int]: token count, -1 if failed
        """
        raise NotImplementedError()


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

    def _get_or_create_encoding_model(self, model_name: str) -> Optional["Encoding"]:
        if model_name in self._cache:
            return self._cache[model_name]
        encoding_model = None
        try:
            import tiktoken

            logger.info(
                "tiktoken installed, using it to count tokens, tiktoken will download "
                "tokenizer from network, also you can download it and put it in the "
                "directory of environment variable TIKTOKEN_CACHE_DIR"
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
        self._proxy_tokenizer = proxy_tokenizer

    def __getstate__(self):
        """Customize the serialization of the object"""
        state = self.__dict__.copy()
        state.pop("executor")
        return state

    def __setstate__(self, state):
        """Customize the deserialization of the object"""
        self.__dict__.update(state)
        self.executor = ThreadPoolExecutor()

    @property
    def proxy_tokenizer(self) -> ProxyTokenizer:
        """Get proxy tokenizer

        Returns:
            ProxyTokenizer: proxy tokenizer
        """
        if not self._proxy_tokenizer:
            self._proxy_tokenizer = TiktokenProxyTokenizer()
        return self._proxy_tokenizer

    @classmethod
    def param_class(cls) -> Type[LLMDeployModelParameters]:
        """Get model parameters class.

        This method will be called by the factory method to get the model parameters
        class.

        Returns:
            Type[LLMDeployModelParameters]: model parameters class

        """
        return LLMDeployModelParameters

    @classmethod
    @abstractmethod
    def new_client(
        cls,
        model_params: LLMDeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "ProxyLLMClient":
        """Create a new client instance from model parameters.

        Args:
            model_params (LLMDeployModelParameters): model parameters
            default_executor (Executor): default executor, If your model is blocking,
                you should pass a ThreadPoolExecutor.
        """

    @classmethod
    def generate_stream_function(
        cls,
    ) -> Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
        """Get generate stream function.

        Returns:
            Optional[Union[GenerateStreamFunction, AsyncGenerateStreamFunction]]:
                generate stream function
        """
        return None

    @classmethod
    def generate_function(
        cls,
    ) -> Optional[Union[GenerateFunction, AsyncGenerateFunction]]:
        """Get generate function.

        Returns:
            Optional[Union[GenerateFunction, AsyncGenerateFunction]]:
                generate function
        """
        return None

    async def generate(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> ModelOutput:
        """Generate model output from model request.

        We strongly recommend you to implement this method instead of sync_generate for
         high performance.

        Args:
            request (ModelRequest): model request
            message_converter (Optional[MessageConverter], optional): message
                converter. Defaults to None.

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
            message_converter (Optional[MessageConverter], optional): message
                converter. Defaults to None.

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

        We strongly recommend you to implement this method instead of
        sync_generate_stream for high performance.

        Args:
            request (ModelRequest): model request
            message_converter (Optional[MessageConverter], optional): message
                converter. Defaults to None.

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
            message_converter (Optional[MessageConverter], optional): message
                converter. Defaults to None.

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
            message_converter (Optional[MessageConverter], optional): message
                converter. Defaults to None.

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
        if self.proxy_tokenizer.support_async():
            cnts = await self.proxy_tokenizer.count_token_async(model, [prompt])
            return cnts[0]
        counts = await blocking_func_to_async(
            self.executor, self.proxy_tokenizer.count_token, model, [prompt]
        )
        return counts[0]


def _is_async_function(
    func: Optional[
        Union[
            GenerateStreamFunction,
            AsyncGenerateStreamFunction,
            GenerateFunction,
            AsyncGenerateFunction,
        ]
    ],
) -> bool:
    """Check if the function is async.

    Args:
        func: The function to check

    Returns:
        bool: True if the function is async
    """
    if func is None:
        return False

    return iscoroutinefunction(func) or isasyncgenfunction(func)


def register_proxy_model_adapter(
    client_cls: Type[ProxyLLMClient],
):
    """Register proxy model adapter

    Args:
        client_cls (Type[ProxyLLMClient]): proxy model client class
    """
    from dbgpt.model.adapter.base import register_model_adapter
    from dbgpt.model.adapter.proxy_adapter import ProxyLLMModelAdapter

    generate_stream_function = client_cls.generate_stream_function()
    is_async_stream = _is_async_function(generate_stream_function)
    generate_function = client_cls.generate_function()
    is_async = _is_async_function(generate_function)
    param_cls = client_cls.param_class()
    provider = param_cls.get_type_value()

    class _DynProxyLLMModelAdapter(ProxyLLMModelAdapter):
        """Dynamic proxy LLM model adapter.

        Automatically generated model adapter for proxy models.
        """

        __provider__ = provider

        def support_async(self) -> bool:
            return is_async_stream or is_async

        def match(
            self,
            _provider: str,
            model_name: Optional[str] = None,
            model_path: Optional[str] = None,
        ) -> bool:
            return _provider == provider

        def do_match(self, lower_model_name_or_path: Optional[str] = None):
            raise NotImplementedError()

        def get_llm_client_class(
            self, params: LLMDeployModelParameters
        ) -> Type[ProxyLLMClient]:
            """Get llm client class"""
            return client_cls

        def get_generate_stream_function(self, model, model_path: str):
            """Get the generate stream function of the model"""
            if not is_async_stream and generate_stream_function is not None:
                return generate_stream_function
            raise NotImplementedError("Sync generate stream not supported")

        def get_async_generate_stream_function(self, model, model_path: str):
            if is_async_stream and generate_stream_function is not None:
                return generate_stream_function
            raise NotImplementedError("Async generate stream not supported")

        def get_generate_function(self, model, model_path: str):
            """Get the generate function of the model"""
            if not is_async and generate_function is not None:
                return generate_function
            raise NotImplementedError

        def get_async_generate_function(self, model, model_path: str):
            """Get the asynchronous generate function of the model"""
            if is_async and generate_function is not None:
                return generate_function
            raise NotImplementedError

    register_model_adapter(_DynProxyLLMModelAdapter)
