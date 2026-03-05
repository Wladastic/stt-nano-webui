"""
Pydantic models for OpenAI-compatible transcription responses.
"""
from pydantic import BaseModel
from typing import List, Optional


class TranscriptionSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str


class TranscriptionResponse(BaseModel):
    text: str


class VerboseTranscriptionResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration: Optional[float] = None
    segments: List[TranscriptionSegment] = []
