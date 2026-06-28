from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

import config
from schemas.computation_schema import ComputationOutput


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
            "session_id": session_id,
            "file_path": file_path,
            "intelligence_brief": intelligence_brief,
            "sheet_data": sheet_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": 0,
            "versions": {},
            "downloads": {},
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

    # -- version history ----------------------------------------------------

    def store_version(self, session_id: str, version: int, output: ComputationOutput) -> None:
        """Record a computed report version and mark it the session's latest."""
        session = self.get_session(session_id)
        session.setdefault("versions", {})[version] = output
        session["version"] = max(int(session.get("version", 0)), int(version))

    def get_version(self, session_id: str, version: int) -> ComputationOutput:
        session = self.get_session(session_id)
        output = session.get("versions", {}).get(version)
        if output is None:
            raise HTTPException(status_code=404, detail=f"Version {version} not found for this session.")
        return output

    def get_latest_version(self, session_id: str) -> tuple[int, ComputationOutput | None]:
        """Return (version_number, output) for the newest version, or (0, None)."""
        session = self.get_session(session_id)
        versions = session.get("versions", {})
        if not versions:
            return 0, None
        latest = max(versions)
        return latest, versions[latest]

    def get_version_count(self, session_id: str) -> int:
        return len(self.get_session(session_id).get("versions", {}))

    def register_download(self, session_id: str, token: str, version: int, output: ComputationOutput) -> None:
        """Map a download token to a specific version's computed output."""
        session = self.get_session(session_id)
        payload = output.model_dump() if isinstance(output, ComputationOutput) else output
        session.setdefault("downloads", {})[token] = {"version": version, "output": payload}

    def find_download(self, token: str) -> tuple[str | None, dict[str, Any] | None]:
        """Locate the session and stored computation output for a download token.

        Supports both the versioned entry ({"version", "output"}) and a raw
        ComputationOutput dump stored directly (back-compat with earlier phases).
        """
        self.cleanup_expired(config.SESSION_EXPIRY_MINUTES)
        for session_id, session in self._sessions.items():
            downloads = session.get("downloads", {})
            if token in downloads:
                entry = downloads[token]
                if isinstance(entry, dict) and "output" in entry and "version" in entry:
                    return session_id, entry["output"]
                return session_id, entry
        return None, None

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
