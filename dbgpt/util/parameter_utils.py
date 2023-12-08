import argparse
import os
from dataclasses import dataclass, fields, MISSING, asdict, field, is_dataclass
from typing import Any, List, Optional, Type, Union, Callable, Dict, TYPE_CHECKING
from collections import OrderedDict

if TYPE_CHECKING:
    from dbgpt._private.pydantic import BaseModel

MISSING_DEFAULT_VALUE = "__MISSING_DEFAULT_VALUE__"


@dataclass
class ParameterDescription:
    param_class: str
    param_name: str
    param_type: str
    default_value: Optional[Any]
    description: str
    required: Optional[bool]
    valid_values: Optional[List[Any]]
    ext_metadata: Dict


@dataclass
class BaseParameters:
    @classmethod
    def from_dict(
        cls, data: dict, ignore_extra_fields: bool = False
    ) -> "BaseParameters":
        """Create an instance of the dataclass from a dictionary.

        Args:
            data: A dictionary containing values for the dataclass fields.
            ignore_extra_fields: If True, any extra fields in the data dictionary that are
                not part of the dataclass will be ignored.
                If False, extra fields will raise an error. Defaults to False.
        Returns:
            An instance of the dataclass with values populated from the given dictionary.

        Raises:
            TypeError: If `ignore_extra_fields` is False and there are fields in the
                           dictionary that aren't present in the dataclass.
        """
        all_field_names = {f.name for f in fields(cls)}
        if ignore_extra_fields:
            data = {key: value for key, value in data.items() if key in all_field_names}
        else:
            extra_fields = set(data.keys()) - all_field_names
            if extra_fields:
                raise TypeError(f"Unexpected fields: {', '.join(extra_fields)}")
        return cls(**data)

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
        return _get_dataclass_print_str(self)

    def to_command_args(self, args_prefix: str = "--") -> List[str]:
        """Convert the fields of the dataclass to a list of command line arguments.

        Args:
            args_prefix: args prefix
        Returns:
            A list of strings where each field is represented by two items:
            one for the field name prefixed by args_prefix, and one for its value.
        """
        return _dict_to_command_args(asdict(self), args_prefix=args_prefix)


def _get_dataclass_print_str(obj):
    class_name = obj.__class__.__name__
    parameters = [
        f"\n\n=========================== {class_name} ===========================\n"
    ]
    for field_info in fields(obj):
        value = _get_simple_privacy_field_value(obj, field_info)
        parameters.append(f"{field_info.name}: {value}")
    parameters.append(
        "\n======================================================================\n\n"
    )
    return "\n".join(parameters)


def _dict_to_command_args(obj: Dict, args_prefix: str = "--") -> List[str]:
    """Convert dict to a list of command line arguments

    Args:
        obj: dict
    Returns:
        A list of strings where each field is represented by two items:
        one for the field name prefixed by args_prefix, and one for its value.
    """
    args = []
    for key, value in obj.items():
        if value is None:
            continue
        args.append(f"{args_prefix}{key}")
        args.append(str(value))
    return args


def _get_simple_privacy_field_value(obj, field_info):
    """Retrieve the value of a field from a dataclass instance, applying privacy rules if necessary.

    This function reads the metadata of a field to check if it's tagged with 'privacy'.
    If the 'privacy' tag is present, then it modifies the value based on its type
    for privacy concerns:
    - int: returns -999
    - float: returns -999.0
    - bool: returns False
    - str: if length > 5, masks the middle part and returns first and last char;
           otherwise, returns "******"

    Args:
        obj: The dataclass instance.
        field_info: A Field object that contains information about the dataclass field.

    Returns:
    The original or modified value of the field based on the privacy rules.

    Example usage:
    @dataclass
    class Person:
        name: str
        age: int
        ssn: str = field(metadata={"tags": "privacy"})
    p = Person("Alice", 30, "123-45-6789")
    print(_get_simple_privacy_field_value(p, Person.ssn))  # A******9
    """
    tags = field_info.metadata.get("tags")
    tags = [] if not tags else tags.split(",")
    is_privacy = False
    if tags and "privacy" in tags:
        is_privacy = True
    value = getattr(obj, field_info.name)
    if not is_privacy or not value:
        return value
    field_type = EnvArgumentParser._get_argparse_type(field_info.type)
    if field_type is int:
        return -999
    if field_type is float:
        return -999.0
    if field_type is bool:
        return False
    # str
    if len(value) > 5:
        return value[0] + "******" + value[-1]
    return "******"


