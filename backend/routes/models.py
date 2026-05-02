"""
Model management endpoints: list, status, load, unload.
"""
import gc
import time

import torch
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

import model_manager
from config import MODEL_CONFIGS, OPENAI_MODEL_MAP, MODEL_TTL_SECONDS

router = APIRouter()


@router.get("/v1/models")
async def list_models():
    """OpenAI-compatible models list."""
    data = []
    for name, cfg in MODEL_CONFIGS.items():
        data.append({
            "id": name,
            "object": "model",
            "owned_by": name.split("-")[0] if "-" in name else "custom",
            "description": cfg["description"],
        })
    # Include aliases
    for alias, target in OPENAI_MODEL_MAP.items():
        if target in MODEL_CONFIGS:
            data.append({
                "id": alias,
                "object": "model",
                "owned_by": "openai",
                "description": f"Alias for {target}",
            })
    return {"object": "list", "data": data}


@router.get("/v1/status")
async def model_status():
    """Get status of all models including TTL countdown."""
    now = time.time()
    models = {}

    for name in MODEL_CONFIGS:
        models[name] = {"status": "unloaded"}

    for name in list(model_manager._model_cache):
        last_used = model_manager._model_last_used.get(name, now)
        idle = now - last_used
        models[name] = {
            "status": "loaded",
            "idle_seconds": round(idle),
            "ttl_remaining": round(max(0, MODEL_TTL_SECONDS - idle)),
            "ttl_total": MODEL_TTL_SECONDS,
        }

    for name in list(model_manager._loading_in_progress):
        if name not in models or models[name]["status"] == "unloaded":
            models[name] = {"status": "loading"}

    # VRAM info
    vram = {}
    if torch.cuda.is_available():
        vram = {
            "total_mb": round(torch.cuda.get_device_properties(0).total_memory / 1024**2),
            "allocated_mb": round(torch.cuda.memory_allocated(0) / 1024**2),
            "reserved_mb": round(torch.cuda.memory_reserved(0) / 1024**2),
        }

    return {"ttl_seconds": MODEL_TTL_SECONDS, "models": models, "vram": vram}


@router.post("/v1/models/flush")
async def flush_all():
    """Hard flush: unload all models and aggressively clear VRAM."""
    unloaded = await run_in_threadpool(model_manager.flush_all)
    vram = {}
    if torch.cuda.is_available():
        vram = {
            "allocated_mb": round(torch.cuda.memory_allocated(0) / 1024**2),
            "reserved_mb": round(torch.cuda.memory_reserved(0) / 1024**2),
        }
    return {"status": "flushed", "unloaded": unloaded, "vram_after": vram}


@router.post("/v1/models/{name}/load")
async def load_model(name: str):
    """Manually load a model."""
    if name not in MODEL_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {name}")
    await run_in_threadpool(model_manager.get_model, name)
    return {"status": "loaded", "model": name}


@router.post("/v1/models/{name}/unload")
async def unload_model(name: str):
    """Manually unload a model."""
    if await run_in_threadpool(model_manager.unload_model, name):
        return {"status": "unloaded", "model": name}
    return {"status": "already_unloaded", "model": name}
