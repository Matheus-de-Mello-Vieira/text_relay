"""Register the public OCR API routes."""

from fastapi import APIRouter

from text_relay.controller import ocr_jobs, ocr_profiles, results

router = APIRouter()
router.add_api_route("/api/results", results.recent_results, methods=["GET"])
router.add_api_route("/api/ocr-profiles", ocr_profiles.ocr_profiles, methods=["GET"])
router.add_api_route(
    "/api/ocr-profiles/active", ocr_profiles.activate_ocr_profile, methods=["PUT"]
)
router.add_api_route("/api/ocr", ocr_jobs.perform_ocr, methods=["POST"], status_code=202)
router.add_api_route(
    "/api/jobs/{job_id}/retry", ocr_jobs.retry_ocr, methods=["POST"], status_code=202
)
