"""FastAPI application for receiving images and relaying their OCR text."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
import uvicorn

from text_relay.config import Settings
from text_relay.ocr import OCRError, OCRStrategy, create_ocr_strategy
from text_relay.store import OCRResult, ResultStore

LOGGER = logging.getLogger(__name__)
ACCEPTED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _result_payload(result: OCRResult) -> dict[str, str]:
    return {"id": result.id, "created_at": result.created_at.isoformat().replace("+00:00", "Z"), "text": result.text}


def create_app(
    settings: Settings | None = None, *, ocr_strategy: OCRStrategy | None = None
) -> FastAPI:
    """Create an application using one selected or injected OCR strategy."""
    resolved_settings = settings or Settings.from_environment()
    selected_strategy = ocr_strategy or create_ocr_strategy(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        close = getattr(selected_strategy, "aclose", None)
        if close is not None:
            await close()

    app = FastAPI(title="TextRelay", lifespan=lifespan)
    app.state.store = ResultStore(resolved_settings.max_result_history)
    app.state.ocr_strategy = selected_strategy

    @app.get("/", response_class=FileResponse)
    async def index() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/api/results")
    async def recent_results(
        after: str | None = Query(default=None),
        wait: bool = Query(default=False),
    ) -> dict[str, list[dict[str, str]]]:
        if wait:
            records = await asyncio.to_thread(
                app.state.store.wait_for_change,
                after,
                resolved_settings.long_poll_timeout_seconds,
            )
        else:
            records = app.state.store.recent()
        return {"results": [_result_payload(result) for result in records]}

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
            try:
                text = await selected_strategy.extract_text(b"".join(chunks), content_type)
            except OCRError as error:
                LOGGER.warning("OCR failed: %s", error)
                raise HTTPException(status_code=422, detail="OCR failed to process the image.") from error
            return _result_payload(app.state.store.add(text))
        finally:
            await file.close()

    return app


app = create_app()


def main() -> None:
    """Run the local server using the documented LAN-friendly defaults."""
    settings = Settings.from_environment()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
