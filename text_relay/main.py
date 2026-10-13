"""FastAPI application for receiving images and relaying their OCR text."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from hashlib import sha256
import logging
from pathlib import Path
from threading import Lock
from types import FrameType
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import Body, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
import uvicorn

from text_relay.config import OCRProfileCatalog, Settings
from text_relay.ocr import OCRConfigurationError, OCRProfileManager, OCRStrategy
from text_relay.queue import OCRWorkItem, OCRWorkQueue
from text_relay.store import OCRJob, OCRResult, ResultStore

ACCEPTED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
CROPPER_ASSETS = {
    "cropper.js": (
        "https://cdn.jsdelivr.net/npm/cropperjs@2.2.0/dist/cropper.js",
        "application/javascript",
    ),
}
logger = logging.getLogger(__name__)


class CropperAssetCache:
    """Fetch pinned Cropper.js assets once, then serve the local cached copies."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._lock = Lock()

    @property
    def directory(self) -> Path:
        """Directory served by the application's assets mount."""
        return self._directory

    def refresh(self) -> None:
        """Refresh every asset, keeping cached files when the CDN is unavailable."""
        failure: RuntimeError | None = None
        for name in CROPPER_ASSETS:
            try:
                self._refresh(name)
            except RuntimeError as error:
                failure = failure or error
        if failure is not None:
            raise failure

    def _refresh(self, name: str) -> None:
        url, _ = CROPPER_ASSETS[name]
        path = self._directory / name
        etag_path = path.with_suffix(f"{path.suffix}.etag")
        with self._lock:
            headers = {"User-Agent": "TextRelay"}
            if etag_path.is_file():
                etag = etag_path.read_text(encoding="utf-8").strip()
                if etag:
                    headers["If-None-Match"] = etag
            try:
                with urlopen(Request(url, headers=headers), timeout=15) as response:
                    asset = response.read()
                    etag = response.headers.get("ETag")
            except HTTPError as error:
                if error.code == 304 and path.is_file():
                    return
                raise RuntimeError("Could not retrieve the Cropper.js asset.") from error
            except URLError as error:
                if path.is_file():
                    return
                raise RuntimeError("Could not retrieve the Cropper.js asset.") from error
            self._directory.mkdir(parents=True, exist_ok=True)
            self._write(path, asset)
            if etag:
                self._write(etag_path, etag.encode())

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        temporary_path.write_bytes(content)
        temporary_path.replace(path)


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
        "profile_id": job.profile_id,
        "result": _result_payload(job.result) if job.result is not None else None,
    }


def create_app(
    settings: Settings | None = None,
    *,
    ocr_strategy: OCRStrategy | None = None,
    cropper_assets: CropperAssetCache | None = None,
) -> FastAPI:
    """Create an application using the configured OCR profile catalog."""
    resolved_settings = settings or Settings.from_environment()
    profile_manager = OCRProfileManager(
        OCRProfileCatalog.from_file(Path.cwd() / "ocr-profiles.toml")
    )
    injected_profile_id = profile_manager.active_profile_id if ocr_strategy is not None else None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            await asyncio.to_thread(app.state.cropper_assets.refresh)
        except RuntimeError:
            logger.warning("Cropper.js assets could not be refreshed at startup.")
        await app.state.ocr_queue.start()
        try:
            yield
        finally:
            app.state.is_shutting_down = True
            app.state.store.interrupt_waiters()
            await app.state.ocr_queue.close()
            if ocr_strategy is not None:
                close = getattr(ocr_strategy, "aclose", None)
                if close is not None:
                    await close()
            await profile_manager.aclose()

    app = FastAPI(title="TextRelay", lifespan=lifespan)
    app.state.store = ResultStore(resolved_settings.max_result_history)
    app.state.ocr_profiles = profile_manager
    app.state.ocr_queue = OCRWorkQueue(
        app.state.store,
        resolved_settings.ocr_workers,
        resolved_settings.ocr_retries,
    )
    app.state.cropper_assets = cropper_assets or CropperAssetCache(Path.cwd() / ".cache")
    app.state.cropper_assets.directory.mkdir(parents=True, exist_ok=True)
    app.state.is_shutting_down = False

    def strategy_for(profile_id: str) -> OCRStrategy:
        if profile_id == injected_profile_id:
            assert ocr_strategy is not None
            return ocr_strategy
        return profile_manager.strategy_for(profile_id)

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
            "active_profile": profile_manager.active_profile_id,
        }
        if app.state.is_shutting_down:
            payload["server_status"] = "stopping"
        return payload

    @app.get("/api/ocr-profiles")
    async def ocr_profiles() -> dict[str, object]:
        return profile_manager.payload()

    @app.put("/api/ocr-profiles/active")
    async def activate_ocr_profile(payload: dict[str, str] = Body(...)) -> dict[str, object]:
        profile_id = payload.get("profile_id")
        if not profile_id:
            raise HTTPException(status_code=422, detail="profile_id is required.")
        try:
            profile_manager.activate(profile_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="OCR profile was not found.") from None
        except OCRConfigurationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        app.state.store.publish_change()
        return profile_manager.payload()

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

            profile_id = profile_manager.active_profile_id
            strategy = strategy_for(profile_id)
            job = app.state.store.enqueue(image_checksum, image, content_type, profile_id)
            if job is None:
                raise HTTPException(
                    status_code=409,
                    detail="This image has already been submitted with the active OCR profile.",
                )
            await app.state.ocr_queue.submit(OCRWorkItem(job.id, image, content_type, strategy))
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
            OCRWorkItem(job.id, job.image, job.content_type, strategy_for(job.profile_id))
        )
        return _job_payload(job)

    app.mount(
        "/assets",
        StaticFiles(directory=app.state.cropper_assets.directory),
        name="assets",
    )
    app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")

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
