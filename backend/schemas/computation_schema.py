"""
ExcelGPT — Computation output Pydantic models.

These models define the hand-off contract FROM the computation engine TO the
Excel generation engine (openpyxl). Every value here is already computed
deterministically in Python. Mirrors architecture/computation-output-schema.md.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Direction = Literal["up", "down", "neutral"]
ChartType = Literal["bar", "line", "pie", "scatter"]


class KpiCard(BaseModel):
    label: str
    value: str  # pre-formatted, e.g. "₦4.21B"
    change: str  # period delta, e.g. "+12.4%"
    direction: Direction = "neutral"


class ExecutiveSummary(BaseModel):
    title: str
    period: str
    data_source: str
    kpi_cards: list[KpiCard] = Field(default_factory=list)


class ConditionalFormatRule(BaseModel):
    column: str
    rule: str  # condition expression, e.g. "value < 0"
    color: str  # fill hex from the ExcelGPT palette


class DataSheet(BaseModel):
    columns: list[Any] = Field(default_factory=list)
    rows: list[Any] = Field(default_factory=list)
    conditional_formatting: list[ConditionalFormatRule] = Field(default_factory=list)


class Metric(BaseModel):
    label: str
    value: str  # pre-formatted computed value
    formula_used: str  # human-readable method, for auditability


class AnalysisSheet(BaseModel):
    metrics: list[Metric] = Field(default_factory=list)
    rankings: list[Any] = Field(default_factory=list)
    growth_table: list[Any] = Field(default_factory=list)
    # Real, computed bullet-point observations (3–5) about the result.
    insights: list[str] = Field(default_factory=list)


class Chart(BaseModel):
    chart_id: str
    chart_type: ChartType
    title: str
    image_path: str  # matplotlib-rendered PNG for openpyxl embedding
    recharts_data: list[Any] = Field(default_factory=list)


class ForecastSheet(BaseModel):
    historical: list[Any] = Field(default_factory=list)
    projected: list[Any] = Field(default_factory=list)
    confidence_upper: list[Any] = Field(default_factory=list)
    confidence_lower: list[Any] = Field(default_factory=list)
    assumptions: list[Any] = Field(default_factory=list)


class ComputationOutput(BaseModel):
    """Full computation output consumed by the Excel generation engine."""

    session_id: str
    version: int = 1
    executive_summary: ExecutiveSummary
    data_sheet: DataSheet = Field(default_factory=DataSheet)
    analysis_sheet: AnalysisSheet = Field(default_factory=AnalysisSheet)
    charts: list[Chart] = Field(default_factory=list)
    forecast_sheet: ForecastSheet = Field(default_factory=ForecastSheet)
    # Raw column name -> presentation-ready display name, so every consumer
    # (Excel writer, in-app dashboard) can relabel columns consistently.
    display_names: dict[str, str] = Field(default_factory=dict)
