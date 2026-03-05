#!/usr/bin/env python3
"""
STT WebUI FastAPI Server
OpenAI-compatible transcription endpoint with multiple model backends.
"""
import asyncio
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import MODEL_TTL_SECONDS
from model_manager import _model_ttl_cleanup
from routes.transcribe import router as transcribe_router
from routes.models import router as models_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="STT WebUI Server",
    version="1.0.0",
    description="OpenAI-compatible Speech-to-Text API (Parakeet + Whisper)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transcribe_router)
app.include_router(models_router)


@app.on_event("startup")
async def startup():
    """Start with no models loaded — all load on demand with TTL."""
    logger.info(f"Server started. Model TTL: {MODEL_TTL_SECONDS}s. All models load on demand.")
    asyncio.create_task(_model_ttl_cleanup())


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8882, log_level="info")
