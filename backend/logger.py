"""
ExcelGPT — structured production logging.

Writes rotating logs to logs/excelgpt.log with the line shape:

    timestamp | level | endpoint | session_id | duration_ms | status | message

Helper functions cover the key lifecycle events (upload, analysis, download,
refinement, errors) plus a generic request logger used by the timing middleware.
Every helper is best-effort and must never raise into a request handler.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "excelgpt.log"

_FORMAT = "%(asctime)s | %(levelname)s | %(endpoint)s | %(session_id)s | %(duration_ms)s | %(status)s | %(message)s"
_CONTEXT_FIELDS = ("endpoint", "session_id", "duration_ms", "status")


class _ContextFilter(logging.Filter):
    """Inject default values so the format string never KeyErrors."""

    def filter(self, record: logging.LogRecord) -> bool:
        for field in _CONTEXT_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, "-")
        return True


logger = logging.getLogger("excelgpt")
logger.setLevel(logging.INFO)

if not logger.handlers:
    _file = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    _file.setFormatter(logging.Formatter(_FORMAT))
    _file.addFilter(_ContextFilter())
    logger.addHandler(_file)

    _console = logging.StreamHandler()
    _console.setFormatter(logging.Formatter(_FORMAT))
    _console.addFilter(_ContextFilter())
    logger.addHandler(_console)

    logger.propagate = False


def _ctx(endpoint="-", session_id="-", duration_ms="-", status="ok") -> dict:
    if isinstance(duration_ms, (int, float)):
        duration_ms = f"{duration_ms:.0f}"
    return {
        "endpoint": endpoint,
        "session_id": session_id or "-",
        "duration_ms": duration_ms if duration_ms is not None else "-",
        "status": status,
    }


def _truncate(text: str, limit: int = 100) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text[:limit]


# -- lifecycle event helpers (best-effort) ----------------------------------

def log_upload(filename, size_mb, sheet_count, row_count, session_id=None, duration_ms=None):
    try:
        logger.info(
            f"upload filename={filename} size_mb={size_mb:.2f} sheets={sheet_count} rows={row_count}",
            extra=_ctx("/upload", session_id, duration_ms),
        )
    except Exception:  # noqa: BLE001 — logging must never break a request
        pass


def log_analysis(session_id, instruction, intent_type, duration_ms, status="ok"):
    try:
        logger.info(
            f"analyse intent={intent_type} instruction=\"{_truncate(instruction)}\"",
            extra=_ctx("/analyse", session_id, duration_ms, status),
        )
    except Exception:  # noqa: BLE001
        pass


def log_refinement(session_id, feedback, version, duration_ms, status="ok"):
    try:
        logger.info(
            f"refine version={version} feedback=\"{_truncate(feedback)}\"",
            extra=_ctx("/refine", session_id, duration_ms, status),
        )
    except Exception:  # noqa: BLE001
        pass


def log_download(session_id, version, file_size_kb):
    try:
        logger.info(
            f"download version={version} size_kb={file_size_kb:.1f}",
            extra=_ctx("/download", session_id),
        )
    except Exception:  # noqa: BLE001
        pass


def log_error(endpoint, error_type, error_message, session_id=None):
    try:
        logger.error(
            f"{error_type}: {_truncate(str(error_message), 300)}",
            extra=_ctx(endpoint, session_id, status="error"),
        )
    except Exception:  # noqa: BLE001
        pass


def log_request(method, path, status_code, duration_ms):
    try:
        logger.info(
            f"{method} {path}",
            extra=_ctx(path, status=str(status_code), duration_ms=duration_ms),
        )
    except Exception:  # noqa: BLE001
        pass


def timed(endpoint: str):
    """Decorator that logs the wrapped coroutine's duration and status."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            status = "ok"
            try:
                return await func(*args, **kwargs)
            except Exception:  # noqa: BLE001
                status = "error"
                raise
            finally:
                logger.info(
                    f"{func.__name__} completed",
                    extra=_ctx(endpoint, duration_ms=(time.perf_counter() - start) * 1000, status=status),
                )
        return wrapper
    return decorator
