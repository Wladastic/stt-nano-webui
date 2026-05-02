"""
POST /v1/audio/transcriptions — OpenAI-compatible transcription endpoint.
Accepts multipart form data with audio file + options.
"""
import os
import logging
import tempfile
import subprocess

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.concurrency import run_in_threadpool

from config import MODEL_CONFIGS, OPENAI_MODEL_MAP, RESPONSE_FORMATS, UPLOAD_DIR
from model_manager import get_model
from format_utils import segments_to_srt, segments_to_vtt

logger = logging.getLogger(__name__)

router = APIRouter()


def _convert_to_wav16k(input_path: str) -> str:
    """Convert any audio file to 16kHz mono WAV using ffmpeg."""
    output_path = input_path + ".16k.wav"
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1", "-f", "wav", output_path
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg conversion failed: {e.stderr.decode()}")
        raise HTTPException(status_code=400, detail="Audio conversion failed. Ensure a valid audio file was uploaded.")
    return output_path


def _transcribe_nemo(model, audio_path: str, language: str | None) -> dict:
    """Transcribe using NeMo ASR model (Parakeet)."""
    # Parakeet expects 16kHz WAV
    wav_path = _convert_to_wav16k(audio_path)
    try:
        output = model.transcribe([wav_path], timestamps=True)
        hyp = output[0]

        text = hyp.text if hasattr(hyp, 'text') else str(hyp)

        # Extract segments from NeMo timestamp dict
        segments = []
        ts = getattr(hyp, 'timestamp', None)
        if isinstance(ts, dict) and 'segment' in ts:
            for i, seg in enumerate(ts['segment']):
                segments.append({
                    "id": i,
                    "start": round(seg['start'], 3),
                    "end": round(seg['end'], 3),
                    "text": seg['segment'],
                })

        if not segments:
            segments = [{"id": 0, "start": 0.0, "end": 0.0, "text": text}]

        return {
            "text": text,
            "language": language or "en",
            "duration": segments[-1]["end"] if segments and segments[-1]["end"] > 0 else None,
            "segments": segments,
        }
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)


def _transcribe_whisper(pipe, audio_path: str, language: str | None) -> dict:
    """Transcribe using Whisper transformers pipeline."""
    generate_kwargs = {}
    if language:
        generate_kwargs["language"] = language

    result = pipe(
        audio_path,
        return_timestamps=True,
        generate_kwargs=generate_kwargs,
    )

    text = result.get("text", "").strip()
    chunks = result.get("chunks", [])

    segments = []
    for i, chunk in enumerate(chunks):
        ts = chunk.get("timestamp", (0.0, 0.0))
        start = ts[0] if ts[0] is not None else 0.0
        end = ts[1] if ts[1] is not None else start
        segments.append({
            "id": i,
            "start": round(start, 3),
            "end": round(end, 3),
            "text": chunk.get("text", "").strip(),
        })

    if not segments:
        segments = [{"id": 0, "start": 0.0, "end": 0.0, "text": text}]

    return {
        "text": text,
        "language": language,
        "duration": segments[-1]["end"] if segments and segments[-1]["end"] > 0 else None,
        "segments": segments,
    }


def _transcribe_onnx(model, audio_path: str, language: str | None) -> dict:
    """Transcribe using ONNX Parakeet model via onnx-asr."""
    wav_path = _convert_to_wav16k(audio_path)
    try:
        result = model.recognize(wav_path)

        text = str(result) if result else ""

        # onnx-asr doesn't always give timestamps, so we do a single segment
        segments = [{"id": 0, "start": 0.0, "end": 0.0, "text": text}]

        return {
            "text": text,
            "language": language or "de",
            "duration": None,
            "segments": segments,
        }
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)


def _format_response(result: dict, response_format: str):
    """Render transcription result in the requested format."""
    if response_format == "text":
        return PlainTextResponse(content=result["text"])
    elif response_format == "srt":
        return PlainTextResponse(content=segments_to_srt(result["segments"]))
    elif response_format == "vtt":
        return PlainTextResponse(content=segments_to_vtt(result["segments"]))
    elif response_format == "verbose_json":
        return JSONResponse(content={
            "text": result["text"],
            "language": result.get("language"),
            "duration": result.get("duration"),
            "segments": result["segments"],
        })
    else:  # json (default)
        return JSONResponse(content={"text": result["text"]})


@router.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form("parakeet-onnx-int8"),
    language: str | None = Form(None),
    response_format: str = Form("json"),
):
    """OpenAI-compatible transcription endpoint."""
    # Resolve model alias
    resolved_model = OPENAI_MODEL_MAP.get(model, model)
    if resolved_model not in MODEL_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: {model}. Available: {list(MODEL_CONFIGS.keys()) + list(OPENAI_MODEL_MAP.keys())}",
        )

    if response_format not in RESPONSE_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid response_format: {response_format}. Supported: {RESPONSE_FORMATS}",
        )

    # Save uploaded file to temp location
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    tmp = tempfile.NamedTemporaryFile(dir=UPLOAD_DIR, suffix=suffix, delete=False)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()

        # Load model and transcribe outside the async event loop so /v1/status
        # remains responsive during long model loads or transcription calls.
        config = MODEL_CONFIGS[resolved_model]
        loaded_model = await run_in_threadpool(get_model, resolved_model)

        if config["backend"] == "nemo":
            result = await run_in_threadpool(_transcribe_nemo, loaded_model, tmp.name, language)
        elif config["backend"] == "onnx":
            result = await run_in_threadpool(_transcribe_onnx, loaded_model, tmp.name, language)
        else:
            result = await run_in_threadpool(_transcribe_whisper, loaded_model, tmp.name, language)

        return _format_response(result, response_format)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


@router.get("/")
async def health():
    return {"status": "ok", "service": "stt-webui"}
