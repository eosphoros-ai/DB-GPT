import os
import re
from dataclasses import MISSING, dataclass, fields, is_dataclass
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

try:
    # tomllib in stdlib after Python 3.11, try to import it first
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

T = TypeVar("T")


class ConfigurationManager:
    """A unified configuration manager that supports loading configuration from files
    and converting them to dataclass objects.

    This class provides functionality to:
    1. Load configuration from TOML files
    2. Convert configuration dictionaries to typed dataclass instances
    3. Support nested configurations with type checking
    4. Handle optional fields and default values
    5. Support environment variable substitution using ${env:ENV_NAME} syntax

    Examples:
        >>> @dataclass
        ... class DatabaseConfig:
        ...     host: str
        ...     port: int
        ...     password: Optional[str] = None
        >>> config_dict = {"host": "${env:DB_HOST}", "port": 5432}
        >>> # Assuming DB_HOST environment variable is set to "localhost"
        >>> config_manager = ConfigurationManager(config_dict)
        >>> db_config = config_manager.parse_config(DatabaseConfig)
        >>> print(db_config.host)  # Will print the value of DB_HOST env var
        'localhost'
    """

    ENV_VAR_PATTERN = re.compile(r"\${env:([^}]+)}")

    def __init__(
        self, config_dict: Optional[Dict] = None, resolve_env_vars: bool = True
    ):
        """Initialize the configuration manager.

        Args:
            config_dict: Optional dictionary containing configuration data.
                        If None, an empty dictionary will be used.
            resolve_env_vars: Whether to resolve environment variables in string values.
                            Defaults to True.
        """
        self.config: Dict = config_dict or {}
        self.resolve_env_vars = resolve_env_vars

    @classmethod
    def from_file(cls, file_path: str | Path) -> "ConfigurationManager":
        """Create a ConfigurationManager instance by loading configuration from a TOML file.

        Args:
            file_path: Path to the TOML configuration file

        Returns:
            A new ConfigurationManager instance with the loaded configuration

        Examples:
            >>> config = ConfigurationManager.from_file("config.toml")
            >>> print(config.get("database.host"))
            'localhost'
        """
        with open(file_path, "rb") as f:
            config_dict = tomllib.load(f)
        return cls(config_dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using a dot-notation key.

        Args:
            key: Dot-notation key to access nested configuration (e.g., 'database.host')
            default: Default value to return if the key is not found

        Returns:
            The configuration value if found, otherwise the default value

        Examples:
            >>> config = ConfigurationManager({"database": {"host": "localhost"}})
            >>> print(config.get("database.host"))
            'localhost'
            >>> print(config.get("database.port", 5432))
            5432
        """
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def _resolve_env_vars(self, value: str) -> str:
        """Resolve environment variables in a string value.

        Args:
            value: String value that may contain environment variable references

        Returns:
            String with environment variables replaced with their values

        Raises:
            ValueError: If an environment variable is not found and no default is specified

        Examples:
            >>> # Assuming DB_HOST="localhost" is set in environment
            >>> cm = ConfigurationManager()
            >>> print(cm._resolve_env_vars("host: ${env:DB_HOST}"))
            'host: localhost'
            >>> print(cm._resolve_env_vars("host: ${env:DB_HOST:-default}"))
            'host: localhost'
            >>> print(cm._resolve_env_vars("host: ${env:NONEXISTENT:-default}"))
            'host: default'
        """

        def replace_env_var(match):
            env_var = match.group(1)
            # Support default values using :- syntax
            if ":-" in env_var:
                env_name, default = env_var.split(":-", 1)
            else:
                env_name, default = env_var, None

            value = os.environ.get(env_name)
            if value is None:
                if default is not None:
                    return default
                raise ValueError(f"Environment variable {env_name} not found")
            return value

        return self.ENV_VAR_PATTERN.sub(replace_env_var, value)

    def _convert_value(self, value: Any, field_type: Type) -> Any:
        """Convert a value to the specified type, supporting complex types and env vars.

        This method handles various type conversions including:
        - Basic types (str, int, float, bool)
        - Optional types
        - List types with type checking
        - Dict types with key/value type checking
        - Nested dataclass instances
        - Environment variable substitution in string values

        Args:
            value: The value to convert
            field_type: The target type to convert to

        Returns:
            The converted value

        Raises:
            ValueError: If the value cannot be converted to the specified type
        """
        # Handle None values
        if value is None:
            if get_origin(field_type) is Union and type(None) in get_args(field_type):
                return None
            raise ValueError(f"Non-optional field received None value")

        # Handle environment variable substitution for string values
        if isinstance(value, str) and self.resolve_env_vars:
            value = self._resolve_env_vars(value)

        origin = get_origin(field_type)
        args = get_args(field_type)

        # Handle basic types
        if origin is None and field_type in (str, int, float, bool):
            try:
                return field_type(value)
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert {value} to {field_type}")

        # Handle Optional types
        if origin is Union and type(None) in args:
            inner_type = next(arg for arg in args if arg is not type(None))
            return self._convert_value(value, inner_type) if value is not None else None

        # Handle List types
        if origin is list or origin is List:
            if not isinstance(value, (list, tuple)):
                raise ValueError(f"Expected list but got {type(value)}")
            element_type = args[0] if args else Any
            try:
                return [self._convert_value(item, element_type) for item in value]
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid list element type: {str(e)}")

        # Handle Dict types
        if origin is dict or origin is Dict:
            if not isinstance(value, dict):
                raise ValueError(f"Expected dict but got {type(value)}")
            key_type, value_type = args if args else (Any, Any)
            try:
                return {
                    self._convert_value(k, key_type): self._convert_value(v, value_type)
                    for k, v in value.items()
                }
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid dictionary entry: {str(e)}")

        # Handle nested dataclass
        if is_dataclass(field_type):
            if not isinstance(value, dict):
                raise ValueError(
                    f"Expected dict for {field_type.__name__} but got {type(value)}"
                )
            try:
                return self._convert_to_dataclass(field_type, value)
            except ValueError as e:
                raise ValueError(f"Invalid data for {field_type.__name__}: {str(e)}")

        return value

    def _convert_to_dataclass(self, cls: Type[T], data: Dict) -> T:
        """Convert a dictionary to a dataclass instance, supporting nested conversion.

        This method handles:
        - Field type validation
        - Default values
        - Required field checking
        - Nested dataclass conversion

        Args:
            cls: The target dataclass type
            data: The dictionary containing the data to convert

        Returns:
            An instance of the specified dataclass

        Raises:
            ValueError: If the data cannot be converted to the specified dataclass
                       or if required fields are missing

        Examples:
            >>> @dataclass
            ... class ServerConfig:
            ...     host: str
            ...     port: int
            >>> data = {"host": "localhost", "port": "8080"}
            >>> config = ConfigurationManager()._convert_to_dataclass(
            ...     ServerConfig, data
            ... )
            >>> print(config.port)
            8080
        """
        if not is_dataclass(cls):
            raise ValueError(f"{cls.__name__} is not a dataclass")

        field_values = {}
        type_hints = get_type_hints(cls)

        for field in fields(cls):
            field_type = type_hints[field.name]
            field_value = data.get(field.name, MISSING)

            if field_value is MISSING and field.default is not MISSING:
                field_values[field.name] = field.default
            elif field_value is MISSING and field.default_factory is not MISSING:
                field_values[field.name] = field.default_factory()
            elif field_value is MISSING:
                raise ValueError(f"Missing required field: {field.name}")
            else:
                field_values[field.name] = self._convert_value(field_value, field_type)

        return cls(**field_values)

    def parse_config(self, cls: Type[T], prefix: str = "") -> T:
        """Parse configuration data into a specified dataclass type.

        Args:
            cls: The target dataclass type to parse into
            prefix: Optional dot-notation prefix to select a configuration section

        Returns:
            An instance of the specified dataclass

        Raises:
            ValueError: If the configuration section is not found or if parsing fails

        Examples:
            >>> @dataclass
            ... class DbConfig:
            ...     host: str
            ...     port: int
            >>> config = ConfigurationManager(
            ...     {"database": {"host": "localhost", "port": 5432}}
            ... )
            >>> db_config = config.parse_config(DbConfig, "database")
            >>> print(db_config.host)
            'localhost'
        """
        if not prefix:
            return self._convert_to_dataclass(cls, self.config)

        config_section = self.get(prefix)
        if config_section is None:
            raise ValueError(f"Configuration section not found: {prefix}")
        return self._convert_to_dataclass(cls, config_section)
