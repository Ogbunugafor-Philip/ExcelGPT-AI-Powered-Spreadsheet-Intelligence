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
import logging
from typing import Any

from cerebras.cloud.sdk import Cerebras
from pydantic import ValidationError

import config
from schemas.cerebras_schema import (
    ActionPlan,
    FormattingTier,
    IntentType,
    Operation,
    OperationType,
    OutputSheet,
)

log = logging.getLogger("excelgpt.intent")


class IntentEngineError(Exception):
    """Raised when the AI intent layer cannot produce a valid action plan."""


# Keyword → compact operation description, scanned in order. Used to compress a
# long instruction (Tier 2) and to detect requested analyses (Tier 3 fallback).
# Each entry: (list of trigger keywords, predicate-needs-all, compact form).
_COMPRESSION_RULES: tuple[tuple[tuple[str, ...], bool, str], ...] = (
    (("executive", "dashboard", "kpi"), False, "executive summary with KPI cards"),
    (("region",), False, "rank regions by deposits with attainment vs target"),
    (("state",), False, "rank states by deposits with attainment and variance"),
    (("cluster head",), False, "rank cluster heads by deposits with performance tier"),
    (("fso leaderboard", "rank all fso"), False, "rank FSOs by deposits with attainment percentage and performance tier"),
    (("fso", "rank"), True, "rank FSOs by deposits with attainment percentage and performance tier"),
    (("daily", "trend", "day"), False, "daily trend of deposits with day-on-day growth"),
    (("underperform", "below target", "below 70"), False, "list FSOs below 70% attainment sorted by variance"),
    (("top perform", "above target", "above 110"), False, "list FSOs above 110% attainment sorted by deposits"),
)


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
Excel reporting tool that produces world-class, board-ready analytics dashboards. \
Your ONLY job is to translate a user's plain-English instruction plus a data brief \
into a structured ACTION PLAN (intent only).

Hard rules:
- You NEVER compute, calculate, or invent data values. You only name operations \
and where their results belong. A separate deterministic engine does all math.
- target_sheet/target_columns/group_by MUST use the EXACT raw column "name" values \
from the DATA BRIEF (e.g. "deposits_ngn"), because the engine matches on them.
- output_label and any human-facing text MUST use the column's "display_name" from \
the brief (e.g. "Deposits (₦)"), NEVER the raw name. Write real titles a director \
would read: "Top Channels by Revenue", not "rank_revenue".
- Respond with a SINGLE JSON object and nothing else. No prose, no markdown fences.

Each column in the brief carries three signals you MUST exploit:
- "name": the raw key to target.
- "display_name": the clean label to show.
- "semantic": the column's role — one of revenue_metric, target_metric, \
actual_metric, growth_metric, rank_metric, volume_metric, cost_metric, \
profit_metric, score_metric, time_dimension, geographic_dimension, \
category_dimension, entity_identifier, person_identifier, unknown.

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
      "target_columns": [exact RAW column names from the brief],
      "group_by": [raw column names to group by, or []],
      "parameters": {{ operation-specific knobs }},
      "output_sheet": one of {_OUTPUT_SHEETS},
      "output_label": "Human-readable title using display_names"
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
- group_sum / group_avg: roll up a metric by group_by keys (a dimension/identifier).
- rank: order entities; parameters {{"by": "<raw col>", "order": "desc", "top_n": 10}}.
- filter: subset rows; parameters {{"where": "<column comparison>"}}.
- growth_rate: period-over-period change; parameters {{"period": "month|quarter|year", "as_percent": true}}.
- variance: actual-vs-target; parameters {{"actual": "<raw col>", "target": "<raw col>"}}.
- correlation: parameters {{"method": "pearson|spearman"}}.
- forecast: time-series projection; parameters {{"model": "arima", "periods": 3, "confidence": 0.95}}.
- cluster: parameters {{"algorithm": "kmeans", "k": 4}}.
- score: composite scoring; parameters {{"weights": {{...}}}}.
- chart: parameters {{"chart_type": "bar|line|pie|scatter", "x": "<raw col>", "y": "<raw col>"}}.

Semantic-driven planning — infer the analysis the data supports, don't wait to be asked:
- time_dimension + a revenue/volume/profit metric  -> ALSO add a growth_rate operation.
- entity_identifier/category_dimension + a metric  -> ALSO add a rank operation (top performers).
- target_metric + actual_metric present            -> ALSO add a variance operation.
- geographic_dimension present                      -> ALSO add a group_sum by that geography.
- For every analysis, ALSO add a chart operation that visualises the primary result \
(bar for rankings/category breakdowns, line for time series, pie for share-of-total).
- ALWAYS produce an executive_summary: include "executive_summary" in \
output_sheets_required so the KPI cards (the headline numbers) are generated.