def _genenv_ignoring_key_case(env_key: str, env_prefix: str = None, default_value=None):
    """Get the value from the environment variable, ignoring the case of the key"""
    if env_prefix:
        env_key = env_prefix + env_key
    return os.getenv(
        env_key, os.getenv(env_key.upper(), os.getenv(env_key.lower(), default_value))
    )


def _genenv_ignoring_key_case_with_prefixes(
    env_key: str, env_prefixes: List[str] = None, default_value=None
) -> str:
    if env_prefixes:
        for env_prefix in env_prefixes:
            env_var_value = _genenv_ignoring_key_case(env_key, env_prefix)
            if env_var_value:
                return env_var_value
    return _genenv_ignoring_key_case(env_key, default_value=default_value)


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
        env_prefixes: List[str] = None,
        command_args: List[str] = None,
        **kwargs,
    ) -> Any:
        """Parse parameters from environment variables and command lines and populate them into data class"""
        parser = argparse.ArgumentParser()
        for field in fields(dataclass_type):
            env_var_value = _genenv_ignoring_key_case_with_prefixes(
                field.name, env_prefixes
            )
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

            # print(f"env_var_value: {env_var_value} for {field.name}")
            # Add a command-line argument for this field
            EnvArgumentParser._build_single_argparse_option(
                parser, field, env_var_value
            )

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
    def _create_arg_parser(dataclass_type: Type) -> argparse.ArgumentParser:
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
    def _create_click_option_from_field(field_name: str, field: Type, is_func=True):
        import click

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
        name = f"--{field_name}"
        if is_func:
            return click.option(
                name,
                **cli_params,
            )
        else:
            return click.Option([name], **cli_params)

    @staticmethod
    def create_click_option(
        *dataclass_types: Type, _dynamic_factory: Callable[[None], List[Type]] = None
    ):
        import functools
        from collections import OrderedDict

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
                option_decorator = EnvArgumentParser._create_click_option_from_field(
                    field_name, field
                )
                func = option_decorator(func)

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    @staticmethod
    def _create_raw_click_option(
        *dataclass_types: Type, _dynamic_factory: Callable[[None], List[Type]] = None
    ):
        combined_fields = _merge_dataclass_types(
            *dataclass_types, _dynamic_factory=_dynamic_factory
        )
        options = []

        for field_name, field in reversed(combined_fields.items()):
            options.append(
                EnvArgumentParser._create_click_option_from_field(
                    field_name, field, is_func=False
                )
            )
        return options

    @staticmethod
    def create_argparse_option(
        *dataclass_types: Type, _dynamic_factory: Callable[[None], List[Type]] = None
    ) -> argparse.ArgumentParser:
        combined_fields = _merge_dataclass_types(
            *dataclass_types, _dynamic_factory=_dynamic_factory
        )
        parser = argparse.ArgumentParser()
        for _, field in reversed(combined_fields.items()):
            EnvArgumentParser._build_single_argparse_option(parser, field)
        return parser

    @staticmethod
    def _build_single_argparse_option(
        parser: argparse.ArgumentParser, field, default_value=None
    ):
        # Add a command-line argument for this field
        help_text = field.metadata.get("help", "")
        valid_values = field.metadata.get("valid_values", None)
        short_name = field.metadata.get("short", None)
        argument_kwargs = {
            "type": EnvArgumentParser._get_argparse_type(field.type),
            "help": help_text,
            "choices": valid_values,
            "required": EnvArgumentParser._is_require_type(field.type),
        }
        if field.default != MISSING:
            argument_kwargs["default"] = field.default
            argument_kwargs["required"] = False
        if default_value:
            argument_kwargs["default"] = default_value
            argument_kwargs["required"] = False
        if field.type is bool or field.type == Optional[bool]:
            argument_kwargs["action"] = "store_true"
            del argument_kwargs["type"]
            del argument_kwargs["choices"]
        names = []
        if short_name:
            names.append(f"-{short_name}")
        names.append(f"--{field.name}")
        parser.add_argument(*names, **argument_kwargs)

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

    @staticmethod
    def _kwargs_to_env_key_value(
        kwargs: Dict, prefix: str = "__dbgpt_gunicorn__env_prefix__"
    ) -> Dict[str, str]:
        return {prefix + k: str(v) for k, v in kwargs.items()}

    @staticmethod
    def _read_env_key_value(
        prefix: str = "__dbgpt_gunicorn__env_prefix__",
    ) -> List[str]:
        env_args = []
        for key, value in os.environ.items():
            if key.startswith(prefix):
                arg_key = "--" + key.replace(prefix, "")
                if value.lower() in ["true", "1"]:
                    # Flag args
                    env_args.append(arg_key)
                elif not value.lower() in ["false", "0"]:
                    env_args.extend([arg_key, value])
        return env_args


