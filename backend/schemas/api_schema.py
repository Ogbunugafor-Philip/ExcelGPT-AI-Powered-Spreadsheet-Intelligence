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
    x_label: str = ""
    y_label: str = ""


# ---------------------------------------------------------------------------
# Phase 6 — In-App Preview Layer
#
# These models mirror, field-for-field, what the Excel writer renders so the
# frontend preview closely matches the downloaded workbook (same KPIs, tables,
# charts, rankings, growth, forecast).
# ---------------------------------------------------------------------------


class ExecutiveSummaryPreview(BaseModel):
    title: str = ""
    period: str = ""
    data_source: str = ""
    kpi_cards: list[KpiCardPreview] = Field(default_factory=list)


class PreviewColumn(BaseModel):
    name: str
    type: Literal["currency", "percentage", "date", "number", "text"] = "text"


class ConditionalFormatPreview(BaseModel):
    column: str
    rule: str
    color: str


class ReportSheetPreview(BaseModel):
    """A computed output sheet rendered as a formatted table in the preview."""

    sheet_name: Literal["data", "analysis", "charts", "forecast"]
    display_name: str
    columns: list[PreviewColumn] = Field(default_factory=list)
    rows: list[Any] = Field(default_factory=list)
    conditional_formatting: list[ConditionalFormatPreview] = Field(default_factory=list)


class MetricPreview(BaseModel):
    label: str
    value: str
    formula_used: str = ""


class TableMeta(BaseModel):
    """Display-name column headers for a rich dashboard table."""

    entity_label: str = ""
    value_label: str = ""
    previous_label: str = ""
    current_label: str = ""
    change_label: str = ""


class RankingPreview(BaseModel):
    rank: Optional[int] = None
    label: str = ""
    value: str = ""
    change: str = ""
    direction: Literal["up", "down", "neutral"] = "neutral"
    # Performance tier vs. the mean: excellent | good | average | below.
    tier: Literal["excellent", "good", "average", "below", "none"] = "none"
    numeric_value: Optional[float] = None


class GrowthRowPreview(BaseModel):
    label: str = ""
    current: str = ""
    previous: str = ""
    growth_rate: str = ""
    direction: Literal["up", "down", "neutral"] = "neutral"
    numeric_current: Optional[float] = None
    numeric_previous: Optional[float] = None
    numeric_change_pct: Optional[float] = None


class ForecastPointPreview(BaseModel):
    period: str = ""
    value: Optional[float] = None


class ForecastPreview(BaseModel):
    historical: list[ForecastPointPreview] = Field(default_factory=list)
    projected: list[ForecastPointPreview] = Field(default_factory=list)
    confidence_upper: list[ForecastPointPreview] = Field(default_factory=list)
    confidence_lower: list[ForecastPointPreview] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class ReportPreview(BaseModel):
    """Preview returned by /analyse and /refine (full report shape, Phase 6)."""

    executive_summary: ExecutiveSummaryPreview = Field(default_factory=ExecutiveSummaryPreview)
    sheets: list[ReportSheetPreview] = Field(default_factory=list)
    charts: list[ChartPreview] = Field(default_factory=list)
    forecast: Optional[ForecastPreview] = None
    metrics: list[MetricPreview] = Field(default_factory=list)
    rankings: list[RankingPreview] = Field(default_factory=list)
    growth_table: list[GrowthRowPreview] = Field(default_factory=list)
    rankings_meta: TableMeta = Field(default_factory=TableMeta)
    growth_meta: TableMeta = Field(default_factory=TableMeta)
    # Raw column name -> display name, so the dashboard relabels every column.
    display_names: dict[str, str] = Field(default_factory=dict)
    # Retained for backward compatibility with earlier consumers.
    kpi_cards: list[KpiCardPreview] = Field(default_factory=list)


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
    # "cerebras" when the AI planner produced the plan (Tier 1/2); "fallback"
    # when the deterministic rule-based planner (Tier 3) was used.
    ai_status: Literal["cerebras", "fallback"] = "cerebras"


# ---------------------------------------------------------------------------
# POST /refine
# ---------------------------------------------------------------------------


class RefineRequest(BaseModel):
    session_id: str
    feedback: str = Field(..., min_length=1)
    history: list[HistoryTurn] = Field(default_factory=list)
    current_version: int = 1


# ---------------------------------------------------------------------------
# POST /download-all — package several insight tokens into one workbook
# ---------------------------------------------------------------------------


class DownloadAllRequest(BaseModel):
    tokens: list[str] = Field(default_factory=list)


class RefineResponse(BaseModel):
    action_plan: ActionPlan
    preview: ReportPreview
    download_token: Optional[str] = None
    version: int
    ai_status: Literal["cerebras", "fallback"] = "cerebras"


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    timestamp: str
