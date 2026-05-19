from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import os
from typing import Optional


try:
    import tiktoken
except ImportError:  # pragma: no cover - fallback when dependency is not installed
    tiktoken = None


@dataclass
class EstimateResult:
    token_count: int
    chunk_count: int
    estimated_cost_usd: float
    estimated_seconds: float
    model: str


def _count_tokens(text: str, model: str) -> int:
    if not text:
        return 0

    if tiktoken is None:
        # Approximation fallback when tokenizer package is not available.
        return max(1, math.ceil(len(text) / 4))

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if not text:
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    step = chunk_size - chunk_overlap
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += step
    return chunks


def estimate_text(
    text: str,
    model: Optional[str] = None,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    token_rate_per_second: Optional[float] = None,
    cost_per_1k_tokens: Optional[float] = None,
) -> EstimateResult:
    selected_model = model or os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-3-small")
    rate = token_rate_per_second or float(os.getenv("DEFAULT_TOKEN_RATE_PER_SECOND", "12000"))
    unit_cost = cost_per_1k_tokens or float(os.getenv("DEFAULT_COST_PER_1K_TOKENS", "0.00013"))

    chunks = _chunk_text(text=text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    token_count = sum(_count_tokens(chunk, selected_model) for chunk in chunks)

    estimated_cost = (token_count / 1000.0) * unit_cost
    estimated_seconds = token_count / max(1.0, rate)

    return EstimateResult(
        token_count=token_count,
        chunk_count=len(chunks),
        estimated_cost_usd=round(estimated_cost, 6),
        estimated_seconds=round(estimated_seconds, 2),
        model=selected_model,
    )


def estimate_file(
    file_path: str,
    model: Optional[str] = None,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> EstimateResult:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    text = path.read_text(encoding="utf-8", errors="ignore")
    return estimate_text(
        text=text,
        model=model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
