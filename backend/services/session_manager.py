from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

import config


class SessionManager:
    """Store workbook session payloads in memory until expiry."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_session(
        self,
        file_path: str,
        intelligence_brief: dict[str, Any],
        sheet_data: dict[str, Any],
        session_id: str | None = None,
    ) -> str:
        self.cleanup_expired(config.SESSION_EXPIRY_MINUTES)
        session_id = session_id or str(uuid4())
        self._sessions[session_id] = {
            "file_path": file_path,
            "intelligence_brief": intelligence_brief,
            "sheet_data": sheet_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version_history": [],
        }
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any]:
        self.cleanup_expired(config.SESSION_EXPIRY_MINUTES)
        session = self._sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return session

    def update_session(self, session_id: str, updates: dict[str, Any]) -> None:
        session = self.get_session(session_id)
        session.update(updates)

    def cleanup_expired(self, max_age_minutes: int) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        expired_ids = []
        for session_id, session in self._sessions.items():
            created_at = session.get("created_at")
            try:
                created_dt = datetime.fromisoformat(str(created_at))
            except (TypeError, ValueError):
                created_dt = datetime.now(timezone.utc)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if created_dt < cutoff:
                expired_ids.append(session_id)
        for session_id in expired_ids:
            self._sessions.pop(session_id, None)
