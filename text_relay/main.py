"""FastAPI application for receiving images and relaying their OCR text."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from hashlib import sha256
import logging
from pathlib import Path
from types import FrameType
from typing import Callable

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
import uvicorn

from text_relay.config import Settings
from text_relay.ocr import OCRError, OCRStrategy, create_ocr_strategy
from text_relay.store import OCRResult, ResultStore

LOGGER = logging.getLogger(__name__)
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


def create_app(
    settings: Settings | None = None, *, ocr_strategy: OCRStrategy | None = None
) -> FastAPI:
    """Create an application using one selected or injected OCR strategy."""
    resolved_settings = settings or Settings.from_environment()
    selected_strategy = ocr_strategy or create_ocr_strategy(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            app.state.is_shutting_down = True
            app.state.store.interrupt_waiters()
            close = getattr(selected_strategy, "aclose", None)
            if close is not None:
                await close()

    app = FastAPI(title="TextRelay", lifespan=lifespan)
    app.state.store = ResultStore(resolved_settings.max_result_history)
    app.state.ocr_strategy = selected_strategy
    app.state.ocr_lock = asyncio.Lock()
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
    ) -> dict[str, list[dict[str, str]] | str]:
        if wait:
            try:
                records = await asyncio.to_thread(
                    app.state.store.wait_for_change,
                    after,
                    resolved_settings.long_poll_timeout_seconds,
                )
            except asyncio.CancelledError:
                app.state.store.interrupt_waiters()
                raise
        else:
            records = app.state.store.recent()
        payload: dict[str, list[dict[str, str]] | str] = {
            "results": [_result_payload(result) for result in records]
        }
        if app.state.is_shutting_down:
            payload["server_status"] = "stopping"
        return payload

    @app.post("/api/ocr")
    async def perform_ocr(file: UploadFile | None = File(default=None)) -> dict[str, str]:
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

            async with app.state.ocr_lock:
                existing_result = app.state.store.find_by_image_checksum(image_checksum)
                if existing_result is not None:
                    raise HTTPException(
                        status_code=409,
                        detail="This image has already been processed.",
                    )
                try:
                    text = await selected_strategy.extract_text(image, content_type)
                except OCRError as error:
                    LOGGER.warning("OCR failed: %s", error)
                    raise HTTPException(status_code=422, detail="OCR failed to process the image.") from error
                return _result_payload(app.state.store.add(text, image_checksum))
        finally:
            await file.close()

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
