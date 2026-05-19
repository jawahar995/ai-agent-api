from __future__ import annotations

from dataclasses import asdict, dataclass
import asyncio
from pathlib import Path
from typing import Literal

from . import estimator
from .url_ingestion import extract_url_markdown
from ..tools.chroma_rag import upsert_documents


SourceType = Literal["text", "file", "url"]


@dataclass
class IngestionResult:
    client_id: str
    source_type: SourceType
    source_ref: str
    estimated_tokens: int
    estimated_cost_usd: float
    estimated_seconds: float
    vector_chunks_written: int
    ingested: bool
    message: str


def _split_for_embeddings(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    if not text:
        return []
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += step
    return chunks


async def execute_ingestion(
    *,
    client_id: str,
    source_type: SourceType,
    source_ref: str,
    content: str | None,
    approved: bool,
    model: str | None = None,
) -> IngestionResult:
    if not approved:
        return IngestionResult(
            client_id=client_id,
            source_type=source_type,
            source_ref=source_ref,
            estimated_tokens=0,
            estimated_cost_usd=0.0,
            estimated_seconds=0.0,
            vector_chunks_written=0,
            ingested=False,
            message="Ingestion aborted because approval was not granted.",
        )

    source_text = ""
    if source_type == "text":
        source_text = content or ""
        estimate = estimator.estimate_text(source_text, model=model)
    elif source_type == "file":
        source_text = Path(source_ref).read_text(encoding="utf-8", errors="ignore")
        estimate = estimator.estimate_file(source_ref, model=model)
    else:
        extracted = await extract_url_markdown(source_ref)
        source_text = extracted.markdown
        estimate = estimator.estimate_text(source_text, model=model)

    chunks = _split_for_embeddings(source_text)
    written = upsert_documents(client_id=client_id, texts=chunks, source_ref=source_ref)

    # Simulate async downstream activity while preserving event loop responsiveness.
    await asyncio.sleep(0.02)

    return IngestionResult(
        client_id=client_id,
        source_type=source_type,
        source_ref=source_ref,
        estimated_tokens=estimate.token_count,
        estimated_cost_usd=estimate.estimated_cost_usd,
        estimated_seconds=estimate.estimated_seconds,
        vector_chunks_written=written,
        ingested=True,
        message="Ingestion and embedding pipeline executed successfully.",
    )


def result_to_dict(result: IngestionResult) -> dict:
    return asdict(result)
