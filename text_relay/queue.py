"""Bounded-concurrency asynchronous OCR work queue."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from text_relay.ocr import OCRError, OCRStrategy
from text_relay.store import ResultStore


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OCRWorkItem:
    """Image data owned by the queue until a worker finishes processing it."""

    job_id: str
    image: bytes
    content_type: str
    strategy: OCRStrategy


class OCRWorkQueue:
    """Runs queued OCR jobs with a fixed number of asynchronous workers."""

    def __init__(
        self, store: ResultStore, worker_count: int, retry_count: int = 0
    ) -> None:
        self._store = store
        self._worker_count = worker_count
        self._retry_count = retry_count
        self._queue: asyncio.Queue[OCRWorkItem] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._workers = [
            asyncio.create_task(self._run_worker(), name=f"ocr-worker-{number}")
            for number in range(1, self._worker_count + 1)
        ]

    async def submit(self, item: OCRWorkItem) -> None:
        await self.start()
        await self._queue.put(item)

    async def close(self) -> None:
        self._store.fail_unfinished_jobs()
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._started = False

    async def _run_worker(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                self._store.mark_processing(item.job_id)
                for attempt in range(self._retry_count + 1):
                    try:
                        text = await item.strategy.extract_text(item.image, item.content_type)
                    except OCRError as error:
                        LOGGER.warning("OCR attempt %s failed: %s", attempt + 1, error)
                    except Exception:
                        LOGGER.exception("Unexpected OCR attempt %s failure", attempt + 1)
                    else:
                        self._store.complete(item.job_id, text)
                        break
                else:
                    self._store.fail(item.job_id)
            finally:
                self._queue.task_done()
