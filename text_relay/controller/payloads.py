"""Convert stored OCR records to API response payloads."""

from text_relay.store import OCRJob, OCRResult


def result_payload(result: OCRResult) -> dict[str, str]:
    return {
        "id": result.id,
        "created_at": result.created_at.isoformat().replace("+00:00", "Z"),
        "text": result.text,
        "image_checksum": result.image_checksum,
    }


def job_payload(job: OCRJob) -> dict[str, str | dict[str, str] | None]:
    return {
        "id": job.id,
        "created_at": job.created_at.isoformat().replace("+00:00", "Z"),
        "image_checksum": job.image_checksum,
        "status": job.status,
        "profile_id": job.profile_id,
        "result": result_payload(job.result) if job.result is not None else None,
    }
