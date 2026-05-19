from __future__ import annotations

from pathlib import Path
import os
import sqlite3


READ_ONLY_BLOCKLIST = ("insert", "update", "delete", "drop", "alter", "truncate", "create")
READ_ONLY_PREFIXES = ("select", "with", "pragma")


def _db_path_for_client(client_id: str) -> Path:
    db_dir = Path(os.getenv("TENANT_DB_DIR", "./tenant_dbs"))
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / f"{client_id}.db"


def run_read_only_query(*, client_id: str, sql: str) -> dict:
    normalized = sql.strip().lower()
    if not normalized:
        return {"ok": False, "client_id": client_id, "error": "SQL query is empty."}

    if not normalized.startswith(READ_ONLY_PREFIXES):
        return {
            "ok": False,
            "client_id": client_id,
            "error": "Only SELECT/WITH/PRAGMA read-only statements are allowed.",
        }

    if any(keyword in normalized for keyword in READ_ONLY_BLOCKLIST):
        return {
            "ok": False,
            "client_id": client_id,
            "error": "Only read-only SQL statements are allowed.",
        }

    db_path = _db_path_for_client(client_id)
    if not db_path.exists():
        return {
            "ok": False,
            "client_id": client_id,
            "error": f"Tenant database not found: {db_path}",
        }

    uri = f"file:{db_path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = [dict(row) for row in cursor.fetchall()]

    return {"ok": True, "client_id": client_id, "rows": rows, "row_count": len(rows)}
