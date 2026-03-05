"""
Model cache management: loading, unloading, TTL cleanup.
Dual-backend loader for NeMo (Parakeet) and transformers (Whisper).
"""
import gc
import logging
import asyncio
import time
import threading

import torch

from config import MODEL_CONFIGS, MODEL_TTL_SECONDS

logger = logging.getLogger(__name__)

# Global model cache — keyed by model name string
_model_cache = {}
_model_last_used = {}
_loading_in_progress = set()


def get_model(name: str):
    """Get or load a model by name, dispatching to the correct backend."""
    if name not in MODEL_CONFIGS:
        raise ValueError(f"Unknown model: {name}. Choose from: {list(MODEL_CONFIGS.keys())}")

    if name in _model_cache:
        logger.info(f"Using cached model: {name}")
        _model_last_used[name] = time.time()
        return _model_cache[name]

    config = MODEL_CONFIGS[name]
    backend = config["backend"]

    if backend == "nemo":
        model = _load_parakeet(config["hf_id"])
    elif backend == "onnx":
        model = _load_parakeet_onnx(config["hf_id"], config.get("quantization"))
    elif backend == "transformers":
        model = _load_whisper(config["hf_id"])
    else:
        raise ValueError(f"Unknown backend: {backend}")

    _model_cache[name] = model
    _model_last_used[name] = time.time()
    logger.info(f"Model {name} loaded and cached!")
    return model


def _load_parakeet(model_id: str):
    """Load NVIDIA Parakeet model via NeMo ASR."""
    import nemo.collections.asr as nemo_asr
    from omegaconf import DictConfig

    logger.info(f"Loading NeMo ASR model: {model_id}...")
    model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_id)

    # Disable CUDA graphs to avoid cu_call unpacking errors (PyTorch/CUDA version mismatch)
    decoding_cfg = DictConfig({
        'strategy': 'greedy_batch',
        'model_type': 'tdt',
        'durations': [0, 1, 2, 3, 4],
        'greedy': {
            'max_symbols': 10,
            'use_cuda_graph_decoder': False,
        },
    })
    model.change_decoding_strategy(decoding_cfg)
    logger.info("Disabled CUDA graph decoder for NeMo decoding")

    model = model.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    model.eval()

    logger.info(f"NeMo model loaded: {model_id}")
    return model


def _load_whisper(model_id: str):
    """Load Whisper model via transformers pipeline."""
    from transformers import pipeline

    logger.info(f"Loading Whisper model: {model_id}...")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    pipe = pipeline(
        "automatic-speech-recognition",
        model=model_id,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device=device,
        chunk_length_s=30,
    )
    logger.info(f"Whisper model loaded: {model_id}")
    return pipe


def _load_parakeet_onnx(model_id: str, quantization: str | None = None):
    """Load Parakeet ONNX model via onnx-asr."""
    import onnx_asr

    logger.info(f"Loading ONNX ASR model from: {model_id} (quantization={quantization})...")
    kwargs = {"quantization": quantization} if quantization else {}
    try:
        model = onnx_asr.load_model(model_id, **kwargs)
    except Exception:
        logger.info("Direct load failed, trying HF download...")
        from huggingface_hub import snapshot_download

        cache_dir = snapshot_download(repo_id=model_id)
        model = onnx_asr.load_model(cache_dir, **kwargs)

    logger.info(f"ONNX Parakeet model loaded from {model_id}")
    return model


def unload_model(name: str):
    """Unload a specific model to free VRAM."""
    if name in _model_cache:
        logger.info(f"Unloading model: {name}")
        del _model_cache[name]
        _model_last_used.pop(name, None)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
        return True
    return False


def flush_all():
    """Hard flush: unload ALL models, clear all CUDA memory, force GC."""
    logger.warning("HARD FLUSH: clearing all models and VRAM")
    names = list(_model_cache.keys())
    _model_cache.clear()
    _model_last_used.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
        gc.collect()
    freed = torch.cuda.memory_reserved(0) / 1024**2 if torch.cuda.is_available() else 0
    logger.warning(f"HARD FLUSH complete. Unloaded: {names}. Reserved after flush: {freed:.0f} MB")
    return names


def background_load_model(name: str):
    """Trigger background loading of a model (non-blocking)."""
    if name in _model_cache or name in _loading_in_progress:
        return

    def _load():
        _loading_in_progress.add(name)
        try:
            logger.info(f"Background loading {name}...")
            get_model(name)
            logger.info(f"Background load complete: {name}")
        except Exception as e:
            logger.error(f"Background load failed for {name}: {e}")
        finally:
            _loading_in_progress.discard(name)

    threading.Thread(target=_load, daemon=True).start()


async def _model_ttl_cleanup():
    """Periodically check and unload idle models to free VRAM."""
    while True:
        await asyncio.sleep(60)
        now = time.time()
        keys_to_unload = []
        for name, last_used in list(_model_last_used.items()):
            if now - last_used > MODEL_TTL_SECONDS:
                keys_to_unload.append(name)

        for name in keys_to_unload:
            logger.info(f"TTL expired for model {name}, unloading to free VRAM...")
            if name in _model_cache:
                del _model_cache[name]
            if name in _model_last_used:
                del _model_last_used[name]

        if keys_to_unload and torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()
            logger.info(f"VRAM freed after unloading {len(keys_to_unload)} model(s)")
