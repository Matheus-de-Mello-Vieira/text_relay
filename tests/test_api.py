from fastapi.testclient import TestClient

from text_relay.config import Settings
from text_relay.main import create_app
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


def test_root_serves_mobile_upload_and_long_polling_interface() -> None:
    response = make_client(FakeOCRStrategy()).get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'accept="image/*"' in response.text
    assert 'capture="environment"' in response.text
    assert 'url.searchParams.set("wait", "true")' in response.text
    assert "window.setInterval" not in response.text
    assert "navigator.clipboard.writeText" in response.text


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
    assert strategy.calls == [(b"image", "image/png")]
    assert result["id"] and result["created_at"].endswith("Z")
    assert client.get("/api/results").json() == {"results": [result]}


def test_long_poll_returns_immediately_when_results_have_changed() -> None:
    client = make_client(FakeOCRStrategy())
    latest = client.app.state.store.add("new result")

    response = client.get("/api/results?wait=true&after=older-result")

    assert response.json() == {"results": [{
        "id": latest.id,
        "created_at": latest.created_at.isoformat().replace("+00:00", "Z"),
        "text": "new result",
    }]}


def test_results_are_newest_first_and_bounded() -> None:
    texts = iter(["first", "second", "third"])
    strategy = FakeOCRStrategy()
    async def extract(image: bytes, content_type: str) -> str:
        strategy.calls.append((image, content_type))
        return next(texts)
    strategy.extract_text = extract  # type: ignore[method-assign]
    client = make_client(strategy)
    for _ in range(3):
        assert image_request(client).status_code == 200
    assert [item["text"] for item in client.get("/api/results").json()["results"]] == ["third", "second"]


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
