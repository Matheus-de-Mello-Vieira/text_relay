"""OCR profile listing and activation endpoints."""

from fastapi import Body, HTTPException, Request

from text_relay.ocr import OCRConfigurationError


async def ocr_profiles(request: Request) -> dict[str, object]:
    return request.app.state.ocr_profiles.payload()


async def activate_ocr_profile(
    request: Request, payload: dict[str, str] = Body(...)
) -> dict[str, object]:
    profile_id = payload.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=422, detail="profile_id is required.")
    profile_manager = request.app.state.ocr_profiles
    try:
        profile_manager.activate(profile_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="OCR profile was not found.") from None
    except OCRConfigurationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    request.app.state.store.publish_change()
    return profile_manager.payload()
