"""Shared background computations: one in-flight task per key, so parallel requests share
a slow download and a request that ran out of time keeps the work going for the next one."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)

RESULT_TTL_S = 1800.0
# A failed computation is reported to the next requests for a while instead of restarting
# the same slow download on every poll.
ERROR_TTL_S = 600.0
_MAX_RESULTS = 256

_in_flight: dict[str, asyncio.Task] = {}
# Results finished after their request timed out, kept for the polling request.
_results: dict[str, tuple[float, object]] = {}
_errors: dict[str, tuple[float, BaseException]] = {}


def _remember[V](store: dict[str, tuple[float, V]], key: str, value: V) -> None:
    if len(store) >= _MAX_RESULTS:
        store.pop(next(iter(store)))
    store[key] = (time.monotonic(), value)


def recent_error(key: str) -> BaseException | None:
    """The exception of the last run of `key` if it failed within ERROR_TTL_S."""
    stored = _errors.get(key)
    if stored is not None and time.monotonic() - stored[0] < ERROR_TTL_S:
        return stored[1]
    return None


def shared_task[T](key: str, start: Callable[[], Awaitable[T]]) -> asyncio.Task[T]:
    task = _in_flight.get(key)
    if task is None:
        task = asyncio.ensure_future(start())
        _in_flight[key] = task

        def _done(t: asyncio.Task) -> None:
            _in_flight.pop(key, None)
            if t.cancelled():
                return
            if (exc := t.exception()) is not None:
                log.error("Background task %s failed", key, exc_info=exc)
                _remember(_errors, key, exc)
                return
            _errors.pop(key, None)
            _remember(_results, key, t.result())

        task.add_done_callback(_done)
    return task


async def run_within[T](key: str, start: Callable[[], Awaitable[T]], budget_s: float) -> T:
    """Result of `start()`, reusing a recent or in-flight run; TimeoutError after `budget_s`
    while the computation continues in the background."""
    stored = _results.get(key)
    if stored is not None and time.monotonic() - stored[0] < RESULT_TTL_S:
        return stored[1]  # type: ignore[return-value]
    if (exc := recent_error(key)) is not None:
        raise exc
    return await asyncio.wait_for(asyncio.shield(shared_task(key, start)), budget_s)
