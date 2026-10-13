"""Google Gemini implementation of the OCR strategy."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from google import genai
from google.genai import errors, types

from .ocr import OCRExecutionError
from .openai_ocr import TRANSCRIPTION_PROMPT

LOGGER = logging.getLogger(__name__)


class AsyncModelsClient(Protocol):
    """Narrow portion of Gemini's asynchronous client used by this strategy."""

    models: Any


class GeminiOCRStrategy:
    """Use Gemini vision to faithfully transcribe an uploaded image."""

    def __init__(
        self, *, api_key: str, model: str, client: AsyncModelsClient | None = None
    ) -> None:
        self._client = client or genai.Client(api_key=api_key).aio
        self._model = model

    async def extract_text(self, image: bytes, content_type: str) -> str:
        """Submit one image inline and return the provider's text output."""
        try:
            response = await self._client.models.generate_content(
                model=self._model,
                contents=[
                    TRANSCRIPTION_PROMPT,
                    types.Part.from_bytes(data=image, mime_type=content_type),
                ],
            )
        except errors.APIError as error:
            LOGGER.warning("Gemini OCR request failed: %s", error)
            raise OCRExecutionError("Gemini could not process the image") from error
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise OCRExecutionError("Gemini returned no transcription")
        return text

    async def aclose(self) -> None:
        """Close the SDK transport when the FastAPI application stops."""
        close = getattr(self._client, "aclose", None)
        if close is not None:
            await close()
