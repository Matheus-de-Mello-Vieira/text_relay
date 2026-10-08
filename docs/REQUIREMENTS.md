# LAN OCR — Requirements

## 1. Purpose

TextRelay must allow a user to send an image from a phone browser to a computer over a local network, extract printed text with a configured OCR strategy, and make the result immediately available for copying from the computer.

---

# 2. Core user workflow

The following workflow must work:

```text
1. Start LAN OCR on the computer.
2. Open LAN OCR in a browser on the computer.
3. Open LAN OCR from a phone on the same network.
4. Take or select a picture from the phone.
5. Submit the image.
6. The computer executes OCR using the configured OCR strategy.
7. The extracted text appears on the phone.
8. The extracted text automatically becomes visible on the computer.
9. The user copies the text from the computer.
```

No page reload should be required on the computer to see newly completed OCR results.

---

# 3. Functional requirements

## FR-001 — HTTP server

The application must expose an HTTP server reachable from other devices on the local network.

It must support binding to:

```text
0.0.0.0
```

---

## FR-002 — Browser UI

The application must provide a browser-based interface.

No native phone application is required.

The UI must work on:

- desktop browsers;
- mobile browsers.

---

## FR-003 — Image selection

The phone UI must allow the user to select an image.

Where supported by the browser, it should allow direct camera capture through:

```html
accept="image/*"
capture="environment"
```

---

## FR-004 — Image upload

The client must upload the selected image to the server using HTTP multipart form data.

The user must receive visible feedback while OCR is being processed.

---

## FR-005 — Supported formats

The initial version must support at least:

- JPEG;
- PNG.

WebP may also be supported.

Unsupported formats must produce a controlled error.

---

## FR-006 — OCR strategies

OCR must use one explicitly configured strategy: `tesseract` for local OCR
using Tesseract installed on the computer, or `openai` for remote vision OCR
using the OpenAI Responses API. The HTTP/API layer must depend only on the
common strategy operation. Changing providers must not require HTTP/API code
changes. Invalid provider configuration must fail clearly, and the unselected
provider must not be initialized or validated.

The local Tesseract strategy configuration must use:

The initial OCR configuration must use:

```text
language: eng
page segmentation mode: 6
```

Equivalent command:

```bash
tesseract <image> stdout -l eng --psm 6
```

The OpenAI strategy must submit the validated uploaded image as a base64 data
URL through the Responses API and return only a faithful transcription. It uses
a server-side `OPENAI_API_KEY`; normal automated tests must not make real
OpenAI requests or require a key. OpenAI mode must work without Tesseract, and
Tesseract mode must work without an OpenAI key.

---

## FR-007 — OCR result

A successful OCR operation must produce a result containing:

```text
unique ID
creation timestamp
extracted text
image checksum
```

---

## FR-008 — Phone result

After OCR completes, the phone must display the extracted text.

The user should therefore be able to verify that the correct image was processed.

---

## FR-009 — Computer synchronization

A browser already open on the computer must discover new OCR results automatically.

The implementation should use long polling.

The server may hold a results request until a new OCR result arrives or a
bounded timeout expires, after which the browser immediately opens the next
request.

---

## FR-010 — Result history

The application must retain multiple recent OCR results rather than only the latest result.

Results must be displayed newest first.

The history must be bounded.

Default:

```text
20 results
```

Restarting the server may clear the history.

---

## FR-011 — Copy action

Each OCR result shown in the browser must provide an action for copying its text to the clipboard.

The text must also remain manually selectable.

---

## FR-012 — Temporary uploads

Uploaded image data must not be permanently retained by default.

Temporary files must be deleted after OCR processing completes or fails.

---

## FR-013 — Maximum upload size

The server must reject uploads larger than a configurable limit.

Suggested default:

```text
10 MiB
```

---

## FR-014 — Empty uploads

The server must reject empty uploads.

---

## FR-015 — OCR failure

If the selected OCR provider fails, the HTTP request must fail gracefully.

The client must receive an understandable error.

The server must not expose internal Python stack traces through the API.

---

## FR-016 — Missing provider prerequisites

If Tesseract cannot be executed, the application must return a controlled error and log enough information to identify that Tesseract is unavailable. OpenAI authentication, API, and malformed-response failures must likewise return controlled errors without exposing credentials or SDK internals.

---

# 4. API requirements

## `GET /`

Must return the browser UI.

Expected:

```text
HTTP 200
Content-Type: text/html
```

---

## `POST /api/ocr`

Must accept:

```text
multipart/form-data
```

with an uploaded file field:

```text
file
```

Successful response example:

```json
{
  "id": "a6daa88c-f48b-4fe9-9310-34aa94570af2",
  "created_at": "2026-10-04T21:40:00Z",
  "text": "Extracted text",
  "image_checksum": "<SHA-256 hex digest>"
}
```

---

## `GET /api/results`

Must return recent OCR results.

Example:

```json
{
  "results": [
    {
      "id": "a6daa88c-f48b-4fe9-9310-34aa94570af2",
      "created_at": "2026-10-04T21:40:00Z",
      "text": "Newest result",
      "image_checksum": "<SHA-256 hex digest>"
    }
  ]
}
```

Results must be ordered from newest to oldest.

---

# 5. UI requirements

## Mobile

The interface must be usable without zooming or horizontal scrolling.

The primary action should be obvious:

```text
Take/select image
      ↓
Extract text
```

While OCR is running, the UI must clearly indicate that processing is in progress.

Prevent accidental duplicate submission while the current upload is still being processed.

---

## Desktop

