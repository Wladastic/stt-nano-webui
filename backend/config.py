"""
Configuration constants for STT server.
All env-driven settings, model configs, and defaults live here.
"""
import os

# Model configurations
MODEL_CONFIGS = {
    "parakeet": {
        "hf_id": "nvidia/parakeet-tdt-0.6b-v3",
        "backend": "nemo",
        "description": "NVIDIA Parakeet TDT 0.6B v3 (NeMo)",
    },
    "parakeet-onnx": {
        "hf_id": "istupakov/parakeet-tdt-0.6b-v3-onnx",
        "backend": "onnx",
        "description": "NVIDIA Parakeet TDT 0.6B v3 (ONNX, lightweight)",
    },
    "parakeet-onnx-int8": {
        "hf_id": "istupakov/parakeet-tdt-0.6b-v3-onnx",
        "backend": "onnx",
        "quantization": "int8",
        "description": "NVIDIA Parakeet TDT 0.6B v3 (ONNX int8, ~700MB)",
    },
    "whisper-turbo": {
        "hf_id": "openai/whisper-large-v3-turbo",
        "backend": "transformers",
        "description": "OpenAI Whisper Large v3 Turbo",
    },
}

# OpenAI API alias mapping
OPENAI_MODEL_MAP = {
    "whisper-1": "whisper-turbo",
}

# TTL for models (seconds). Models are unloaded after this idle period.
MODEL_TTL_SECONDS = int(os.getenv("MODEL_TTL_SECONDS", "300"))

# Upload directory for temporary audio files
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/stt-uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Supported response formats
RESPONSE_FORMATS = {"json", "verbose_json", "text", "srt", "vtt"}
