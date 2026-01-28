from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field


class ResolveResult(BaseModel):
    mention_id: str
    mention: str
    choice: int = Field(..., description="Index of best candidate, -1 if none")
    status: Literal["resolved", "no_candidate", "rejected"]


class ResolveOutput(BaseModel):
    results: list[ResolveResult]


def build_prompt(text: str, candidates_payload: list[dict]) -> str:
    payload_json = json.dumps(candidates_payload, ensure_ascii=False)
    return (
        "You are selecting the best candidate for each mention based on context. "
        "You must return one result for every mention_id in CANDIDATES. "
        "If none match, choose -1 and status 'rejected'. "
        "Return JSON only, matching the provided schema.\n\n"
        f"TEXT:\n{text}\n\n"
        "CANDIDATES (index starts at 0):\n"
        f"{payload_json}"
    )
