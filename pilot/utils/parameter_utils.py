import argparse
import os
from dataclasses import dataclass, fields, MISSING
from typing import Any, List, Optional, Type, Union, Callable


@dataclass
class ParameterDescription:
    param_name: str
    param_type: str
    description: str
    default_value: Optional[Any]
    valid_values: Optional[List[Any]]


@dataclass
class BaseParameters:
    def update_from(self, source: Union["BaseParameters", dict]) -> bool:
        """
        Update the attributes of this object using the values from another object (of the same or parent type) or a dictionary.
        Only update if the new value is different from the current value and the field is not marked as "fixed" in metadata.

        Args:
            source (Union[BaseParameters, dict]): The source to update from. Can be another object of the same type or a dictionary.

        Returns:
            bool: True if at least one field was updated, otherwise False.
        """
        updated = False  # Flag to indicate whether any field was updated
        if isinstance(source, (BaseParameters, dict)):
            for field_info in fields(self):
                # Check if the field has a "fixed" tag in metadata
                tags = field_info.metadata.get("tags")
                tags = [] if not tags else tags.split(",")
                if tags and "fixed" in tags:
                    continue  # skip this field
                # Get the new value from source (either another BaseParameters object or a dict)
                new_value = (
                    getattr(source, field_info.name)
                    if isinstance(source, BaseParameters)
                    else source.get(field_info.name, None)
                )

                # If the new value is not None and different from the current value, update the field and set the flag
                if new_value is not None and new_value != getattr(
                    self, field_info.name
                ):
                    setattr(self, field_info.name, new_value)
                    updated = True
        else:
            raise ValueError(
                "Source must be an instance of BaseParameters (or its derived class) or a dictionary."
            )

        return updated

    def __str__(self) -> str:
        class_name = self.__class__.__name__
        parameters = [
            f"\n\n=========================== {class_name} ===========================\n"
        ]
        for field_info in fields(self):
            value = getattr(self, field_info.name)
            parameters.append(f"{field_info.name}: {value}")
        parameters.append(
            "\n======================================================================\n\n"
        )
        return "\n".join(parameters)


def _genenv_ignoring_key_case(env_key: str, env_prefix: str = None, default_value=None):
    """Get the value from the environment variable, ignoring the case of the key"""
    if env_prefix:
        env_key = env_prefix + env_key
    return os.getenv(
        env_key, os.getenv(env_key.upper(), os.getenv(env_key.lower(), default_value))
    )


