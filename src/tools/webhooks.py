from __future__ import annotations

from typing import Any


def notify_webhook(*, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not url:
        return {"ok": False, "error": "Webhook URL is required."}

    # Placeholder webhook behavior. Replace with an async HTTP client in implementation.
    return {
        "ok": True,
        "url": url,
        "delivered": False,
        "message": "Webhook adapter scaffolded. Delivery client not yet configured.",
        "payload_keys": sorted(payload.keys()),
    }
