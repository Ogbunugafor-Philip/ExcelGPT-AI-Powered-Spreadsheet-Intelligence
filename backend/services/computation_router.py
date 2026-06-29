"""
ComputationRouter — dispatch each action-plan operation to the right deterministic
module, collect results, and package them into a ComputationOutput.

The Cerebras action plan describes *intent*; this layer does all the maths.
"""

from __future__ import annotations

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
