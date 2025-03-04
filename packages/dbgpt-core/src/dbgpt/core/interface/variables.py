"""Variables Module."""

import base64
import dataclasses
import hashlib
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.util.executor_utils import (
    DefaultExecutorFactory,
    blocking_func_to_async,
    blocking_func_to_async_no_executor,
)

from .storage import (
    InMemoryStorage,
    QuerySpec,
    ResourceIdentifier,
    StorageInterface,
    StorageItem,
)

_EMPTY_DEFAULT_VALUE = "_EMPTY_DEFAULT_VALUE"

BUILTIN_VARIABLES_CORE_FLOWS = "dbgpt.core.flow.flows"
BUILTIN_VARIABLES_CORE_FLOW_NODES = "dbgpt.core.flow.nodes"
BUILTIN_VARIABLES_CORE_VARIABLES = "dbgpt.core.variables"
BUILTIN_VARIABLES_CORE_SECRETS = "dbgpt.core.secrets"
BUILTIN_VARIABLES_CORE_LLMS = "dbgpt.core.model.llms"
BUILTIN_VARIABLES_CORE_EMBEDDINGS = "dbgpt.core.model.embeddings"
# Not implemented yet
BUILTIN_VARIABLES_CORE_RERANKERS = "dbgpt.core.model.rerankers"
BUILTIN_VARIABLES_CORE_DATASOURCES = "dbgpt.core.datasources"
BUILTIN_VARIABLES_CORE_AGENTS = "dbgpt.core.agent.agents"
BUILTIN_VARIABLES_CORE_KNOWLEDGE_SPACES = "dbgpt.core.knowledge_spaces"


class Encryption(ABC):
    """Encryption interface."""

    name: str = "__abstract__"

    @abstractmethod
    def encrypt(self, data: str, salt: str) -> str:
        """Encrypt the data."""

    @abstractmethod
    def decrypt(self, encrypted_data: str, salt: str) -> str:
        """Decrypt the data."""


def _generate_key_from_password(
    password: bytes, salt: Optional[Union[str, bytes]] = None
):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    if salt is None:
        salt = os.urandom(16)
    elif isinstance(salt, str):
        salt = salt.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=800000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key, salt


class FernetEncryption(Encryption):
    """Fernet encryption.

    A symmetric encryption algorithm that uses the same key for both encryption and
    decryption which is powered by the cryptography library.
    """

    name = "fernet"

    def __init__(self, key: Optional[bytes] = None):
        """Initialize the fernet encryption."""
        if key is not None and isinstance(key, str):
            key = key.encode()
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError(
                "cryptography is required for encryption, please install by running "
                "`pip install cryptography`"
            )
        if key is None:
            key = Fernet.generate_key()
        self.key = key

    def encrypt(self, data: str, salt: str) -> str:
        """Encrypt the data with the salt.

        Args:
            data (str): The data to encrypt.
            salt (str): The salt to use, which is used to derive the key.

        Returns:
            str: The encrypted data.
        """
        from cryptography.fernet import Fernet

        key, salt = _generate_key_from_password(self.key, salt)
        fernet = Fernet(key)
        encrypted_secret = fernet.encrypt(data.encode()).decode()
        return encrypted_secret

    def decrypt(self, encrypted_data: str, salt: str) -> str:
        """Decrypt the data with the salt.

        Args:
            encrypted_data (str): The encrypted data.
            salt (str): The salt to use, which is used to derive the key.

        Returns:
            str: The decrypted data.
        """
        from cryptography.fernet import Fernet

        key, salt = _generate_key_from_password(self.key, salt)
        fernet = Fernet(key)
        return fernet.decrypt(encrypted_data.encode()).decode()


