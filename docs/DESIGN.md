# LAN OCR — Design

## 1. Overview

LAN OCR is a small local HTTP application that allows a phone to send an image to a computer over the local network.

The computer runs OCR on the uploaded image using a configured OCR strategy and exposes the extracted text through a browser interface.

The intended workflow is:

```text
Phone
  ↓
Take/select image
  ↓
Upload through browser
  ↓
Computer receives image
  ↓
Configured OCR strategy extracts text
  ↓
Result is stored temporarily
  ↓
Computer browser receives/displays result
  ↓
User copies text
```

The application is intended for personal use on a trusted local network.

It is not intended to be an internet-facing service.

---

# 2. Goals

The project should optimize for:

- very small implementation;
- simple local deployment;
- minimal dependencies;
- low operational overhead;
- fast OCR of clean printed English text;
- easy use from a phone browser;
- easy copying of results from a computer;
- no persistent infrastructure requirements.

The application should be usable without:

- a database;
- Docker;
- a JavaScript framework;
- authentication;
- cloud services or external OCR APIs when the local Tesseract strategy is selected.

---

# 3. Non-goals

The initial version does not need to support:

- handwritten text;
- complex document analysis;
- table extraction;
- semantic document reconstruction;
- user accounts;
- public internet access;
- synchronization between multiple computers;
- long-term image storage;
- long-term OCR history;
- multi-user isolation;
- distributed execution;
- image editing;
- PDF OCR.

These may be added later if there is a demonstrated need.

---

# 4. Technology stack

## Backend

Use Python with FastAPI.

Responsibilities:

- serve the web UI;
- accept image uploads;
- invoke the configured OCR strategy;
- retain recent OCR results;
- expose recent results to browser clients.

Recommended runtime:

```text
Python 3.12+
FastAPI
Uvicorn
python-multipart
```

Avoid introducing additional libraries unless they solve a concrete requirement.

---

# 5. OCR strategies

The application owns a small `OCRStrategy` protocol with one asynchronous
operation: it accepts validated image bytes and their MIME type, then returns
transcribed text. Strategy construction occurs once in the application factory
from validated settings; request handlers do not branch by provider.

Two concrete strategies are intentionally supported:

- `TesseractOCRStrategy`: writes a temporary validated image, calls Tesseract
  without a shell, and removes the temporary file.
- `OpenAIOCRStrategy`: uses the official asynchronous OpenAI SDK Responses API,
  sends a base64 data URL, and asks for faithful transcription.

Tesseract is the local strategy.

The primary expected input is:

- English;
- clean printed text;
- conventional fonts;
- reasonably sharp images.

Default invocation:

```bash
tesseract <image> stdout -l eng --psm 6
```

`--psm 6` should initially be used because the primary use case is an image containing a block of text.

OpenAI is the remote vision strategy. It uses a server-side `OPENAI_API_KEY`, a
configurable model (default `gpt-6-luna`), and a configurable image detail
(default `high`). The API key never reaches browser JavaScript or API responses.
OpenAI mode sends each uploaded image to the OpenAI API and may incur usage cost.

---

# 6. High-level architecture

```text
┌─────────────────────┐
│     Phone Browser   │
│                     │
│ Camera / file input │
└──────────┬──────────┘
           │
           │ HTTP multipart upload
           ▼
┌─────────────────────┐
│     FastAPI App     │
│                     │
│ POST /api/ocr       │
└──────────┬──────────┘
           │
           │ validated bytes + MIME type
           ▼
┌─────────────────────┐
│    OCRStrategy      │
└──────────┬──────────┘
           │
       ┌───┴────┐
       ▼        ▼
┌────────────┐ ┌────────────┐
│ Tesseract  │ │   OpenAI   │
│   Local    │ │   Vision   │
└────────────┘ └────────────┘
           │
           ▼
┌─────────────────────┐
│   In-memory Store   │
│                     │
│ recent OCR results  │
└──────────┬──────────┘
           │
           │ polling
           ▼
┌─────────────────────┐
│   Computer Browser  │
│                     │
│ Results + Copy      │
└─────────────────────┘
```

---

# 7. HTTP interface

Keep the HTTP interface small.

## `GET /`

Serve the web application.

The same page should work on both:

- phone;
- computer.

The UI may adapt responsively according to screen size.

---

## `POST /api/ocr`

Accept one image as multipart form data.

Example request field:

```text
file
```

Process:

```text
receive upload
    ↓
validate
    ↓
read validated image bytes
    ↓
call OCRStrategy.extract_text
    ↓
create OCR result
    ↓
return result
```

Example response:

```json
{
  "id": "0199...",
  "created_at": "2026-10-04T21:30:00Z",
  "text": "Recognized text..."
}
```

Do not expose the server's temporary filesystem paths.

---

## `GET /api/results`

