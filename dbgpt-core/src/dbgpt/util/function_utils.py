import asyncio
import inspect
from functools import wraps
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    _UnionGenericAlias,
    get_args,
    get_origin,
    get_type_hints,
)

from typeguard import check_type
from typing_extensions import Annotated, Doc, _AnnotatedAlias


def _is_typing(obj):
    from typing import _Final  # type: ignore

    return isinstance(obj, _Final)


def _is_instance_of_generic_type(obj, generic_type):
    """Check if an object is an instance of a generic type."""
    if generic_type is Any:
        return True  # Any type is compatible with any object

    origin = get_origin(generic_type)
    if origin is None:
        return isinstance(obj, generic_type)  # Handle non-generic types

    args = get_args(generic_type)
    if not args:
        return isinstance(obj, origin)

    # Check if object matches the generic origin (like list, dict)
    if not _is_typing(origin):
        return isinstance(obj, origin)

    objs = [obj for _ in range(len(args))]

    # For each item in the object, check if it matches the corresponding type argument
    for sub_obj, arg in zip(objs, args):
        # Skip check if the type argument is Any
        if arg is not Any:
            if _is_typing(arg):
                sub_args = get_args(arg)
                if (
                    sub_args
                    and not _is_typing(sub_args[0])
                    and not isinstance(sub_obj, sub_args[0])
                ):
                    return False
            elif not isinstance(sub_obj, arg):
                return False
    return True


def _check_type(obj, t) -> bool:
    try:
        check_type(obj, t)
        return True
    except Exception:
        return False


def _get_orders(obj, arg_types):
    try:
        orders = [i for i, t in enumerate(arg_types) if _check_type(obj, t)]
        return orders[0] if orders else int(1e8)
    except Exception:
        return int(1e8)


def _sort_args(func, args, kwargs):
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    arg_types = [
        type_hints[param_name]
        for param_name in sig.parameters
        if param_name != "return" and param_name != "self"
    ]

    if "self" in sig.parameters:
        self_arg = [args[0]]
        other_args = args[1:]
    else:
        self_arg = []
        other_args = args

    sorted_args = sorted(
        other_args,
        key=lambda x: _get_orders(x, arg_types),
    )
    return (*self_arg, *sorted_args), kwargs


def rearrange_args_by_type(func):
    """Decorator to rearrange the arguments of a function by type.

    Examples:

        .. code-block:: python

            from dbgpt.util.function_utils import rearrange_args_by_type


            @rearrange_args_by_type
            def sync_regular_function(a: int, b: str, c: float):
                return a, b, c


            assert instance.sync_class_method(1, "b", 3.0) == (1, "b", 3.0)
            assert instance.sync_class_method("b", 3.0, 1) == (1, "b", 3.0)

    """

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        sorted_args, sorted_kwargs = _sort_args(func, args, kwargs)
        return func(*sorted_args, **sorted_kwargs)

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        sorted_args, sorted_kwargs = _sort_args(func, args, kwargs)
        return await func(*sorted_args, **sorted_kwargs)

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def type_to_string(obj: Any, default_type: str = "unknown") -> str:
    """Convert a type to a string representation."""
    type_map = {
        int: "integer",
        str: "string",
        float: "float",
        bool: "boolean",
        Any: "any",
        List: "array",
        dict: "object",
    }
    # Check NoneType
    if obj is type(None):
        return "null"

    # Get the origin of the type
    origin = getattr(obj, "__origin__", None)
    if origin:
        if _is_typing(origin) and not isinstance(obj, _UnionGenericAlias):
            obj = origin
            origin = origin.__origin__
        # Handle special cases like List[int]
        if origin is Union and hasattr(obj, "__args__"):
            subtypes = ", ".join(
                type_to_string(t) for t in obj.__args__ if t is not type(None)
            )
            # return f"Optional[{subtypes}]"
            return subtypes
        elif origin is list or origin is List:
            subtypes = ", ".join(type_to_string(t) for t in obj.__args__)
            # return f"List[{subtypes}]"
            return "array"
        elif origin in [dict, Dict]:
            key_type, value_type = (type_to_string(t) for t in obj.__args__)
            # return f"Dict[{key_type}, {value_type}]"
            return "object"
        return type_map.get(origin, default_type)
    else:
        if hasattr(obj, "__args__"):
            subtypes = ", ".join(
                type_to_string(t) for t in obj.__args__ if t is not type(None)
            )
            return subtypes

    return type_map.get(obj, default_type)


def parse_param_description(name: str, obj: Any) -> str:
    default_type_title = name.replace("_", " ").title()
    if isinstance(obj, _AnnotatedAlias):
        metadata = obj.__metadata__
        docs = [arg for arg in metadata if isinstance(arg, Doc)]
        doc_str = docs[0].documentation if docs else default_type_title
    else:
        doc_str = default_type_title
    return doc_str
