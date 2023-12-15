def PublicAPI(*args, **kwargs):
    """Decorator to mark a function or class as a public API.

    Args:
        stability: The stability of the API. Can be "alpha", "beta" or "stable".
            If "alpha", the API is in alpha may come breaking changes before becoming beta.
            If "beta", the API is in beta and may change before becoming stable.
            If "stable", the API will remain backwards compatible with the current major version.
            Defaults to "stable".
    Examples:
        >>> from dbgpt.util.annotations import PublicAPI
        >>> @PublicAPI
        ... def foo():
        ...     pass

        >>> @PublicAPI(stability="beta")
        ... def bar():
        ...     pass

    """
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        return PublicAPI(stability="stable")(args[0])
    stability = None
    if "stability" in kwargs:
        stability = kwargs["stability"]
    if not stability:
        stability = "stable"
    assert stability in ["alpha", "beta", "stable"]

    def decorator(obj):
        if stability in ["alpha", "beta"]:
            _modify_docstring(
                obj,
                f"**PublicAPI ({stability}):** This API is in {stability} and may change before becoming stable.",
            )
            _modify_annotation(obj, stability)
        return obj

    return decorator


def DeveloperAPI(*args, **kwargs):
    """Decorator to mark a function or class as a developer API.

    Developer APIs are low-level APIs for advanced users and may change cross major versions.

    Examples:
        >>> from dbgpt.util.annotations import DeveloperAPI
        >>> @DeveloperAPI
        ... def foo():
        ...     pass

    """
    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        return DeveloperAPI()(args[0])

    def decorator(obj):
        _modify_docstring(
            obj,
            "**DeveloperAPI:** This API is for advanced users and may change cross major versions.",
        )
        return obj

    return decorator


def _modify_docstring(obj, message: str = None):
    if not message:
        return
    if not obj.__doc__:
        obj.__doc__ = ""
    original_doc = obj.__doc__

    lines = original_doc.splitlines()

    min_indent = float("inf")
    for line in lines[1:]:
        stripped = line.lstrip()
        if stripped:
            min_indent = min(min_indent, len(line) - len(stripped))

    if min_indent == float("inf"):
        min_indent = 0
    indented_message = message.rstrip() + "\n" + (" " * min_indent)
    obj.__doc__ = indented_message + original_doc


def _modify_annotation(obj, stability) -> None:
    if stability:
        obj._public_stability = stability
    if hasattr(obj, "__name__"):
        obj._annotated = obj.__name__
