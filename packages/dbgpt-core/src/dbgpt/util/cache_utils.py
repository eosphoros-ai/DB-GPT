"""Cache utils.

Adapted from https://github.com/hephex/asyncache/blob/master/asyncache/__init__.py.
It has stopped updating since 2022. So I copied the code here for future reference.
"""

import asyncio
import functools
from contextlib import AbstractContextManager
from typing import Any, Callable, MutableMapping, Optional, Protocol, TypeVar

from cachetools import keys

_KT = TypeVar("_KT")
_T = TypeVar("_T")


class IdentityFunction(Protocol):  # pylint: disable=too-few-public-methods
    """
    Type for a function returning the same type as the one it received.
    """

    def __call__(self, __x: _T) -> _T: ...


class NullContext:
    """A class for noop context managers."""

    def __enter__(self):
        """Return ``self`` upon entering the runtime context."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Raise any exception triggered within the runtime context."""
        return None

    async def __aenter__(self):
        """Return ``self`` upon entering the runtime context."""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Raise any exception triggered within the runtime context."""
        return None


def cached(
    cache: Optional[MutableMapping[_KT, Any]],
    # ignoring the mypy error to be consistent with the type used
    # in https://github.com/python/typeshed/tree/master/stubs/cachetools
    key: Callable[..., _KT] = keys.hashkey,  # type:ignore
    lock: Optional["AbstractContextManager[Any]"] = None,
) -> IdentityFunction:
    """
    Decorator to wrap a function or a coroutine with a memoizing callable
    that saves results in a cache.

    When ``lock`` is provided for a standard function, it's expected to
    implement ``__enter__`` and ``__exit__`` that will be used to lock
    the cache when gets updated. If it wraps a coroutine, ``lock``
    must implement ``__aenter__`` and ``__aexit__``.
    """
    lock = lock or NullContext()

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            async def wrapper(*args, **kwargs):
                k = key(*args, **kwargs)
                try:
                    async with lock:
                        return cache[k]

                except KeyError:
                    pass  # key not found

                val = await func(*args, **kwargs)

                try:
                    async with lock:
                        cache[k] = val

                except ValueError:
                    pass  # val too large

                return val

        else:

            def wrapper(*args, **kwargs):
                k = key(*args, **kwargs)
                try:
                    with lock:
                        return cache[k]

                except KeyError:
                    pass  # key not found

                val = func(*args, **kwargs)

                try:
                    with lock:
                        cache[k] = val

                except ValueError:
                    pass  # val too large

                return val

        return functools.wraps(func)(wrapper)

    return decorator
