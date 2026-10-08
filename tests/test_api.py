import signal
from hashlib import sha256
from threading import Thread

from fastapi.testclient import TestClient
import uvicorn

from text_relay.config import Settings
from text_relay import main
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


def make_client(strategy: FakeOCRStrategy, *, maximum_size: int = 1024, history_size: int = 2) -> TestClient:
    return TestClient(create_app(Settings(max_upload_size=maximum_size, max_result_history=history_size), ocr_strategy=strategy))


def image_request(client: TestClient):
    return client.post("/api/ocr", files={"file": ("photo.png", b"image", "image/png")})


def result_payload(result) -> dict[str, str]:
    return {
        "id": result.id,
        "created_at": result.created_at.isoformat().replace("+00:00", "Z"),
        "text": result.text,
        "image_checksum": result.image_checksum,
    }


def test_root_serves_mobile_upload_and_long_polling_interface() -> None:
    response = make_client(FakeOCRStrategy()).get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<link rel="icon" type="image/png" href="/textrelay-icon.png">' in response.text
    assert '<img class="brand-mark" src="/textrelay-icon.png"' in response.text
    assert 'accept="image/*"' in response.text
    assert 'capture="environment"' in response.text
    assert 'url.searchParams.set("wait", "true")' in response.text
    assert "window.setInterval" not in response.text
    assert "navigator.clipboard.writeText" in response.text


def test_app_icon_is_served_as_a_png() -> None:
    response = make_client(FakeOCRStrategy()).get("/textrelay-icon.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_missing_upload_is_rejected() -> None:
    response = make_client(FakeOCRStrategy()).post("/api/ocr")
    assert (response.status_code, response.json()["detail"]) == (400, "An image file is required.")


def test_upload_returns_result_and_adds_it_to_history() -> None:
    strategy = FakeOCRStrategy("Extracted text")
    client = make_client(strategy)
    response = image_request(client)
    assert response.status_code == 200
    result = response.json()
    assert result["text"] == "Extracted text"
    assert result["image_checksum"] == sha256(b"image").hexdigest()
    assert strategy.calls == [(b"image", "image/png")]
    assert result["id"] and result["created_at"].endswith("Z")
    assert client.get("/api/results").json() == {"results": [result]}


def test_long_poll_returns_immediately_when_results_have_changed() -> None:
    client = make_client(FakeOCRStrategy())
    latest = client.app.state.store.add("new result", "checksum")

    response = client.get("/api/results?wait=true&after=older-result")

    assert response.json() == {"results": [result_payload(latest)]}


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
        assert response.status_code == 200
    assert [item["text"] for item in client.get("/api/results").json()["results"]] == ["third", "second"]


def test_duplicate_image_is_rejected_without_running_ocr_again() -> None:
    strategy = FakeOCRStrategy("Extracted text")
    client = make_client(strategy)

    original = image_request(client)
    duplicate = image_request(client)

    assert original.status_code == 200
    assert (duplicate.status_code, duplicate.json()) == (
        409,
        {"detail": "This image has already been processed."},
    )
    assert strategy.calls == [(b"image", "image/png")]
    assert client.get("/api/results").json() == {"results": [original.json()]}


def test_invalid_and_empty_uploads_are_rejected() -> None:
    client = make_client(FakeOCRStrategy())
    invalid = client.post("/api/ocr", files={"file": ("note.txt", b"text", "text/plain")})
    empty = client.post("/api/ocr", files={"file": ("photo.png", b"", "image/png")})
    assert (invalid.status_code, invalid.json()["detail"]) == (415, "Unsupported image type.")
    assert (empty.status_code, empty.json()["detail"]) == (400, "Image upload is empty.")


def test_oversized_upload_is_rejected() -> None:
    client = make_client(FakeOCRStrategy(), maximum_size=3)
    response = image_request(client)
    assert (response.status_code, response.json()["detail"]) == (413, "Image is too large.")


def test_ocr_failures_are_controlled() -> None:
    response = image_request(make_client(FakeOCRStrategy(error=OCRExecutionError("details not for clients"))))
    assert (response.status_code, response.json()["detail"]) == (422, "OCR failed to process the image.")


def test_shutdown_signal_releases_all_long_polls_immediately() -> None:
    app = create_app(Settings())
    server = LongPollShutdownServer(
        uvicorn.Config(app),
        app.state.store.interrupt_waiters,
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


def test_main_creates_a_server_with_the_configured_address(monkeypatch) -> None:
    settings = Settings(host="127.0.0.1", port=9876)
    captured: dict[str, object] = {}
    monkeypatch.setattr(main.Settings, "from_environment", lambda: settings)
    monkeypatch.setattr(main.uvicorn, "Config", lambda app, **kwargs: captured.update(kwargs))
    monkeypatch.setattr(main, "LongPollShutdownServer", lambda config, interrupt: type("Server", (), {"run": lambda self: None})())

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
    monkeypatch.setattr(main, "LongPollShutdownServer", lambda config, interrupt: InterruptingServer())

    main.main()
