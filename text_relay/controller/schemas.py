"""Public request and response shapes for the OCR API."""

from typing import Literal

from pydantic import BaseModel, Field


class APIError(BaseModel):
    detail: str


class OCRResultResponse(BaseModel):
    id: str
    created_at: str = Field(description="UTC timestamp in ISO 8601 format.")
    text: str
    image_checksum: str = Field(description="SHA-256 hash of the uploaded image.")


class OCRJobResponse(BaseModel):
    id: str
    created_at: str = Field(description="UTC timestamp in ISO 8601 format.")
    image_checksum: str = Field(description="SHA-256 hash of the uploaded image.")
    status: Literal["queued", "processing", "completed", "failed"]
    profile_id: str
    result: OCRResultResponse | None


class ResultsResponse(BaseModel):
    results: list[OCRResultResponse]
    jobs: list[OCRJobResponse]
    cursor: str | None = Field(description="Pass this value as `after` when long polling.")
    active_profile: str
    server_status: Literal["stopping"] | None = None


class OCRProfileResponse(BaseModel):
    id: str
    label: str
    provider: Literal["tesseract", "openai", "gemini"]


class OCRProfilesResponse(BaseModel):
    active_profile: str
    profiles: list[OCRProfileResponse]


class ActivateOCRProfileRequest(BaseModel):
    profile_id: str = Field(description="ID from GET /api/ocr-profiles.")
