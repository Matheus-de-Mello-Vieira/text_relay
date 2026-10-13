"""FastAPI application for receiving images and relaying their OCR text."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from text_relay.assets import AssetCache
from text_relay.config import OCRProfileCatalog, Settings
from text_relay.ocr import OCRProfileManager, OCRStrategy
from text_relay.queue import OCRWorkQueue
from text_relay.routes import router
from text_relay.server import LongPollShutdownServer
from text_relay.store import ResultStore

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    ocr_strategy: OCRStrategy | None = None,
    assets: AssetCache | None = None,
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
            await asyncio.to_thread(app.state.assets.refresh)
        except RuntimeError:
            logger.warning("Assets could not be refreshed at startup.")
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
    app.state.settings = resolved_settings
    app.state.store = ResultStore(resolved_settings.max_result_history)
    app.state.ocr_profiles = profile_manager
    app.state.ocr_queue = OCRWorkQueue(
        app.state.store,
        resolved_settings.ocr_workers,
        resolved_settings.ocr_retries,
    )
    app.state.assets = assets or AssetCache(Path.cwd() / ".cache")
    app.state.assets.directory.mkdir(parents=True, exist_ok=True)
    app.state.is_shutting_down = False

    def strategy_for(profile_id: str) -> OCRStrategy:
        if profile_id == injected_profile_id:
            assert ocr_strategy is not None
            return ocr_strategy
        return profile_manager.strategy_for(profile_id)

    app.state.strategy_for = strategy_for
    app.include_router(router)
    app.mount(
        "/assets",
        StaticFiles(directory=app.state.assets.directory),
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
