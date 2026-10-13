import os
import socket
from types import SimpleNamespace

import pytest

from text_relay import config
from text_relay.config import OCRProfileCatalog, Settings, environment_value


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    original_environment = os.environ.copy()
    monkeypatch.chdir(tmp_path)
    for name in (
        "HOST",
        "HOST_CIDR",
        "PORT",
        "MAX_UPLOAD_SIZE",
        "MAX_RESULT_HISTORY",
        "LONG_POLL_TIMEOUT_SECONDS",
        "OCR_WORKERS",
        "OCR_RETRIES",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    os.environ.clear()
    os.environ.update(original_environment)


@pytest.fixture
def local_interfaces(monkeypatch: pytest.MonkeyPatch) -> None:
    interfaces = {
        "lo": [SimpleNamespace(family=socket.AF_INET, address="127.0.0.1")],
        "en1": [SimpleNamespace(family=socket.AF_INET, address="192.168.0.50")],
        "en0": [
            SimpleNamespace(family=config.psutil.AF_LINK, address="aa:bb:cc:dd:ee:ff"),
            SimpleNamespace(family=socket.AF_INET, address="10.0.0.2"),
            SimpleNamespace(family=socket.AF_INET, address="192.168.0.42"),
            SimpleNamespace(family=socket.AF_INET6, address="fd00::42"),
            SimpleNamespace(family=socket.AF_INET6, address="fe80::42%en0"),
        ],
    }
    monkeypatch.setattr(config.psutil, "net_if_addrs", lambda: interfaces)


def test_settings_default_port_is_8000(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert Settings.from_environment().port == 8000


def test_settings_read_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "200")
    monkeypatch.setenv("MAX_RESULT_HISTORY", "5")
    monkeypatch.setenv("LONG_POLL_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("OCR_WORKERS", "4")

    assert Settings.from_environment() == Settings(
        host="127.0.0.1",
        port=9000,
        max_upload_size=200,
        max_result_history=5,
        long_poll_timeout_seconds=3.5,
        ocr_workers=4,
    )


def test_settings_reject_invalid_positive_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "0")
    with pytest.raises(ValueError, match="PORT"):
        Settings.from_environment()


def test_profile_catalog_rejects_invalid_provider(tmp_path) -> None:
    path = tmp_path / "ocr-profiles.toml"
    path.write_text('default_profile = "bad"\n[profiles.bad]\nprovider = "other"\n')
    with pytest.raises(ValueError, match="unsupported provider"):
        OCRProfileCatalog.from_file(path)


def test_profile_catalog_reads_tesseract_openai_and_gemini_profiles(tmp_path) -> None:
    path = tmp_path / "ocr-profiles.toml"
    path.write_text(
        'default_profile = "local"\n[profiles.local]\nprovider = "tesseract"\n'
        '[profiles.cloud]\nlabel = "Cloud"\nprovider = "openai"\napi_key_env = "TEST_KEY"\n'
        '[profiles.gemini]\nlabel = "Gemini"\nprovider = "gemini"\napi_key_env = "GEMINI_KEY"\n'
    )
    catalog = OCRProfileCatalog.from_file(path)
    assert catalog.default_profile == "local"
    assert catalog.profiles["local"].psm == 6
    assert catalog.profiles["cloud"].public_payload() == {
        "id": "cloud", "label": "Cloud", "provider": "openai"
    }
    assert catalog.profiles["gemini"].model == "gemini-3.8-flash"
    assert catalog.profiles["gemini"].image_detail is None


def test_settings_read_port_from_dotenv(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PORT=7001\n", encoding="utf-8")

    assert Settings.from_environment().port == 7001
    assert os.environ["PORT"] == "7001"


def test_dotenv_does_not_override_process_environment(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text(
        'PORT=7001\nAPI_KEY="file key"\n', encoding="utf-8"
    )
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("API_KEY", "process key")

    assert Settings.from_environment().port == 9000
    assert environment_value("API_KEY") == "process key"
    assert os.environ["API_KEY"] == "process key"


def test_environment_value_loads_quoted_dotenv_value(tmp_path) -> None:
    (tmp_path / ".env").write_text(
        'TEXT_RELAY_TEST_KEY="a=b # c"\n', encoding="utf-8"
    )

    assert environment_value("TEXT_RELAY_TEST_KEY") == "a=b # c"
    assert os.environ["TEXT_RELAY_TEST_KEY"] == "a=b # c"


def test_settings_select_local_ip_from_dotenv_cidr(tmp_path, local_interfaces) -> None:
    (tmp_path / ".env").write_text(
        "HOST=127.0.0.1\nHOST_CIDR=192.168.0.0/24\n", encoding="utf-8"
    )

    assert Settings.from_environment().host == "192.168.0.42"


def test_environment_cidr_overrides_dotenv(tmp_path, local_interfaces, monkeypatch) -> None:
    (tmp_path / ".env").write_text("HOST_CIDR=10.0.0.0/24\n", encoding="utf-8")
    monkeypatch.setenv("HOST_CIDR", "192.168.0.0/24")

    assert Settings.from_environment().host == "192.168.0.42"


@pytest.mark.parametrize(
    ("cidr", "expected"),
    [
        ("192.168.0.42/24", "192.168.0.42"),
        ("192.168.0.42/32", "192.168.0.42"),
        ("fd00::/64", "fd00::42"),
        ("fe80::/64", "fe80::42%en0"),
    ],
)
def test_settings_select_matching_address(cidr, expected, local_interfaces, monkeypatch) -> None:
    monkeypatch.setenv("HOST_CIDR", cidr)

    assert Settings.from_environment().host == expected


@pytest.mark.parametrize("cidr", ["not-a-cidr", "192.168.0.0/33", "192.168.0.42"])
def test_settings_reject_invalid_cidr(cidr, monkeypatch) -> None:
    monkeypatch.setenv("HOST_CIDR", cidr)

    with pytest.raises(ValueError, match="HOST_CIDR must be a valid"):
        Settings.from_environment()


def test_settings_reject_network_without_local_address(local_interfaces, monkeypatch) -> None:
    monkeypatch.setenv("HOST_CIDR", "172.16.0.0/24")

    with pytest.raises(ValueError, match="No local IP address matches HOST_CIDR"):
        Settings.from_environment()


@pytest.mark.parametrize("cidr", [None, ""])
def test_settings_keep_host_without_cidr(cidr, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOST", "127.0.0.1")
    if cidr is not None:
        (tmp_path / ".env").write_text("HOST_CIDR=10.0.0.0/24\n", encoding="utf-8")
        monkeypatch.setenv("HOST_CIDR", cidr)

    def unexpected_discovery():
        pytest.fail("Interface discovery should only run when HOST_CIDR is set")

    monkeypatch.setattr(config.psutil, "net_if_addrs", unexpected_discovery)

    assert Settings.from_environment().host == "127.0.0.1"
