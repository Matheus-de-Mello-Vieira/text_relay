import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from openai import APIError
from google.genai import errors as gemini_errors

from text_relay.config import OCRProfile
from text_relay.ocr.gemini_ocr import GeminiOCRStrategy
from text_relay.ocr import OCRConfigurationError, OCRExecutionError, create_ocr_strategy
from text_relay.ocr.openai_ocr import OpenAIOCRStrategy, TRANSCRIPTION_PROMPT
from text_relay.ocr.tesseract_ocr import TesseractOCRStrategy, TesseractUnavailable, _extract_text


def test_tesseract_uses_required_command() -> None:
    completed = Mock(returncode=0, stdout="Recognized text", stderr="")
    with patch("text_relay.ocr.tesseract_ocr.subprocess.run", return_value=completed) as run:
        result = _extract_text(Path("/tmp/image.png"), language="eng", psm=6)
    assert result == "Recognized text"
    run.assert_called_once_with(
        ["tesseract", "/tmp/image.png", "stdout", "-l", "eng", "--psm", "6"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_tesseract_maps_nonzero_exit_to_controlled_error() -> None:
    with patch("text_relay.ocr.tesseract_ocr.subprocess.run", return_value=Mock(returncode=1)):
        with pytest.raises(OCRExecutionError, match="Tesseract failed"):
            _extract_text(Path("image.png"), language="eng", psm=6)


def test_tesseract_maps_missing_executable_to_controlled_error() -> None:
    with patch("text_relay.ocr.tesseract_ocr.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(TesseractUnavailable, match="not installed"):
            _extract_text(Path("image.png"), language="eng", psm=6)


def test_tesseract_removes_temporary_file() -> None:
    strategy = TesseractOCRStrategy(language="eng", psm=6)
    paths: list[Path] = []

    def extract(path: Path, **_: object) -> str:
        paths.append(path)
        assert path.read_bytes() == b"image"
        return "text"

    with patch("text_relay.ocr.tesseract_ocr._extract_text", side_effect=extract):
        assert asyncio.run(strategy.extract_text(b"image", "image/png")) == "text"
    assert paths and not paths[0].exists()


def test_strategy_selection_is_explicit() -> None:
    assert isinstance(
        create_ocr_strategy(OCRProfile("local", "Local", "tesseract", language="eng", psm=6)),
        TesseractOCRStrategy,
    )
    with patch("text_relay.ocr.ocr.environment_value", return_value="test-key"):
        strategy = create_ocr_strategy(
            OCRProfile(
                "cloud", "Cloud", "openai", model="model", image_detail="high", api_key_env="TEST_KEY"
            )
        )
    assert isinstance(strategy, OpenAIOCRStrategy)
    with patch("text_relay.ocr.ocr.environment_value", return_value="test-key"):
        strategy = create_ocr_strategy(
            OCRProfile("gemini", "Gemini", "gemini", model="model", api_key_env="TEST_KEY")
        )
    assert isinstance(strategy, GeminiOCRStrategy)


def test_invalid_strategy_selection_is_controlled() -> None:
    with pytest.raises(OCRConfigurationError, match="Unsupported OCR provider"):
        create_ocr_strategy(OCRProfile("unknown", "Unknown", "other"))


def test_openai_selection_requires_a_server_side_key() -> None:
    profile = OCRProfile(
        "cloud", "Cloud", "openai", model="model", image_detail="high", api_key_env="OPENAI_API_KEY"
    )
    with patch("text_relay.ocr.ocr.environment_value", return_value=None):
        with pytest.raises(OCRConfigurationError, match="OPENAI_API_KEY"):
            create_ocr_strategy(profile)


def test_gemini_selection_requires_a_server_side_key() -> None:
    profile = OCRProfile(
        "gemini", "Gemini", "gemini", model="model", api_key_env="GEMINI_API_KEY"
    )
    with patch("text_relay.ocr.ocr.environment_value", return_value=None):
        with pytest.raises(OCRConfigurationError, match="GEMINI_API_KEY"):
            create_ocr_strategy(profile)


def test_openai_sends_a_data_url_and_returns_transcription() -> None:
    client = Mock()
    client.responses.create = AsyncMock(return_value=Mock(output_text="Expected transcription"))
    strategy = OpenAIOCRStrategy(
        api_key="test-key", model="gpt-6-luna", image_detail="high", client=client
    )
    assert asyncio.run(strategy.extract_text(b"image-bytes", "image/png")) == "Expected transcription"
    request = client.responses.create.await_args.kwargs
    assert request["model"] == "gpt-6-luna"
    content = request["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": TRANSCRIPTION_PROMPT}
    assert content[1] == {
        "type": "input_image",
        "image_url": "data:image/png;base64,aW1hZ2UtYnl0ZXM=",
        "detail": "high",
    }


def test_openai_rejects_empty_response() -> None:
    client = Mock()
    client.responses.create = AsyncMock(return_value=Mock(output_text=" "))
    strategy = OpenAIOCRStrategy(api_key="test-key", model="model", image_detail="high", client=client)
    with pytest.raises(OCRExecutionError, match="no transcription"):
        asyncio.run(strategy.extract_text(b"image", "image/jpeg"))


def test_openai_maps_sdk_failures_to_controlled_errors() -> None:
    client = Mock()
    client.responses.create = AsyncMock(
        side_effect=APIError("provider failure", request=Mock(), body=None)
    )
    strategy = OpenAIOCRStrategy(api_key="test-key", model="model", image_detail="high", client=client)
    with pytest.raises(OCRExecutionError, match="OpenAI could not process"):
        asyncio.run(strategy.extract_text(b"image", "image/jpeg"))


def test_gemini_sends_an_inline_image_and_returns_transcription() -> None:
    client = Mock()
    client.models.generate_content = AsyncMock(return_value=Mock(text="Expected transcription"))
    strategy = GeminiOCRStrategy(api_key="test-key", model="gemini-3.8-flash", client=client)

    assert asyncio.run(strategy.extract_text(b"image-bytes", "image/png")) == "Expected transcription"

    request = client.models.generate_content.await_args.kwargs
    assert request["model"] == "gemini-3.8-flash"
    assert request["contents"][0] == TRANSCRIPTION_PROMPT
    image = request["contents"][1]
    assert image.inline_data.mime_type == "image/png"
    assert image.inline_data.data == b"image-bytes"


def test_gemini_rejects_empty_response() -> None:
    client = Mock()
    client.models.generate_content = AsyncMock(return_value=Mock(text=" "))
    strategy = GeminiOCRStrategy(api_key="test-key", model="model", client=client)

    with pytest.raises(OCRExecutionError, match="no transcription"):
        asyncio.run(strategy.extract_text(b"image", "image/jpeg"))


def test_gemini_maps_sdk_failures_to_controlled_errors() -> None:
    client = Mock()
    client.models.generate_content = AsyncMock(
        side_effect=gemini_errors.APIError(500, {"error": {"message": "provider failure"}})
    )
    strategy = GeminiOCRStrategy(api_key="test-key", model="model", client=client)

    with pytest.raises(OCRExecutionError, match="Gemini could not process"):
        asyncio.run(strategy.extract_text(b"image", "image/jpeg"))
