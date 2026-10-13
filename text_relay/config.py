"""Application and OCR profile configuration."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
import os
from pathlib import Path
import socket
import tomllib

import psutil


DEFAULT_MAX_UPLOAD_SIZE = 10 * 1024 * 1024
DEFAULT_MAX_RESULT_HISTORY = 20
DEFAULT_LONG_POLL_TIMEOUT_SECONDS = 25.0
DEFAULT_OCR_WORKERS = 2
DEFAULT_OCR_RETRIES = 3
OCR_PROVIDERS = {"tesseract", "openai"}
OPENAI_IMAGE_DETAILS = {"low", "high", "original", "auto"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the local TextRelay server."""

    host: str = "0.0.0.0"
    port: int = 8000
    max_upload_size: int = DEFAULT_MAX_UPLOAD_SIZE
    max_result_history: int = DEFAULT_MAX_RESULT_HISTORY
    long_poll_timeout_seconds: float = DEFAULT_LONG_POLL_TIMEOUT_SECONDS
    ocr_workers: int = DEFAULT_OCR_WORKERS
    ocr_retries: int = DEFAULT_OCR_RETRIES

    @classmethod
    def from_environment(cls) -> Settings:
        """Create settings from environment variables and a local dotenv file."""
        dotenv_values = _read_dotenv(Path.cwd() / ".env")
        return cls(
            host=_bind_host(dotenv_values, cls.host),
            port=_positive_int("PORT", dotenv_values, cls.port),
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
            ocr_workers=_positive_int("OCR_WORKERS", dotenv_values, cls.ocr_workers),
            ocr_retries=_non_negative_int("OCR_RETRIES", dotenv_values, cls.ocr_retries),
        )


@dataclass(frozen=True)
class OCRProfile:
    """One named OCR provider configuration."""

    id: str
    label: str
    provider: str
    language: str | None = None
    psm: int | None = None
    model: str | None = None
    image_detail: str | None = None
    api_key_env: str | None = None

    def public_payload(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "provider": self.provider}


@dataclass(frozen=True)
class OCRProfileCatalog:
    """Validated OCR profiles and the profile selected after startup."""

    default_profile: str
    profiles: dict[str, OCRProfile]

    @classmethod
    def from_file(cls, path: Path) -> OCRProfileCatalog:
        if not path.is_file():
            raise ValueError(f"OCR profile file is required: {path}")
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"OCR profile file is invalid TOML: {path}") from error
        default_profile = data.get("default_profile")
        raw_profiles = data.get("profiles")
        if not isinstance(default_profile, str) or not default_profile:
            raise ValueError("OCR profile file must define default_profile")
        if not isinstance(raw_profiles, dict) or not raw_profiles:
            raise ValueError("OCR profile file must define at least one profile")
        profiles = {
            profile_id: _profile_from_mapping(profile_id, raw_profile)
            for profile_id, raw_profile in raw_profiles.items()
        }
        if default_profile not in profiles:
            raise ValueError("default_profile must name a configured profile")
        return cls(default_profile=default_profile, profiles=profiles)


def _profile_from_mapping(profile_id: object, raw_profile: object) -> OCRProfile:
    if not isinstance(profile_id, str) or not profile_id:
        raise ValueError("OCR profile IDs must be non-empty strings")
    if not isinstance(raw_profile, dict):
        raise ValueError(f"OCR profile {profile_id!r} must be a table")
    provider = raw_profile.get("provider")
    if not isinstance(provider, str) or provider.lower() not in OCR_PROVIDERS:
        raise ValueError(f"OCR profile {profile_id!r} has an unsupported provider")
    provider = provider.lower()
    label = raw_profile.get("label", profile_id)
    if not isinstance(label, str) or not label:
        raise ValueError(f"OCR profile {profile_id!r} label must be a non-empty string")
    if provider == "tesseract":
        language = raw_profile.get("language", "eng")
        psm = raw_profile.get("psm", 6)
        if not isinstance(language, str) or not language:
            raise ValueError(f"OCR profile {profile_id!r} language must be a non-empty string")
        if not isinstance(psm, int) or psm <= 0:
            raise ValueError(f"OCR profile {profile_id!r} psm must be a positive integer")
        return OCRProfile(profile_id, label, provider, language=language, psm=psm)
    model = raw_profile.get("model", "gpt-6-luna")
    image_detail = raw_profile.get("image_detail", "high")
    api_key_env = raw_profile.get("api_key_env")
    if not isinstance(model, str) or not model:
        raise ValueError(f"OCR profile {profile_id!r} model must be a non-empty string")
    if not isinstance(image_detail, str) or image_detail not in OPENAI_IMAGE_DETAILS:
        raise ValueError(f"OCR profile {profile_id!r} image_detail is invalid")
    if not isinstance(api_key_env, str) or not api_key_env:
        raise ValueError(f"OCR profile {profile_id!r} api_key_env must be a non-empty string")
    return OCRProfile(profile_id, label, provider, model=model, image_detail=image_detail, api_key_env=api_key_env)


def _setting(name: str, dotenv_values: dict[str, str], default: str) -> str:
    return os.getenv(name, dotenv_values.get(name, default))


def _bind_host(dotenv_values: dict[str, str], default: str) -> str:
    cidr = _optional_setting("HOST_CIDR", dotenv_values)
    if cidr is None:
        return _setting("HOST", dotenv_values, default)

    try:
        if "/" not in cidr:
            raise ValueError("Missing network prefix")
        network = ip_network(cidr, strict=False)
    except ValueError as error:
        raise ValueError("HOST_CIDR must be a valid IPv4 or IPv6 CIDR block") from error

    interfaces = psutil.net_if_addrs()
    for name in sorted(interfaces):
        for address in interfaces[name]:
            if address.family not in {socket.AF_INET, socket.AF_INET6}:
                continue
            if ip_address(address.address) in network:
                return address.address

    raise ValueError(f"No local IP address matches HOST_CIDR={cidr}")


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


def _non_negative_int(name: str, dotenv_values: dict[str, str], default: int) -> int:
    value = _setting(name, dotenv_values, str(default))
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a non-negative integer") from error
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return parsed


def _choice(
    name: str, dotenv_values: dict[str, str], default: str, choices: set[str]
) -> str:
    value = _setting(name, dotenv_values, default).lower()
    if value not in choices:
        expected = ", ".join(sorted(choices))
        raise ValueError(f"{name} must be one of: {expected}")
    return value


def _optional_setting(name: str, dotenv_values: dict[str, str]) -> str | None:
    value = os.getenv(name, dotenv_values.get(name))
    return value if value else None


def environment_value(name: str) -> str | None:
    """Return an environment value, allowing the local dotenv file as fallback."""
    return _optional_setting(name, _read_dotenv(Path.cwd() / ".env"))


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
