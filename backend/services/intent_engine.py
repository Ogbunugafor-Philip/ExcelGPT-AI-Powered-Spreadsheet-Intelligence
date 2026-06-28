"""
ExcelGPT — Cerebras AI intent layer.

The IntentEngine is the ONLY place Cerebras is used. It translates a natural-
language instruction (plus the data intelligence brief) into a structured
``ActionPlan`` — pure intent. It never sees raw data values and never performs
math; all numbers come later from the deterministic computation engine.

Contract:
    engine.classify(intelligence_brief, instruction) -> ActionPlan

The returned plan is validated against ``schemas.cerebras_schema.ActionPlan`` and
normalized so it always satisfies the validation rules in
``architecture/cerebras-schema.md`` before it leaves this layer.
"""

from __future__ import annotations

import json
from typing import Any

from cerebras.cloud.sdk import Cerebras
from pydantic import ValidationError

import config
from schemas.cerebras_schema import (
    ActionPlan,
    FormattingTier,
    IntentType,
    OperationType,
    OutputSheet,
)


class IntentEngineError(Exception):
    """Raised when the AI intent layer cannot produce a valid action plan."""


# Canonical workbook order for output sheets, used when normalizing the plan.
_OUTPUT_SHEET_ORDER: tuple[str, ...] = (
    "executive_summary",
    "data",
    "analysis",
    "charts",
    "forecast",
)


def _enum_values(literal: Any) -> list[str]:
    """Extract the allowed string values from a typing.Literal alias."""
    return list(getattr(literal, "__args__", ()))


_INTENT_TYPES = _enum_values(IntentType)
_OPERATION_TYPES = _enum_values(OperationType)
_OUTPUT_SHEETS = _enum_values(OutputSheet)
_FORMATTING_TIERS = _enum_values(FormattingTier)


SYSTEM_PROMPT = f"""You are the intent classifier for ExcelGPT, a Nigerian-market \
Excel reporting tool. Your ONLY job is to translate a user's plain-English \
instruction plus a data brief into a structured ACTION PLAN (intent only).

Hard rules:
- You NEVER compute, calculate, or invent data values. You only name operations \
and where their results belong. A separate deterministic engine does all math.
- You only reference sheet and column names that appear in the DATA BRIEF.
- Respond with a SINGLE JSON object and nothing else. No prose, no markdown fences.

Output JSON shape:
{{
  "intent_type": one of {_INTENT_TYPES},
  "clarification_needed": boolean,
  "clarification_question": string or null,
  "operations": [
    {{
      "operation_id": "op_1",
      "operation_type": one of {_OPERATION_TYPES},
      "target_sheet": exact sheet name from the brief,
      "target_columns": [exact column names from the brief],
      "group_by": [column names to group by, or []],
      "parameters": {{ operation-specific knobs }},
      "output_sheet": one of {_OUTPUT_SHEETS},
      "output_label": "Human readable label"
    }}
  ],
  "output_sheets_required": [subset of {_OUTPUT_SHEETS}],
  "formatting_tier": one of {_FORMATTING_TIERS},
  "nigerian_context": {{
    "currency": "NGN",
    "template_type": "banking | sales | hr | general",
    "fiscal_calendar": "january | april",
    "lga_analysis": boolean
  }}
}}

operation_type guidance:
- group_sum / group_avg: roll up a numeric column by group_by keys.
- rank: order entities; parameters like {{"by": "<col>", "order": "desc", "top_n": 10}}.
- filter: subset rows; parameters {{"where": "<column comparison>"}}.
- growth_rate: period-over-period change; parameters {{"period": "month|quarter|year", "as_percent": true}}.
- correlation: parameters {{"method": "pearson|spearman"}}.
- forecast: time-series projection; parameters {{"model": "arima", "periods": 3, "confidence": 0.95}}.
- cluster: parameters {{"algorithm": "kmeans", "k": 4}}.
- score: composite scoring; parameters {{"weights": {{...}}}}.
- chart: parameters {{"chart_type": "bar|line|pie|scatter", "x": "<col>", "y": "<col>"}}.

Planning rules:
1. Choose the single best intent_type for the overall goal.
2. output_sheets_required MUST include every operation's output_sheet. Include \
"executive_summary" whenever the user wants a report or summary.
3. Any chart operation MUST use output_sheet "charts".
4. Use the brief's suggested_template and Nigerian flags to fill nigerian_context. \
Default currency is "NGN". Set lga_analysis true only if the data has LGA/state columns \
and the user wants geographic breakdowns.
5. formatting_tier: "standard" for quick tables, "premium" for polished analysis, \
"executive" for board-ready/executive reports.
6. operations may be empty ONLY when intent_type is "formatting_only".

Ambiguity:
- If the instruction is too vague to plan safely (no clear metric, column, or goal), \
set clarification_needed=true, write ONE concise clarification_question, and leave \
operations empty. Otherwise clarification_needed=false and clarification_question=null. \
Prefer making a reasonable plan over asking; only ask when you genuinely cannot proceed."""


