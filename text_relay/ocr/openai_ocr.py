"""OpenAI Responses API implementation of the OCR strategy."""

from __future__ import annotations

import base64
import logging
from typing import Any, Protocol

from openai import APIError, AsyncOpenAI

from .ocr import OCRExecutionError

LOGGER = logging.getLogger(__name__)

TRANSCRIPTION_PROMPT = """Transcribe all legible printed text in this image and format the result as Markdown.

Rules:
- Preserve the original wording.
- Preserve capitalization and punctuation.
- Preserve paragraph boundaries and the document's structure.
- Format headings with Markdown heading markers (#, ##, etc.).
- Format unordered list items with a hyphen and a space (-), not a bullet character.
- Format ordered lists as numbered Markdown list items.
- Format tabular content as a Markdown table when the rows and columns are clear.
- Use Markdown emphasis only when the source clearly indicates emphasis.
- Do not add Markdown fences around the result.
- Do not summarize.
- Do not rewrite.
- Do not correct grammar or spelling.
- Do not silently complete text that is not visible.
- If text cannot be read confidently, indicate that uncertainty rather than inventing content.
- Output only the transcription."""


class ResponsesClient(Protocol):
    """Narrow portion of the asynchronous OpenAI client used by this strategy."""

    responses: Any


class OpenAIOCRStrategy:
    """Use OpenAI vision to faithfully transcribe an uploaded image."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        image_detail: str,
        client: ResponsesClient | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=api_key)
        self._model = model
        self._image_detail = image_detail

    async def extract_text(self, image: bytes, content_type: str) -> str:
        """Submit one image as a data URL and return the provider's text output."""
        image_data = base64.b64encode(image).decode("ascii")
        try:
            response = await self._client.responses.create(
                model=self._model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": TRANSCRIPTION_PROMPT},
                            {
                                "type": "input_image",
                                "image_url": f"data:{content_type};base64,{image_data}",
                                "detail": self._image_detail,
                            },
                        ],
                    }
                ],
            )
        except APIError as error:
            LOGGER.warning("OpenAI OCR request failed: %s", error)
            raise OCRExecutionError("OpenAI could not process the image") from error
        text = getattr(response, "output_text", None)
        if not isinstance(text, str) or not text.strip():
            raise OCRExecutionError("OpenAI returned no transcription")
        return text

    async def aclose(self) -> None:
        """Close the SDK transport when the FastAPI application stops."""
        close = getattr(self._client, "close", None)
        if close is not None:
            await close()
