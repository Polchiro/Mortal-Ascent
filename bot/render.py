"""
Card rendering off the event loop, one card at a time.

Pillow font objects are cached and shared (see profile_card), and FreeType is
not safe to use from several threads at once, so every card renders on one
dedicated worker thread.
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("mortal-ascent")
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="card-render")


def _timed(fn, data):
    t0 = time.perf_counter()
    try:
        return fn(data)
    finally:
        log.info("Rendered %s in %.2fs", fn.__name__, time.perf_counter() - t0)


async def render(fn, data):
    return await asyncio.get_running_loop().run_in_executor(_EXECUTOR, _timed, fn, data)
