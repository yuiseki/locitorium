from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Query

from locitorium.config import AppConfig
from locitorium.clients.nominatim import NominatimClient
from locitorium.pipeline.runner import run_doc

app = FastAPI(title="locitorium", version="0.1.0")

@app.on_event("startup")
async def startup_check() -> None:
    config = AppConfig()
    client = NominatimClient(
        config.nominatim_base_url,
        timeout_s=config.nominatim_timeout_s,
        limit=config.nominatim_limit,
    )
    await client.search("Tokyo")


@app.get("/")
async def resolve(
    q: str = Query(..., min_length=1),
    model: str | None = Query(None),
):
    config = AppConfig()
    if model:
        config = AppConfig(ollama_model=model)

    if len(q) > config.max_chars:
        raise HTTPException(status_code=400, detail="input too long")

    doc_id = str(uuid.uuid4())
    try:
        pred = await run_doc(q, doc_id, config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return pred.model_dump()
