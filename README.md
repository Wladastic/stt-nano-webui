# Parakeet-v3 & Whisper-Turbo STT Nano WebUI

A local, VRAM-efficient speech-to-text WebUI and API built around NVIDIA
Parakeet v3 and Whisper Large v3 Turbo.
I built this to use with my AI Agents to talk to them and expect a fast response.

Works well with Openclaw and Openwebui.

The rest of the readme is Vibe-Coded, I only fixed what I found, like the Ram usage, if anything is off, create an Issue for that, or better, create a Pull Request and I will review it.

The Parakeet model is being pulled from:
https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx
Thanks for your work, istupanov!

The backend exposes an OpenAI-style transcription endpoint, so local tools,
agents, and OpenWebUI-style setups can send audio to
`/v1/audio/transcriptions` and receive `json`, `verbose_json`, `text`, `srt`,
or `vtt` responses.
Parakeet v3 is returning 0.0 timestamps though, if you need accurate timestamps, use the `whisper-turbo` model.

## Highlights

- Browser WebUI for recording, uploading, transcribing, and inspecting model state
- FastAPI backend with OpenAI-compatible transcription shape
- Lightweight default model: `parakeet-onnx-int8`
- Optional full ONNX, NeMo Parakeet, and Whisper Turbo backends
- Model load/unload controls and automatic TTL cleanup
- CUDA VRAM status endpoint
- Docker Compose setup with persistent Hugging Face cache

## Models

| Model | Backend | Typical VRAM | Best For |
| --- | --- | --- | --- |
| `parakeet-onnx-int8` | ONNX int8 | ~800 MB | Default, fast and accurate with low VRAM use |
| `parakeet-onnx` | ONNX | ~1600 MB | Pedantic usage |
| `parakeet` | NeMo | ~2.5 GB | Most accurate Parakeet path, higher VRAM |
| `whisper-turbo` | Transformers | ~3 GB | Multilingual and auto-detect transcription |
| `whisper-1` | Alias | same as `whisper-turbo` | OpenAI-compatible model name |

## Quick Start

```bash
cp .env-example .env
docker compose up --build
```

Default URLs:

- WebUI: `http://localhost:7861`
- Backend API: `http://localhost:8882`
- FastAPI docs: `http://localhost:8882/docs`
- OpenAPI schema: `http://localhost:8882/openapi.json`

The frontend container serves static files with nginx and proxies `/v1/*` to the
backend container. External clients can call the backend directly at
`http://localhost:8882`.

## Configuration

Copy `.env-example` to `.env` and adjust local settings there. `.env` is ignored
by git.

| Variable | Default | Description |
| --- | --- | --- |
| `STT_BACKEND_PORT` | `8882` | Host port for the transcription API |
| `STT_FRONTEND_PORT` | `7861` | Host port for the WebUI |
| `CUDA_VISIBLE_DEVICES` | `0` | GPU visible to the backend container |
| `MODEL_TTL_SECONDS` | `300` | Idle seconds before loaded models unload |
| `UPLOAD_DIR` | `/tmp/stt-uploads` | Temporary upload directory in the backend container |
| `API_URL` | `http://localhost:8882` | Vite dev/preview proxy target; production Docker uses nginx |

Docker Compose mounts `~/.cache/huggingface` into the backend container so model
weights persist across restarts.

## API Usage

Health check:

```bash
curl http://localhost:8882/
```

List models:

```bash
curl http://localhost:8882/v1/models
```

Transcribe with the default low-VRAM model:

```bash
curl -s http://localhost:8882/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F response_format=verbose_json
```

Transcribe with Whisper Turbo through the OpenAI-compatible alias:

```bash
curl -s http://localhost:8882/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=whisper-1 \
  -F response_format=json
```

Supported form fields for `POST /v1/audio/transcriptions`:

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `file` | yes | none | Audio upload; any ffmpeg-readable format for Parakeet/ONNX |
| `model` | no | `parakeet-onnx-int8` | Model id or alias from `GET /v1/models` |
| `language` | no | backend-specific | Optional hint such as `en`, `de`, or `ja`; mainly useful for Whisper |
| `response_format` | no | `json` | `json`, `verbose_json`, `text`, `srt`, or `vtt` |

OpenAI compatibility notes:

- Endpoint path and core multipart fields match OpenAI-style transcription use.
- `whisper-1` is accepted as an alias for `whisper-turbo`.
- Authentication is not implemented.
- Translation endpoints and advanced OpenAI parameters such as `prompt`,
  `temperature`, and `timestamp_granularities` are not implemented.
- CORS is open on the backend.

## Model Management

The backend loads models on demand and unloads idle models after
`MODEL_TTL_SECONDS`.

Useful endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/status` | Model cache state, TTL countdowns, and CUDA VRAM usage |
| `POST /v1/models/{name}/load` | Load one model before transcription |
| `POST /v1/models/{name}/unload` | Unload one model |
| `POST /v1/models/flush` | Unload all models and clear CUDA memory |

Flush all models before switching workloads:

```bash
curl -X POST http://localhost:8882/v1/models/flush
```

## OpenWebUI And Companion Use

Use this repo as the local STT side of a voice stack:

```text
http://localhost:8882/v1/audio/transcriptions
```

It pairs with the OmniVoice TTS Nano WebUI repo: this project handles
speech-to-text, while OmniVoice handles TTS, voice cloning, and voice design.

## WebUI

The WebUI has two main areas:

- Transcribe: record microphone audio or upload a file, choose a model, set an
  optional language hint, choose response format, and view the output.
- Status: inspect loaded models, VRAM usage, TTL state, and manually load,
  unload, or flush models.

## Project Layout

```text
backend/
  serve.py              FastAPI app and router registration
  config.py             model registry, aliases, response formats, env config
  model_manager.py      model loading, cache, unload, flush, TTL cleanup
  routes/transcribe.py  transcription endpoint and response formatting
  routes/models.py      model list, status, load, unload, flush endpoints
  format_utils.py       SRT and WebVTT helpers
  schemas.py            Pydantic response models
frontend/
  index.html            WebUI shell
  src/                  TypeScript UI modules
  nginx.conf            static frontend server and /v1 reverse proxy
docker-compose.yaml     backend and frontend services
```

## Notes

- The first transcription with a model may take time because weights are loaded
  or downloaded from Hugging Face.
- Parakeet and ONNX inputs are converted to 16 kHz mono WAV with `ffmpeg`.
- Whisper uses the Transformers audio pipeline directly.
- Temporary uploads are removed after each request.
- The backend has no authentication layer; keep it behind trusted local network
  boundaries unless you add your own access control.
