# Parakeet Whisper STT WebUI

Parakeet Whisper STT WebUI is a local, VRAM-efficient speech-to-text application with a browser UI and a FastAPI backend. The API is intentionally close to OpenAI's audio transcription API, so agents and scripts can send `multipart/form-data` requests to `/v1/audio/transcriptions` and receive plain text, JSON, verbose JSON, SRT, or WebVTT.

The project is designed to pair well with local voice/LLM stacks such as OpenWebUI and the companion OmniVoice TTS WebUI. It exposes an OpenAI-style transcription endpoint while keeping model loading on demand and unloading idle models with a TTL.

The backend supports multiple model backends:

| Model | Backend | VRAM | Notes |
| --- | --- | --- | --- |
| `parakeet-onnx-int8` | onnx-asr | ~430 MB | **Default. Recommended for most use.** Fast, lightweight int8-quantized ONNX. English only. |
| `parakeet-onnx` | onnx-asr | ~900 MB | Full-precision ONNX variant. English only. |
| `parakeet` | NeMo | ~2.5 GB | NeMo native. Most accurate for English. Higher VRAM. |
| `whisper-turbo` | transformers | ~3 GB | OpenAI Whisper Large v3 Turbo. Best choice for non-English or auto-detect. |
| `whisper-1` | — | — | OpenAI-compatible alias for `whisper-turbo`. |

## Quick Start

Start both services with Docker Compose:

```bash
docker compose up --build
```

Default URLs:

- WebUI: `http://localhost:7861`
- Backend API: `http://localhost:8882`
- FastAPI docs: `http://localhost:8882/docs`
- OpenAPI schema: `http://localhost:8882/openapi.json`

The frontend container serves the WebUI with nginx and proxies `/v1/*` API calls to the backend. If an agent is running outside Docker, use the backend directly at `http://localhost:8882`.

## Configuration

Copy the public example to a private local `.env` file:

```bash
cp .env-example .env
```

`.env` is ignored by git. Common variables:

- `STT_BACKEND_PORT`: host port for the transcription API
- `STT_FRONTEND_PORT`: host port for the browser UI
- `CUDA_VISIBLE_DEVICES`: GPU selection for Docker
- `MODEL_TTL_SECONDS`: unload idle models after this many seconds
- `UPLOAD_DIR`: temporary upload directory inside the backend container
- `API_URL`: frontend dev/preview proxy target; production Docker uses nginx

## OpenWebUI / Companion Usage

Use the backend as an OpenAI-compatible transcription service at:

```text
http://localhost:8882/v1/audio/transcriptions
```

For a lightweight default, use `parakeet-onnx-int8`. For multilingual or
auto-detect transcription, use `whisper-turbo` or the OpenAI-compatible alias
`whisper-1`.

This repo can run alongside the OmniVoice TTS WebUI: STT lives here, TTS and
voice cloning live in the OmniVoice repo.

## Agent Usage

An AI agent should use the API in this order:

1. Check availability with `GET /`.
2. Discover valid model IDs with `GET /v1/models`.
3. Optionally inspect model load state and GPU memory with `GET /v1/status`.
4. Send audio to `POST /v1/audio/transcriptions`.
5. Use `POST /v1/models/flush` only when it needs to reclaim all model memory.

Minimal transcription request (uses default model `parakeet-onnx-int8`):

```bash
curl -s http://localhost:8882/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F response_format=verbose_json
```

With an explicit model:

```bash
curl -s http://localhost:8882/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=parakeet-onnx-int8 \
  -F response_format=verbose_json
```

OpenAI-compatible alias:

```bash
curl -s http://localhost:8882/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=whisper-1
```

Python example:

```python
import requests

base_url = "http://localhost:8882"

with open("audio.wav", "rb") as audio:
    response = requests.post(
        f"{base_url}/v1/audio/transcriptions",
        files={"file": ("audio.wav", audio, "audio/wav")},
        data={
            "model": "parakeet-onnx-int8",
            "language": "en",
            "response_format": "verbose_json",
        },
        timeout=600,
    )

response.raise_for_status()
print(response.json()["text"])
```

JavaScript example:

