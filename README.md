# TextRelay

TextRelay is a small, local-network OCR relay. Open it on a phone, take or
select a JPEG, PNG, or WebP image, and the computer transcribes it with the
configured OCR provider.
The recognized text is immediately returned to the phone and appears in open
computer browsers without reloading.

It is designed for a trusted LAN and must not be exposed directly to the
public internet. It has no authentication or transport-security layer.

## Requirements

- Python 3.13+
- [Poetry](https://python-poetry.org/)
- Tesseract with the English language data (only for local OCR mode)
- An OpenAI API key (only for OpenAI OCR mode)

On macOS, install Tesseract with Homebrew:

```bash
brew install tesseract
```

## Install and run

```bash
poetry install --with dev
poetry run text-relay
```

The default server binds to `0.0.0.0:8000`, so it can accept browser requests
from other devices on the local network. On the computer, open:

```text
http://localhost:8000
```

Find the Mac's typical Wi-Fi LAN address:

```bash
ipconfig getifaddr en0
```

Then, with the phone on the same network, open:

```text
http://<computer-lan-ip>:8000
```

Firewall or guest-network settings can prevent devices from reaching each
other. Both devices normally need to be on the same trusted network.

## Configuration

All settings are optional environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | Bind host |
| `HOST_CIDR` | unset | Select a local IP in this CIDR block; overrides `HOST` |
| `PORT` | `8000` | Bind port |
| `OCR_PROVIDER` | `tesseract` | OCR provider: `tesseract` or `openai` |
| `OCR_LANGUAGE` | `eng` | Tesseract language |
| `OCR_PSM` | `6` | Tesseract page segmentation mode |
| `OPENAI_OCR_MODEL` | `gpt-6-luna` | OpenAI vision model for OCR mode |
| `OPENAI_IMAGE_DETAIL` | `high` | OpenAI image detail: `low`, `high`, `original`, or `auto` |
| `MAX_UPLOAD_SIZE` | `10485760` | Maximum image size in bytes (10 MiB) |
| `MAX_RESULT_HISTORY` | `20` | Number of recent results retained |
| `LONG_POLL_TIMEOUT_SECONDS` | `25` | Maximum duration of one results wait |
| `OCR_WORKERS` | `2` | Maximum number of images extracted in parallel |

For example:

```bash
PORT=8080 MAX_RESULT_HISTORY=50 OCR_WORKERS=4 poetry run text-relay
```

To bind to your computer's IP on a specific network, add this to `.env` in
the directory where you start the server:

```dotenv
HOST_CIDR=192.168.0.0/24
```

The server checks local interface addresses and listens on the first matching
IP, ordered by interface name. IPv4 and IPv6 CIDR blocks are supported.
Startup fails with a clear error if the CIDR is invalid or no local IP matches.
An unset or empty `HOST_CIDR` uses `HOST` as before. Process environment values
take precedence over `.env` values. When bound to a specific IP, use that IP
instead of `localhost` in both computer and phone browsers.

### Local Tesseract OCR

```bash
OCR_PROVIDER=tesseract poetry run text-relay
```

This is the default: it works offline, has no API cost, and requires Tesseract
on the computer. Photograph quality, page curvature, shadows, and perspective
can have a larger impact on recognition quality.

### OpenAI vision OCR

```bash
OCR_PROVIDER=openai \
OPENAI_API_KEY=... \
OPENAI_OCR_MODEL=gpt-6-luna \
OPENAI_IMAGE_DETAIL=high \
poetry run text-relay
```

This mode sends the uploaded image to the OpenAI API. It requires network
access and incurs API usage cost, but is generally more robust to photographed
pages with curvature, shadows, perspective, or complex visual conditions. The
API key remains on the server; it is never sent to the browser or returned by
the API. Do not put a real key in source control.

Only the selected provider is initialized: Tesseract mode does not require an
OpenAI key, and OpenAI mode does not require a Tesseract installation.

The OCR history is held only in memory and is cleared when the server restarts.
Run Uvicorn with a single worker: multiple workers have separate histories.

Each upload is accepted immediately and enters the shared extraction queue.
The browser shows whether each queued image is waiting, processing, completed,
or failed; up to `OCR_WORKERS` extractions run at once. Each retained OCR job
records the SHA-256 checksum of its uploaded image. Submitting the same bytes
again shows an error without adding duplicate work.

Open browsers synchronize through long polling: a results request waits until a
new OCR result arrives or its 25-second timeout expires, then the browser
immediately opens the next request.

## Development checks

```bash
poetry run pytest
```

The tests use fake OCR strategies and mocked OpenAI clients, so they do not
require Tesseract, an OpenAI API key, network access, or API credits. To
manually verify a provider, start the server in the selected mode, upload a
sharp image of clean printed English text, and confirm the extracted text is
shown both in the submitting browser and in another already-open browser.

## Security boundary

TextRelay limits uploads, accepts only supported image content types, invokes
Tesseract without a shell, and deletes temporary image files after local
processing. OpenAI mode transmits each uploaded image to the OpenAI API.
Those measures do not make it safe as an internet-facing service. Do not port
forward it or expose it directly to the public internet.