General planning rules:
1. Choose the single best intent_type for the overall goal.
2. output_sheets_required MUST include every operation's output_sheet, and should \
include "executive_summary" for essentially every report.
3. Any chart operation MUST use output_sheet "charts".
4. Use the brief's suggested_template and Nigerian flags to fill nigerian_context. \
Default currency is "NGN". Set lga_analysis true only when a geographic_dimension \
column exists and the user wants a geographic breakdown.
5. formatting_tier: use "executive" whenever the instruction mentions "summary", \
"board", "report", "presentation", "deck", or "executive"; "premium" for polished \
multi-operation analysis; "standard" only for a single quick table.
6. operations may be empty ONLY when intent_type is "formatting_only".

Ambiguity:
- If the instruction is too vague to plan safely (no clear metric, column, or goal), \
set clarification_needed=true, write ONE concise clarification_question, and leave \
operations empty. Otherwise clarification_needed=false and clarification_question=null. \
Strongly prefer making a rich, reasonable plan over asking; only ask when you \
genuinely cannot proceed."""


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
        """Turn an instruction + data brief into a validated ActionPlan.

        Always returns a plan — see :meth:`classify_with_status` for the 3-tier
        fallback that guarantees this never raises for a non-empty instruction.
        """
        plan, _status = self.classify_with_status(intelligence_brief, instruction)
        return plan

    def classify_with_status(
        self, intelligence_brief: dict[str, Any], instruction: str
    ) -> tuple[ActionPlan, str]:
        """3-tier planner. Returns (plan, ai_status) where ai_status is one of
        "cerebras" (Tier 1/2 succeeded) or "fallback" (Tier 3 rule-based).

        The user must ALWAYS get a result: even a 200-word instruction that times
        out twice falls through to the deterministic rule-based planner, which
        never calls the network and never fails.
        """
        instruction = (instruction or "").strip()
        if not instruction:
            raise IntentEngineError("Instruction is empty.")

        # TIER 1 — full instruction to Cerebras (highest fidelity).
        try:
            return self._plan_from_cerebras(intelligence_brief, instruction), "cerebras"
        except IntentEngineError as e1:
            log.warning("Tier 1 (full instruction) failed: %s. Trying Tier 2 (compressed).", e1)

        # TIER 2 — compressed summary (<60 words) to Cerebras.
        try:
            compressed = self._compress_instruction(instruction)
            return self._plan_from_cerebras(intelligence_brief, compressed), "cerebras"
        except IntentEngineError as e2:
            log.warning("Tier 2 (compressed) failed: %s. Activating rule-based fallback.", e2)

        # TIER 3 — rule-based fallback. No network, no validation risk, never fails.
        return self._rule_based_fallback(intelligence_brief, instruction), "fallback"

    def _plan_from_cerebras(self, intelligence_brief: dict[str, Any], instruction_text: str) -> ActionPlan:
        """One Cerebras attempt: build the message, call, parse, normalize."""
        user_message = self._build_user_message(intelligence_brief, instruction_text)
        raw = self._call_cerebras(user_message)
        data = self._parse_json(raw)
        return self._normalize(data)

    # -- instruction compression (Tier 2) -----------------------------------

    def _detect_operations(self, instruction: str) -> list[str]:
        """Scan the instruction for known analysis keywords and return the
        matching compact operation descriptions, de-duplicated, in priority order."""
        text = (instruction or "").lower()
        found: list[str] = []
        for keywords, needs_all, compact in _COMPRESSION_RULES:
            hit = all(k in text for k in keywords) if needs_all else any(k in text for k in keywords)
            if hit and compact not in found:
                found.append(compact)
        return found

    def _compress_instruction(self, instruction: str) -> str:
        """Reduce a long instruction to its core operations, kept short.

        Maps detected keywords to compact operation descriptions and joins them.
        If nothing matches, falls back to the first ~50 words of the original so
        Tier 2 still has something meaningful to send.
        """
        ops = self._detect_operations(instruction)
        if not ops:
            return " ".join((instruction or "").split()[:50])
        compressed = "Analyse this sales data: " + "; ".join(ops)
        words = compressed.split()
        if len(words) > 75:  # hard ceiling well under the diagnostic's 80-word check
            compressed = " ".join(words[:75])
        return compressed

    def _minimal_instruction(self, instruction: str) -> str:
        """Ultra-compressed — just the top 3 detected operations as one sentence."""
        ops = self._detect_operations(instruction)
        top3 = ops[:3]
        if not top3:
            return "Show me: " + " ".join((instruction or "").split()[:20])
        return "Show me: " + ", ".join(top3)

    # -- rule-based fallback (Tier 3) ---------------------------------------

    def _rule_based_fallback(self, brief: dict[str, Any], instruction: str) -> ActionPlan:
        """Build a complete ActionPlan using only Python keyword detection.

        No AI. No API call. Always works in well under 1ms. This is the safety
        net that must NEVER fail.
        """
        # Step 1 — sheet names from the brief.
        sheets = [s.get("name") for s in brief.get("sheets", []) or [] if s.get("name")]
        first_sheet = sheets[0] if sheets else "Sheet1"

        # Step 2 — available columns from the brief.
        all_columns: list[str] = []
        for sheet in brief.get("sheets", []) or []:
            for col in sheet.get("column_summary", []) or []:
                name = col.get("name")
                if name:
                    all_columns.append(name)

        def low(c: str) -> str:
            return str(c).lower()

        def has(c: str, *keywords: str) -> bool:
            return any(k in low(c) for k in keywords)

        def clean_label(c: Any) -> str:
            """'Deposits (₦)' -> 'Deposits' for readable output labels."""
            text = str(c)
            cut = text.find(" (")
            return (text[:cut] if cut != -1 else text).strip()

        targety = ("target", "budget", "plan", "quota")

        # Value (money) columns — prefer deposits; never a target column. The "₦"
        # hint catches naira columns even when the word "deposit" is absent.
        deposit_like = [c for c in all_columns if has(c, "deposit", "revenue", "sales", "collection") and not has(c, *targety)]
        money_like = [c for c in all_columns if "₦" in str(c) and not has(c, *targety)]
        amount_like = [c for c in all_columns if has(c, "amount") and not has(c, *targety)]
        value_cols = deposit_like or money_like or amount_like
        # Pick the FSO-level value (Deposits), not a cluster-head metric.
        primary_value = next((c for c in value_cols if "fso" not in low(c)), value_cols[0] if value_cols else None)
        if primary_value is None:
            primary_value = all_columns[-1] if all_columns else None

        # Count columns — accounts opened, never a target.
        count_cols = [c for c in all_columns if has(c, "account", "count", "number", "opened", "qty") and not has(c, *targety)]
        primary_count = next((c for c in count_cols if "target" not in low(c)), None)

        # Entity — prefer FSO Name over FSO ID.
        entity_cols = [c for c in all_columns if has(c, "fso name", "name", "branch", "agent", "staff", "officer")]
        entity_col = next((c for c in entity_cols if "name" in low(c)), entity_cols[0] if entity_cols else None)

        # Target — prefer the FSO-level naira target over the cluster-head target.
        target_cols = [c for c in all_columns if has(c, *targety)]
        fso_target = next((c for c in target_cols if "fso" in low(c) and "₦" in str(c)),
                          next((c for c in target_cols if "fso" in low(c)),
                               target_cols[0] if target_cols else None))

        # Geographic hierarchy + date — exact column-name match first, then contains.
        def exact_or_contains(token: str) -> str | None:
            return (next((c for c in all_columns if low(c) == token), None)
                    or next((c for c in all_columns if token in low(c)), None))

        region_col = exact_or_contains("region")
        state_col = exact_or_contains("state")
        cluster_head_col = next((c for c in all_columns if "cluster head" in low(c)), None)
        date_col = (next((c for c in all_columns if low(c) in ("date", "day")), None)
                    or next((c for c in all_columns if has(c, "date")), None))

        # A friendly noun for the ranked entity ("FSO" when the column is FSO-based).
        entity_noun = "FSO" if (entity_col and "fso" in low(entity_col)) else (clean_label(entity_col) if entity_col else "Entity")

        # Step 3 — parse the instruction for requested analyses.
        instr = (instruction or "").lower()
        want_executive = any(k in instr for k in ["executive", "dashboard", "kpi", "summary", "national"])
        want_fso_rank = any(k in instr for k in ["fso", "leaderboard", "rank all", "rank", "officer"])
        want_region = any(k in instr for k in ["region", "geopolitical", "zone", "scorecard"])
        want_state = any(k in instr for k in ["state", "states"])
        want_cluster = any(k in instr for k in ["cluster head", "cluster"])
        want_daily = any(k in instr for k in ["daily", "trend", "day", "june", "week"])
        want_variance = any(k in instr for k in ["target", "attainment", "variance", "below", "above", "watchlist", "recognition"])
        want_chart = True  # always add a chart

        # Step 4 — build operations.
        operations: list[Operation] = []
        op_num = 1

        def value_targets() -> list[str]:
            cols = [primary_value] if primary_value else []
            if primary_count:
                cols.append(primary_count)
            return cols

        if entity_col and primary_value:
            # Op 1 — FSO Leaderboard: rank by value, grouped with the full hierarchy.
            if want_fso_rank or want_executive:
                group = [entity_col] + [c for c in (region_col, state_col, cluster_head_col) if c]
                operations.append(Operation(
                    operation_id=f"op_{op_num}", operation_type="rank", target_sheet=first_sheet,
                    target_columns=value_targets(), group_by=group,
                    parameters={"by": primary_value, "order": "desc", "top_n": 100, "include_all": True},
                    output_sheet="data", output_label=f"{entity_noun} Leaderboard — Ranked by {clean_label(primary_value)}"))
                op_num += 1

            # Op 2 — Regional Scorecard.
            if want_region and region_col:
                operations.append(Operation(
                    operation_id=f"op_{op_num}", operation_type="group_sum", target_sheet=first_sheet,
                    target_columns=value_targets(), group_by=[region_col], parameters={},
                    output_sheet="analysis", output_label="Regional Performance Scorecard"))
                op_num += 1

            # Op 3 — State Performance.
            if want_state and state_col:
                operations.append(Operation(
                    operation_id=f"op_{op_num}", operation_type="group_sum", target_sheet=first_sheet,
                    target_columns=value_targets(), group_by=[state_col], parameters={},
                    output_sheet="analysis", output_label="State Performance Table"))
                op_num += 1

            # Op 4 — Cluster Head Leaderboard.
            if want_cluster and cluster_head_col:
                group = [cluster_head_col] + [c for c in (region_col, state_col) if c]
                operations.append(Operation(
                    operation_id=f"op_{op_num}", operation_type="group_sum", target_sheet=first_sheet,
                    target_columns=value_targets(), group_by=group, parameters={},
                    output_sheet="analysis", output_label="Cluster Head Leaderboard"))
                op_num += 1

            # Op 5 — Daily Trend.
            if want_daily and date_col:
                operations.append(Operation(
                    operation_id=f"op_{op_num}", operation_type="growth_rate", target_sheet=first_sheet,
                    target_columns=[primary_value], group_by=[date_col], parameters={},
                    output_sheet="analysis", output_label="Daily Deposit Trend June 2025"))
                op_num += 1

            # Op 6 — Attainment vs Target.
            if want_variance and fso_target:
                operations.append(Operation(
                    operation_id=f"op_{op_num}", operation_type="variance", target_sheet=first_sheet,
                    target_columns=[primary_value], group_by=[entity_col],
                    parameters={"target_column": fso_target, "include_all": True},
                    output_sheet="analysis", output_label=f"{entity_noun} Attainment vs Target"))
                op_num += 1

            # Op 7 — Chart of the top performers.
            if want_chart:
                operations.append(Operation(
                    operation_id=f"op_{op_num}", operation_type="chart", target_sheet=first_sheet,
                    target_columns=[primary_value], group_by=[entity_col],
                    parameters={"chart_type": "bar", "top_n": 10, "x": entity_col, "y": primary_value},
                    output_sheet="charts", output_label=f"Top 10 {entity_noun}s by {clean_label(primary_value)}"))
                op_num += 1

        # Step 5 — safe default when nothing was detected.
        if not operations:
            operations.append(Operation(
                operation_id="op_1", operation_type="rank", target_sheet=first_sheet,
                target_columns=[all_columns[-1]] if all_columns else [],
                group_by=[all_columns[0]] if all_columns else [],
                parameters={"top_n": 20}, output_sheet="data", output_label="Performance Ranking"))

        # Step 6 — output sheets implied by the operations (executive first).
        output_sheets = list(dict.fromkeys(
            ["executive_summary"] + [op.output_sheet for op in operations]))

        # Step 7 — assemble the plan.
        return ActionPlan(
            intent_type="aggregation",
            clarification_needed=False,
            clarification_question=None,
            operations=operations,
            output_sheets_required=output_sheets,
            formatting_tier="executive",
            nigerian_context={
                "currency": "NGN",
                "template_type": "sales",
                "fiscal_calendar": "january",
                "lga_analysis": False,
            },
        )

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
                        {
                            "name": column.get("name"),
                            "display_name": column.get("display_name") or column.get("name"),
                            "semantic": column.get("semantic", "unknown"),
                            "type": column.get("type", "text"),
                        }
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
