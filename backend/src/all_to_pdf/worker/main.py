"""Standalone translation-worker process entry point."""

from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from all_to_pdf.bootstrap import build_container, build_worker
from all_to_pdf.config import Settings

logger = logging.getLogger(__name__)


async def serve() -> None:
    settings = Settings()
    container = build_container(settings)
    worker = build_worker(container)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    task = asyncio.create_task(
        worker.process_job.run_forever(container.queue),
        name="translation-worker",
    )
    await stop.wait()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await container.close()


def run() -> None:
    logging.basicConfig(level=Settings().log_level)
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("worker interrupted")


if __name__ == "__main__":
    run()
