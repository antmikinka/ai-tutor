"""Small helpers shared by services and API routes."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Timezone-aware ISO-8601 timestamp (``datetime.utcnow`` is deprecated and naive)."""
    return utc_now().isoformat()
