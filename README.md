# TextRelay

TextRelay is a small, local-network OCR relay. Open it on a phone, take or
select a JPEG, PNG, or WebP image, and the computer transcribes it with the
selected OCR profile.
The recognized text is immediately returned to the phone and appears in open
computer browsers without reloading.

It is designed for a trusted LAN and must not be exposed directly to the
public internet. It has no authentication or transport-security layer.

## Privacy by design

Uploaded images, OCR results, and job history are kept in the server process
memory. TextRelay does not save them to a database, and they are cleared when
the server restarts. `MAX_RESULT_HISTORY` limits the retained history. Local
Tesseract OCR briefly writes an image to a temporary file and deletes it after
processing. The `.cache` directory stores the Cropper.js browser asset, not
uploads or OCR results.

Set `HOST_CIDR` to bind the server to a local IP in the network you intend to
use, instead of the default `0.0.0.0` binding on all interfaces. For example,
`HOST_CIDR=192.168.0.0/24` selects a matching local address on that network.
This narrows where the server listens; it does not authenticate clients or
restrict requests by their source IP. Use TextRelay only on a trusted network.

The local Tesseract profile processes images on your computer. OpenAI and
Gemini profiles send uploaded images to their respective APIs for OCR.

## Requirements

- Python 3.13+
- [Poetry](https://python-poetry.org/)
- Tesseract with the English language data (only for local OCR mode)
- An OpenAI API key (only for OpenAI OCR mode)
- A Gemini API key (only for Gemini OCR mode)

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

Server settings are optional environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | Bind host |
| `HOST_CIDR` | unset | Select a local IP in this CIDR block; overrides `HOST` |
| `PORT` | `8000` | Bind port |
| `MAX_UPLOAD_SIZE` | `10485760` | Maximum image size in bytes (10 MiB) |
| `MAX_RESULT_HISTORY` | `20` | Number of recent results retained |
| `LONG_POLL_TIMEOUT_SECONDS` | `25` | Maximum duration of one results wait |
| `OCR_WORKERS` | `2` | Maximum number of images extracted in parallel |
| `OCR_RETRIES` | `3` | Additional OCR attempts after a failure, for new uploads and manual retries |

For example:

```bash
PORT=8080 MAX_RESULT_HISTORY=50 OCR_WORKERS=4 OCR_RETRIES=3 poetry run text-relay
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

### OCR profiles

`ocr-profiles.toml` is required in the directory where you start the server.
It defines all selectable OCR profiles and their startup default:

```toml
default_profile = "local"

[profiles.local]
label = "Local Tesseract"
provider = "tesseract"
language = "eng"
psm = 6

[profiles.openai]
label = "OpenAI Vision"
provider = "openai"
model = "gpt-6-luna"
image_detail = "high"
api_key_env = "OPENAI_API_KEY"

[profiles.gemini]
label = "Gemini Vision"
provider = "gemini"
model = "gemini-3.8-flash"
api_key_env = "GEMINI_API_KEY"
```

Select a profile in the web interface to change the server-wide setting for
future uploads. The choice is not persisted: a restart returns to
`default_profile`. Queued jobs and retries retain the profile selected when
they were submitted. The same image may be submitted once for each profile.

For OpenAI and Gemini profiles, set the named key in the process environment or `.env`:

```dotenv
OPENAI_API_KEY=...
GEMINI_API_KEY=...
```

The key remains on the server and is never returned to the browser. Do not put
real keys in source control.

The OCR history is held only in memory and is cleared when the server restarts.
Run Uvicorn with a single worker: multiple workers have separate histories.

### Image cropper assets

The browser loads Cropper.js from TextRelay's `/assets/cropper.js` endpoint.
At startup, the server retrieves the pinned Cropper.js release and caches it in
`.cache`, storing the upstream ETag beside the asset. Later startups make a
conditional request and retain the cached copy after a `304 Not Modified`
response or a temporary CDN outage. Phones using TextRelay do not need outbound
internet access.

Each upload is accepted immediately and enters the shared extraction queue.
The browser shows whether each queued image is waiting, processing, completed,
or failed; up to `OCR_WORKERS` extractions run at once. Each retained OCR job
records the SHA-256 checksum and profile ID. Submitting the same bytes to the
same profile again shows an error without adding duplicate work.
When OCR fails, the server retries up to `OCR_RETRIES` additional times before
marking the job failed. Clicking Retry on a failed job starts a fresh run with
the same retry policy.

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
processing. OpenAI and Gemini modes transmit each uploaded image to their respective APIs.
Those measures do not make it safe as an internet-facing service. Do not port
forward it or expose it directly to the public internet.
