from typing import Any, get_type_hints, get_origin, get_args
from functools import wraps
import inspect
import asyncio


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
    if not isinstance(obj, origin):
        return False

    # For each item in the object, check if it matches the corresponding type argument
    for sub_obj, arg in zip(obj, args):
        # Skip check if the type argument is Any
        if arg is not Any and not isinstance(sub_obj, arg):
            return False

    return True


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
        key=lambda x: next(
            i for i, t in enumerate(arg_types) if _is_instance_of_generic_type(x, t)
        ),
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
