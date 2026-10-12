"""FastAPI application for receiving images and relaying their OCR text."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path
from types import FrameType
from typing import Callable

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
import uvicorn

from text_relay.config import Settings
from text_relay.ocr import OCRStrategy, create_ocr_strategy
from text_relay.queue import OCRWorkItem, OCRWorkQueue
from text_relay.store import OCRJob, OCRResult, ResultStore

ACCEPTED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


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


def _result_payload(result: OCRResult) -> dict[str, str]:
    return {
        "id": result.id,
        "created_at": result.created_at.isoformat().replace("+00:00", "Z"),
        "text": result.text,
        "image_checksum": result.image_checksum,
    }


def _job_payload(job: OCRJob) -> dict[str, str | dict[str, str] | None]:
    return {
        "id": job.id,
        "created_at": job.created_at.isoformat().replace("+00:00", "Z"),
        "image_checksum": job.image_checksum,
        "status": job.status,
        "result": _result_payload(job.result) if job.result is not None else None,
    }


def create_app(
    settings: Settings | None = None, *, ocr_strategy: OCRStrategy | None = None
) -> FastAPI:
    """Create an application using one selected or injected OCR strategy."""
    resolved_settings = settings or Settings.from_environment()
    selected_strategy = ocr_strategy or create_ocr_strategy(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await app.state.ocr_queue.start()
        try:
            yield
        finally:
            app.state.is_shutting_down = True
            app.state.store.interrupt_waiters()
            await app.state.ocr_queue.close()
            close = getattr(selected_strategy, "aclose", None)
            if close is not None:
                await close()

    app = FastAPI(title="TextRelay", lifespan=lifespan)
    app.state.store = ResultStore(resolved_settings.max_result_history)
    app.state.ocr_strategy = selected_strategy
    app.state.ocr_queue = OCRWorkQueue(
        selected_strategy,
        app.state.store,
        resolved_settings.ocr_workers,
        resolved_settings.ocr_retries,
    )
    app.state.is_shutting_down = False

    @app.get("/", response_class=FileResponse)
    async def index() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/textrelay-icon.png", response_class=FileResponse)
    async def app_icon() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "textrelay-icon.png")

    @app.get("/api/results")
    async def recent_results(
        after: str | None = Query(default=None),
        wait: bool = Query(default=False),
    ) -> dict[str, list[dict[str, str | dict[str, str] | None]] | str | None]:
        if wait:
            try:
                await asyncio.to_thread(
                    app.state.store.wait_for_change,
                    after,
                    resolved_settings.long_poll_timeout_seconds,
                )
            except asyncio.CancelledError:
                app.state.store.interrupt_waiters()
                raise
        payload: dict[str, list[dict[str, str | dict[str, str] | None]] | str | None] = {
            "results": [_result_payload(result) for result in app.state.store.recent()],
            "jobs": [_job_payload(job) for job in app.state.store.jobs()],
            "cursor": app.state.store.change_id(),
        }
        if app.state.is_shutting_down:
            payload["server_status"] = "stopping"
        return payload

    @app.post("/api/ocr", status_code=202)
    async def perform_ocr(
        file: UploadFile | None = File(default=None),
    ) -> dict[str, str | dict[str, str] | None]:
        if file is None:
            raise HTTPException(status_code=400, detail="An image file is required.")
        content_type = file.content_type
        if content_type not in ACCEPTED_CONTENT_TYPES:
            raise HTTPException(status_code=415, detail="Unsupported image type.")

        try:
            chunks: list[bytes] = []
            total_size = 0
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > resolved_settings.max_upload_size:
                    raise HTTPException(status_code=413, detail="Image is too large.")
                chunks.append(chunk)

            if total_size == 0:
                raise HTTPException(status_code=400, detail="Image upload is empty.")
            image = b"".join(chunks)
            image_checksum = sha256(image).hexdigest()

            job = app.state.store.enqueue(image_checksum, image, content_type)
            if job is None:
                raise HTTPException(
                    status_code=409,
                    detail="This image has already been submitted.",
                )
            await app.state.ocr_queue.submit(OCRWorkItem(job.id, image, content_type))
            return _job_payload(job)
        finally:
            await file.close()

    @app.post("/api/jobs/{job_id}/retry", status_code=202)
    async def retry_ocr(job_id: str) -> dict[str, str | dict[str, str] | None]:
        job = app.state.store.retry(job_id)
        if job is None:
            raise HTTPException(
                status_code=409,
                detail="Only retained failed extractions can be retried.",
            )
        await app.state.ocr_queue.submit(
            OCRWorkItem(job.id, job.image, job.content_type)
        )
        return _job_payload(job)

    return app


app = create_app()


def main() -> None:
    """Run the local server and release long polls when it receives an exit signal."""
    settings = Settings.from_environment()
    server_app = create_app(settings)
    config = uvicorn.Config(
        server_app,
        host=settings.host,
        port=settings.port,
    )
    try:
        LongPollShutdownServer(
            config,
            server_app.state.store.interrupt_waiters,
            lambda: setattr(server_app.state, "is_shutting_down", True),
        ).run()
    except KeyboardInterrupt:
        # Uvicorn replays Ctrl+C after restoring the previous signal handler.
        pass


if __name__ == "__main__":
    main()
