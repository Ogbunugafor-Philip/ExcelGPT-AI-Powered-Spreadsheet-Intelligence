"""
ExcelGPT — Cerebras action plan Pydantic models.

These models validate the action plan JSON returned by the AI intent layer
BEFORE it is routed to the computation engine. The action plan is intent only:
it names operations, target sheets/columns, and output destinations — it never
contains computed values. Mirrors architecture/cerebras-schema.md.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

IntentType = Literal[
    "aggregation",
    "growth_analysis",
    "statistical_analysis",
    "forecasting",
    "performance_scoring",
    "formatting_only",
    "custom",
]

OperationType = Literal[
    "group_sum",
    "group_avg",
    "rank",
    "filter",
    "growth_rate",
    "correlation",
    "forecast",
    "cluster",
    "score",
    "chart",
]

OutputSheet = Literal[
    "executive_summary",
    "data",
    "analysis",
    "charts",
    "forecast",
]

FormattingTier = Literal["standard", "premium", "executive"]
TemplateType = Literal["banking", "sales", "hr", "general"]
FiscalCalendar = Literal["january", "april"]


class NigerianContext(BaseModel):
    """Market context carried end-to-end through the pipeline."""

    currency: str = "NGN"
    template_type: TemplateType = "general"
    fiscal_calendar: FiscalCalendar = "january"
    lga_analysis: bool = False


class Operation(BaseModel):
    """A single deterministic operation for the computation engine to execute."""

    operation_id: str = Field(..., description="Unique id within the plan, e.g. 'op_1'.")
    operation_type: OperationType
    target_sheet: str = Field(..., description="Source sheet from the uploaded workbook.")
    target_columns: list[str] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_sheet: OutputSheet
    output_label: str = Field(..., description="Human-readable label for the result block.")


class ActionPlan(BaseModel):
    """The full action plan produced by the Cerebras AI intent layer."""

    intent_type: IntentType
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    operations: list[Operation] = Field(default_factory=list)
    output_sheets_required: list[OutputSheet] = Field(default_factory=list)
    formatting_tier: FormattingTier = "standard"
    nigerian_context: NigerianContext = Field(default_factory=NigerianContext)
