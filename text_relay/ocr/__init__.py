"""Public OCR strategy boundary and provider selection API."""

from .ocr import (
    OCRConfigurationError,
    OCRExecutionError,
    OCRError,
    OCRProfileManager,
    OCRStrategy,
    create_ocr_strategy,
)

__all__ = [
    "OCRConfigurationError",
    "OCRExecutionError",
    "OCRError",
    "OCRProfileManager",
    "OCRStrategy",
    "create_ocr_strategy",
]