```js
const form = new FormData();
form.append("file", audioFile);
form.append("model", "parakeet-onnx-int8");
form.append("response_format", "json");

const response = await fetch("http://localhost:8882/v1/audio/transcriptions", {
  method: "POST",
  body: form,
});

if (!response.ok) {
  throw new Error(await response.text());
}

const result = await response.json();
console.log(result.text);
```

## API Reference

### `GET /`

Health check.

Response:

```json
{
  "status": "ok",
  "service": "stt-webui"
}
```

### `GET /v1/models`

List available model IDs. This endpoint follows the OpenAI model-list shape.

Response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "whisper-turbo",
      "object": "model",
      "owned_by": "whisper",
      "description": "OpenAI Whisper Large v3 Turbo"
    },
    {
      "id": "whisper-1",
      "object": "model",
      "owned_by": "openai",
      "description": "Alias for whisper-turbo"
    }
  ]
}
```

Agents should use `id` values from this response as the `model` form field. The frontend hides alias entries, but the API accepts aliases.

### `POST /v1/audio/transcriptions`

Transcribe an uploaded audio file.

Content type: `multipart/form-data`

Fields:

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes | none | Audio upload. Browser recordings are sent as `recording.webm`; uploaded files may be any ffmpeg-readable audio format. |
| `model` | no | `parakeet-onnx-int8` | Model ID or alias. Use `GET /v1/models` to discover valid values. |
| `language` | no | backend-specific | Optional language hint such as `en`, `de`, or `ja`. Whisper receives this as a generation hint. Parakeet and ONNX currently do not use it for decoding, but include it or a backend default in verbose output. |
| `response_format` | no | `json` | One of `json`, `verbose_json`, `text`, `srt`, or `vtt`. |

Supported response formats:

`json`:

```json
{
  "text": "Transcribed speech."
}
```

`verbose_json`:

```json
{
  "text": "Transcribed speech.",
  "language": "en",
  "duration": 12.34,
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.5,
      "text": "Transcribed speech."
    }
  ]
}
```

`text`:

```text
Transcribed speech.
```

`srt`:

```text
1
00:00:00,000 --> 00:00:02,500
Transcribed speech.
```

`vtt`:

```text
WEBVTT

