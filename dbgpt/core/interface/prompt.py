"""The prompt template interface."""

from __future__ import annotations

import dataclasses
import json
from abc import ABC, abstractmethod
from string import Formatter
from typing import Any, Callable, Dict, List, Optional, Set, Union

from dbgpt._private.pydantic import BaseModel, root_validator
from dbgpt.core.interface.message import BaseMessage, HumanMessage, SystemMessage
from dbgpt.core.interface.storage import (
    InMemoryStorage,
    QuerySpec,
    ResourceIdentifier,
    StorageInterface,
    StorageItem,
)
from dbgpt.util.formatting import formatter, no_strict_formatter


def _jinja2_formatter(template: str, **kwargs: Any) -> str:
    """Format a template using jinja2."""
    try:
        from jinja2 import Template
    except ImportError:
        raise ImportError(
            "jinja2 not installed, which is needed to use the jinja2_formatter. "
            "Please install it with `pip install jinja2`."
        )

    return Template(template).render(**kwargs)


_DEFAULT_FORMATTER_MAPPING: Dict[str, Callable] = {
    "f-string": lambda is_strict: formatter.format
    if is_strict
    else no_strict_formatter.format,
    "jinja2": lambda is_strict: _jinja2_formatter,
}


class BasePromptTemplate(BaseModel):
    """Base class for all prompt templates, returning a prompt."""

    input_variables: List[str]
    """A list of the names of the variables the prompt template expects."""


class PromptTemplate(BasePromptTemplate):
    """Prompt template."""

    template: str
    """The prompt template."""

    template_format: str = "f-string"
    """The format of the prompt template. Options are: 'f-string', 'jinja2'."""

    response_key: str = "response"

    template_is_strict: bool = True
    """strict template will check template args"""

    response_format: Optional[str] = None

    template_scene: Optional[str] = None

    template_define: Optional[str] = None
    """this template define"""

    class Config:
        """Configuration for this pydantic object."""

        arbitrary_types_allowed = True

    @property
    def _prompt_type(self) -> str:
        """Return the prompt type key."""
        return "prompt"

    def format(self, **kwargs: Any) -> str:
        """Format the prompt with the inputs."""
        if self.response_format:
            kwargs[self.response_key] = json.dumps(
                self.response_format, ensure_ascii=False, indent=4
            )
        return _DEFAULT_FORMATTER_MAPPING[self.template_format](
            self.template_is_strict
        )(self.template, **kwargs)

    @classmethod
    def from_template(
        cls, template: str, template_format: str = "f-string", **kwargs: Any
    ) -> BasePromptTemplate:
        """Create a prompt template from a template string."""
        input_variables = get_template_vars(template, template_format)
        return cls(
            template=template,
            input_variables=input_variables,
            template_format=template_format,
            **kwargs,
        )


class BaseChatPromptTemplate(BaseModel, ABC):
    """The base chat prompt template."""

    prompt: BasePromptTemplate

    @property
    def input_variables(self) -> List[str]:
        """Return a list of the names of the variables the prompt template expects."""
        return self.prompt.input_variables

    @abstractmethod
    def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
        """Format the prompt with the inputs."""

    @classmethod
    def from_template(
        cls,
        template: str,
        template_format: str = "f-string",
        response_format: Optional[str] = None,
        response_key: str = "response",
        template_is_strict: bool = True,
        **kwargs: Any,
    ) -> BaseChatPromptTemplate:
        """Create a prompt template from a template string."""
        prompt = PromptTemplate.from_template(
            template,
            template_format,
            response_format=response_format,
            response_key=response_key,
            template_is_strict=template_is_strict,
        )
        return cls(prompt=prompt, **kwargs)


class SystemPromptTemplate(BaseChatPromptTemplate):
    """The system prompt template."""

    def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
        """Format the prompt with the inputs.

        Returns:
            List[BaseMessage]: The formatted messages.
        """
        content = self.prompt.format(**kwargs)
        return [SystemMessage(content=content)]


class HumanPromptTemplate(BaseChatPromptTemplate):
    """The human prompt template."""

    def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
        """Format the prompt with the inputs.

        Returns:
            List[BaseMessage]: The formatted messages.
        """
        content = self.prompt.format(**kwargs)
        return [HumanMessage(content=content)]


