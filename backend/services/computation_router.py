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

        return self.packager.package(action_plan, all_results, session, sheets=sheets)

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
        file_path = session.get("file_path")
        if not file_path:
            return {}
        try:
            return {name: df for name, df in self.reader.read_sheets(file_path)}
        except Exception:  # noqa: BLE001
            return {}
