"""
ExcelGPT — API request/response Pydantic models.

Backs the REST contract in architecture/api-contract.md. These models are the
typed boundary between the React frontend and the FastAPI backend.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .cerebras_schema import ActionPlan

# ---------------------------------------------------------------------------
# Shared preview structures
# ---------------------------------------------------------------------------


class SheetPreview(BaseModel):
    name: str
    columns: list[str] = Field(default_factory=list)
    rows: list[Any] = Field(default_factory=list)
    row_count: int = 0


class UploadPreview(BaseModel):
    """Preview returned by /upload (raw sheet contents)."""

    sheets: list[SheetPreview] = Field(default_factory=list)


class KpiCardPreview(BaseModel):
    label: str
    value: str
    change: str
    direction: Literal["up", "down", "neutral"] = "neutral"


class ChartPreview(BaseModel):
    chart_id: str
    chart_type: Literal["bar", "line", "pie", "scatter"]
    title: str
    recharts_data: list[Any] = Field(default_factory=list)


class ReportPreview(BaseModel):
    """Preview returned by /analyse and /refine (report shape)."""

    sheets: list[SheetPreview] = Field(default_factory=list)
    kpi_cards: list[KpiCardPreview] = Field(default_factory=list)
    charts: list[ChartPreview] = Field(default_factory=list)


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    session_id: str
    preview: UploadPreview
    intelligence_brief: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# POST /analyse
# ---------------------------------------------------------------------------


class AnalyseRequest(BaseModel):
    session_id: str
    instruction: str = Field(..., min_length=1)


class AnalyseResponse(BaseModel):
    action_plan: ActionPlan
    preview: ReportPreview
    download_token: Optional[str] = None
    version: int = 1


# ---------------------------------------------------------------------------
# POST /refine
# ---------------------------------------------------------------------------


class RefineRequest(BaseModel):
    session_id: str
    feedback: str = Field(..., min_length=1)
    history: list[HistoryTurn] = Field(default_factory=list)
    current_version: int = 1


class RefineResponse(BaseModel):
    action_plan: ActionPlan
    preview: ReportPreview
    download_token: Optional[str] = None
    version: int


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    timestamp: str
