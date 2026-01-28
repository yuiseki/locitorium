from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def normalize_country_code(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return value.upper()


class GoldMention(BaseModel):
    mention_id: str
    mention: str
    iso_country: str = Field(..., description="ISO 3166-1 alpha2 uppercase")
    start: int | None = None
    end: int | None = None
    note: str | None = None

    @field_validator("iso_country")
    @classmethod
    def _normalize_iso_country(cls, v: str) -> str:
        return normalize_country_code(v) or ""


class GoldDoc(BaseModel):
    doc_id: str
    text: str
    meta: dict[str, Any] | None = None
    mentions: list[GoldMention]


class SelectedCandidate(BaseModel):
    osm_type: str
    osm_id: int | str
    lat: float | str
    lon: float | str
    bbox: list[str | float]
    display_name: str
    country_code: str | None = None
    confidence: float | None = None

    @field_validator("country_code")
    @classmethod
    def _normalize_country_code(cls, v: str | None) -> str | None:
        return normalize_country_code(v)


class Candidate(BaseModel):
    rank: int
    osm_type: str
    osm_id: int | str
    display_name: str
    lat: float | str
    lon: float | str
    bbox: list[str | float]
    country_code: str | None = None
    category: str | None = None
    place_rank: int | None = None
    importance: float | None = None

    @field_validator("country_code")
    @classmethod
    def _normalize_country_code(cls, v: str | None) -> str | None:
        return normalize_country_code(v)


class PredResult(BaseModel):
    mention_id: str
    mention: str
    status: Literal[
        "resolved", "no_candidate", "rejected", "invalid_output", "timeout"
    ]
    selected: SelectedCandidate | None = None
    candidates: list[Candidate] = Field(default_factory=list)


class ModelInfo(BaseModel):
    ollama_model: str
    ollama_base_url: str
    nominatim_base_url: str
    config_hash: str


class PredDoc(BaseModel):
    doc_id: str
    model_info: ModelInfo
    results: list[PredResult]
