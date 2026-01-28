from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedMention(BaseModel):
    mention: str = Field(..., description="Mention text as it appears")


class ExtractOutput(BaseModel):
    mentions: list[ExtractedMention]


def build_prompt(text: str) -> str:
    return (
        "Extract location-like mentions from the text. "
        "Return only likely toponyms (including country names). "
        "Return JSON only, matching the provided schema.\n\n"
        f"TEXT:\n{text}"
    )
