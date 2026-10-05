from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from text_relay.ocr import OCRFailure, TesseractUnavailable, extract_text


def test_extract_text_uses_required_tesseract_command() -> None:
    completed = Mock(returncode=0, stdout="Recognized text", stderr="")

    with patch("text_relay.ocr.subprocess.run", return_value=completed) as run:
        result = extract_text(Path("/tmp/image.png"), language="eng", psm=6)

    assert result == "Recognized text"
    run.assert_called_once_with(
        ["tesseract", "/tmp/image.png", "stdout", "-l", "eng", "--psm", "6"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_extract_text_maps_nonzero_exit_to_controlled_error() -> None:
    completed = Mock(returncode=1, stdout="", stderr="bad image")

    with patch("text_relay.ocr.subprocess.run", return_value=completed):
        with pytest.raises(OCRFailure, match="Tesseract failed"):
            extract_text(Path("image.png"), language="eng", psm=6)


def test_extract_text_maps_missing_executable_to_controlled_error() -> None:
    with patch("text_relay.ocr.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(TesseractUnavailable, match="not installed"):
            extract_text(Path("image.png"), language="eng", psm=6)
