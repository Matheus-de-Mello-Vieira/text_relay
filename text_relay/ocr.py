"""Tesseract integration kept separate from HTTP concerns."""

from __future__ import annotations

from pathlib import Path
import subprocess


class OCRFailure(Exception):
    """Raised when Tesseract cannot produce text from an image."""


class TesseractUnavailable(OCRFailure):
    """Raised when the Tesseract executable cannot be started."""


def extract_text(image_path: Path, *, language: str, psm: int) -> str:
    """Run Tesseract against *image_path* and return its extracted text."""
    command = [
        "tesseract",
        str(image_path),
        "stdout",
        "-l",
        language,
        "--psm",
        str(psm),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise TesseractUnavailable("Tesseract is not installed or is not on PATH") from error
    except OSError as error:
        raise OCRFailure("Could not start Tesseract") from error

    if completed.returncode != 0:
        raise OCRFailure("Tesseract failed to process the image")
    return completed.stdout