class IntentEngine:
    """Cerebras-backed action-plan generator."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else config.CEREBRAS_API_KEY
        self._model = model or config.CEREBRAS_MODEL
        self._client: Cerebras | None = None

    @property
    def client(self) -> Cerebras:
        """Lazily construct the Cerebras client so import never requires a key."""
        if self._client is None:
            if not self._api_key:
                raise IntentEngineError(
                    "CEREBRAS_API_KEY is not configured; cannot reach the intent service."
                )
            self._client = Cerebras(
                api_key=self._api_key,
                timeout=config.CEREBRAS_TIMEOUT_SECONDS,
            )
        return self._client

    # -- public API ---------------------------------------------------------

    def classify(self, intelligence_brief: dict[str, Any], instruction: str) -> ActionPlan:
        """Turn an instruction + data brief into a validated ActionPlan."""
        instruction = (instruction or "").strip()
        if not instruction:
            raise IntentEngineError("Instruction is empty.")

        user_message = self._build_user_message(intelligence_brief, instruction)
        raw = self._call_cerebras(user_message)
        data = self._parse_json(raw)
        return self._normalize(data)

    # -- prompt construction ------------------------------------------------

    def _build_user_message(self, intelligence_brief: dict[str, Any], instruction: str) -> str:
        compact = self._compact_brief(intelligence_brief)
        return (
            "DATA BRIEF (structure only — no raw values):\n"
            + json.dumps(compact, ensure_ascii=False)
            + "\n\nUSER INSTRUCTION:\n"
            + instruction
            + "\n\nReturn ONLY the action plan JSON object."
        )

    def _compact_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        """Trim the intelligence brief to the structure Cerebras needs (token-light)."""
        sheets = []
        for sheet in brief.get("sheets", []) or []:
            sheets.append(
                {
                    "name": sheet.get("name"),
                    "row_count": sheet.get("row_count"),
                    "is_time_series": sheet.get("is_time_series", False),
                    "columns": [
                        {"name": column.get("name"), "type": column.get("type", "text")}
                        for column in sheet.get("column_summary", []) or []
                    ],
                }
            )
        nigerian = brief.get("nigerian_context", {}) or {}
        return {
            "filename": brief.get("filename"),
            "sheets": sheets,
            "potential_join_keys": brief.get("potential_join_keys", []),
            "nigerian_context": {
                "detected": nigerian.get("detected", False),
                "flags": nigerian.get("flags", []),
                "suggested_template": nigerian.get("suggested_template", "general"),
            },
        }

    # -- Cerebras call ------------------------------------------------------

    def _call_cerebras(self, user_message: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=config.CEREBRAS_TEMPERATURE,
                max_completion_tokens=config.CEREBRAS_MAX_TOKENS,
            )
        except IntentEngineError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface any SDK/transport failure uniformly
            raise IntentEngineError(f"Cerebras intent service unavailable: {exc}") from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise IntentEngineError("Cerebras returned an empty response.") from exc

        if not content or not content.strip():
            raise IntentEngineError("Cerebras returned an empty action plan.")
        return content

    # -- parsing & normalization -------------------------------------------

    def _parse_json(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            # Strip a ```json ... ``` fence if the model added one.
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise IntentEngineError("Cerebras did not return valid JSON.")
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise IntentEngineError("Cerebras did not return valid JSON.") from exc

        if not isinstance(data, dict):
            raise IntentEngineError("Cerebras action plan was not a JSON object.")
        return data

    def _normalize(self, data: dict[str, Any]) -> ActionPlan:
        """Repair safe rule violations, then validate against the schema."""
        operations = data.get("operations") or []
        if not isinstance(operations, list):
            operations = []

        # Rule 3: every chart operation writes to the charts sheet.
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                continue
            if operation.get("operation_type") == "chart":
                operation["output_sheet"] = "charts"
            operation.setdefault("operation_id", f"op_{index + 1}")
        data["operations"] = operations

        # Rule 2: output_sheets_required must include every operation's output sheet.
        required = [s for s in (data.get("output_sheets_required") or []) if s in _OUTPUT_SHEETS]
        for operation in operations:
            sheet = operation.get("output_sheet") if isinstance(operation, dict) else None
            if sheet in _OUTPUT_SHEETS and sheet not in required:
                required.append(sheet)
        # Canonical ordering for a tidy workbook.
        data["output_sheets_required"] = [s for s in _OUTPUT_SHEET_ORDER if s in required]

        try:
            plan = ActionPlan(**data)
        except ValidationError as exc:
            raise IntentEngineError(f"Cerebras action plan failed validation: {exc}") from exc

        # Rule 1: clarification_question is non-null iff clarification_needed is true.
        if plan.clarification_needed:
            if not plan.clarification_question:
                plan.clarification_question = (
                    "Could you clarify the goal — which metric or columns should this report focus on?"
                )
        else:
            plan.clarification_question = None

        # Rule 5: empty operations are only valid for formatting_only. If the model
        # produced no operations for a computational intent, ask rather than emit a
        # plan that computes nothing.
        if (
            not plan.operations
            and plan.intent_type != "formatting_only"
            and not plan.clarification_needed
        ):
            plan.clarification_needed = True
            plan.clarification_question = (
                "I couldn't determine a concrete operation from that — what would you like the report to compute?"
            )

        return plan
