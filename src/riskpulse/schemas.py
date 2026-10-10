"""Validated data contracts shared by the pipeline, API, dashboard and exports."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .universe import ALL_EVENT_LABELS, SENTIMENT_LABELS

SourceType = Literal["news", "social", "rss"]


class RawRecord(BaseModel):
    """One normalised unstructured-text record, after ingestion and before NLP."""

    record_id: str
    source_type: SourceType
    source_name: str
    timestamp: datetime
    text: str = Field(min_length=3)
    title: Optional[str] = None
    author: Optional[str] = None
    engagement: int = 0
    is_synthetic: bool = True

    @field_validator("timestamp")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")
        return v


class RiskSignal(BaseModel):
    """Structured, explainable risk signal produced for one record."""

    signal_id: str
    record_id: str
    timestamp: datetime
    source_type: SourceType
    source_name: str
    entity: Optional[str] = None
    ticker: Optional[str] = None
    sector: Optional[str] = None
    text: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    sentiment_label: str
    event_type: str
    secondary_event_type: Optional[str] = None
    is_ambiguous: bool = False
    impact_score: int = Field(ge=1, le=10)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    impact_factors: dict[str, float] = Field(default_factory=dict)
    is_synthetic: bool = True
    model_version: str = "riskpulse-0.1"

    @field_validator("sentiment_label")
    @classmethod
    def _sentiment_label(cls, v: str) -> str:
        if v not in SENTIMENT_LABELS:
            raise ValueError(f"sentiment_label must be one of {SENTIMENT_LABELS}")
        return v

    @field_validator("event_type")
    @classmethod
    def _event_type(cls, v: str) -> str:
        if v not in ALL_EVENT_LABELS:
            raise ValueError(f"event_type must be one of {ALL_EVENT_LABELS}")
        return v


class IngestionIssue(BaseModel):
    source: str
    row: Optional[int] = None
    reason: str


class IngestionReport(BaseModel):
    files: list[str] = Field(default_factory=list)
    rows_read: int = 0
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0
    issues: list[IngestionIssue] = Field(default_factory=list)
