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
    image_checksum: str


@dataclass(frozen=True)
class OCRJob:
    """The client-visible lifecycle of one submitted image."""

    id: str
    created_at: datetime
    image_checksum: str
    status: str
    result: OCRResult | None = None


class ResultStore:
    """Thread-safe newest-first history with a fixed maximum size."""

    def __init__(self, maximum_size: int) -> None:
        if maximum_size <= 0:
            raise ValueError("maximum_size must be positive")
        self._results: deque[OCRResult] = deque(maxlen=maximum_size)
        self._jobs: deque[OCRJob] = deque()
        self._jobs_by_checksum: dict[str, OCRJob] = {}
        self._changed = Condition()
        self._waiters_interrupted = False
        self._change_id: str | None = None

    def add(self, text: str, image_checksum: str) -> OCRResult:
        """Create and retain one result, returning the new record."""
        result = OCRResult(
            id=str(uuid4()),
            created_at=datetime.now(UTC),
            text=text,
            image_checksum=image_checksum,
        )
        with self._changed:
            self._results.appendleft(result)
            self._publish_change()
        return result

    def enqueue(self, image_checksum: str) -> OCRJob | None:
        """Reserve an image for OCR unless it is already queued or retained."""
        with self._changed:
            if image_checksum in self._jobs_by_checksum:
                return None
            job = OCRJob(
                id=str(uuid4()),
                created_at=datetime.now(UTC),
                image_checksum=image_checksum,
                status="queued",
            )
            self._jobs.appendleft(job)
            self._jobs_by_checksum[image_checksum] = job
            self._publish_change()
            return job

    def mark_processing(self, job_id: str) -> OCRJob | None:
        return self._replace_job(job_id, status="processing")

    def complete(self, job_id: str, text: str) -> OCRJob | None:
        with self._changed:
            job = self._get_job(job_id)
            if job is None:
                return None
            result = OCRResult(
                id=str(uuid4()),
                created_at=datetime.now(UTC),
                text=text,
                image_checksum=job.image_checksum,
            )
            self._results.appendleft(result)
            return self._replace_job_locked(job, status="completed", result=result)

    def fail(self, job_id: str) -> OCRJob | None:
        return self._replace_job(job_id, status="failed")

    def find_by_image_checksum(self, image_checksum: str) -> OCRResult | None:
        """Return the retained result for an image checksum, if one exists."""
        with self._changed:
            return next(
                (result for result in self._results if result.image_checksum == image_checksum),
                None,
            )

    def recent(self) -> list[OCRResult]:
        """Return a stable newest-first snapshot of the current history."""
        with self._changed:
            return list(self._results)

    def jobs(self) -> list[OCRJob]:
        """Return a stable newest-first snapshot of all visible OCR jobs."""
        with self._changed:
            return list(self._jobs)

    def change_id(self) -> str | None:
        with self._changed:
            return self._change_id

    def wait_for_change(
        self, change_id: str | None, timeout_seconds: float
    ) -> list[OCRResult]:
        """Return results after any visible OCR state change or the timeout."""
        with self._changed:
            self._changed.wait_for(
                lambda: self._waiters_interrupted
                or (
                    self._change_id is not None and self._change_id != change_id
                ),
                timeout=timeout_seconds,
            )
            return list(self._results)

    def interrupt_waiters(self) -> None:
        """Wake long-poll threads so shutdown does not wait for their timeout."""
        with self._changed:
            self._waiters_interrupted = True
            self._changed.notify_all()

    def fail_unfinished_jobs(self) -> None:
        """Make queue shutdown visible to clients instead of leaving stale work."""
        with self._changed:
            changed = False
            for job in tuple(self._jobs):
                if job.status in {"queued", "processing"}:
                    self._replace_job_locked(job, status="failed", notify=False)
                    changed = True
            if changed:
                self._publish_change()

    def _replace_job(self, job_id: str, *, status: str) -> OCRJob | None:
        with self._changed:
            job = self._get_job(job_id)
            if job is None:
                return None
            return self._replace_job_locked(job, status=status)

    def _replace_job_locked(
        self, job: OCRJob, *, status: str, result: OCRResult | None = None, notify: bool = True
    ) -> OCRJob:
        replacement = OCRJob(
            id=job.id,
            created_at=job.created_at,
            image_checksum=job.image_checksum,
            status=status,
            result=result,
        )
        self._jobs.remove(job)
        self._jobs.appendleft(replacement)
        self._jobs_by_checksum[job.image_checksum] = replacement
        if notify:
            self._publish_change()
            self._trim_finished_jobs()
        return replacement

    def _get_job(self, job_id: str) -> OCRJob | None:
        return next((job for job in self._jobs if job.id == job_id), None)

    def _publish_change(self) -> None:
        self._change_id = str(uuid4())
        self._changed.notify_all()

    def _trim_finished_jobs(self) -> None:
        finished = [job for job in self._jobs if job.status in {"completed", "failed"}]
        for job in finished[self._results.maxlen :]:
            self._jobs.remove(job)
            self._jobs_by_checksum.pop(job.image_checksum, None)
