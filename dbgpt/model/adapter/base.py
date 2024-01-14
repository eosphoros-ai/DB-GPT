import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.model.adapter.template import (
    ConversationAdapter,
    ConversationAdapterFactory,
    get_conv_template,
)
from dbgpt.model.base import ModelType
from dbgpt.model.parameter import (
    BaseModelParameters,
    LlamaCppModelParameters,
    ModelParameters,
    ProxyModelParameters,
)

logger = logging.getLogger(__name__)


class LLMModelAdapter(ABC):
    """New Adapter for DB-GPT LLM models"""

    model_name: Optional[str] = None
    model_path: Optional[str] = None
    conv_factory: Optional[ConversationAdapterFactory] = None
    # TODO: more flexible quantization config
    support_4bit: bool = False
    support_8bit: bool = False
    support_system_message: bool = True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model_name={self.model_name} model_path={self.model_path}>"

    def __str__(self):
        return self.__repr__()

    @abstractmethod
    def new_adapter(self, **kwargs) -> "LLMModelAdapter":
        """Create a new adapter instance

        Args:
            **kwargs: The parameters of the new adapter instance

        Returns:
            LLMModelAdapter: The new adapter instance
        """

    def use_fast_tokenizer(self) -> bool:
        """Whether use a [fast Rust-based tokenizer](https://huggingface.co/docs/tokenizers/index) if it is supported
        for a given model.
        """
        return False

    def model_type(self) -> str:
        return ModelType.HF

    def model_param_class(self, model_type: str = None) -> Type[BaseModelParameters]:
        """Get the startup parameters instance of the model

        Args:
            model_type (str, optional): The type of model. Defaults to None.

        Returns:
            Type[BaseModelParameters]: The startup parameters instance of the model
        """
        # """Get the startup parameters instance of the model"""
        model_type = model_type if model_type else self.model_type()
        if model_type == ModelType.LLAMA_CPP:
            return LlamaCppModelParameters
        elif model_type == ModelType.PROXY:
            return ProxyModelParameters
        return ModelParameters

    def match(
        self,
        model_type: str,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
    ) -> bool:
        """Whether the model adapter can load the given model

        Args:
            model_type (str): The type of model
            model_name (Optional[str], optional): The name of model. Defaults to None.
            model_path (Optional[str], optional): The path of model. Defaults to None.
        """
        return False

    def support_quantization_4bit(self) -> bool:
        """Whether the model adapter can load 4bit model

        If it is True, we will load the 4bit model with :meth:`~LLMModelAdapter.load`

        Returns:
            bool: Whether the model adapter can load 4bit model, default is False
        """
        return self.support_4bit

    def support_quantization_8bit(self) -> bool:
        """Whether the model adapter can load 8bit model

        If it is True, we will load the 8bit model with :meth:`~LLMModelAdapter.load`

        Returns:
            bool: Whether the model adapter can load 8bit model, default is False
        """
        return self.support_8bit

    def load(self, model_path: str, from_pretrained_kwargs: dict):
        """Load model and tokenizer"""
        raise NotImplementedError

    def load_from_params(self, params):
        """Load the model and tokenizer according to the given parameters"""
        raise NotImplementedError

    def support_async(self) -> bool:
        """Whether the loaded model supports asynchronous calls"""
        return False

    def get_generate_stream_function(self, model, model_path: str):
        """Get the generate stream function of the model"""
        raise NotImplementedError

    def get_async_generate_stream_function(self, model, model_path: str):
        """Get the asynchronous generate stream function of the model"""
        raise NotImplementedError

    def get_default_conv_template(
        self, model_name: str, model_path: str
    ) -> Optional[ConversationAdapter]:
        """Get the default conversation template

        Args:
            model_name (str): The name of the model.
            model_path (str): The path of the model.

        Returns:
            Optional[ConversationAdapter]: The conversation template.
        """
        raise NotImplementedError

    def get_default_message_separator(self) -> str:
        """Get the default message separator"""
        try:
            conv_template = self.get_default_conv_template(
                self.model_name, self.model_path
            )
            return conv_template.sep
        except Exception:
            return "\n"

    def get_prompt_roles(self) -> List[str]:
        """Get the roles of the prompt

        Returns:
            List[str]: The roles of the prompt
        """
        roles = [ModelMessageRoleType.HUMAN, ModelMessageRoleType.AI]
        if self.support_system_message:
            roles.append(ModelMessageRoleType.SYSTEM)
        return roles

    def transform_model_messages(
        self, messages: List[ModelMessage], convert_to_compatible_format: bool = False
    ) -> List[Dict[str, str]]:
        """Transform the model messages

        Default is the OpenAI format, example:
            .. code-block:: python

                return_messages = [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi"},
                ]

        But some model may need to transform the messages to other format(e.g. There is no system message), such as:
            .. code-block:: python

                return_messages = [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi"},
                ]
        Args:
            messages (List[ModelMessage]): The model messages
            convert_to_compatible_format (bool, optional): Whether to convert to compatible format. Defaults to False.

        Returns:
            List[Dict[str, str]]: The transformed model messages
        """
        logger.info(f"support_system_message: {self.support_system_message}")
        if not self.support_system_message and convert_to_compatible_format:
            # We will not do any transform in the future
            return self._transform_to_no_system_messages(messages)
        else:
            return ModelMessage.to_common_messages(
                messages, convert_to_compatible_format=convert_to_compatible_format
            )

    def _transform_to_no_system_messages(
        self, messages: List[ModelMessage]
    ) -> List[Dict[str, str]]:
        """Transform the model messages to no system messages

        Some opensource chat model no system messages, so wo should transform the messages to no system messages.

        Merge the system messages to the last user message, example:
            .. code-block:: python

                return_messages = [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi"},
                ]
            =>
                return_messages = [
                    {"role": "user", "content": "You are a helpful assistant\nHello"},
                    {"role": "assistant", "content": "Hi"}
                ]

        Args:
            messages (List[ModelMessage]): The model messages

        Returns:
            List[Dict[str, str]]: The transformed model messages
        """
        openai_messages = ModelMessage.to_common_messages(messages)
        system_messages = []
        return_messages = []
        for message in openai_messages:
            if message["role"] == "system":
                system_messages.append(message["content"])
            else:
                return_messages.append(message)
        if len(system_messages) > 1:
            # Too much system messages should be a warning
            logger.warning("Your system messages have more than one message")
        if system_messages:
            sep = self.get_default_message_separator()
            str_system_messages = ",".join(system_messages)
            # Update last user message
            return_messages[-1]["content"] = (
                str_system_messages + sep + return_messages[-1]["content"]
            )
        return return_messages

    def get_str_prompt(
        self,
        params: Dict,
        messages: List[ModelMessage],
        tokenizer: Any,
        prompt_template: str = None,
        convert_to_compatible_format: bool = False,
    ) -> Optional[str]:
        """Get the string prompt from the given parameters and messages

        If the value of return is not None, we will skip :meth:`~LLMModelAdapter.get_prompt_with_template` and use the value of return.

        Args:
            params (Dict): The parameters
            messages (List[ModelMessage]): The model messages
            tokenizer (Any): The tokenizer of model, in huggingface chat model, we can create the prompt by tokenizer
            prompt_template (str, optional): The prompt template. Defaults to None.
            convert_to_compatible_format (bool, optional): Whether to convert to compatible format. Defaults to False.

        Returns:
            Optional[str]: The string prompt
        """
        return None

    def get_prompt_with_template(
        self,
        params: Dict,
        messages: List[ModelMessage],
        model_name: str,
        model_path: str,
        model_context: Dict,
        prompt_template: str = None,
    ):
        convert_to_compatible_format = params.get("convert_to_compatible_format")
        conv: ConversationAdapter = self.get_default_conv_template(
            model_name, model_path
        )

        if prompt_template:
            logger.info(f"Use prompt template {prompt_template} from config")
            conv = get_conv_template(prompt_template)
        if not conv or not messages:
            # Nothing to do
            logger.info(
                f"No conv from model_path {model_path} or no messages in params, {self}"
            )
            return None, None, None

        conv = conv.copy()
        if convert_to_compatible_format:
            # In old version, we will convert the messages to compatible format
            conv = self._set_conv_converted_messages(conv, messages)
        else:
            # In new version, we will use the messages directly
            conv = self._set_conv_messages(conv, messages)

        # Add a blank message for the assistant.
        conv.append_message(conv.roles[1], None)
        new_prompt = conv.get_prompt()
        return new_prompt, conv.stop_str, conv.stop_token_ids

    def _set_conv_messages(
        self, conv: ConversationAdapter, messages: List[ModelMessage]
    ) -> ConversationAdapter:
        """Set the messages to the conversation template

        Args:
            conv (ConversationAdapter): The conversation template
            messages (List[ModelMessage]): The model messages

        Returns:
            ConversationAdapter: The conversation template with messages
        """
        system_messages = []
        for message in messages:
            if isinstance(message, ModelMessage):
                role = message.role
                content = message.content
            elif isinstance(message, dict):
                role = message["role"]
                content = message["content"]
            else:
                raise ValueError(f"Invalid message type: {message}")

            if role == ModelMessageRoleType.SYSTEM:
                system_messages.append(content)
            elif role == ModelMessageRoleType.HUMAN:
                conv.append_message(conv.roles[0], content)
            elif role == ModelMessageRoleType.AI:
                conv.append_message(conv.roles[1], content)
            else:
                raise ValueError(f"Unknown role: {role}")
        if len(system_messages) > 1:
            raise ValueError(
                f"Your system messages have more than one message: {system_messages}"
            )
        if system_messages:
            conv.set_system_message(system_messages[0])
        return conv

    def _set_conv_converted_messages(
        self, conv: ConversationAdapter, messages: List[ModelMessage]
    ) -> ConversationAdapter:
        """Set the messages to the conversation template

        In the old version, we will convert the messages to compatible format.
        This method will be deprecated in the future.

        Args:
            conv (ConversationAdapter): The conversation template
            messages (List[ModelMessage]): The model messages

        Returns:
            ConversationAdapter: The conversation template with messages
        """
        system_messages = []
        user_messages = []
        ai_messages = []

        for message in messages:
            if isinstance(message, ModelMessage):
                role = message.role
                content = message.content
            elif isinstance(message, dict):
                role = message["role"]
                content = message["content"]
            else:
                raise ValueError(f"Invalid message type: {message}")

            if role == ModelMessageRoleType.SYSTEM:
                # Support for multiple system messages
                system_messages.append(content)
            elif role == ModelMessageRoleType.HUMAN:
                user_messages.append(content)
            elif role == ModelMessageRoleType.AI:
                ai_messages.append(content)
            else:
                raise ValueError(f"Unknown role: {role}")

        can_use_systems: [] = []
        if system_messages:
            if len(system_messages) > 1:
                # Compatible with dbgpt complex scenarios, the last system will protect more complete information
                # entered by the current user
                user_messages[-1] = system_messages[-1]
                can_use_systems = system_messages[:-1]
            else:
                can_use_systems = system_messages

        for i in range(len(user_messages)):
            conv.append_message(conv.roles[0], user_messages[i])
            if i < len(ai_messages):
                conv.append_message(conv.roles[1], ai_messages[i])

        # TODO join all system messages may not be a good idea
        conv.set_system_message("".join(can_use_systems))
        return conv

    def apply_conv_template(self) -> bool:
        return self.model_type() != ModelType.PROXY

    def model_adaptation(
        self,
        params: Dict,
        model_name: str,
        model_path: str,
        tokenizer: Any,
        prompt_template: str = None,
    ) -> Tuple[Dict, Dict]:
        """Params adaptation"""
        messages = params.get("messages")
        convert_to_compatible_format = params.get("convert_to_compatible_format")
        message_version = params.get("version", "v2").lower()
        logger.info(f"Message version is {message_version}")
        if convert_to_compatible_format is None:
            # Support convert messages to compatible format when message version is v1
            convert_to_compatible_format = message_version == "v1"
        # Save to params
        params["convert_to_compatible_format"] = convert_to_compatible_format

        # Some model context to dbgpt server
        model_context = {
            "prompt_echo_len_char": -1,
            "has_format_prompt": False,
            "echo": params.get("echo", True),
        }
        if messages:
            # Dict message to ModelMessage
            messages = [
                m if isinstance(m, ModelMessage) else ModelMessage(**m)
                for m in messages
            ]
            params["messages"] = messages
        params["string_prompt"] = ModelMessage.messages_to_string(messages)

        if not self.apply_conv_template():
            # No need to apply conversation template, now for proxy LLM
            return params, model_context

        new_prompt = self.get_str_prompt(
            params, messages, tokenizer, prompt_template, convert_to_compatible_format
        )
        conv_stop_str, conv_stop_token_ids = None, None
        if not new_prompt:
            (
                new_prompt,
                conv_stop_str,
                conv_stop_token_ids,
            ) = self.get_prompt_with_template(
                params, messages, model_name, model_path, model_context, prompt_template
            )
            if not new_prompt:
                return params, model_context

        # Overwrite the original prompt
        # TODO remote bos token and eos token from tokenizer_config.json of model
        prompt_echo_len_char = len(new_prompt.replace("</s>", "").replace("<s>", ""))
        model_context["prompt_echo_len_char"] = prompt_echo_len_char
        model_context["has_format_prompt"] = True
        params["prompt"] = new_prompt

        custom_stop = params.get("stop")
        custom_stop_token_ids = params.get("stop_token_ids")

        # Prefer the value passed in from the input parameter
        params["stop"] = custom_stop or conv_stop_str
        params["stop_token_ids"] = custom_stop_token_ids or conv_stop_token_ids

        return params, model_context


