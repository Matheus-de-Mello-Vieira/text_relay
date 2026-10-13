"""Application-owned OCR strategy boundary and provider selection."""

from __future__ import annotations

from typing import Protocol

from text_relay.config import OCRProfile, OCRProfileCatalog, environment_value


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


def create_ocr_strategy(profile: OCRProfile) -> OCRStrategy:
    """Create the strategy described by one validated OCR profile."""
    if profile.provider == "tesseract":
        from text_relay.tesseract_ocr import TesseractOCRStrategy

        assert profile.language is not None and profile.psm is not None
        return TesseractOCRStrategy(language=profile.language, psm=profile.psm)
    if profile.provider == "openai":
        assert profile.api_key_env is not None
        api_key = environment_value(profile.api_key_env)
        if not api_key:
            raise OCRConfigurationError(
                f"{profile.api_key_env} is required for OCR profile {profile.id!r}"
            )
        from text_relay.openai_ocr import OpenAIOCRStrategy

        assert profile.model is not None and profile.image_detail is not None
        return OpenAIOCRStrategy(
            api_key=api_key,
            model=profile.model,
            image_detail=profile.image_detail,
        )
    raise OCRConfigurationError(f"Unsupported OCR provider: {profile.provider}")


class OCRProfileManager:
    """Own OCR profile selection and strategies used by queued jobs."""

    def __init__(self, catalog: OCRProfileCatalog) -> None:
        self._catalog = catalog
        self._active_profile_id = catalog.default_profile
        self._strategies: dict[str, OCRStrategy] = {}
        self.strategy_for(catalog.default_profile)

    @property
    def active_profile_id(self) -> str:
        return self._active_profile_id

    def payload(self) -> dict[str, object]:
        return {
            "active_profile": self._active_profile_id,
            "profiles": [profile.public_payload() for profile in self._catalog.profiles.values()],
        }

    def strategy_for(self, profile_id: str) -> OCRStrategy:
        profile = self._catalog.profiles.get(profile_id)
        if profile is None:
            raise KeyError(profile_id)
        if profile_id not in self._strategies:
            self._strategies[profile_id] = create_ocr_strategy(profile)
        return self._strategies[profile_id]

    def activate(self, profile_id: str) -> None:
        self.strategy_for(profile_id)
        self._active_profile_id = profile_id

    async def aclose(self) -> None:
        for strategy in self._strategies.values():
            close = getattr(strategy, "aclose", None)
            if close is not None:
                await close()
