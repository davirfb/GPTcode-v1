from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

DATA_DIR = Path(__file__).resolve().parent / "data"
PENDING_FILE = DATA_DIR / "pending_submissions.json"

RESOURCE_LABELS = {
    "project": "Projeto",
    "publication": "Publicação",
    "member": "Membro da equipe",
}


def _load() -> dict:
    if not PENDING_FILE.exists():
        return {}
    with PENDING_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(pending: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with PENDING_FILE.open("w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)


def add_pending(
    resource: str,
    submission_type: str,
    data: dict,
    item_id: str | None = None,
) -> str:
    pending = _load()
    submission_id = f"pending-{uuid4().hex}"
    pending[submission_id] = {
        "id": submission_id,
        "resource": resource,
        "resource_label": RESOURCE_LABELS.get(resource, resource),
        "type": submission_type,   # "add" | "edit"
        "item_id": item_id,
        "data": data,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    _save(pending)
    return submission_id


def get_pending_list() -> list[dict]:
    pending = _load()
    items = [v for v in pending.values() if v.get("status") == "pending"]
    return sorted(items, key=lambda x: x.get("submitted_at", ""), reverse=True)


def get_pending_item(submission_id: str) -> dict | None:
    return _load().get(submission_id)


def mark_approved(submission_id: str) -> None:
    pending = _load()
    if submission_id in pending:
        pending[submission_id]["status"] = "approved"
        _save(pending)


def mark_rejected(submission_id: str) -> None:
    pending = _load()
    if submission_id in pending:
        pending[submission_id]["status"] = "rejected"
        _save(pending)


def count_pending() -> int:
    return len(get_pending_list())