class MessagesPlaceholder(BaseModel):
    """The messages placeholder template.

    Mostly used for the chat history.
    """

    variable_name: str

    def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
        """Format the prompt with the inputs.

        Just return the messages from the kwargs with the variable name.

        Returns:
            List[BaseMessage]: The messages.
        """
        messages = kwargs.get(self.variable_name, [])
        if not isinstance(messages, list):
            raise ValueError(
                f"Unsupported messages type: {type(messages)}, should be list."
            )
        for message in messages:
            if not isinstance(message, BaseMessage):
                raise ValueError(
                    f"Unsupported message type: {type(message)}, should be BaseMessage."
                )
        return messages

    @property
    def input_variables(self) -> List[str]:
        """Return a list of the names of the variables the prompt template expects.

        Returns:
            List[str]: The input variables.
        """
        return [self.variable_name]


MessageType = Union[BaseChatPromptTemplate, MessagesPlaceholder, BaseMessage]


class ChatPromptTemplate(BasePromptTemplate):
    """The chat prompt template.

    Examples:
        .. code-block:: python

            prompt_template = ChatPromptTemplate(
                messages=[
                    SystemPromptTemplate.from_template(
                        "You are a helpful AI assistant."
                    ),
                    MessagesPlaceholder(variable_name="chat_history"),
                    HumanPromptTemplate.from_template("{question}"),
                ]
            )
    """

    messages: List[MessageType]

    def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
        """Format the prompt with the inputs."""
        result_messages = []
        for message in self.messages:
            if isinstance(message, BaseMessage):
                result_messages.append(message)
            elif isinstance(message, (BaseChatPromptTemplate, MessagesPlaceholder)):
                pass_kwargs = {
                    k: v for k, v in kwargs.items() if k in message.input_variables
                }
                result_messages.extend(message.format_messages(**pass_kwargs))
            else:
                raise ValueError(f"Unsupported message type: {type(message)}")
        return result_messages

    @root_validator(pre=True)
    def base_pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-fill the messages."""
        input_variables = values.get("input_variables", {})
        messages = values.get("messages", [])
        if not input_variables:
            input_variables = set()
            for message in messages:
                if isinstance(message, (BaseChatPromptTemplate, MessagesPlaceholder)):
                    input_variables.update(message.input_variables)
            values["input_variables"] = sorted(input_variables)
        return values


@dataclasses.dataclass
class PromptTemplateIdentifier(ResourceIdentifier):
    """The identifier of a prompt template."""

    identifier_split: str = dataclasses.field(default="___$$$$___", init=False)
    prompt_name: str
    prompt_language: Optional[str] = None
    sys_code: Optional[str] = None
    model: Optional[str] = None

    def __post_init__(self):
        """Post init method."""
        if self.prompt_name is None:
            raise ValueError("prompt_name cannot be None")

        if any(
            self.identifier_split in key
            for key in [
                self.prompt_name,
                self.prompt_language,
                self.sys_code,
                self.model,
            ]
            if key is not None
        ):
            raise ValueError(
                f"identifier_split {self.identifier_split} is not allowed in "
                f"prompt_name, prompt_language, sys_code, model"
            )

    @property
    def str_identifier(self) -> str:
        """Return the string identifier of the identifier."""
        return self.identifier_split.join(
            key
            for key in [
                self.prompt_name,
                self.prompt_language,
                self.sys_code,
                self.model,
            ]
            if key is not None
        )

    def to_dict(self) -> Dict:
        """Convert the identifier to a dict.

        Returns:
            Dict: The dict of the identifier.
        """
        return {
            "prompt_name": self.prompt_name,
            "prompt_language": self.prompt_language,
            "sys_code": self.sys_code,
            "model": self.model,
        }


@dataclasses.dataclass
class StoragePromptTemplate(StorageItem):
    """The storage prompt template."""

    prompt_name: str
    content: Optional[str] = None
    prompt_language: Optional[str] = None
    prompt_format: Optional[str] = None
    input_variables: Optional[str] = None
    model: Optional[str] = None
    chat_scene: Optional[str] = None
    sub_chat_scene: Optional[str] = None
    prompt_type: Optional[str] = None
    user_name: Optional[str] = None
    sys_code: Optional[str] = None
    _identifier: PromptTemplateIdentifier = dataclasses.field(init=False)

    def __post_init__(self):
        """Post init method."""
        self._identifier = PromptTemplateIdentifier(
            prompt_name=self.prompt_name,
            prompt_language=self.prompt_language,
            sys_code=self.sys_code,
            model=self.model,
        )
        # Assuming _check() is a method you need to call after initialization
        self._check()

    def to_prompt_template(self) -> PromptTemplate:
        """Convert the storage prompt template to a prompt template."""
        input_variables = (
            [] if not self.input_variables else self.input_variables.strip().split(",")
        )
        template_format = self.prompt_format or "f-string"
        return PromptTemplate(
            input_variables=input_variables,
            template=self.content,
            template_scene=self.chat_scene,
            # prompt_name=self.prompt_name,
            template_format=template_format,
        )

    @staticmethod
    def from_prompt_template(
        prompt_template: PromptTemplate,
        prompt_name: str,
        prompt_language: Optional[str] = None,
        prompt_type: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
        sub_chat_scene: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> "StoragePromptTemplate":
        """Convert a prompt template to a storage prompt template.

        Args:
            prompt_template (PromptTemplate): The prompt template to convert from.
            prompt_name (str): The name of the prompt.
            prompt_language (Optional[str], optional): The language of the prompt.
                Defaults to None. e.g. zh-cn, en.
            prompt_type (Optional[str], optional): The type of the prompt.
                Defaults to None. e.g. common, private.
            sys_code (Optional[str], optional): The system code of the prompt.
                Defaults to None.
            user_name (Optional[str], optional): The username of the prompt.
                Defaults to None.
            sub_chat_scene (Optional[str], optional): The sub chat scene of the prompt.
                Defaults to None.
            model (Optional[str], optional): The model name of the prompt.
                Defaults to None.
            kwargs (Dict): Other params to build the storage prompt template.
        """
        input_variables = prompt_template.input_variables or kwargs.get(
            "input_variables"
        )
        if input_variables and isinstance(input_variables, list):
            input_variables = ",".join(input_variables)
        return StoragePromptTemplate(
            prompt_name=prompt_name,
            sys_code=sys_code,
            user_name=user_name,
            input_variables=input_variables,
            model=model,
            content=prompt_template.template or kwargs.get("content"),
            prompt_language=prompt_language,
            prompt_format=prompt_template.template_format
            or kwargs.get("prompt_format"),
            chat_scene=prompt_template.template_scene or kwargs.get("chat_scene"),
            sub_chat_scene=sub_chat_scene,
            prompt_type=prompt_type,
        )

    @property
    def identifier(self) -> PromptTemplateIdentifier:
        """Return the identifier of the storage prompt template."""
        return self._identifier

    def merge(self, other: "StorageItem") -> None:
        """Merge the other item into the current item.

        Args:
            other (StorageItem): The other item to merge
        """
        if not isinstance(other, StoragePromptTemplate):
            raise ValueError(
                f"Cannot merge {type(other)} into {type(self)} because they are not "
                f"the same type."
            )
        self.from_object(other)

    def to_dict(self) -> Dict:
        """Convert the storage prompt template to a dict.

        Returns:
            Dict: The dict of the storage prompt template.
        """
        return {
            "prompt_name": self.prompt_name,
            "content": self.content,
            "prompt_language": self.prompt_language,
            "prompt_format": self.prompt_format,
            "input_variables": self.input_variables,
            "model": self.model,
            "chat_scene": self.chat_scene,
            "sub_chat_scene": self.sub_chat_scene,
            "prompt_type": self.prompt_type,
            "user_name": self.user_name,
            "sys_code": self.sys_code,
        }

    def _check(self):
        if self.prompt_name is None:
            raise ValueError("prompt_name cannot be None")
        if self.content is None:
            raise ValueError("content cannot be None")

    def from_object(self, template: "StoragePromptTemplate") -> None:
        """Load the prompt template from an existing prompt template object.

        Args:
            template (PromptTemplate): The prompt template to load from.
        """
        self.content = template.content
        self.prompt_format = template.prompt_format
        self.input_variables = template.input_variables
        self.model = template.model
        self.chat_scene = template.chat_scene
        self.sub_chat_scene = template.sub_chat_scene
        self.prompt_type = template.prompt_type
        self.user_name = template.user_name


class PromptManager:
    """The manager class for prompt templates.

    Simple wrapper for the storage interface.

    Examples:
        .. code-block:: python

            # Default use InMemoryStorage
            prompt_manager = PromptManager()
            prompt_template = PromptTemplate(
                template="hello {input}",
                input_variables=["input"],
                template_scene="chat_normal",
            )
            prompt_manager.save(prompt_template, prompt_name="hello")
            prompt_template_list = prompt_manager.list()
            prompt_template_list = prompt_manager.prefer_query("hello")

        With a custom storage interface.

        .. code-block:: python

            from dbgpt.core.interface.storage import InMemoryStorage

            prompt_manager = PromptManager(InMemoryStorage())
            prompt_template = PromptTemplate(
                template="hello {input}",
                input_variables=["input"],
                template_scene="chat_normal",
            )
            prompt_manager.save(prompt_template, prompt_name="hello")
            prompt_template_list = prompt_manager.list()
            prompt_template_list = prompt_manager.prefer_query("hello")


    """

    def __init__(
        self, storage: Optional[StorageInterface[StoragePromptTemplate, Any]] = None
    ):
        """Create a new prompt manager."""
        if storage is None:
            storage = InMemoryStorage()
        self._storage = storage

    @property
    def storage(self) -> StorageInterface[StoragePromptTemplate, Any]:
        """Return the storage interface for prompt templates."""
        return self._storage

    def prefer_query(
        self,
        prompt_name: str,
        sys_code: Optional[str] = None,
        prefer_prompt_language: Optional[str] = None,
        prefer_model: Optional[str] = None,
        **kwargs,
    ) -> List[StoragePromptTemplate]:
        """Query prompt templates from storage with prefer params.

        Sometimes, we want to query prompt templates with prefer params(e.g. some
        language or some model).
        This method will query prompt templates with prefer params first, if not found,
        will query all prompt templates.

        Examples:
            Query a prompt template.
            .. code-block:: python

                prompt_template_list = prompt_manager.prefer_query("hello")

            Query with sys_code and username.

            .. code-block:: python

                prompt_template_list = prompt_manager.prefer_query(
                    "hello", sys_code="sys_code", user_name="user_name"
                )

            Query with prefer prompt language.

            .. code-block:: python

                # First query with prompt name "hello" exactly.
                # Second filter with prompt language "zh-cn", if not found, will return
                # all prompt templates.
                prompt_template_list = prompt_manager.prefer_query(
                    "hello", prefer_prompt_language="zh-cn"
                )

            Query with prefer model.

            .. code-block:: python

                # First query with prompt name "hello" exactly.
                # Second filter with model "vicuna-13b-v1.5", if not found, will return
                # all prompt templates.
                prompt_template_list = prompt_manager.prefer_query(
                    "hello", prefer_model="vicuna-13b-v1.5"
                )

        Args:
            prompt_name (str): The name of the prompt template.
            sys_code (Optional[str], optional): The system code of the prompt template.
                Defaults to None.
            prefer_prompt_language (Optional[str], optional): The language of the
                prompt template. Defaults to None.
            prefer_model (Optional[str], optional): The model of the prompt template.
                Defaults to None.
            kwargs (Dict): Other query params(If some key and value not None, wo we
                query it exactly).
        """
        query_spec = QuerySpec(
            conditions={
                "prompt_name": prompt_name,
                "sys_code": sys_code,
                **kwargs,
            }
        )
        queries: List[StoragePromptTemplate] = self.storage.query(
            query_spec, StoragePromptTemplate
        )
        if not queries:
            return []
        if prefer_prompt_language:
            prefer_prompt_language = prefer_prompt_language.lower()
            temp_queries = [
                query
                for query in queries
                if query.prompt_language
                and query.prompt_language.lower() == prefer_prompt_language
            ]
            if temp_queries:
                queries = temp_queries
        if prefer_model:
            prefer_model = prefer_model.lower()
            temp_queries = [
                query
                for query in queries
                if query.model and query.model.lower() == prefer_model
            ]
            if temp_queries:
                queries = temp_queries
        return queries

    def save(self, prompt_template: PromptTemplate, prompt_name: str, **kwargs) -> None:
        """Save a prompt template to storage.

        Examples:
            .. code-block:: python

                prompt_template = PromptTemplate(
                    template="hello {input}",
                    input_variables=["input"],
                    template_scene="chat_normal",
                    prompt_name="hello",
                )
                prompt_manager.save(prompt_template)

            Save with sys_code and username.

            .. code-block:: python

                prompt_template = PromptTemplate(
                    template="hello {input}",
                    input_variables=["input"],
                    template_scene="chat_normal",
                    prompt_name="hello",
                )
                prompt_manager.save(
                    prompt_template, sys_code="sys_code", user_name="user_name"
                )

        Args:
            prompt_template (PromptTemplate): The prompt template to save.
            prompt_name (str): The name of the prompt template.
            kwargs (Dict): Other params to build the storage prompt template.
                More details in :meth:`~StoragePromptTemplate.from_prompt_template`.
        """
        storage_prompt_template = StoragePromptTemplate.from_prompt_template(
            prompt_template, prompt_name, **kwargs
        )
        self.storage.save(storage_prompt_template)

    def query_or_save(
        self, prompt_template: PromptTemplate, prompt_name: str, **kwargs
    ) -> StoragePromptTemplate:
        """Query a prompt template from storage, if not found, save it.

        Args:
            prompt_template (PromptTemplate): The prompt template to save.
            prompt_name (str): The name of the prompt template.
            kwargs (Dict): Other params to build the storage prompt template.
                More details in :meth:`~StoragePromptTemplate.from_prompt_template`.

        Returns:
            StoragePromptTemplate: The storage prompt template.
        """
        storage_prompt_template = StoragePromptTemplate.from_prompt_template(
            prompt_template, prompt_name, **kwargs
        )
        exist_prompt_template = self.storage.load(
            storage_prompt_template.identifier, StoragePromptTemplate
        )
        if exist_prompt_template:
            return exist_prompt_template
        self.save(prompt_template, prompt_name, **kwargs)
        prompt = self.storage.load(
            storage_prompt_template.identifier, StoragePromptTemplate
        )
        if not prompt:
            raise ValueError("Can't read prompt from storage")
        return prompt

    def list(self, **kwargs) -> List[StoragePromptTemplate]:
        """List prompt templates from storage.

        Examples:
            List all prompt templates.
            .. code-block:: python

                all_prompt_templates = prompt_manager.list()

            List with sys_code and username.

            .. code-block:: python

                templates = prompt_manager.list(
                    sys_code="sys_code", user_name="user_name"
                )

        Args:
            kwargs (Dict): Other query params.
        """
        query_spec = QuerySpec(conditions=kwargs)
        return self.storage.query(query_spec, StoragePromptTemplate)

    def delete(
        self,
        prompt_name: str,
        prompt_language: Optional[str] = None,
        sys_code: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """Delete a prompt template from storage.

        Examples:
            Delete a prompt template.

            .. code-block:: python

                prompt_manager.delete("hello")

            Delete with sys_code and username.

            .. code-block:: python

                prompt_manager.delete(
                    "hello", sys_code="sys_code", user_name="user_name"
                )

        Args:
            prompt_name (str): The name of the prompt template.
            prompt_language (Optional[str], optional): The language of the prompt
                template. Defaults to None.
            sys_code (Optional[str], optional): The system code of the prompt template.
                Defaults to None.
            model (Optional[str], optional): The model of the prompt template.
                Defaults to None.
        """
        identifier = PromptTemplateIdentifier(
            prompt_name=prompt_name,
            prompt_language=prompt_language,
            sys_code=sys_code,
            model=model,
        )
        self.storage.delete(identifier)


def _get_string_template_vars(template_str: str) -> Set[str]:
    """Get template variables from a template string."""
    variables = set()
    formatter = Formatter()

    for _, variable_name, _, _ in formatter.parse(template_str):
        if variable_name:
            variables.add(variable_name)

    return variables


def _get_jinja2_template_vars(template_str: str) -> Set[str]:
    """Get template variables from a template string."""
    from jinja2 import Environment, meta

    env = Environment()
    ast = env.parse(template_str)
    variables = meta.find_undeclared_variables(ast)
    return variables


def get_template_vars(
    template_str: str, template_format: str = "f-string"
) -> List[str]:
    """Get template variables from a template string."""
    if template_format == "f-string":
        result = _get_string_template_vars(template_str)
    elif template_format == "jinja2":
        result = _get_jinja2_template_vars(template_str)
    else:
        raise ValueError(f"Unsupported template format: {template_format}")
    return sorted(result)
