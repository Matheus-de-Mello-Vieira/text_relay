"""Application configuration read from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


DEFAULT_MAX_UPLOAD_SIZE = 10 * 1024 * 1024
DEFAULT_MAX_RESULT_HISTORY = 20
DEFAULT_LONG_POLL_TIMEOUT_SECONDS = 25.0


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the local TextRelay server."""

    host: str = "0.0.0.0"
    port: int = 8000
    ocr_language: str = "eng"
    ocr_psm: int = 6
    max_upload_size: int = DEFAULT_MAX_UPLOAD_SIZE
    max_result_history: int = DEFAULT_MAX_RESULT_HISTORY
    long_poll_timeout_seconds: float = DEFAULT_LONG_POLL_TIMEOUT_SECONDS

    @classmethod
    def from_environment(cls) -> Settings:
        """Create settings from environment variables and a local dotenv file."""
        dotenv_values = _read_dotenv(Path.cwd() / ".env")
        return cls(
            host=_setting("HOST", dotenv_values, cls.host),
            port=_positive_int("PORT", dotenv_values, cls.port),
            ocr_language=_setting("OCR_LANGUAGE", dotenv_values, cls.ocr_language),
            ocr_psm=_positive_int("OCR_PSM", dotenv_values, cls.ocr_psm),
            max_upload_size=_positive_int(
                "MAX_UPLOAD_SIZE", dotenv_values, cls.max_upload_size
            ),
            max_result_history=_positive_int(
                "MAX_RESULT_HISTORY", dotenv_values, cls.max_result_history
            ),
            long_poll_timeout_seconds=_positive_float(
                "LONG_POLL_TIMEOUT_SECONDS",
                dotenv_values,
                cls.long_poll_timeout_seconds,
            ),
        )


def _setting(name: str, dotenv_values: dict[str, str], default: str) -> str:
    return os.getenv(name, dotenv_values.get(name, default))


def _positive_int(name: str, dotenv_values: dict[str, str], default: int) -> int:
    value = _setting(name, dotenv_values, str(default))
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        message = f"{name} must be a positive integer"
        raise ValueError(message) from error
    if parsed <= 0:
        message = f"{name} must be a positive integer"
        raise ValueError(message)
    return parsed


def _positive_float(
    name: str, dotenv_values: dict[str, str], default: float
) -> float:
    value = _setting(name, dotenv_values, str(default))
    try:
        parsed = float(value)
    except ValueError as error:
        message = f"{name} must be a positive number"
        raise ValueError(message) from error
    if parsed <= 0:
        message = f"{name} must be a positive number"
        raise ValueError(message)
    return parsed


def _read_dotenv(path: Path) -> dict[str, str]:
    """Read simple KEY=value entries without overriding process environment."""
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", maxsplit=1)
        values[name.strip()] = value.strip().strip("'").strip('"')
    return values
