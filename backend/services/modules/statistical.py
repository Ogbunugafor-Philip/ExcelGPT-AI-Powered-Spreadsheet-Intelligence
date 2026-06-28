"""Statistical operations: correlation, outlier detection (IQR), distribution shape."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from schemas.cerebras_schema import Operation

from .common import coerce_numeric, numeric_columns, to_jsonable


class StatisticalModule:
    def execute(self, operation: Operation, df: pd.DataFrame) -> dict[str, Any]:
        op_type = operation.operation_type
        if op_type == "correlation":
            return self._correlation(operation, df)
        if op_type == "outlier":
            return self._outlier(operation, df)
        if op_type == "distribution":
            return self._distribution(operation, df)
        return self._result(operation, op_type, {}, warnings=[f"Unsupported statistical type: {op_type}"])

    def _result(self, operation, result_type, data, warnings=None):
        return {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type,
            "label": operation.output_label,
            "result_type": result_type,
            "data": data,
            "warnings": warnings or [],
        }

    # -- correlation --------------------------------------------------------

    def _correlation(self, operation, df):
        warnings: list[str] = []
        if len(df) < 2:
            return self._result(operation, "correlation", {}, ["Need at least 2 rows for correlation."])

        # Only continuous-ish columns: numeric with more than 10 distinct values.
        cols = [c for c in numeric_columns(df) if coerce_numeric(df[c]).nunique(dropna=True) > 10]
        if len(cols) < 2:
            return self._result(
                operation, "correlation", {"columns": cols},
                ["Fewer than 2 numeric columns with >10 distinct values — correlation skipped."],
            )

        numeric_df = pd.DataFrame({c: coerce_numeric(df[c]) for c in cols})
        matrix = numeric_df.corr(method="pearson")
        rows = [[to_jsonable(round(matrix.loc[r, c], 4)) for c in cols] for r in cols]

        strong: list[dict[str, Any]] = []
        for i, col_a in enumerate(cols):
            for col_b in cols[i + 1:]:
                value = matrix.loc[col_a, col_b]
                if pd.isna(value):
                    continue
                if value > 0.7:
                    strong.append({"pair": [col_a, col_b], "correlation": round(float(value), 4), "type": "strong_positive"})
                elif value < -0.7:
                    strong.append({"pair": [col_a, col_b], "correlation": round(float(value), 4), "type": "strong_negative"})

        data = {"columns": cols, "matrix": rows, "strong_correlations": strong, "method": "pearson"}
        return self._result(operation, "correlation", data, warnings)

    # -- outlier (IQR) ------------------------------------------------------

    def _outlier(self, operation, df):
        warnings: list[str] = []
        cols = numeric_columns(df)
        if df.empty or not cols:
            return self._result(operation, "outlier", {"outliers": []}, ["No numeric columns for outlier detection."])

        outliers: list[dict[str, Any]] = []
        bounds_by_column: dict[str, Any] = {}
        for column in cols:
            series = coerce_numeric(df[column])
            if series.notna().sum() < 4:
                continue
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            low = q1 - 1.5 * iqr
            high = q3 + 1.5 * iqr
            bounds_by_column[column] = {"q1": to_jsonable(q1), "q3": to_jsonable(q3), "lower": to_jsonable(low), "upper": to_jsonable(high)}
            mask = ((series < low) | (series > high)).fillna(False)
            for idx in df.index[mask]:
                value = series.loc[idx]
                outliers.append({
                    "row_index": int(idx),
                    "column": column,
                    "value": to_jsonable(value),
                    "direction": "high" if value > high else "low",
                })

        data = {"outliers": outliers, "bounds_by_column": bounds_by_column, "outlier_count": len(outliers)}
        return self._result(operation, "outlier", data, warnings)

    # -- distribution -------------------------------------------------------

    def _distribution(self, operation, df):
        warnings: list[str] = []
        cols = numeric_columns(df)
        if not cols:
            return self._result(operation, "distribution", {"distributions": []}, ["No numeric columns to describe."])

        distributions: list[dict[str, Any]] = []
        for column in cols:
            series = coerce_numeric(df[column]).dropna()
            if len(series) < 3:
                warnings.append(f"Column '{column}' has too few values for distribution stats.")
                continue
            skewness = float(stats.skew(series))
            kurtosis = float(stats.kurtosis(series))  # excess kurtosis (normal -> 0)
            distributions.append({
                "column": column,
                "mean": to_jsonable(round(series.mean(), 4)),
                "median": to_jsonable(round(series.median(), 4)),
                "std": to_jsonable(round(series.std(ddof=1), 4)) if len(series) > 1 else 0.0,
                "skewness": round(skewness, 4),
                "kurtosis": round(kurtosis, 4),
                "shape": self._classify_shape(skewness, kurtosis),
            })

        return self._result(operation, "distribution", {"distributions": distributions}, warnings)

    @staticmethod
    def _classify_shape(skewness: float, kurtosis: float) -> str:
        if abs(skewness) < 0.5:
            # Strongly negative excess kurtosis with low skew suggests two modes.
            if kurtosis < -1.0:
                return "bimodal"
            return "normal"
        return "right_skewed" if skewness > 0 else "left_skewed"
