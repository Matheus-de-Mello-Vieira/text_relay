"""Cache browser assets for local serving."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ASSETS = {
    "cropper.js": (
        "https://cdn.jsdelivr.net/npm/cropperjs@2.2.0/dist/cropper.js",
        "application/javascript",
    ),
}


class AssetCache:
    """Fetch pinned assets once, then serve the local cached copies."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._lock = Lock()

    @property
    def directory(self) -> Path:
        """Directory served by the application's assets mount."""
        return self._directory

    def refresh(self) -> None:
        """Refresh every asset, keeping cached files when the CDN is unavailable."""
        failure: RuntimeError | None = None
        for name in ASSETS:
            try:
                self._refresh(name)
            except RuntimeError as error:
                failure = failure or error
        if failure is not None:
            raise failure

    def _refresh(self, name: str) -> None:
        url, _ = ASSETS[name]
        path = self._directory / name
        etag_path = path.with_suffix(f"{path.suffix}.etag")
        with self._lock:
            headers = {"User-Agent": "TextRelay"}
            if etag_path.is_file():
                etag = etag_path.read_text(encoding="utf-8").strip()
                if etag:
                    headers["If-None-Match"] = etag
            try:
                with urlopen(Request(url, headers=headers), timeout=15) as response:
                    asset = response.read()
                    etag = response.headers.get("ETag")
            except HTTPError as error:
                if error.code == 304 and path.is_file():
                    return
                raise RuntimeError("Could not retrieve an asset.") from error
            except URLError as error:
                if path.is_file():
                    return
                raise RuntimeError("Could not retrieve an asset.") from error
            self._directory.mkdir(parents=True, exist_ok=True)
            self._write(path, asset)
            if etag:
                self._write(etag_path, etag.encode())

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        temporary_path.write_bytes(content)
        temporary_path.replace(path)
