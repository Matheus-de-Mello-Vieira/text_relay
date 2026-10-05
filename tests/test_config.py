import pytest

from text_relay.config import Settings


def test_settings_default_port_is_8000(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert Settings.from_environment().port == 8000


def test_settings_read_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("OCR_LANGUAGE", "deu")
    monkeypatch.setenv("OCR_PSM", "11")
    monkeypatch.setenv("OCR_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_OCR_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_IMAGE_DETAIL", "low")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "200")
    monkeypatch.setenv("MAX_RESULT_HISTORY", "5")
    monkeypatch.setenv("LONG_POLL_TIMEOUT_SECONDS", "3.5")

    assert Settings.from_environment() == Settings(
        host="127.0.0.1",
        port=9000,
        ocr_language="deu",
        ocr_psm=11,
        ocr_provider="openai",
        openai_ocr_model="test-model",
        openai_image_detail="low",
        openai_api_key="server-key",
        max_upload_size=200,
        max_result_history=5,
        long_poll_timeout_seconds=3.5,
    )


def test_settings_reject_invalid_positive_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "0")
    with pytest.raises(ValueError, match="PORT"):
        Settings.from_environment()


def test_settings_reject_invalid_ocr_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "other")
    with pytest.raises(ValueError, match="OCR_PROVIDER"):
        Settings.from_environment()


def test_settings_read_port_from_dotenv(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PORT=7001\n", encoding="utf-8")

    assert Settings.from_environment().port == 7001