Return recent OCR results in reverse chronological order.

Example:

```json
{
  "results": [
    {
      "id": "0199...",
      "created_at": "2026-10-04T21:30:00Z",
      "text": "Newest OCR result"
    },
    {
      "id": "0198...",
      "created_at": "2026-10-04T21:28:00Z",
      "text": "Previous OCR result"
    }
  ]
}
```

The initial implementation may keep only a small bounded number of entries.

For example:

```text
20 results
```

The exact limit should be represented by a named configuration constant rather than scattered throughout the code.

---

# 8. Result model

Each OCR result should contain at least:

```text
id
created_at
text
```

Suggested representation:

```python
@dataclass(frozen=True)
class OCRResult:
    id: str
    created_at: datetime
    text: str
```

A Pydantic model is also acceptable if it makes FastAPI integration cleaner.

The identifier should be unique but does not need to encode business meaning.

UUID is sufficient.

---

# 9. Result storage

Use an in-memory bounded collection.

For example:

```text
deque(maxlen=20)
```

Persistence across application restarts is not required.

This means restarting the server intentionally clears history.

This is acceptable for the intended workflow.

Do not introduce SQLite or another database in the first implementation.

---

# 10. Concurrency

The result store must be safe if multiple HTTP requests occur concurrently.

The implementation should not rely accidentally on CPython behavior for correctness.

Use an explicit synchronization mechanism where needed.

The design should remain simple because:

- write frequency will be low;
- result history is small;
- this is a single-process local service.

If Uvicorn is run with multiple worker processes, in-memory state would no longer be shared.

Therefore the application should initially assume:

```text
one process
one Uvicorn worker
```

Document this constraint.

Do not solve distributed state until it becomes necessary.

---

# 11. Temporary files

Uploaded images should be temporary.

The server should:

1. create a temporary file;
2. write the uploaded image;
3. pass its path to Tesseract;
4. remove the temporary file regardless of OCR success or failure.

Prefer constructs that guarantee cleanup.

For example:

```python
with tempfile.NamedTemporaryFile(...) as file:
    ...
```

or an equivalent `try/finally` implementation.

Images should not remain permanently stored on disk.

---

# 12. Local Tesseract subprocess

Invoke Tesseract directly without going through a shell.

Preferred:

```python
subprocess.run(
    [
        "tesseract",
        image_path,
        "stdout",
        "-l",
        "eng",
        "--psm",
        "6",
    ],
    ...
)
```

Do not use:

```python
shell=True
```

User-controlled filenames must never become executable shell syntax.

Capture:

- stdout;
- stderr;
- exit status.

Tesseract failures become controlled application OCR errors rather than exposing
a Python traceback. The OpenAI strategy applies the same application-level
error boundary to SDK authentication, API, and malformed-response failures.

---

# 13. Upload validation

The endpoint should reject obviously invalid inputs.

At minimum:

- missing upload;
- empty file;
- file exceeding configured maximum size;
- unsupported content type.

Initially accepted image types may include:

```text
image/jpeg
image/png
image/webp
```

The maximum upload size should be configurable.

A reasonable initial default is:

```text
10 MiB
```

Do not depend exclusively on the original filename extension for validation.

This is primarily defensive correctness rather than protection against hostile internet traffic.

---

# 14. Web interface

The UI should deliberately remain simple.

## Phone

The primary phone interaction is:

```text
Take photo / select image
        ↓
Upload
        ↓
Receive confirmation
```

Use:

```html
<input
    type="file"
    accept="image/*"
    capture="environment"
>
```

This allows mobile browsers to offer the camera directly when supported.

The UI should clearly indicate:

- selected file;
- upload/OCR in progress;
- success;
- failure.

The phone should also display the extracted result after completion so that it can be verified immediately.

---

# 15. Computer interface

The computer page should display recent OCR results.

Suggested layout:

```text
LAN OCR

Latest results

┌──────────────────────────────────────┐
│ 18:53                                │
│                                      │
│ The newest extracted text...         │
│                                      │
│                            [Copy]     │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ 18:49                                │
│                                      │
│ Previous extraction...               │
│                                      │
│                            [Copy]     │
└──────────────────────────────────────┘
```

The newest result must appear first.

Each result should have its own copy button.

The text should also remain manually selectable.

---

# 16. Browser synchronization

Use long polling for result synchronization.

The browser requests recent results and includes the newest result identifier it
has seen. If no newer result exists, the server holds the request until a result
arrives or a bounded timeout expires. The browser then immediately starts the
next request.

Advantages:

- avoids an unnecessary request every second when history is unchanged;
- easy reconnection;
- no stateful socket;
- no WebSocket lifecycle handling.

Do not introduce WebSockets initially.

Server-Sent Events may later replace polling if there is a concrete benefit, but they are not necessary for the first version.