The interface must emphasize extracted results.

Each result must show:

- extracted text;
- timestamp or relative creation time;
- Copy button.

Newest results must appear first.

---

# 6. Performance requirements

This application is optimized for interactive personal use rather than throughput.

For ordinary phone photos containing clean printed text, unnecessary delays must not be introduced around the selected OCR strategy execution.

The HTTP server must remain responsive while an OCR request is being processed.

The implementation should not deliberately serialize unrelated reads of the result history behind a long-running OCR subprocess.

---

# 7. Resource requirements

The application must not require:

- a database;
- Redis;
- a message broker;
- Docker;
- Kubernetes;
- a cloud account or external API when `OCR_PROVIDER=tesseract`;
- Node.js;
- a JavaScript build system.

Runtime requirements should remain approximately:

```text
Python
FastAPI
Uvicorn
Tesseract (local strategy) or the OpenAI Python SDK (OpenAI strategy)
```

---

# 8. Security requirements

The application is intended for a trusted local network, but must still satisfy the following:

- uploaded filenames must never be passed into shell commands;
- Tesseract must be invoked without `shell=True`;
- upload size must be bounded;
- temporary files must be cleaned up;
- arbitrary server files must not be downloadable;
- internal exceptions must not be returned to clients;
- unsupported input must be rejected cleanly.

The documentation must state that the application is not designed to be exposed directly to the public internet.

---

# 9. Configuration requirements

The following values should be configurable without changing application logic:

```text
host
port
OCR language
Tesseract page segmentation mode
OCR provider
OpenAI OCR model
OpenAI image detail
maximum upload size
maximum result history
```

Reasonable defaults must allow the application to run without explicit configuration.

Suggested values:

```text
host = 0.0.0.0
port = 8000
OCR language = eng
OCR PSM = 6
OCR provider = tesseract
OpenAI OCR model = gpt-6-luna
OpenAI image detail = high
maximum upload size = 10 MiB
maximum history = 20
```

---

# 10. Testing requirements

Automated tests must cover at least:

- successful image upload;
- result returned from OCR endpoint;
- result added to history;
- newest-first ordering;
- bounded history;
- invalid content type;
- empty upload;
- oversized upload;
- OCR subprocess failure;
- missing Tesseract behavior;
- strategy selection and invalid provider configuration;
- OpenAI data URL construction, configured model/detail, controlled failures,
  and malformed responses, using mocks/fakes only.

HTTP tests should not depend on actually invoking Tesseract unless they are specifically integration tests.

The Tesseract integration must therefore be structured so that it can be replaced or mocked during tests.

At least one real-Tesseract integration test or documented manual fixture should verify the complete OCR path.

---

# 11. Code quality requirements

The implementation should favor small modules with clear responsibilities.

At minimum, isolate:

```text
HTTP/API concerns
OCR/Tesseract execution
result storage
browser UI
```

Do not introduce architecture layers that are not justified by the project size.

The implementation should be understandable without framework-specific abstractions beyond what FastAPI naturally requires.

---

# 12. Documentation requirements

`README.md` must explain:

- project purpose;
- dependencies;
- how to install Tesseract on macOS;
- how to install Python dependencies;
- how to start the server;
- how to obtain the computer's LAN IP;
- how to open the application from the phone;
- that both devices normally need to be on the same network;
- that the service should not be exposed directly to the public internet.

Example startup command:

```bash
uvicorn lan_ocr.main:app \
  --host 0.0.0.0 \
  --port 8000
```

Example macOS LAN IP command:

```bash
ipconfig getifaddr en0
```

---

# 13. Acceptance criteria

The initial implementation is complete when all of the following are true:

- [ ] The server starts successfully on the computer.
- [ ] The computer can access the UI through `localhost`.
- [ ] A phone on the same LAN can access the UI.
- [ ] The phone can take or select a JPEG/PNG image.
- [ ] The phone can upload that image.
- [ ] Tesseract runs locally on the computer.
- [ ] TextRelay can use Tesseract as the OCR strategy.
- [ ] TextRelay can use OpenAI as the OCR strategy.
- [ ] The strategy is selected through configuration with no HTTP/API code changes.
- [ ] Invalid strategy configuration fails clearly.
- [ ] OpenAI credentials remain server-side.
- [ ] OpenAI mode works without Tesseract installed.
- [ ] Tesseract mode works without an OpenAI API key.
- [ ] Normal automated tests perform no real OpenAI requests.
- [ ] Clean printed English text is extracted.
- [ ] The result is returned to the phone.
- [ ] The result appears automatically on an already-open computer browser.
- [ ] No computer-page refresh is required.
- [ ] Multiple recent results remain visible.
- [ ] Results appear newest first.
- [ ] Each result has a working Copy action.
- [ ] Temporary uploaded images are cleaned up.
- [ ] Invalid uploads produce controlled errors.
- [ ] Tesseract failures produce controlled errors.
- [ ] Core behavior is covered by automated tests.
- [ ] The project can run without a database, Docker, or Node.js; local Tesseract mode needs no cloud service.

---

# 14. Explicit scope boundary

Codex should implement only what is necessary to satisfy this document and `DESIGN.md`.

Do not proactively add:

- authentication;
- accounts;
- persistent databases;
- WebSockets;
- React/Vue/Svelte;
- Docker;
- reverse proxies;
- cloud deployment;
- queues;
- background workers;
- elaborate dependency injection frameworks;
- generic plugin architectures.

When there is a choice between a simple implementation satisfying the requirements and a more extensible architecture, prefer the simpler implementation.
