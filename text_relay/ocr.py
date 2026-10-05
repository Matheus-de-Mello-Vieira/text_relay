"""Application-owned OCR strategy boundary and provider selection."""

from __future__ import annotations

from typing import Protocol

from text_relay.config import Settings


class OCRError(Exception):
    """Raised when an OCR provider cannot complete a transcription."""


class OCRConfigurationError(OCRError):
    """Raised when the selected OCR provider lacks required configuration."""


class OCRExecutionError(OCRError):
    """Raised when a configured OCR provider cannot process an image."""


class OCRStrategy(Protocol):
    """Transcribe one already-validated image without HTTP concerns."""

    async def extract_text(self, image: bytes, content_type: str) -> str:
        """Return text transcribed from the supplied image."""


def create_ocr_strategy(settings: Settings) -> OCRStrategy:
    """Create exactly the OCR provider selected by *settings*."""
    if settings.ocr_provider == "tesseract":
        from text_relay.tesseract_ocr import TesseractOCRStrategy

        return TesseractOCRStrategy(language=settings.ocr_language, psm=settings.ocr_psm)
    if settings.ocr_provider == "openai":
        if not settings.openai_api_key:
            raise OCRConfigurationError("OPENAI_API_KEY is required when OCR_PROVIDER=openai")
        from text_relay.openai_ocr import OpenAIOCRStrategy

        return OpenAIOCRStrategy(
            api_key=settings.openai_api_key,
            model=settings.openai_ocr_model,
            image_detail=settings.openai_image_detail,
        )
    raise OCRConfigurationError(f"Unsupported OCR_PROVIDER: {settings.ocr_provider}")
