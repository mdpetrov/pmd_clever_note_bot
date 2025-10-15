from __future__ import annotations
import time
import logging
from functools import wraps
from typing import Awaitable, Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")

logger = logging.getLogger("pmd_clever_note")

def log_if_slow(threshold_ms: int = 200) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    # Logs only when an async function takes longer than threshold.
    def deco(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            try:
                return await fn(*args, **kwargs)
            finally:
                dur_ms = (time.perf_counter() - start) * 1000
                if dur_ms >= threshold_ms:
                    logger.info("slow_op: %s took %d ms", fn.__name__, int(dur_ms))
        return wrapper
    return deco
