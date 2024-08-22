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
        iterations=100000,
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

        if any(
            self.identifier_split in key
            for key in [
                self.key,
                self.name,
                self.scope,
                self.scope_key,
                self.sys_code,
                self.user_name,
            ]
            if key is not None
        ):
            raise ValueError(
                f"identifier_split {self.identifier_split} is not allowed in "
                f"key, name, scope, scope_key, sys_code, user_name."
            )

    @property
    def str_identifier(self) -> str:
        """Return the string identifier of the identifier."""
        return self.identifier_split.join(
            key or ""
            for key in [
                self.key,
                self.name,
                self.scope,
                self.scope_key,
                self.sys_code,
                self.user_name,
            ]
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
        cls, str_identifier: str, identifier_split: str = "@"
    ) -> "VariablesIdentifier":
        """Create a VariablesIdentifier from a string identifier.

        Args:
            str_identifier (str): The string identifier.
            identifier_split (str): The identifier split.

        Returns:
            VariablesIdentifier: The VariablesIdentifier.
        """
        keys = str_identifier.split(identifier_split)
        if not keys:
            raise ValueError("Invalid string identifier.")
        if len(keys) < 2:
            raise ValueError("Invalid string identifier, must have name")
        if len(keys) < 3:
            raise ValueError("Invalid string identifier, must have scope")

        return cls(
            key=keys[0],
            name=keys[1],
            scope=keys[2],
            scope_key=keys[3] if len(keys) > 3 else None,
            sys_code=keys[4] if len(keys) > 4 else None,
            user_name=keys[5] if len(keys) > 5 else None,
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
        self, full_key: str, default_value: Optional[str] = _EMPTY_DEFAULT_VALUE
    ) -> Any:
        """Query variables from storage."""

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


class VariablesPlaceHolder:
    """The variables place holder."""

    def __init__(
        self,
        param_name: str,
        full_key: str,
        value_type: str,
        default_value: Any = _EMPTY_DEFAULT_VALUE,
    ):
        """Initialize the variables place holder."""
        self.param_name = param_name
        self.full_key = full_key
        self.value_type = value_type
        self.default_value = default_value

    def parse(self, variables_provider: VariablesProvider) -> Any:
        """Parse the variables."""
        value = variables_provider.get(self.full_key, self.default_value)
        if value:
            return self._cast_to_type(value)
        else:
            return value

    def _cast_to_type(self, value: Any) -> Any:
        if self.value_type == "str":
            return str(value)
        elif self.value_type == "int":
            return int(value)
        elif self.value_type == "float":
            return float(value)
        elif self.value_type == "bool":
            if value.lower() in ["true", "1"]:
                return True
            elif value.lower() in ["false", "0"]:
                return False
            else:
                return bool(value)
        else:
            return value

    def __repr__(self):
        """Return the representation of the variables place holder."""
        return (
            f"<VariablesPlaceHolder "
            f"{self.param_name} {self.full_key} {self.value_type}>"
        )


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
        self, full_key: str, default_value: Optional[str] = _EMPTY_DEFAULT_VALUE
    ) -> Any:
        """Query variables from storage."""
        key = VariablesIdentifier.from_str_identifier(full_key)
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
        return variable.value

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
        executor_factory: Optional[
            DefaultExecutorFactory
        ] = DefaultExecutorFactory.get_instance(self.system_app, default_component=None)
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
        self, full_key: str, default_value: Optional[str] = _EMPTY_DEFAULT_VALUE
    ) -> Any:
        """Query variables from storage."""
        raise NotImplementedError("BuiltinVariablesProvider does not support get.")

    def save(self, variables_item: StorageVariables) -> None:
        """Save variables to storage."""
        raise NotImplementedError("BuiltinVariablesProvider does not support save.")
