from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent import run_realtime_agent_event_loop
from src.services.data_estimation import estimate_from_data_id
from src.services.ingestion import execute_ingestion, result_to_dict
from src.services.url_ingestion import extract_url_markdown


SourceType = Literal["text", "file", "url"]


class IngestRequest(BaseModel):
    client_id: str = Field(..., min_length=1)
    source_type: SourceType
    approved: bool = False
    content: str | None = None
    file_path: str | None = None
    url: str | None = None
    model: str | None = None


class AgentStartRequest(BaseModel):
    room_metadata: dict = Field(default_factory=dict)


app = FastAPI(title="ai-agent-api", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/agent/start")
async def start_agent(payload: AgentStartRequest) -> dict:
    try:
        return await run_realtime_agent_event_loop(payload.room_metadata)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {exc}") from exc


@app.get("/v1/estimate/{data_id}")
async def estimate(data_id: str, model: str | None = None) -> dict:
    try:
        result = await estimate_from_data_id(data_id, model=model)
        return {
            "data_id": result.data_id,
            "client_id": result.client_id,
            "source_type": result.source_type,
            "source_url": result.source_url,
            "page_count": result.page_count,
            "token_count": result.token_count,
            "chunk_count": result.chunk_count,
            "estimated_cost_usd": result.estimated_cost_usd,
            "estimated_seconds": result.estimated_seconds,
            "model": result.model,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/ingest")
async def ingest(payload: IngestRequest) -> dict:
    source_ref = payload.file_path or payload.url or "inline"

    if payload.source_type == "file":
        if payload.file_path:
            source_ref = payload.file_path
        else:
            raise HTTPException(status_code=400, detail="file_path is required for source_type='file'")

    result = await execute_ingestion(
        client_id=payload.client_id,
        source_type=payload.source_type,
        source_ref=source_ref,
        content=payload.content,
        approved=payload.approved,
        model=payload.model,
    )

    if not payload.approved:
        raise HTTPException(status_code=400, detail=result.message)

    return result_to_dict(result)