00:00:00.000 --> 00:00:02.500
Transcribed speech.
```

OpenAI compatibility notes:

- The endpoint path and core fields are OpenAI-compatible.
- `model`, `language`, and `response_format` are supported.
- Parameters such as `prompt`, `temperature`, `timestamp_granularities`, and translation endpoints are not implemented.
- There is no authentication layer in this project.
- CORS is open on the backend.

Audio handling:

- NeMo Parakeet and ONNX Parakeet inputs are converted to 16 kHz mono WAV with `ffmpeg`.
- Whisper uses the `transformers` audio pipeline directly.
- Temporary uploaded files are written to `UPLOAD_DIR` and removed after each request.
- The nginx frontend proxy allows request bodies up to `100m`.

Error responses:

- Unknown model: HTTP `400`
- Unsupported `response_format`: HTTP `400`
- Invalid or unconvertible audio for Parakeet/ONNX conversion: HTTP `400`
- Model download/load failures may return HTTP `500`

Example error body:

```json
{
  "detail": "Invalid response_format: xml. Supported: {'json', 'verbose_json', 'text', 'srt', 'vtt'}"
}
```

### `GET /v1/status`

Return model load state, model TTL countdowns, and CUDA VRAM usage when CUDA is available.

Response:

```json
{
  "ttl_seconds": 300,
  "models": {
    "whisper-turbo": {
      "status": "loaded",
      "idle_seconds": 14,
      "ttl_remaining": 286,
      "ttl_total": 300
    },
    "parakeet": {
      "status": "unloaded"
    }
  },
  "vram": {
    "total_mb": 24564,
    "allocated_mb": 5120,
    "reserved_mb": 6144
  }
}
```

Possible model statuses:

- `unloaded`: model is not in memory
- `loading`: background loading has been started
- `loaded`: model is cached and ready

The status tab in the WebUI polls this endpoint every 5 seconds.

### `POST /v1/models/{name}/load`

Load a model into memory before transcription.

Example:

```bash
curl -X POST http://localhost:8882/v1/models/whisper-turbo/load
```

Response:

```json
{
  "status": "loaded",
  "model": "whisper-turbo"
}
```

This request blocks until the model is loaded. First load may take a long time because weights can be downloaded from Hugging Face.

### `POST /v1/models/{name}/unload`

Unload one model.

Example:

```bash
curl -X POST http://localhost:8882/v1/models/whisper-turbo/unload
```

Response when loaded:

```json
{
  "status": "unloaded",
  "model": "whisper-turbo"
}
```

Response when it was already unloaded:

```json
{
  "status": "already_unloaded",
  "model": "whisper-turbo"
}
```

### `POST /v1/models/flush`

Unload all cached models and aggressively clear CUDA memory.

Example:

```bash
curl -X POST http://localhost:8882/v1/models/flush
```

Response:

```json
{
  "status": "flushed",
  "unloaded": ["whisper-turbo"],
  "vram_after": {
    "allocated_mb": 0,
    "reserved_mb": 0
  }
}
```

Use this when an agent needs to release VRAM before switching workloads or recovering from memory pressure.

## WebUI Behavior

The browser UI has two tabs:

- Transcribe: record microphone audio or upload an audio file, choose a model, optionally set language, choose response format, and display the result.
- Status: inspect VRAM and model TTL state, load a model, unload a model, or flush all models.

Important frontend details:

- Browser recordings use `MediaRecorder` and are submitted as `recording.webm`.
- Uploaded files are sent directly as the `file` form field.
- The WebUI sends requests to relative `/v1/*` paths. In Docker, nginx proxies those requests to the backend service.
- When `response_format` is `text`, `srt`, or `vtt`, the UI reads the response as text.
- When `response_format` is `json` or `verbose_json`, the UI reads JSON and displays `text`.
- For `verbose_json`, timestamp segments are also rendered in the Segments box.

## Configuration

Environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `MODEL_TTL_SECONDS` | `300` | Idle seconds before loaded models are automatically unloaded. |
| `UPLOAD_DIR` | `/tmp/stt-uploads` | Directory for temporary uploaded audio files. Created on startup. |
| `CUDA_VISIBLE_DEVICES` | set in `docker-compose.yaml` to `0` | Selects the GPU visible to the backend container. |

Docker Compose mounts `~/.cache/huggingface` into the backend container at `/root/.cache/huggingface` so downloaded model weights persist across restarts.

## Operational Notes

- Models load on demand. The first transcription with a model may be slow.
- A background cleanup task checks idle models every 60 seconds and unloads models whose TTL expired.
- Manual load/unload and transcription share the same in-process model cache.
- The backend uses CUDA when `torch.cuda.is_available()`; otherwise it runs on CPU.
- `ffmpeg` is required for Parakeet/ONNX audio conversion and is installed in the backend Docker image.
- The backend has no request queue. Agents should avoid launching many large transcription requests at the same time unless the host has enough CPU, RAM, and VRAM.

## Project Layout

```text
backend/
  serve.py              FastAPI app, CORS, router registration, TTL cleanup startup
  config.py             model registry, aliases, response formats, environment config
  model_manager.py      model loading, cache, unload, flush, TTL cleanup
  routes/transcribe.py  transcription endpoint and response formatting
  routes/models.py      model list, status, load, unload, flush endpoints
  format_utils.py       SRT and WebVTT formatting helpers
  schemas.py            Pydantic response models
frontend/
  index.html            WebUI structure
  src/main.ts           tab and module initialization
  src/recorder.ts       microphone recording
  src/transcribe.ts     transcription form submission and response rendering
  src/status.ts         model/status polling and controls
  nginx.conf            static frontend server and /v1 reverse proxy
docker-compose.yaml     backend and frontend services
```

## Adding Models

To add a model, update `MODEL_CONFIGS` in `backend/config.py` with a new key and backend configuration. The current loader supports these backend values:

- `transformers`: loaded by `_load_whisper`
- `nemo`: loaded by `_load_parakeet`
- `onnx`: loaded by `_load_parakeet_onnx`

If the new model should have an OpenAI-compatible alias, add it to `OPENAI_MODEL_MAP`.

After changing model configuration, restart the backend. The frontend model selectors are populated from `GET /v1/models`, so non-alias model IDs appear automatically.
