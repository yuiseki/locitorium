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
        "Mentions must appear verbatim in the input text; do not infer or translate. "
        "Do not add countries unless they are explicitly present in the text. "
        "Prefer returning administrative areas and venues when present. "
        "Return JSON only, matching the provided schema.\n\n"
        "EXAMPLES:\n"
        "Text: 大会は広島県で開催。会場は広島市の広島国際会議場。\n"
        "Output: {\"mentions\":[{\"mention\":\"広島県\"},{\"mention\":\"広島市\"},{\"mention\":\"広島国際会議場\"}]}\n\n"
        f"TEXT:\n{text}"
    )
