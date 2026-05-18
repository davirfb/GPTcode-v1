from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
TOKENS_FILE = DATA_DIR / "edit_tokens.json"
TOKEN_VALIDITY_DAYS = 7


def _load() -> dict:
    if not TOKENS_FILE.exists():
        return {}
    with TOKENS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save(tokens: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with TOKENS_FILE.open("w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


def generate_token(
    token_type: str,
    resource: str,
    item_id: str | None = None,
    created_by: str = "",
    days: int = TOKEN_VALIDITY_DAYS,
) -> str:
    tokens = _load()
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    tokens[token] = {
        "type": token_type,        # "add" | "edit"
        "resource": resource,      # "project" | "publication" | "member"
        "item_id": item_id,
        "used": False,
        "expires_at": expires_at,
        "created_by": created_by,
    }
    _save(tokens)
    return token


def validate_token(token: str) -> dict | None:
    """Returns token data if valid and unused, otherwise None."""
    tokens = _load()
    data = tokens.get(token)
    if not data:
        return None
    if data.get("used"):
        return None
    try:
        expiry = datetime.fromisoformat(data.get("expires_at", ""))
        if datetime.now(timezone.utc) > expiry:
            return None
    except ValueError:
        return None
    return data


def mark_token_used(token: str) -> None:
    tokens = _load()
    if token in tokens:
        tokens[token]["used"] = True
        _save(tokens)
