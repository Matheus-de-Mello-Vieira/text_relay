"""Local Tesseract implementation of the OCR strategy."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import subprocess
import tempfile

from .ocr import OCRExecutionError

LOGGER = logging.getLogger(__name__)


class TesseractUnavailable(OCRExecutionError):
    """Raised when the Tesseract executable cannot be started."""


class TesseractOCRStrategy:
    """Run the configured local Tesseract executable for each image."""

    def __init__(self, *, language: str, psm: int) -> None:
        self._language = language
        self._psm = psm

    async def extract_text(self, image: bytes, content_type: str) -> str:
        """Write *image* temporarily, then execute Tesseract off the event loop."""
        suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(
            content_type, ".img"
        )
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
                temporary_file.write(image)
                temporary_path = Path(temporary_file.name)
            return await asyncio.to_thread(
                _extract_text,
                temporary_path,
                language=self._language,
                psm=self._psm,
            )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def _extract_text(image_path: Path, *, language: str, psm: int) -> str:
    command = ["tesseract", str(image_path), "stdout", "-l", language, "--psm", str(psm)]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise TesseractUnavailable("Tesseract is not installed or is not on PATH") from error
    except OSError as error:
        raise OCRExecutionError("Could not start Tesseract") from error
    if completed.returncode != 0:
        LOGGER.warning("Tesseract exited with status %s: %s", completed.returncode, completed.stderr.strip())
        raise OCRExecutionError("Tesseract failed to process the image")
    return completed.stdout