def _merge_dataclass_types(
    *dataclass_types: Type, _dynamic_factory: Callable[[None], List[Type]] = None
) -> OrderedDict:
    combined_fields = OrderedDict()
    if _dynamic_factory:
        _types = _dynamic_factory()
        if _types:
            dataclass_types = list(_types)
    for dataclass_type in dataclass_types:
        for field in fields(dataclass_type):
            if field.name not in combined_fields:
                combined_fields[field.name] = field
    return combined_fields


def _type_str_to_python_type(type_str: str) -> Type:
    type_mapping: Dict[str, Type] = {
        "int": int,
        "float": float,
        "bool": bool,
        "str": str,
    }
    return type_mapping.get(type_str, str)


def _get_parameter_descriptions(
    dataclass_type: Type, **kwargs
) -> List[ParameterDescription]:
    descriptions = []
    for field in fields(dataclass_type):
        ext_metadata = {
            k: v for k, v in field.metadata.items() if k not in ["help", "valid_values"]
        }
        default_value = field.default if field.default != MISSING else None
        if field.name in kwargs:
            default_value = kwargs[field.name]
        descriptions.append(
            ParameterDescription(
                param_class=f"{dataclass_type.__module__}.{dataclass_type.__name__}",
                param_name=field.name,
                param_type=EnvArgumentParser._get_argparse_type_str(field.type),
                description=field.metadata.get("help", None),
                required=field.default is MISSING,
                default_value=default_value,
                valid_values=field.metadata.get("valid_values", None),
                ext_metadata=ext_metadata,
            )
        )
    return descriptions


def _build_parameter_class(desc: List[ParameterDescription]) -> Type:
    from dbgpt.util.module_utils import import_from_string

    if not desc:
        raise ValueError("Parameter descriptions cant be empty")
    param_class_str = desc[0].param_class
    if param_class_str:
        param_class = import_from_string(param_class_str, ignore_import_error=True)
        if param_class:
            return param_class
    module_name, _, class_name = param_class_str.rpartition(".")

    fields_dict = {}  # This will store field names and their default values or field()
    annotations = {}  # This will store the type annotations for the fields

    for d in desc:
        metadata = d.ext_metadata if d.ext_metadata else {}
        metadata["help"] = d.description
        metadata["valid_values"] = d.valid_values

        annotations[d.param_name] = _type_str_to_python_type(
            d.param_type
        )  # Set type annotation
        fields_dict[d.param_name] = field(default=d.default_value, metadata=metadata)

    # Create the new class. Note the setting of __annotations__ for type hints
    new_class = type(
        class_name, (object,), {**fields_dict, "__annotations__": annotations}
    )
    result_class = dataclass(new_class)  # Make it a dataclass

    return result_class


