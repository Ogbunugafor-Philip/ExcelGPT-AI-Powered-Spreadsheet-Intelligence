"""
ExcelGPT — Configuration & constants.

Loads environment variables (via python-dotenv) and exposes all constants used
across the backend. Every layer reads configuration from HERE, never from
os.environ directly. See architecture/environment-variables.md for full docs.
"""

import os
from dotenv import load_dotenv

# override=True makes backend/.env the source of truth, even when a stale
# variable of the same name already exists in the process environment.
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY", "")
CEREBRAS_MODEL: str = os.getenv("CEREBRAS_MODEL", "llama-3.3-70b")
CEREBRAS_TIMEOUT_SECONDS: float = float(os.getenv("CEREBRAS_TIMEOUT_SECONDS", "20"))
CEREBRAS_TEMPERATURE: float = float(os.getenv("CEREBRAS_TEMPERATURE", "0.1"))
# Reasoning models (e.g. gpt-oss-120b) spend tokens on hidden reasoning before
# emitting the JSON, so the budget must comfortably exceed the plan size.
CEREBRAS_MAX_TOKENS: int = int(os.getenv("CEREBRAS_MAX_TOKENS", "4000"))
ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "25"))
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./storage/uploads")
SESSION_EXPIRY_MINUTES: int = int(os.getenv("SESSION_EXPIRY_MINUTES", "60"))
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8003"))
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------
APP_NAME: str = "ExcelGPT"
APP_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# Upload / file constraints
# ---------------------------------------------------------------------------
MAX_FILE_SIZE: int = MAX_FILE_SIZE_MB * 1024 * 1024  # bytes
ALLOWED_EXTENSIONS: set[str] = {".xlsx", ".xls"}
XLSX_MEDIA_TYPE: str = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
SESSION_EXPIRY: int = SESSION_EXPIRY_MINUTES * 60  # seconds

# ---------------------------------------------------------------------------
# Output sheet names (openpyxl) — keys map to the action plan's output_sheet.
# ---------------------------------------------------------------------------
SHEET_NAMES: dict[str, str] = {
    "executive_summary": "Executive Summary",
    "data": "Data",
    "analysis": "Analysis",
    "charts": "Charts",
    "forecast": "Forecast",
}

# ---------------------------------------------------------------------------
# ExcelGPT color palette (hex) — shared by openpyxl styling and chart rendering.
# Mirrors the frontend design system (frontend/src/design-system.md).
# ---------------------------------------------------------------------------
COLOR_PALETTE: dict[str, str] = {
    "navy": "#0A0F1E",
    "navy_light": "#111827",
    "blue_electric": "#2563EB",
    "blue_glow": "#3B82F6",
    "emerald": "#10B981",  # positive / success
    "amber": "#F59E0B",  # warning
    "red_alert": "#EF4444",  # negative / danger
    "gold": "#D97706",  # premium / executive tier
    "text_primary": "#F9FAFB",
    "text_secondary": "#9CA3AF",
}

# ---------------------------------------------------------------------------
# Nigerian formatting
# ---------------------------------------------------------------------------
NIGERIAN_CURRENCY_FORMAT: str = '"₦"#,##0.00'  # openpyxl number format (NGN)
DEFAULT_CURRENCY: str = "NGN"
FISCAL_CALENDARS: tuple[str, ...] = ("january", "april")
TEMPLATE_TYPES: tuple[str, ...] = ("banking", "sales", "hr", "general")
FORMATTING_TIERS: tuple[str, ...] = ("standard", "premium", "executive")