class SimpleEncryption(Encryption):
    """Simple implementation of encryption.

    A simple encryption algorithm that uses a key to XOR the data.
    """

    name = "simple"

    def __init__(self, key: Optional[str] = None):
        """Initialize the simple encryption."""
        if key is None:
            key = base64.b64encode(os.urandom(32)).decode()
        self.key = key

    def _derive_key(self, salt: str) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", self.key.encode(), salt.encode(), 100000)

    def encrypt(self, data: str, salt: str) -> str:
        """Encrypt the data with the salt."""
        key = self._derive_key(salt)
        encrypted = bytes(
            x ^ y for x, y in zip(data.encode(), key * (len(data) // len(key) + 1))
        )
        return base64.b64encode(encrypted).decode()

    def decrypt(self, encrypted_data: str, salt: str) -> str:
        """Decrypt the data with the salt."""
        key = self._derive_key(salt)
        data = base64.b64decode(encrypted_data)
        decrypted = bytes(
            x ^ y for x, y in zip(data, key * (len(data) // len(key) + 1))
        )
        return decrypted.decode()


@dataclasses.dataclass
class VariablesIdentifier(ResourceIdentifier):
    """The variables identifier."""

    identifier_split: str = dataclasses.field(default="@", init=False)

    key: str
    name: str
    scope: str = "global"
    scope_key: Optional[str] = None
    sys_code: Optional[str] = None
    user_name: Optional[str] = None

    def __post_init__(self):
        """Post init method."""
        if not self.key or not self.name or not self.scope:
            raise ValueError("Key, name, and scope are required.")

    @property
    def str_identifier(self) -> str:
        """Return the string identifier of the identifier."""
        return build_variable_string(
            {
                "key": self.key,
                "name": self.name,
                "scope": self.scope,
                "scope_key": self.scope_key,
                "sys_code": self.sys_code,
                "user_name": self.user_name,
            }
        )

    def to_dict(self) -> Dict:
        """Convert the identifier to a dict.

        Returns:
            Dict: The dict of the identifier.
        """
        return {
            "key": self.key,
            "name": self.name,
            "scope": self.scope,
            "scope_key": self.scope_key,
            "sys_code": self.sys_code,
            "user_name": self.user_name,
        }

    @classmethod
    def from_str_identifier(
        cls,
        str_identifier: str,
        default_identifier_map: Optional[Dict[str, str]] = None,
    ) -> "VariablesIdentifier":
        """Create a VariablesIdentifier from a string identifier.

        Args:
            str_identifier (str): The string identifier.
            default_identifier_map (Optional[Dict[str, str]]): The default identifier
                map, which contains the default values for the identifier. Defaults to
                None.

        Returns:
            VariablesIdentifier: The VariablesIdentifier.
        """
        variable_dict = parse_variable(str_identifier)
        if not variable_dict:
            raise ValueError("Invalid string identifier.")
        if not variable_dict.get("key"):
            raise ValueError("Invalid string identifier, must have key")
        if not variable_dict.get("name"):
            raise ValueError("Invalid string identifier, must have name")

        def _get_value(key, default_value: Optional[str] = None) -> Optional[str]:
            if variable_dict.get(key) is not None:
                return variable_dict.get(key)
            if default_identifier_map is not None and default_identifier_map.get(key):
                return default_identifier_map.get(key)
            return default_value

        return cls(
            key=variable_dict["key"],
            name=variable_dict["name"],
            scope=variable_dict["scope"],
            scope_key=_get_value("scope_key"),
            sys_code=_get_value("sys_code"),
            user_name=_get_value("user_name"),
        )


@dataclasses.dataclass
class StorageVariables(StorageItem):
    """The storage variables."""

    key: str
    name: str
    label: str
    value: Any
    category: Literal["common", "secret"] = "common"
    scope: str = "global"
    value_type: Optional[str] = None
    scope_key: Optional[str] = None
    sys_code: Optional[str] = None
    user_name: Optional[str] = None
    encryption_method: Optional[str] = None
    salt: Optional[str] = None
    enabled: int = 1
    description: Optional[str] = None

    _identifier: VariablesIdentifier = dataclasses.field(init=False)

    def __post_init__(self):
        """Post init method."""
        self._identifier = VariablesIdentifier(
            key=self.key,
            name=self.name,
            scope=self.scope,
            scope_key=self.scope_key,
            sys_code=self.sys_code,
            user_name=self.user_name,
        )
        if not self.value_type:
            self.value_type = type(self.value).__name__

    @property
    def identifier(self) -> ResourceIdentifier:
        """Return the identifier."""
        return self._identifier

    def merge(self, other: "StorageItem") -> None:
        """Merge with another storage variables."""
        if not isinstance(other, StorageVariables):
            raise ValueError(f"Cannot merge with {type(other)}")
        self.from_object(other)

    def to_dict(self) -> Dict:
        """Convert the storage variables to a dict.

        Returns:
            Dict: The dict of the storage variables.
        """
        return {
            **self._identifier.to_dict(),
            "label": self.label,
            "value": self.value,
            "value_type": self.value_type,
            "category": self.category,
            "encryption_method": self.encryption_method,
            "salt": self.salt,
            "enabled": self.enabled,
            "description": self.description,
        }

    def from_object(self, other: "StorageVariables") -> None:
        """Copy the values from another storage variables object."""
        self.label = other.label
        self.value = other.value
        self.value_type = other.value_type
        self.category = other.category
        self.scope = other.scope
        self.scope_key = other.scope_key
        self.sys_code = other.sys_code
        self.user_name = other.user_name
        self.encryption_method = other.encryption_method
        self.salt = other.salt
        self.enabled = other.enabled
        self.description = other.description

    @classmethod
    def from_identifier(
        cls,
        identifier: VariablesIdentifier,
        value: Any,
        value_type: str,
        label: str = "",
        category: Literal["common", "secret"] = "common",
        encryption_method: Optional[str] = None,
        salt: Optional[str] = None,
    ) -> "StorageVariables":
        """Copy the values from an identifier."""
        return cls(
            key=identifier.key,
            name=identifier.name,
            label=label,
            value=value,
            value_type=value_type,
            category=category,
            scope=identifier.scope,
            scope_key=identifier.scope_key,
            sys_code=identifier.sys_code,
            user_name=identifier.user_name,
            encryption_method=encryption_method,
            salt=salt,
        )


class VariablesProvider(BaseComponent, ABC):
    """The variables provider interface."""

    name = ComponentType.VARIABLES_PROVIDER.value

    @abstractmethod
    def get(
        self,
        full_key: str,
        default_value: Optional[str] = _EMPTY_DEFAULT_VALUE,
        default_identifier_map: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Query variables from storage."""

    async def async_get(
        self,
        full_key: str,
        default_value: Optional[str] = _EMPTY_DEFAULT_VALUE,
        default_identifier_map: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Query variables from storage async."""
        raise NotImplementedError("Current variables provider does not support async.")

    @abstractmethod
    def save(self, variables_item: StorageVariables) -> None:
        """Save variables to storage."""

    @abstractmethod
    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get variables by key."""

    async def async_get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Get variables by key async."""
        raise NotImplementedError("Current variables provider does not support async.")

    def support_async(self) -> bool:
        """Whether the variables provider support async."""
        return False

    def _convert_to_value_type(self, var: StorageVariables):
        """Convert the variable to the value type."""
        if var.value is None:
            return None
        if var.value_type == "str":
            return str(var.value)
        elif var.value_type == "int":
            return int(var.value)
        elif var.value_type == "float":
            return float(var.value)
        elif var.value_type == "bool":
            if var.value.lower() in ["true", "1"]:
                return True
            elif var.value.lower() in ["false", "0"]:
                return False
            else:
                return bool(var.value)
        else:
            return var.value


class VariablesPlaceHolder:
    """The variables place holder."""

    def __init__(
        self,
        param_name: str,
        full_key: str,
        default_value: Any = _EMPTY_DEFAULT_VALUE,
    ):
        """Initialize the variables place holder."""
        self.param_name = param_name
        self.full_key = full_key
        self.default_value = default_value

    def parse(
        self,
        variables_provider: VariablesProvider,
        ignore_not_found_error: bool = False,
        default_identifier_map: Optional[Dict[str, str]] = None,
    ):
        """Parse the variables."""
        try:
            return variables_provider.get(
                self.full_key,
                self.default_value,
                default_identifier_map=default_identifier_map,
            )
        except ValueError as e:
            if ignore_not_found_error:
                return None
            raise e

    async def async_parse(
        self,
        variables_provider: VariablesProvider,
        ignore_not_found_error: bool = False,
        default_identifier_map: Optional[Dict[str, str]] = None,
    ):
        """Parse the variables async."""
        try:
            return await variables_provider.async_get(
                self.full_key,
                self.default_value,
                default_identifier_map=default_identifier_map,
            )
        except ValueError as e:
            if ignore_not_found_error:
                return None
            raise e

    def __repr__(self):
        """Return the representation of the variables place holder."""
        return f"<VariablesPlaceHolder {self.param_name} {self.full_key}>"


class StorageVariablesProvider(VariablesProvider):
    """The storage variables provider."""

    def __init__(
        self,
        storage: Optional[StorageInterface] = None,
        encryption: Optional[Encryption] = None,
        system_app: Optional[SystemApp] = None,
        key: Optional[str] = None,
    ):
        """Initialize the storage variables provider."""
        if storage is None:
            storage = InMemoryStorage()
        self.system_app = system_app
        self.encryption = encryption or SimpleEncryption(key)

        self.storage = storage
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        """Initialize the storage variables provider."""
        self.system_app = system_app

    def get(
        self,
        full_key: str,
        default_value: Optional[str] = _EMPTY_DEFAULT_VALUE,
        default_identifier_map: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Query variables from storage."""
        key = VariablesIdentifier.from_str_identifier(full_key, default_identifier_map)
        variable: Optional[StorageVariables] = self.storage.load(key, StorageVariables)
        if variable is None:
            if default_value == _EMPTY_DEFAULT_VALUE:
                raise ValueError(f"Variable {full_key} not found")
            return default_value
        variable.value = self.deserialize_value(variable.value)
        if (
            variable.value is not None
            and variable.category == "secret"
            and variable.encryption_method
            and variable.salt
        ):
            variable.value = self.encryption.decrypt(variable.value, variable.salt)
        return self._convert_to_value_type(variable)

    async def async_get(
        self,
        full_key: str,
        default_value: Optional[str] = _EMPTY_DEFAULT_VALUE,
        default_identifier_map: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Query variables from storage async."""
        # Try to get variables from storage
        value = await blocking_func_to_async_no_executor(
            self.get,
            full_key,
            default_value=None,
            default_identifier_map=default_identifier_map,
        )
        if value is not None:
            return value
        key = VariablesIdentifier.from_str_identifier(full_key, default_identifier_map)
        # Get all builtin variables
        variables = await self.async_get_variables(
            key=key.key,
            scope=key.scope,
            scope_key=key.scope_key,
            sys_code=key.sys_code,
            user_name=key.user_name,
        )
        values = [v for v in variables if v.name == key.name]
        if not values:
            if default_value == _EMPTY_DEFAULT_VALUE:
                raise ValueError(f"Variable {full_key} not found")
            return default_value
        if len(values) > 1:
            raise ValueError(f"Multiple variables found for {full_key}")

        variable = values[0]
        return self._convert_to_value_type(variable)

    def save(self, variables_item: StorageVariables) -> None:
        """Save variables to storage."""
        if variables_item.category == "secret":
            salt = base64.b64encode(os.urandom(16)).decode()
            variables_item.value = self.encryption.encrypt(
                str(variables_item.value), salt
            )
            variables_item.encryption_method = self.encryption.name
            variables_item.salt = salt
        # Replace value to a json serializable object
        variables_item.value = self.serialize_value(variables_item.value)

        self.storage.save_or_update(variables_item)

    def get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Query variables from storage."""
        # Try to get builtin variables
        is_builtin, builtin_variables = self._get_builtins_variables(
            key,
            scope=scope,
            scope_key=scope_key,
            sys_code=sys_code,
            user_name=user_name,
        )
        if is_builtin:
            return builtin_variables
        variables = self.storage.query(
            QuerySpec(
                conditions={
                    "key": key,
                    "scope": scope,
                    "scope_key": scope_key,
                    "sys_code": sys_code,
                    "user_name": user_name,
                    "enabled": 1,
                }
            ),
            StorageVariables,
        )
        for variable in variables:
            variable.value = self.deserialize_value(variable.value)
        return variables

    async def async_get_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> List[StorageVariables]:
        """Query variables from storage async."""
        # Try to get builtin variables
        is_builtin, builtin_variables = await self._async_get_builtins_variables(
            key,
            scope=scope,
            scope_key=scope_key,
            sys_code=sys_code,
            user_name=user_name,
        )
        if is_builtin:
            return builtin_variables
        executor_factory: Optional[DefaultExecutorFactory] = None
        if self.system_app:
            executor_factory = DefaultExecutorFactory.get_instance(
                self.system_app, default_component=None
            )
        if executor_factory:
            return await blocking_func_to_async(
                executor_factory.create(),
                self.get_variables,
                key,
                scope,
                scope_key,
                sys_code,
                user_name,
            )
        else:
            return await blocking_func_to_async_no_executor(
                self.get_variables, key, scope, scope_key, sys_code, user_name
            )

    def _get_builtins_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> Tuple[bool, List[StorageVariables]]:
        """Get builtin variables."""
        if self.system_app is None:
            return False, []
        provider: BuiltinVariablesProvider = self.system_app.get_component(
            key,
            component_type=BuiltinVariablesProvider,
            default_component=None,
        )
        if not provider:
            return False, []
        return True, provider.get_variables(
            key,
            scope=scope,
            scope_key=scope_key,
            sys_code=sys_code,
            user_name=user_name,
        )

    async def _async_get_builtins_variables(
        self,
        key: str,
        scope: str = "global",
        scope_key: Optional[str] = None,
        sys_code: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> Tuple[bool, List[StorageVariables]]:
        """Get builtin variables."""
        if self.system_app is None:
            return False, []
        provider: BuiltinVariablesProvider = self.system_app.get_component(
            key,
            component_type=BuiltinVariablesProvider,
            default_component=None,
        )
        if not provider:
            return False, []
        if not provider.support_async():
            return False, []
        return True, await provider.async_get_variables(
            key,
            scope=scope,
            scope_key=scope_key,
            sys_code=sys_code,
            user_name=user_name,
        )

    @classmethod
    def serialize_value(cls, value: Any) -> str:
        """Serialize the value."""
        value_dict = {"value": value}
        return json.dumps(value_dict, ensure_ascii=False)

    @classmethod
    def deserialize_value(cls, value: str) -> Any:
        """Deserialize the value."""
        value_dict = json.loads(value)
        return value_dict["value"]


class BuiltinVariablesProvider(VariablesProvider, ABC):
    """The builtin variables provider.

    You can implement this class to provide builtin variables. Such LLMs, agents,
    datasource, knowledge base, etc.
    """

    name = "dbgpt_variables_builtin"

    def __init__(self, system_app: Optional[SystemApp] = None):
        """Initialize the builtin variables provider."""
        self.system_app = system_app
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        """Initialize the builtin variables provider."""
        self.system_app = system_app

    def get(
        self,
        full_key: str,
        default_value: Optional[str] = _EMPTY_DEFAULT_VALUE,
        default_identifier_map: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Query variables from storage."""
        raise NotImplementedError("BuiltinVariablesProvider does not support get.")

    def save(self, variables_item: StorageVariables) -> None:
        """Save variables to storage."""
        raise NotImplementedError("BuiltinVariablesProvider does not support save.")


def parse_variable(
    variable_str: str,
    enable_escape: bool = True,
) -> Dict[str, Any]:
    """Parse the variable string.

    Examples:
        .. code-block:: python

            cases = [
                {
                    "full_key": "${test_key:test_name@test_scope:test_scope_key}",
                    "expected": {
                        "key": "test_key",
                        "name": "test_name",
                        "scope": "test_scope",
                        "scope_key": "test_scope_key",
                        "sys_code": None,
                        "user_name": None,
                    },
                },
                {
                    "full_key": "${test_key#test_sys_code}",
                    "expected": {
                        "key": "test_key",
                        "name": None,
                        "scope": None,
                        "scope_key": None,
                        "sys_code": "test_sys_code",
                        "user_name": None,
                    },
                },
                {
                    "full_key": "${test_key@:test_scope_key}",
                    "expected": {
                        "key": "test_key",
                        "name": None,
                        "scope": None,
                        "scope_key": "test_scope_key",
                        "sys_code": None,
                        "user_name": None,
                    },
                },
            ]
            for case in cases:
                assert parse_variable(case["full_key"]) == case["expected"]
    Args:
        variable_str (str): The variable string.
        enable_escape (bool): Whether to handle escaped characters.
    Returns:
        Dict[str, Any]: The parsed variable.
    """
    if not variable_str.startswith("${") or not variable_str.endswith("}"):
        raise ValueError(
            "Invalid variable format, must start with '${' and end with '}'"
        )

    # Remove the surrounding ${ and }
    content = variable_str[2:-1]

    # Define placeholders for escaped characters
    placeholders = {
        r"\@": "__ESCAPED_AT__",
        r"\#": "__ESCAPED_HASH__",
        r"\%": "__ESCAPED_PERCENT__",
        r"\:": "__ESCAPED_COLON__",
    }

    if enable_escape:
        # Replace escaped characters with placeholders
        for original, placeholder in placeholders.items():
            content = content.replace(original, placeholder)

    # Initialize the result dictionary
    result: Dict[str, Optional[str]] = {
        "key": None,
        "name": None,
        "scope": None,
        "scope_key": None,
        "sys_code": None,
        "user_name": None,
    }

    # Split the content by special characters
    parts = content.split("@")

    # Parse key and name
    key_name = parts[0].split("#")[0].split("%")[0]
    if ":" in key_name:
        result["key"], result["name"] = key_name.split(":", 1)
    else:
        result["key"] = key_name

    # Parse scope and scope_key
    if len(parts) > 1:
        scope_part = parts[1].split("#")[0].split("%")[0]
        if ":" in scope_part:
            result["scope"], result["scope_key"] = scope_part.split(":", 1)
        else:
            result["scope"] = scope_part

    # Parse sys_code
    if "#" in content:
        result["sys_code"] = content.split("#", 1)[1].split("%")[0]

    # Parse user_name
    if "%" in content:
        result["user_name"] = content.split("%", 1)[1]

    if enable_escape:
        # Replace placeholders back with escaped characters
        reverse_placeholders = {v: k[1:] for k, v in placeholders.items()}
        for key, value in result.items():
            if value:
                for placeholder, original in reverse_placeholders.items():
                    result[key] = result[key].replace(  # type: ignore
                        placeholder, original
                    )

    # Replace empty strings with None
    for key, value in result.items():
        if value == "":
            result[key] = None

    return result


def _is_variable_format(value: str) -> bool:
    if not value.startswith("${") or not value.endswith("}"):
        return False
    return True


def is_variable_string(variable_str: str) -> bool:
    """Check if the given string is a variable string.

    A valid variable string should start with "${" and end with "}", and contain key
    and name

    Args:
        variable_str (str): The string to check.

    Returns:
        bool: True if the string is a variable string, False otherwise.
    """
    if not variable_str or not isinstance(variable_str, str):
        return False
    if not _is_variable_format(variable_str):
        return False
    try:
        variable_dict = parse_variable(variable_str)
        if not variable_dict.get("key"):
            return False
        if not variable_dict.get("name"):
            return False
        return True
    except Exception:
        return False


def is_variable_list_string(variable_str: str) -> bool:
    """Check if the given string is a variable string.

    A valid variable list string should start with "${" and end with "}", and contain
    key and not contain name

    A valid variable list string means that the variable is a list of variables with the
    same key.

    Args:
        variable_str (str): The string to check.

    Returns:
        bool: True if the string is a variable string, False otherwise.
    """
    if not _is_variable_format(variable_str):
        return False
    try:
        variable_dict = parse_variable(variable_str)
        if not variable_dict.get("key"):
            return False
        if variable_dict.get("name"):
            return False
        return True
    except Exception:
        return False


def build_variable_string(
    variable_dict: Dict[str, Any],
    scope_sig: str = "@",
    sys_code_sig: str = "#",
    user_sig: str = "%",
    kv_sig: str = ":",
    enable_escape: bool = True,
) -> str:
    """Build a variable string from the given dictionary.

    Args:
        variable_dict (Dict[str, Any]): The dictionary containing the variable details.
        scope_sig (str): The scope signature.
        sys_code_sig (str): The sys code signature.
        user_sig (str): The user signature.
        kv_sig (str): The key-value split signature.
        enable_escape (bool): Whether to escape special characters

    Returns:
        str: The formatted variable string.

    Examples:
        >>> build_variable_string(
        ...     {
        ...         "key": "test_key",
        ...         "name": "test_name",
        ...         "scope": "test_scope",
        ...         "scope_key": "test_scope_key",
        ...         "sys_code": "test_sys_code",
        ...         "user_name": "test_user",
        ...     }
        ... )
        '${test_key:test_name@test_scope:test_scope_key#test_sys_code%test_user}'

        >>> build_variable_string({"key": "test_key", "scope_key": "test_scope_key"})
        '${test_key@:test_scope_key}'

        >>> build_variable_string({"key": "test_key", "sys_code": "test_sys_code"})
        '${test_key#test_sys_code}'

        >>> build_variable_string({"key": "test_key"})
        '${test_key}'
    """
    special_chars = {scope_sig, sys_code_sig, user_sig, kv_sig}
    # Replace None with ""
    new_variable_dict = {key: value or "" for key, value in variable_dict.items()}

    # Check if the variable_dict contains any special characters
    for key, value in new_variable_dict.items():
        if value != "" and any(char in value for char in special_chars):
            if enable_escape:
                # Escape special characters
                new_variable_dict[key] = (
                    value.replace("@", "\\@")
                    .replace("#", "\\#")
                    .replace("%", "\\%")
                    .replace(":", "\\:")
                )
            else:
                raise ValueError(
                    f"{key} contains special characters, error value: {value}, special "
                    f"characters: {special_chars}"
                )

    key = new_variable_dict.get("key", "")
    name = new_variable_dict.get("name", "")
    scope = new_variable_dict.get("scope", "")
    scope_key = new_variable_dict.get("scope_key", "")
    sys_code = new_variable_dict.get("sys_code", "")
    user_name = new_variable_dict.get("user_name", "")

    # Construct the base of the variable string
    variable_str = f"${{{key}"

    # Add name if present
    if name:
        variable_str += f":{name}"

    # Add scope and scope_key if present
    if scope or scope_key:
        variable_str += f"@{scope}"
        if scope_key:
            variable_str += f":{scope_key}"

    # Add sys_code if present
    if sys_code:
        variable_str += f"#{sys_code}"

    # Add user_name if present
    if user_name:
        variable_str += f"%{user_name}"

    # Close the variable string
    variable_str += "}"

    return variable_str