class EnvArgumentParser:
    @staticmethod
    def get_env_prefix(env_key: str) -> str:
        if not env_key:
            return None
        env_key = env_key.replace("-", "_")
        return env_key + "_"

    def parse_args_into_dataclass(
        self,
        dataclass_type: Type,
        env_prefix: str = None,
        command_args: List[str] = None,
        **kwargs,
    ) -> Any:
        """Parse parameters from environment variables and command lines and populate them into data class"""
        parser = argparse.ArgumentParser()
        for field in fields(dataclass_type):
            env_var_value = _genenv_ignoring_key_case(field.name, env_prefix)
            if not env_var_value:
                # Read without env prefix
                env_var_value = _genenv_ignoring_key_case(field.name)

            if env_var_value:
                env_var_value = env_var_value.strip()
                if field.type is int or field.type == Optional[int]:
                    env_var_value = int(env_var_value)
                elif field.type is float or field.type == Optional[float]:
                    env_var_value = float(env_var_value)
                elif field.type is bool or field.type == Optional[bool]:
                    env_var_value = env_var_value.lower() == "true"
                elif field.type is str or field.type == Optional[str]:
                    pass
                else:
                    raise ValueError(f"Unsupported parameter type {field.type}")
            if not env_var_value:
                env_var_value = kwargs.get(field.name)

            # Add a command-line argument for this field
            help_text = field.metadata.get("help", "")
            valid_values = field.metadata.get("valid_values", None)

            argument_kwargs = {
                "type": EnvArgumentParser._get_argparse_type(field.type),
                "help": help_text,
                "choices": valid_values,
                "required": EnvArgumentParser._is_require_type(field.type),
            }
            if field.default != MISSING:
                argument_kwargs["default"] = field.default
                argument_kwargs["required"] = False
            if env_var_value:
                argument_kwargs["default"] = env_var_value
                argument_kwargs["required"] = False

            parser.add_argument(f"--{field.name}", **argument_kwargs)

        # Parse the command-line arguments
        cmd_args, cmd_argv = parser.parse_known_args(args=command_args)
        # cmd_args = parser.parse_args(args=command_args)
        # print(f"cmd_args: {cmd_args}")
        for field in fields(dataclass_type):
            # cmd_line_value = getattr(cmd_args, field.name)
            if field.name in cmd_args:
                cmd_line_value = getattr(cmd_args, field.name)
                if cmd_line_value is not None:
                    kwargs[field.name] = cmd_line_value

        return dataclass_type(**kwargs)

    @staticmethod
    def create_arg_parser(dataclass_type: Type) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=dataclass_type.__doc__)
        for field in fields(dataclass_type):
            help_text = field.metadata.get("help", "")
            valid_values = field.metadata.get("valid_values", None)
            argument_kwargs = {
                "type": EnvArgumentParser._get_argparse_type(field.type),
                "help": help_text,
                "choices": valid_values,
                "required": EnvArgumentParser._is_require_type(field.type),
            }
            if field.default != MISSING:
                argument_kwargs["default"] = field.default
                argument_kwargs["required"] = False
            parser.add_argument(f"--{field.name}", **argument_kwargs)
        return parser

    @staticmethod
    def create_click_option(
        *dataclass_types: Type, _dynamic_factory: Callable[[None], List[Type]] = None
    ):
        import click
        import functools
        from collections import OrderedDict

        # TODO dynamic configuration
        # pre_args = _SimpleArgParser('model_name', 'model_path')
        # pre_args.parse()
        # print(pre_args)

        combined_fields = OrderedDict()
        if _dynamic_factory:
            _types = _dynamic_factory()
            if _types:
                dataclass_types = list(_types)
        for dataclass_type in dataclass_types:
            for field in fields(dataclass_type):
                if field.name not in combined_fields:
                    combined_fields[field.name] = field

        def decorator(func):
            for field_name, field in reversed(combined_fields.items()):
                help_text = field.metadata.get("help", "")
                valid_values = field.metadata.get("valid_values", None)
                cli_params = {
                    "default": None if field.default is MISSING else field.default,
                    "help": help_text,
                    "show_default": True,
                    "required": field.default is MISSING,
                }
                if valid_values:
                    cli_params["type"] = click.Choice(valid_values)
                real_type = EnvArgumentParser._get_argparse_type(field.type)
                if real_type is int:
                    cli_params["type"] = click.INT
                elif real_type is float:
                    cli_params["type"] = click.FLOAT
                elif real_type is str:
                    cli_params["type"] = click.STRING
                elif real_type is bool:
                    cli_params["is_flag"] = True

                option_decorator = click.option(
                    # f"--{field_name.replace('_', '-')}", **cli_params
                    f"--{field_name}",
                    **cli_params,
                )
                func = option_decorator(func)

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    @staticmethod
    def _get_argparse_type(field_type: Type) -> Type:
        # Return the appropriate type for argparse to use based on the field type
        if field_type is int or field_type == Optional[int]:
            return int
        elif field_type is float or field_type == Optional[float]:
            return float
        elif field_type is bool or field_type == Optional[bool]:
            return bool
        elif field_type is str or field_type == Optional[str]:
            return str
        else:
            raise ValueError(f"Unsupported parameter type {field_type}")

    @staticmethod
    def _get_argparse_type_str(field_type: Type) -> str:
        argparse_type = EnvArgumentParser._get_argparse_type(field_type)
        if argparse_type is int:
            return "int"
        elif argparse_type is float:
            return "float"
        elif argparse_type is bool:
            return "bool"
        else:
            return "str"

    @staticmethod
    def _is_require_type(field_type: Type) -> str:
        return field_type not in [Optional[int], Optional[float], Optional[bool]]


def _get_parameter_descriptions(dataclass_type: Type) -> List[ParameterDescription]:
    descriptions = []
    for field in fields(dataclass_type):
        descriptions.append(
            ParameterDescription(
                param_name=field.name,
                param_type=EnvArgumentParser._get_argparse_type_str(field.type),
                description=field.metadata.get("help", None),
                default_value=field.default,  # TODO handle dataclasses._MISSING_TYPE
                valid_values=field.metadata.get("valid_values", None),
            )
        )
    return descriptions


class _SimpleArgParser:
    def __init__(self, *args):
        self.params = {arg.replace("_", "-"): None for arg in args}

    def parse(self, args=None):
        import sys

        if args is None:
            args = sys.argv[1:]
        else:
            args = list(args)
        prev_arg = None
        for arg in args:
            if arg.startswith("--"):
                if prev_arg:
                    self.params[prev_arg] = None
                prev_arg = arg[2:]
            else:
                if prev_arg:
                    self.params[prev_arg] = arg
                    prev_arg = None

        if prev_arg:
            self.params[prev_arg] = None

    def _get_param(self, key):
        return self.params.get(key.replace("_", "-"), None)

    def __getattr__(self, item):
        return self._get_param(item)

    def __getitem__(self, key):
        return self._get_param(key)

    def get(self, key, default=None):
        return self._get_param(key) or default

    def __str__(self):
        return "\n".join(
            [f'{key.replace("-", "_")}: {value}' for key, value in self.params.items()]
        )
