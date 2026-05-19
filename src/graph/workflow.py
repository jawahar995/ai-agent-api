from __future__ import annotations

from typing import Any

from .state import AgentState
from ..tools.chroma_rag import search_vectors


async def run_workflow(state: AgentState) -> dict[str, Any]:
    query = state.get("input_text", "")
    client_id = state.get("client_id", "unknown")
    retrieval = search_vectors(client_id=client_id, query=query, k=3)

    return {
        "status": "ok",
        "client_id": client_id,
        "retrieval": retrieval,
        "message": "Workflow executed.",
    }