The frontend should update the DOM only when the result set changes.

---

# 17. Clipboard behavior

Each OCR result must provide a Copy action.

Preferred implementation:

```javascript
navigator.clipboard.writeText(text)
```

If clipboard access is unavailable because of browser security restrictions, the text must still be:

- visible;
- selectable;
- manually copyable.

Clipboard convenience must not be required for core functionality.

---

# 18. Error handling

Errors should be understandable to the user.

Examples:

```text
Unsupported image type.
Image is too large.
OCR failed.
Tesseract is not installed.
Could not process the uploaded image.
```

Do not expose internal stack traces in HTTP responses.

Server logs should retain enough information to diagnose failures.

---

# 19. Configuration

Configuration should stay minimal.

Candidate settings:

```text
HOST
PORT
OCR_PROVIDER
OCR_LANGUAGE
OCR_PSM
OPENAI_OCR_MODEL
OPENAI_IMAGE_DETAIL
MAX_UPLOAD_SIZE
MAX_RESULT_HISTORY
```

Defaults should work without environment configuration.

Suggested defaults:

```text
HOST=0.0.0.0
PORT=8000
OCR_LANGUAGE=eng
OCR_PSM=6
MAX_UPLOAD_SIZE=10 MiB
MAX_RESULT_HISTORY=20
```

Do not introduce a complex configuration framework.

---

# 20. Local networking

The server must bind to:

```text
0.0.0.0
```

rather than only:

```text
127.0.0.1
```

so that other devices on the LAN can reach it.

Example:

```bash
uvicorn lan_ocr.main:app \
  --host 0.0.0.0 \
  --port 8000
```

Typical access:

Computer:

```text
http://localhost:8000
```

Phone:

```text
http://<computer-lan-ip>:8000
```

Both devices must normally be on the same local network.

---

# 21. Security boundary

The application is explicitly designed for a trusted LAN.

Nevertheless:

- never invoke uploaded values through a shell;
- enforce upload size limits;
- restrict accepted input types;
- avoid preserving uploaded images;
- do not serve arbitrary filesystem paths;
- do not expose internal exceptions.

The README must warn against exposing the service directly to the public internet.

If public access is ever required, authentication and transport security become separate design requirements.

---

# 22. Suggested project structure

Keep the project small but separate responsibilities.

```text
lan-ocr/
├── lan_ocr/
│   ├── __init__.py
│   ├── main.py
│   ├── ocr.py              # OCRStrategy and provider selection
│   ├── tesseract_ocr.py
│   ├── openai_ocr.py
│   ├── store.py
│   └── static/
│       └── index.html
├── tests/
│   ├── test_api.py
│   ├── test_ocr.py
│   └── test_store.py
├── DESIGN.md
├── REQUIREMENTS.md
├── README.md
├── pyproject.toml
└── .gitignore
```

Responsibilities:

```text
main.py
    HTTP application and routes

ocr.py
    OCRStrategy boundary and explicit provider selection

tesseract_ocr.py
    local Tesseract strategy

openai_ocr.py
    remote OpenAI Responses API strategy

store.py
    bounded in-memory result history

static/index.html
    browser UI

tests/
    automated tests
```

Avoid adding layers such as:

```text
repositories/
services/
use_cases/
controllers/
domain/
```

unless the application actually becomes complex enough to justify them.

---

# 23. Testing strategy

The test suite should distinguish application behavior from real OCR integration.

## Unit tests

Test:

- result history ordering;
- history size limit;
- OCR command construction;
- error handling;
- upload validation.

Do not require Tesseract to execute for every HTTP test.

Mock or inject the OCR function where appropriate.

## Integration test

Have at least one integration test or manual test fixture containing clean printed English text.

The purpose is to verify:

```text
image
  ↓
real Tesseract
  ↓
expected recognizable text
```

OCR output should not necessarily be asserted character-for-character if insignificant whitespace differences are possible.

---

# 24. Implementation principles

Prefer:

```text
simple > extensible
explicit > magical
standard library > unnecessary dependency
bounded state > persistent infrastructure
plain HTML/JS > frontend framework
```

The project should remain understandable by reading a handful of small files.

Do not preemptively design for scale the application does not have.

---

# 25. Potential future improvements

These are explicitly outside the initial implementation.

Possible later extensions include:

- configurable Tesseract page segmentation modes;
- multiple OCR languages;
- drag-and-drop uploads;
- paste-from-clipboard image upload;
- image preprocessing;
- automatic deskew;
- contrast enhancement;
- result deletion;
- clear-history button;
- Server-Sent Events;
- installable PWA;
- local hostname via mDNS;
- QR code containing the phone URL;
- HTTPS for LAN use;
- PDF support;
- PaddleOCR backend;
- OCR confidence metadata.

Implement them only when requested.