class AdapterEntry:
    """The entry of model adapter"""

    def __init__(
        self,
        model_adapter: LLMModelAdapter,
        match_funcs: List[Callable[[str, str, str], bool]] = None,
    ):
        self.model_adapter = model_adapter
        self.match_funcs = match_funcs or []


model_adapters: List[AdapterEntry] = []


def register_model_adapter(
    model_adapter_cls: Type[LLMModelAdapter],
    match_funcs: List[Callable[[str, str, str], bool]] = None,
) -> None:
    """Register a model adapter.

    Args:
        model_adapter_cls (Type[LLMModelAdapter]): The model adapter class.
        match_funcs (List[Callable[[str, str, str], bool]], optional): The match functions. Defaults to None.
    """
    model_adapters.append(AdapterEntry(model_adapter_cls(), match_funcs))


def get_model_adapter(
    model_type: str,
    model_name: str,
    model_path: str,
    conv_factory: Optional[ConversationAdapterFactory] = None,
) -> Optional[LLMModelAdapter]:
    """Get a model adapter.

    Args:
        model_type (str): The type of the model.
        model_name (str): The name of the model.
        model_path (str): The path of the model.
        conv_factory (Optional[ConversationAdapterFactory], optional): The conversation factory. Defaults to None.
    Returns:
        Optional[LLMModelAdapter]: The model adapter.
    """
    adapter = None
    # First find adapter by model_name
    for adapter_entry in model_adapters:
        if adapter_entry.model_adapter.match(model_type, model_name, None):
            adapter = adapter_entry.model_adapter
            break
    for adapter_entry in model_adapters:
        if adapter_entry.model_adapter.match(model_type, None, model_path):
            adapter = adapter_entry.model_adapter
            break
    if adapter:
        new_adapter = adapter.new_adapter()
        new_adapter.model_name = model_name
        new_adapter.model_path = model_path
        if conv_factory:
            new_adapter.conv_factory = conv_factory
        return new_adapter
    return None