def _extract_parameter_details(
    parser: argparse.ArgumentParser,
    param_class: str = None,
    skip_names: List[str] = None,
    overwrite_default_values: Dict = {},
) -> List[ParameterDescription]:
    descriptions = []

    for action in parser._actions:
        if (
            action.default == argparse.SUPPRESS
        ):  # typically this means the argument was not provided
            continue

        # determine parameter class (store_true/store_false are flags)
        flag_or_option = (
            "flag" if isinstance(action, argparse._StoreConstAction) else "option"
        )

        # extract parameter name (use the first option string, typically the long form)
        param_name = action.option_strings[0] if action.option_strings else action.dest
        if param_name.startswith("--"):
            param_name = param_name[2:]
        if param_name.startswith("-"):
            param_name = param_name[1:]

        param_name = param_name.replace("-", "_")

        if skip_names and param_name in skip_names:
            continue

        # gather other details
        default_value = action.default
        if param_name in overwrite_default_values:
            default_value = overwrite_default_values[param_name]
        arg_type = (
            action.type if not callable(action.type) else str(action.type.__name__)
        )
        description = action.help

        # determine if the argument is required
        required = action.required

        # extract valid values for choices, if provided
        valid_values = action.choices if action.choices is not None else None

        # set ext_metadata as an empty dict for now, can be updated later if needed
        ext_metadata = {}

        descriptions.append(
            ParameterDescription(
                param_class=param_class,
                param_name=param_name,
                param_type=arg_type,
                default_value=default_value,
                description=description,
                required=required,
                valid_values=valid_values,
                ext_metadata=ext_metadata,
            )
        )

    return descriptions


def _get_dict_from_obj(obj, default_value=None) -> Optional[Dict]:
    if not obj:
        return None
    if is_dataclass(type(obj)):
        params = {}
        for field_info in fields(obj):
            value = _get_simple_privacy_field_value(obj, field_info)
            params[field_info.name] = value
        return params
    if isinstance(obj, dict):
        return obj
    return default_value


def _get_base_model_descriptions(model_cls: "BaseModel") -> List[ParameterDescription]:
    from dbgpt._private import pydantic

    version = int(pydantic.VERSION.split(".")[0])
    schema = model_cls.model_json_schema() if version >= 2 else model_cls.schema()
    required_fields = set(schema.get("required", []))
    param_descs = []
    for field_name, field_schema in schema.get("properties", {}).items():
        field = model_cls.model_fields[field_name]
        param_type = field_schema.get("type")
        if not param_type and "anyOf" in field_schema:
            for any_of in field_schema["anyOf"]:
                if any_of["type"] != "null":
                    param_type = any_of["type"]
                    break
        if version >= 2:
            default_value = (
                field.default
                if hasattr(field, "default")
                and str(field.default) != "PydanticUndefined"
                else None
            )
        else:
            default_value = (
                field.default
                if not field.allow_none
                else (
                    field.default_factory() if callable(field.default_factory) else None
                )
            )
        description = field_schema.get("description", "")
        is_required = field_name in required_fields
        valid_values = None
        ext_metadata = None
        if hasattr(field, "field_info"):
            valid_values = (
                list(field.field_info.choices)
                if hasattr(field.field_info, "choices")
                else None
            )
            ext_metadata = (
                field.field_info.extra if hasattr(field.field_info, "extra") else None
            )
        param_class = (f"{model_cls.__module__}.{model_cls.__name__}",)
        param_desc = ParameterDescription(
            param_class=param_class,
            param_name=field_name,
            param_type=param_type,
            default_value=default_value,
            description=description,
            required=is_required,
            valid_values=valid_values,
            ext_metadata=ext_metadata,
        )
        param_descs.append(param_desc)
    return param_descs


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
        return self.params.get(key.replace("_", "-")) or self.params.get(key)

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


def build_lazy_click_command(*dataclass_types: Type, _dynamic_factory=None):
    import click

    class LazyCommand(click.Command):
        def __init__(self, *args, **kwargs):
            super(LazyCommand, self).__init__(*args, **kwargs)
            self.dynamic_params_added = False

        def get_params(self, ctx):
            if ctx and not self.dynamic_params_added:
                dynamic_params = EnvArgumentParser._create_raw_click_option(
                    *dataclass_types, _dynamic_factory=_dynamic_factory
                )
                for param in reversed(dynamic_params):
                    self.params.append(param)
                self.dynamic_params_added = True
            return super(LazyCommand, self).get_params(ctx)

    return LazyCommand
