"""Growth operations: period-over-period growth_rate and target-vs-actual variance."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from schemas.cerebras_schema import Operation

from .common import (
    coerce_numeric,
    detect_date_column,
    direction_from,
    is_currency_column,
    rows_payload,
    to_jsonable,
)


class GrowthModule:
    def execute(self, operation: Operation, df: pd.DataFrame) -> dict[str, Any]:
        if operation.operation_type == "variance":
            return self._variance(operation, df)
        return self._growth_rate(operation, df)

    def _result(self, operation, columns, rows, display_rows, directional_summary=None, warnings=None, **extra):
        result = {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type,
            "label": operation.output_label,
            "columns": columns,
            "rows": rows,
            "display_rows": display_rows,
            "directional_summary": directional_summary or {},
            "warnings": warnings or [],
        }
        result.update(extra)
        return result

    def _first_numeric_target(self, operation, df, exclude, warnings):
        for column in operation.target_columns:
            if column == exclude or column not in df.columns:
                continue
            if coerce_numeric(df[column]).notna().sum() > 0:
                return column
        # Fall back to any numeric column not the date column.
        for column in df.columns:
            if column == exclude:
                continue
            if coerce_numeric(df[column]).notna().sum() > 0:
                warnings.append(f"No usable target column given; using '{column}'.")
                return column
        return None

    # -- growth_rate --------------------------------------------------------

    def _growth_rate(self, operation, df):
        warnings: list[str] = []
        if df.empty:
            return self._result(operation, [], [], [], warnings=["Empty dataframe — nothing to compute."])

        date_col = detect_date_column(df, prefer=operation.target_columns + operation.group_by)
        value_col = self._first_numeric_target(operation, df, exclude=date_col, warnings=warnings)
        if value_col is None:
            return self._result(operation, [], [], [], warnings=warnings + ["No numeric value column for growth."])

        group_cols = [c for c in operation.group_by if c in df.columns and c != date_col]
        work = df.copy()
        work[value_col] = coerce_numeric(df[value_col])

        if date_col:
            work["__period__"] = pd.to_datetime(work[date_col], errors="coerce")
        else:
            work["__period__"] = range(len(work))
            warnings.append("No date column detected — using row order as the period sequence.")

        work = work.sort_values(group_cols + ["__period__"]).reset_index(drop=True)

        if group_cols:
            previous = work.groupby(group_cols, dropna=False)[value_col].shift(1)
        else:
            previous = work[value_col].shift(1)
        current = work[value_col]

        # (current - previous) / previous * 100; division by zero -> NaN -> None.
        with np.errstate(divide="ignore", invalid="ignore"):
            growth = (current - previous) / previous * 100.0
        growth = growth.replace([np.inf, -np.inf], np.nan)
        work["growth_pct"] = growth.round(2)
        work["direction"] = work["growth_pct"].map(direction_from)

        if date_col:
            work["period"] = work["__period__"].dt.strftime("%Y-%m")
        else:
            work["period"] = work["__period__"]

        out_cols = group_cols + ["period", value_col, "growth_pct", "direction"]
        out = work[out_cols]

        currency_cols = [value_col] if is_currency_column(value_col) else []
        columns, rows, display_rows = rows_payload(out, currency_cols)

        valid = out["growth_pct"].dropna()
        directional_summary = {
            "value_column": value_col,
            "period_column": date_col or "row_order",
            "up": int((out["direction"] == "up").sum()),
            "down": int((out["direction"] == "down").sum()),
            "neutral": int((out["direction"] == "neutral").sum()),
            "average_growth_pct": round(float(valid.mean()), 2) if len(valid) else None,
            "latest_growth_pct": to_jsonable(valid.iloc[-1]) if len(valid) else None,
        }
        return self._result(
            operation, columns, rows, display_rows, directional_summary, warnings,
            currency_columns=currency_cols,
        )

    # -- variance -----------------------------------------------------------

    def _variance(self, operation, df):
        warnings: list[str] = []
        if df.empty:
            return self._result(operation, [], [], [], warnings=["Empty dataframe — nothing to compute."])

        params = operation.parameters or {}
        actual_col = params.get("actual") or self._find_named(df, ["actual", "achieved", "result"])
        if actual_col is None and operation.target_columns:
            actual_col = operation.target_columns[0]
        target_col = params.get("target") or self._find_named(df, ["target", "budget", "plan", "forecast", "goal"])

        if actual_col not in df.columns or target_col is None or target_col not in df.columns:
            return self._result(
                operation, [], [], [],
                warnings=warnings + [f"Need an actual and a target column; found actual='{actual_col}', target='{target_col}'."],
            )

        work = df.copy()
        actual = coerce_numeric(df[actual_col])
        target = coerce_numeric(df[target_col])
        work[actual_col] = actual.round(2)
        work[target_col] = target.round(2)

        with np.errstate(divide="ignore", invalid="ignore"):
            variance = (actual - target) / target * 100.0
        variance = variance.replace([np.inf, -np.inf], np.nan)
        work["variance_pct"] = variance.round(2)
        work["status"] = work["variance_pct"].map(self._variance_status)
        work["direction"] = work["variance_pct"].map(direction_from)

        id_cols = [c for c in df.columns if c not in (actual_col, target_col) and coerce_numeric(df[c]).notna().sum() == 0]
        out_cols = id_cols + [target_col, actual_col, "variance_pct", "status", "direction"]
        out = work[[c for c in out_cols if c in work.columns]]

        currency_cols = [c for c in (actual_col, target_col) if is_currency_column(c)]
        columns, rows, display_rows = rows_payload(out, currency_cols)

        valid = out["variance_pct"].dropna()
        directional_summary = {
            "actual_column": actual_col,
            "target_column": target_col,
            "overperformers": int((out["status"] == "overperformer").sum()),
            "underperformers": int((out["status"] == "underperformer").sum()),
            "on_track": int((out["status"] == "on_track").sum()),
            "average_variance_pct": round(float(valid.mean()), 2) if len(valid) else None,
        }
        return self._result(
            operation, columns, rows, display_rows, directional_summary, warnings,
            currency_columns=currency_cols,
        )

    @staticmethod
    def _variance_status(value: Any) -> str:
        number = to_jsonable(value)
        if not isinstance(number, (int, float)):
            return "unknown"
        if number > 10:
            return "overperformer"
        if number < -10:
            return "underperformer"
        return "on_track"

    @staticmethod
    def _find_named(df: pd.DataFrame, keywords: list[str]) -> str | None:
        for column in df.columns:
            lowered = str(column).lower()
            if any(keyword in lowered for keyword in keywords):
                return column
        return None
