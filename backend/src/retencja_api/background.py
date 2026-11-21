"""Shared background computations: one in-flight task per key, so parallel requests share
a slow download and a request that ran out of time keeps the work going for the next one."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)

RESULT_TTL_S = 1800.0
_MAX_RESULTS = 256

_in_flight: dict[str, asyncio.Task] = {}
# Results finished after their request timed out, kept for the polling request.
_results: dict[str, tuple[float, object]] = {}


def shared_task[T](key: str, start: Callable[[], Awaitable[T]]) -> asyncio.Task[T]:
    task = _in_flight.get(key)
    if task is None:
        task = asyncio.ensure_future(start())
        _in_flight[key] = task

        def _done(t: asyncio.Task) -> None:
            _in_flight.pop(key, None)
            if t.cancelled():
                return
            if t.exception() is not None:
                log.error("Background task %s failed", key, exc_info=t.exception())
                return
            if len(_results) >= _MAX_RESULTS:
                _results.pop(next(iter(_results)))
            _results[key] = (time.monotonic(), t.result())

        task.add_done_callback(_done)
    return task


async def run_within[T](key: str, start: Callable[[], Awaitable[T]], budget_s: float) -> T:
    """Result of `start()`, reusing a recent or in-flight run; TimeoutError after `budget_s`
    while the computation continues in the background."""
    stored = _results.get(key)
    if stored is not None and time.monotonic() - stored[0] < RESULT_TTL_S:
        return stored[1]  # type: ignore[return-value]
    return await asyncio.wait_for(asyncio.shield(shared_task(key, start)), budget_s)
