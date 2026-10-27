import signal
import time
from hashlib import sha256
from pathlib import Path
from threading import Event, Thread

from fastapi.testclient import TestClient
import pytest
import uvicorn

from text_relay.config import Settings
from text_relay import main
from text_relay import assets as asset_module
from text_relay.main import LongPollShutdownServer, create_app
from text_relay.ocr import OCRExecutionError


class FakeOCRStrategy:
    def __init__(self, text: str = "Expected transcription", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[tuple[bytes, str]] = []

    async def extract_text(self, image: bytes, content_type: str) -> str:
        self.calls.append((image, content_type))
        if self.error is not None:
            raise self.error
        return self.text


class UnavailableAssets:
    """Keep unrelated API tests independent from the external Cropper CDN."""

    directory = Path.cwd() / ".cache"

    def refresh(self) -> None:
        pass

    def get(self, name: str) -> bytes:
        raise RuntimeError(f"{name} is unavailable")


_active_clients: list[TestClient] = []


@pytest.fixture(autouse=True)
def close_test_clients():
    yield
    while _active_clients:
        _active_clients.pop().__exit__(None, None, None)


def make_client(
    strategy: FakeOCRStrategy,
    *,
    maximum_size: int = 1024,
    history_size: int = 2,
    workers: int = 2,
    assets=None,
) -> TestClient:
    client = TestClient(
        create_app(
            Settings(
                max_upload_size=maximum_size,
                max_result_history=history_size,
                ocr_workers=workers,
            ),
            ocr_strategy=strategy,
            assets=assets or UnavailableAssets(),
        )
    )
    client.__enter__()
    _active_clients.append(client)
    return client


def image_request(client: TestClient):
    return client.post("/api/ocr", files={"file": ("photo.png", b"image", "image/png")})


def result_payload(result) -> dict[str, str]:
    return {
        "id": result.id,
        "created_at": result.created_at.isoformat().replace("+00:00", "Z"),
        "text": result.text,
        "image_checksum": result.image_checksum,
    }


def wait_for_job(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        jobs = client.get("/api/results").json()["jobs"]
        job = next(job for job in jobs if job["id"] == job_id)
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    pytest.fail("OCR job did not finish")


def test_swagger_documents_the_api_contract() -> None:
    client = make_client(FakeOCRStrategy())

    docs = client.get("/docs")
    schema_response = client.get("/openapi.json")

    assert docs.status_code == 200
    assert "/openapi.json" in docs.text
    assert schema_response.status_code == 200

    paths = schema_response.json()["paths"]
    assert set(paths) == {
        "/api/results",
        "/api/ocr-profiles",
        "/api/ocr-profiles/active",
        "/api/ocr",
        "/api/jobs/{job_id}/retry",
    }
    upload = paths["/api/ocr"]["post"]
    assert upload["responses"]["202"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/OCRJobResponse"
    )
    assert {"400", "409", "413", "415"}.issubset(upload["responses"])
    activate = paths["/api/ocr-profiles/active"]["put"]
    body_schema = activate["requestBody"]["content"]["application/json"]["schema"]
    assert body_schema["required"] == ["profile_id"]
    assert body_schema["properties"]["profile_id"]["type"] == "string"


def test_root_serves_mobile_upload_and_long_polling_interface() -> None:
    client = make_client(FakeOCRStrategy())
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<link rel="icon" type="image/png" href="/textrelay-icon.png">' in response.text
    assert '<link rel="stylesheet" href="/styles.css">' in response.text
    assert '<img class="brand-mark" src="/textrelay-icon.png"' in response.text
    assert 'accept="image/jpeg,image/png,image/webp"' in response.text
    assert 'capture="environment"' in response.text
    assert 'src="/assets/cropper.js"' in response.text
    assert '<script type="module" src="/app.js"></script>' in response.text
    assert '<script>' not in response.text
    app_script = client.get("/app.js")
    upload_script = client.get("/image-upload.js")
    for script in (app_script, upload_script):
        assert script.status_code == 200
        assert "javascript" in script.headers["content-type"]
    assert 'from "./image-upload.js"' in app_script.text
    assert "window.Cropper?.default" in upload_script.text
    assert 'id="crop-dialog"' in response.text
    assert 'name="file"' in response.text
    assert 'selection.$toCanvas' in upload_script.text
    assert 'URL.revokeObjectURL' in upload_script.text
    assert 'url.searchParams.set("wait", "true")' in app_script.text
    assert "window.setInterval" not in app_script.text
    assert "navigator.clipboard.writeText" in app_script.text
    assert "RESULTS_REQUEST_TIMEOUT_MS" in app_script.text
    assert 'payload.server_status === "stopping"' in app_script.text
    assert "The server is shutting down." in app_script.text
    assert "The server is not responding." in app_script.text
    assert "Extraction queue" in response.text
    assert "Image queued for text extraction." in app_script.text


def test_app_icon_is_served_as_a_png() -> None:
    response = make_client(FakeOCRStrategy()).get("/textrelay-icon.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_stylesheet_is_served() -> None:
    response = make_client(FakeOCRStrategy()).get("/styles.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert ".file-picker.dragging" in response.text
    assert "height: 100dvh" in response.text
    assert ".cropper-container { height: auto;" in response.text


def test_cropper_assets_are_refreshed_at_startup_with_etags(monkeypatch, tmp_path) -> None:
    requests: list[object] = []

    class DownloadedAsset:
        headers = {"ETag": '"cropper-version"'}

        def __init__(self, asset: bytes) -> None:
            self.asset = asset

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self) -> bytes:
            return self.asset

    def download(request, timeout):
        requests.append(request)
        return DownloadedAsset(f"asset from {request.full_url}".encode())

    monkeypatch.setattr(asset_module, "urlopen", download)
    cache = main.AssetCache(tmp_path)
    client = make_client(FakeOCRStrategy(), assets=cache)

    first_script = client.get("/assets/cropper.js")
    second_script = client.get("/assets/cropper.js")

    assert first_script.status_code == 200
    assert first_script.headers["content-type"].startswith("text/javascript")
    assert second_script.content == first_script.content
    assert [request.full_url for request in requests] == [
        asset_module.ASSETS["cropper.js"][0]
    ]
    assert (tmp_path / "cropper.js.etag").read_text() == '"cropper-version"'

    def unchanged(request, timeout):
        requests.append(request)
        raise asset_module.HTTPError(request.full_url, 304, "Not Modified", {}, None)

    monkeypatch.setattr(asset_module, "urlopen", unchanged)
    make_client(FakeOCRStrategy(), assets=cache)

    assert requests[-1].get_header("If-none-match") == '"cropper-version"'


def test_missing_cropper_asset_returns_not_found_after_a_failed_startup_refresh(monkeypatch, tmp_path) -> None:
    def unavailable(*_args, **_kwargs):
        raise asset_module.URLError("offline")

    monkeypatch.setattr(asset_module, "urlopen", unavailable)
    client = make_client(FakeOCRStrategy(), assets=main.AssetCache(tmp_path))

    response = client.get("/assets/cropper.js")

    assert response.status_code == 404


def test_missing_upload_is_rejected() -> None:
    response = make_client(FakeOCRStrategy()).post("/api/ocr")
    assert (response.status_code, response.json()["detail"]) == (400, "An image file is required.")


def test_upload_queues_a_job_and_adds_its_completed_result_to_history() -> None:
    strategy = FakeOCRStrategy("Extracted text")
    client = make_client(strategy)
    response = image_request(client)
    assert response.status_code == 202
    job = response.json()
    assert job["status"] in {"queued", "processing"}
    assert job["image_checksum"] == sha256(b"image").hexdigest()
    completed = wait_for_job(client, job["id"])
    assert completed["status"] == "completed"
    assert completed["result"]["text"] == "Extracted text"
    assert strategy.calls == [(b"image", "image/png")]
    assert client.get("/api/results").json()["results"] == [completed["result"]]


def test_long_poll_returns_immediately_when_results_have_changed() -> None:
    client = make_client(FakeOCRStrategy())
    latest = client.app.state.store.add("new result", "checksum")

    response = client.get("/api/results?wait=true&after=older-result")

    payload = response.json()
    assert payload["results"] == [result_payload(latest)]
    assert payload["jobs"] == []
    assert payload["cursor"]


def test_results_are_newest_first_and_bounded() -> None:
    texts = iter(["first", "second", "third"])
    strategy = FakeOCRStrategy()
    async def extract(image: bytes, content_type: str) -> str:
        strategy.calls.append((image, content_type))
        return next(texts)
    strategy.extract_text = extract  # type: ignore[method-assign]
    client = make_client(strategy)
    for image in (b"first-image", b"second-image", b"third-image"):
        response = client.post(
            "/api/ocr",
            files={"file": ("photo.png", image, "image/png")},
        )
        assert response.status_code == 202
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        records = client.get("/api/results").json()["results"]
        if len(records) == 2:
            break
        time.sleep(0.01)
    assert [item["text"] for item in records] == ["third", "second"]


def test_duplicate_image_is_rejected_without_running_ocr_again() -> None:
    strategy = FakeOCRStrategy("Extracted text")
    client = make_client(strategy)

    original = image_request(client)
    duplicate = image_request(client)

    assert original.status_code == 202
    assert (duplicate.status_code, duplicate.json()) == (
        409,
        {"detail": "This image has already been submitted with the active OCR profile."},
    )
    assert strategy.calls == [(b"image", "image/png")]
    completed = wait_for_job(client, original.json()["id"])
    assert client.get("/api/results").json()["results"] == [completed["result"]]


def test_invalid_and_empty_uploads_are_rejected() -> None:
    client = make_client(FakeOCRStrategy())
    invalid = client.post("/api/ocr", files={"file": ("note.txt", b"text", "text/plain")})
    empty = client.post("/api/ocr", files={"file": ("photo.png", b"", "image/png")})
    assert (invalid.status_code, invalid.json()["detail"]) == (415, "Unsupported image type.")
    assert (empty.status_code, empty.json()["detail"]) == (400, "Image upload is empty.")


def test_ocr_profiles_are_listed_and_can_be_activated() -> None:
    client = make_client(FakeOCRStrategy())

    listed = client.get("/api/ocr-profiles")
    assert listed.status_code == 200
    assert listed.json()["active_profile"] == "local"
    assert listed.json()["profiles"][0] == {
        "id": "local", "label": "Local Tesseract", "provider": "tesseract"
    }

    changed = client.put("/api/ocr-profiles/active", json={"profile_id": "local"})
    assert changed.status_code == 200
    assert changed.json()["active_profile"] == "local"


def test_unknown_ocr_profile_is_rejected() -> None:
    response = make_client(FakeOCRStrategy()).put(
        "/api/ocr-profiles/active", json={"profile_id": "unknown"}
    )
    assert (response.status_code, response.json()) == (404, {"detail": "OCR profile was not found."})


def test_oversized_upload_is_rejected() -> None:
    client = make_client(FakeOCRStrategy(), maximum_size=3)
    response = image_request(client)
    assert (response.status_code, response.json()["detail"]) == (413, "Image is too large.")


def test_ocr_failures_are_visible_as_failed_jobs() -> None:
    client = make_client(FakeOCRStrategy(error=OCRExecutionError("details not for clients")))
    response = image_request(client)

    assert response.status_code == 202
    assert wait_for_job(client, response.json()["id"])["status"] == "failed"


def test_worker_limit_allows_parallel_extraction() -> None:
    started = Event()
    release = Event()

    class BlockingOCRStrategy(FakeOCRStrategy):
        async def extract_text(self, image: bytes, content_type: str) -> str:
            self.calls.append((image, content_type))
            if len(self.calls) == 2:
                started.set()
            await __import__("asyncio").to_thread(release.wait, 1)
            return image.decode()

    strategy = BlockingOCRStrategy()
    client = make_client(strategy, history_size=4, workers=2)
    first = client.post("/api/ocr", files={"file": ("one.png", b"one", "image/png")})
    second = client.post("/api/ocr", files={"file": ("two.png", b"two", "image/png")})

    assert (first.status_code, second.status_code) == (202, 202)
    assert started.wait(timeout=1)
    release.set()
    assert wait_for_job(client, first.json()["id"])["status"] == "completed"
    assert wait_for_job(client, second.json()["id"])["status"] == "completed"


def test_shutdown_signal_releases_all_long_polls_immediately() -> None:
    app = create_app(Settings())
    server = LongPollShutdownServer(
        uvicorn.Config(app),
        app.state.store.interrupt_waiters,
        lambda: setattr(app.state, "is_shutting_down", True),
    )
    received: list[list] = []
    thread = Thread(
        target=lambda: received.append(
            app.state.store.wait_for_change(None, timeout_seconds=10)
        )
    )

    thread.start()
    server.handle_exit(signal.SIGTERM, None)
    thread.join(timeout=0.1)

    assert not thread.is_alive()
    assert received == [[]]
    assert server.should_exit
    response = TestClient(app).get("/api/results")
    assert response.json()["server_status"] == "stopping"


def test_main_creates_a_server_with_the_configured_address(monkeypatch) -> None:
    settings = Settings(host="127.0.0.1", port=9876)
    captured: dict[str, object] = {}
    monkeypatch.setattr(main.Settings, "from_environment", lambda: settings)
    monkeypatch.setattr(main.uvicorn, "Config", lambda app, **kwargs: captured.update(kwargs))
    monkeypatch.setattr(
        main,
        "LongPollShutdownServer",
        lambda config, interrupt, mark_stopping: type("Server", (), {"run": lambda self: None})(),
    )

    main.main()

    assert captured == {
        "host": "127.0.0.1",
        "port": 9876,
    }


def test_main_suppresses_uvicorns_replayed_keyboard_interrupt(monkeypatch) -> None:
    class InterruptingServer:
        def run(self) -> None:
            raise KeyboardInterrupt

    monkeypatch.setattr(main.uvicorn, "Config", lambda app, **kwargs: None)
    monkeypatch.setattr(
        main,
        "LongPollShutdownServer",
        lambda config, interrupt, mark_stopping: InterruptingServer(),
    )

    main.main()
