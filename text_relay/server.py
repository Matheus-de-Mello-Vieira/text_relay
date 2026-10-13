"""Uvicorn integration for interrupting long polls on shutdown."""

from __future__ import annotations

from types import FrameType
from typing import Callable

import uvicorn


class LongPollShutdownServer(uvicorn.Server):
    """Notify long polls as soon as Uvicorn receives a shutdown signal."""

    def __init__(
        self,
        config: uvicorn.Config,
        interrupt_waiters: Callable[[], None],
        mark_stopping: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(config)
        self._interrupt_waiters = interrupt_waiters
        self._mark_stopping = mark_stopping

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if self._mark_stopping is not None:
            self._mark_stopping()
        self._interrupt_waiters()
        super().handle_exit(sig, frame)
