"""
ComputationRouter — dispatch each action-plan operation to the right deterministic
module, collect results, and package them into a ComputationOutput.

The Cerebras action plan describes *intent*; this layer does all the maths.
"""

from __future__ import annotations

import difflib
import logging
from pathlib import Path
from typing import Any

import pandas as pd

import config
from schemas.cerebras_schema import ActionPlan, Operation
from schemas.computation_schema import ComputationOutput

from .excel_reader import ExcelReader
from .modules.aggregation import AggregationModule
from .modules.chart_generator import ChartGenerator
from .modules.forecasting import ForecastingModule
from .modules.growth import GrowthModule
from .modules.scoring import ScoringModule
from .modules.statistical import StatisticalModule
from .output_packager import OutputPackager

log = logging.getLogger("excelgpt.router")

# operation_type -> module attribute name
OPERATION_MAP = {
    "group_sum": "aggregation",
    "group_avg": "aggregation",
    "rank": "aggregation",
    "filter": "aggregation",
    "growth_rate": "growth",
    "variance": "growth",
    "correlation": "statistical",
    "outlier": "statistical",
    "distribution": "statistical",
    "forecast": "forecasting",
    "cluster": "scoring",
    "score": "scoring",
    "chart": "chart",
}


class ComputationRouter:
    def __init__(self) -> None:
        self.reader = ExcelReader()
        self.aggregation = AggregationModule()
        self.growth = GrowthModule()
        self.statistical = StatisticalModule()
        self.forecasting = ForecastingModule()
        self.scoring = ScoringModule()
        self.chart = ChartGenerator()
        self.packager = OutputPackager()

    def route(self, action_plan: ActionPlan, session: dict[str, Any]) -> ComputationOutput:
        sheets = self._load_sheets(session)
        session_id = session.get("session_id", "")
        charts_dir = Path(config.UPLOAD_DIR) / session_id / "charts"

        all_results: list[dict[str, Any]] = []
        for operation in action_plan.operations:
            result = self._execute_one(operation, sheets, charts_dir)
            if result is not None:
                all_results.append(result)

        # Auto-generate charts when the plan wants a Charts sheet but the planner
        # supplied no explicit chart operation (e.g. a "top 5 + variance" question).
        all_results.extend(self._auto_charts(action_plan, all_results, sheets, charts_dir))

        return self.packager.package(action_plan, all_results, session, sheets=sheets)

    def _auto_charts(self, action_plan, results, sheets, charts_dir) -> list[dict[str, Any]]:
        if any(op.operation_type == "chart" for op in action_plan.operations):
            return []
        if "charts" not in [str(s) for s in action_plan.output_sheets_required]:
            return []
        rank = next((r for r in results if r.get("operation_type") == "rank" and r.get("rows")), None)
        if not rank:
            # No ranking, but a grouped roll-up (e.g. regional group_sum) still
            # deserves a chart — built from the AGGREGATED result rows, never the
            # raw 50k-row frame.
            group = next((r for r in results if r.get("operation_type") in ("group_sum", "group_avg") and r.get("rows")), None)
            if group:
                return self._group_charts(group, charts_dir)
            return []
        cols = rank.get("columns", [])
        rows = rank.get("rows", [])
        ranked_by = rank.get("ranked_by")
        if ranked_by not in cols or not rows:
            return []
        dep_i = cols.index(ranked_by)
        ent_i = next((i for i, c in enumerate(cols) if c not in ("Rank", ranked_by) and isinstance(rows[0][i], str)), None)
        if ent_i is None:
            return []

        entity_col = cols[ent_i]
        branches = [r[ent_i] for r in rows]
        deposits = [r[dep_i] for r in rows]
        top_n = len(branches)
        target_sheet = next(iter(sheets), "Sheet1")
        charts: list[dict[str, Any]] = []

        # Chart 1 — Top N branches by the ranked metric (horizontal bar).
        df1 = pd.DataFrame({entity_col: branches, ranked_by: deposits})
        op1 = Operation(
            operation_id="auto_chart_primary", operation_type="chart", target_sheet=target_sheet,
            target_columns=[entity_col, ranked_by], group_by=[],
            parameters={"chart_type": "bar", "x": entity_col, "y": ranked_by, "top_n": top_n},
            output_sheet="charts", output_label=f"Top {top_n} Branches by {ranked_by} (₦)",
        )
        charts.append(self.chart.execute(op1, df1, str(charts_dir)))

        # Chart 2 — Deposits vs Target comparison LINE chart when a target exists.
        var_op = next((op for op in action_plan.operations if op.operation_type == "variance"), None)
        target_col = None
        if var_op:
            target_col = var_op.parameters.get("target_column") or var_op.parameters.get("target")
        if target_col not in cols:
            target_col = next((c for c in cols if str(c).lower() in ("target", "budget", "goal", "plan")), None)
        if target_col in cols:
            tgt_i = cols.index(target_col)
            targets = [r[tgt_i] for r in rows]
            df2 = pd.DataFrame({entity_col: branches, ranked_by: deposits, target_col: targets})
            op2 = Operation(
                operation_id="auto_chart_variance", operation_type="chart", target_sheet=target_sheet,
                target_columns=[entity_col, ranked_by, target_col], group_by=[],
                parameters={"chart_type": "line", "top_n": top_n},
                output_sheet="charts", output_label=f"{ranked_by} vs Target — Top {top_n} Branches",
            )
            charts.append(self.chart.comparison(op2, df2, str(charts_dir), entity_col, ranked_by, target_col))

        return [c for c in charts if c and c.get("image_path")]

    def _group_charts(self, group: dict[str, Any], charts_dir) -> list[dict[str, Any]]:
        """Horizontal bar chart of a grouped roll-up, fed the AGGREGATED rows
        (one per group), so a regional question charts Region → Deposits."""
        cols = group.get("columns", []) or []
        rows = group.get("rows", []) or []
        value_cols = group.get("value_columns", []) or []
        if not cols or not rows or not value_cols:
            return []

        # First non-value column is the group dimension (e.g. Region).
        value_set = set(value_cols)
        group_col = next((c for c in cols if c not in value_set), cols[0])
        value_col = value_cols[0]
        if group_col not in cols or value_col not in cols:
            return []
        g_i, v_i = cols.index(group_col), cols.index(value_col)

        groups = [r[g_i] for r in rows if g_i < len(r)]
        values = [r[v_i] for r in rows if v_i < len(r)]
        if not groups:
            return []

        df = pd.DataFrame({group_col: groups, value_col: values})
        label = group.get("label") or f"{value_col} by {group_col}"
        op = Operation(
            operation_id="auto_chart_group", operation_type="chart", target_sheet="",
            target_columns=[group_col, value_col], group_by=[],
            parameters={"chart_type": "bar", "x": group_col, "y": value_col, "top_n": len(groups)},
            output_sheet="charts", output_label=label,
        )
        chart = self.chart.execute(op, df, str(charts_dir))
        return [chart] if chart and chart.get("image_path") else []

    # -- internals ----------------------------------------------------------

    def _execute_one(self, operation: Operation, sheets, charts_dir) -> dict[str, Any] | None:
        module_name = OPERATION_MAP.get(operation.operation_type)
        if module_name is None:
            return {
                "operation_id": operation.operation_id,
                "operation_type": operation.operation_type,
                "label": operation.output_label,
                "warnings": [f"No module handles operation type '{operation.operation_type}'."],
            }

        df = self._select_sheet(operation, sheets)
        self._remap_columns(operation, df)
        try:
            if module_name == "chart":
                return self.chart.execute(operation, df, str(charts_dir))
            module = getattr(self, module_name)
            return module.execute(operation, df)
        except Exception as exc:  # noqa: BLE001 — one bad op must not sink the whole report
            return {
                "operation_id": operation.operation_id,
                "operation_type": operation.operation_type,
                "label": operation.output_label,
                "warnings": [f"Operation failed: {exc}"],
            }

    def _remap_columns(self, operation: Operation, df: pd.DataFrame) -> None:
        """Repair group_by / target_columns that don't exactly match the frame.

        Cerebras (or a fuzzy header) can hand us 'Region ' or 'regions' when the
        column is 'Region'. Rather than silently dropping it — which is how a
        regional group_sum degrades into a meaningless date ranking — we snap each
        missing column to its closest real column name. Exact and case-insensitive
        matches are preferred; difflib handles the near-misses.
        """
        if df is None or df.empty:
            return
        available = [str(c) for c in df.columns]
        lower_map = {c.lower(): c for c in available}

        def closest(col: str) -> str | None:
            if col in available:
                return col
            hit = lower_map.get(str(col).lower())
            if hit:
                return hit
            matches = difflib.get_close_matches(str(col), available, n=1, cutoff=0.6)
            return matches[0] if matches else None

        def remap_list(name: str, values: list[str]) -> None:
            fixed: list[str] = []
            for col in values:
                match = closest(col)
                if match is None:
                    fixed.append(col)  # leave it; the module will warn/skip
                    continue
                if match != col:
                    log.info("Remapped %s '%s' to '%s'", name, col, match)
                    print(f"[router] Remapped {name} '{col}' to '{match}'")
                fixed.append(match)
            values[:] = fixed

        remap_list("group_by", operation.group_by)
        remap_list("target_columns", operation.target_columns)

    def _select_sheet(self, operation: Operation, sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
        if not sheets:
            return pd.DataFrame()
        if operation.target_sheet in sheets:
            return sheets[operation.target_sheet]
        # Case-insensitive match, then fall back to the first (usually only) sheet.
        for name, df in sheets.items():
            if str(name).lower() == str(operation.target_sheet).lower():
                return df
        return next(iter(sheets.values()))

    def _load_sheets(self, session: dict[str, Any]) -> dict[str, pd.DataFrame]:
        # Honour pre-loaded dataframes on the session first (tests, in-memory flows).
        pre = session.get("sheet_dataframes")
        if isinstance(pre, dict) and pre:
            return {str(name): df for name, df in pre.items() if isinstance(df, pd.DataFrame)}

        file_path = session.get("file_path")
        if not file_path:
            return {}
        try:
            return {name: df for name, df in self.reader.read_sheets(file_path)}
        except Exception:  # noqa: BLE001
            return {}
