"""Register the public OCR API routes."""

from fastapi import APIRouter

from text_relay.controller import ocr_jobs, ocr_profiles, results
from text_relay.controller.schemas import (
    APIError,
    ActivateOCRProfileRequest,
    OCRJobResponse,
    OCRProfilesResponse,
    ResultsResponse,
)

router = APIRouter()
router.add_api_route(
    "/api/results",
    results.recent_results,
    methods=["GET"],
    response_model=ResultsResponse,
    response_model_exclude_unset=True,
    tags=["Results"],
    summary="List recent results and jobs",
    description="Set `wait=true` and pass the last `cursor` as `after` to wait for a change or the configured long-poll timeout. Results and jobs are newest first and retained only in server memory.",
)
router.add_api_route(
    "/api/ocr-profiles",
    ocr_profiles.ocr_profiles,
    methods=["GET"],
    response_model=OCRProfilesResponse,
    tags=["OCR profiles"],
    summary="List OCR profiles",
)
router.add_api_route(
    "/api/ocr-profiles/active",
    ocr_profiles.activate_ocr_profile,
    methods=["PUT"],
    response_model=OCRProfilesResponse,
    tags=["OCR profiles"],
    summary="Activate an OCR profile",
    description="Changes the server-wide profile for future uploads. Queued jobs and retries keep their original profile. The selection resets on server restart.",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": ActivateOCRProfileRequest.model_json_schema()
                }
            }
        }
    },
    responses={
        404: {"model": APIError, "description": "Profile ID was not found."},
        422: {"description": "Profile ID is missing or invalid, or the provider is not configured."},
    },
)
router.add_api_route(
    "/api/ocr",
    ocr_jobs.perform_ocr,
    methods=["POST"],
    status_code=202,
    response_model=OCRJobResponse,
    tags=["OCR jobs"],
    summary="Submit an image for OCR",
    description="Upload a JPEG, PNG, or WebP image as multipart form field `file`. The job is queued immediately. Duplicate image bytes for the same active profile are rejected while the job is retained.",
    responses={
        400: {"model": APIError, "description": "Image is missing or empty."},
        409: {"model": APIError, "description": "Image was already submitted with this profile."},
        413: {"model": APIError, "description": "Image exceeds the configured size limit."},
        415: {"model": APIError, "description": "Image content type is unsupported."},
    },
)
router.add_api_route(
    "/api/jobs/{job_id}/retry",
    ocr_jobs.retry_ocr,
    methods=["POST"],
    status_code=202,
    response_model=OCRJobResponse,
    tags=["OCR jobs"],
    summary="Retry a failed OCR job",
    description="Requeues a retained failed job with its original image and profile.",
    responses={
        409: {"model": APIError, "description": "Job is missing, no longer retained, or not failed."},
    },
)
