from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    client_id: str
    user_id: str
    input_text: str
    messages: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    metadata: dict[str, Any]
