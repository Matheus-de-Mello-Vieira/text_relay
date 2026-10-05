"""Bounded, process-local storage for recent OCR results."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Condition
from uuid import uuid4


@dataclass(frozen=True)
class OCRResult:
    """A completed OCR operation exposed through the HTTP API."""

    id: str
    created_at: datetime
    text: str


class ResultStore:
    """Thread-safe newest-first history with a fixed maximum size."""

    def __init__(self, maximum_size: int) -> None:
        if maximum_size <= 0:
            raise ValueError("maximum_size must be positive")
        self._results: deque[OCRResult] = deque(maxlen=maximum_size)
        self._changed = Condition()
        self._waiters_interrupted = False

    def add(self, text: str) -> OCRResult:
        """Create and retain one result, returning the new record."""
        result = OCRResult(
            id=str(uuid4()),
            created_at=datetime.now(UTC),
            text=text,
        )
        with self._changed:
            self._results.appendleft(result)
            self._changed.notify_all()
        return result

    def recent(self) -> list[OCRResult]:
        """Return a stable newest-first snapshot of the current history."""
        with self._changed:
            return list(self._results)

    def wait_for_change(
        self, latest_result_id: str | None, timeout_seconds: float
    ) -> list[OCRResult]:
        """Return results after a newer record arrives or the timeout expires."""
        with self._changed:
            self._changed.wait_for(
                lambda: self._waiters_interrupted
                or (
                    bool(self._results)
                    and self._results[0].id != latest_result_id
                ),
                timeout=timeout_seconds,
            )
            return list(self._results)

    def interrupt_waiters(self) -> None:
        """Wake long-poll threads so shutdown does not wait for their timeout."""
        with self._changed:
            self._waiters_interrupted = True
            self._changed.notify_all()
