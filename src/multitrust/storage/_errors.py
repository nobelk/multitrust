"""Internal helper for wrapping storage backend errors as ``StoreError``.

All storage backends share the same boilerplate: catch any backend exception
and re-raise as ``StoreError`` (or its subclass ``ConcurrencyError``) with a
descriptive message. The :func:`store_op` decorator centralises that pattern.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from multitrust.core.errors import StoreError

P = ParamSpec("P")
R = TypeVar("R")


def store_op(
    message: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Wrap an async storage method so any exception becomes a ``StoreError``.

    ``StoreError`` (and subclasses such as ``ConcurrencyError``) raised by the
    wrapped function pass through unmodified — only foreign exceptions are
    converted. ``message`` is used as the new ``StoreError`` text; the original
    exception is preserved via ``raise ... from exc``.
    """

    def decorator(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await fn(*args, **kwargs)
            except StoreError:
                raise
            except Exception as exc:
                raise StoreError(message) from exc

        return wrapper

    return decorator
