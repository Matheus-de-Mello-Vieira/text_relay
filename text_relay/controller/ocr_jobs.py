"""OCR submission and retry endpoints."""

from hashlib import sha256

from fastapi import File, HTTPException, Request, UploadFile

from text_relay.controller.payloads import job_payload
from text_relay.queue import OCRWorkItem

ACCEPTED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


async def perform_ocr(
    request: Request,
    file: UploadFile | None = File(default=None),
) -> dict[str, str | dict[str, str] | None]:
    if file is None:
        raise HTTPException(status_code=400, detail="An image file is required.")
    content_type = file.content_type
    if content_type not in ACCEPTED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image type.")

    app = request.app
    try:
        chunks: list[bytes] = []
        total_size = 0
        while chunk := await file.read(1024 * 1024):
            total_size += len(chunk)
            if total_size > app.state.settings.max_upload_size:
                raise HTTPException(status_code=413, detail="Image is too large.")
            chunks.append(chunk)

        if total_size == 0:
            raise HTTPException(status_code=400, detail="Image upload is empty.")
        image = b"".join(chunks)
        image_checksum = sha256(image).hexdigest()

        profile_id = app.state.ocr_profiles.active_profile_id
        strategy = app.state.strategy_for(profile_id)
        job = app.state.store.enqueue(image_checksum, image, content_type, profile_id)
        if job is None:
            raise HTTPException(
                status_code=409,
                detail="This image has already been submitted with the active OCR profile.",
            )
        await app.state.ocr_queue.submit(OCRWorkItem(job.id, image, content_type, strategy))
        return job_payload(job)
    finally:
        await file.close()


async def retry_ocr(
    request: Request, job_id: str
) -> dict[str, str | dict[str, str] | None]:
    app = request.app
    job = app.state.store.retry(job_id)
    if job is None:
        raise HTTPException(
            status_code=409,
            detail="Only retained failed extractions can be retried.",
        )
    await app.state.ocr_queue.submit(
        OCRWorkItem(job.id, job.image, job.content_type, app.state.strategy_for(job.profile_id))
    )
    return job_payload(job)
