from __future__ import annotations

import os

import httpx


def _node_base() -> str:
    return os.getenv("NODE_API_BASE_URL", "http://127.0.0.1:9091").rstrip("/")


async def fetch_data_record(data_id: str) -> dict:
    url = f"{_node_base()}/api/v1/upload/data/{data_id}"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url)
        if response.status_code == 404:
            raise FileNotFoundError(f"data not found: {data_id}")
        response.raise_for_status()
        payload = response.json()

    data = payload.get("data") if isinstance(payload, dict) else None
    if not data:
        raise FileNotFoundError(f"data not found: {data_id}")
    return data


async def save_estimate_result(data_id: str, estimate: dict) -> None:
    """Persist estimation fields back to the Node data record."""
    url = f"{_node_base()}/api/v1/upload/data/{data_id}/estimate"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.patch(url, json=estimate)
        response.raise_for_status()
