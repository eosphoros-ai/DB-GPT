from importlib import import_module
from typing import Type


def import_from_string(module_path: str, ignore_import_error: bool = False):
    try:
        module_path, class_name = module_path.rsplit(".", 1)
    except ValueError:
        raise ImportError(f"{module_path} doesn't look like a module path")
    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        if ignore_import_error:
            return None
        raise ImportError(
            f'Module "{module_path}" does not define a "{class_name}" attribute/class'
        )


def import_from_checked_string(module_path: str, supper_cls: Type):
    cls = import_from_string(module_path)
    if not issubclass(cls, supper_cls):
        raise ImportError(
            f'Module "{module_path}" does not the subclass of {str(supper_cls)}'
        )
    return cls
