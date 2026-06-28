"""Scoring operations: weighted performance score and KMeans clustering."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from schemas.cerebras_schema import Operation

from .common import coerce_numeric, is_currency_column, numeric_columns, rows_payload, to_jsonable


class ScoringModule:
    def execute(self, operation: Operation, df: pd.DataFrame) -> dict[str, Any]:
        if operation.operation_type == "cluster":
            return self._cluster(operation, df)
        return self._score(operation, df)

    def _result(self, operation, columns, rows, display_rows, warnings=None, **extra):
        result = {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type,
            "label": operation.output_label,
            "columns": columns,
            "rows": rows,
            "display_rows": display_rows,
            "warnings": warnings or [],
        }
        result.update(extra)
        return result

    # -- score --------------------------------------------------------------

    def _score(self, operation, df):
        warnings: list[str] = []
        if df.empty:
            return self._result(operation, [], [], [], warnings=["Empty dataframe — nothing to score."])

        params = operation.parameters or {}
        numeric = numeric_columns(df)
        requested = [c for c in operation.target_columns if c in numeric]
        score_cols = requested or numeric
        if not score_cols:
            return self._result(operation, [], [], [], warnings=["No numeric columns to score."])

        weights_param = params.get("weights") or {}
        weights = {c: float(weights_param.get(c, 1.0)) for c in score_cols}
        weight_total = sum(weights.values()) or 1.0

        normalized = pd.DataFrame(index=df.index)
        for column in score_cols:
            series = coerce_numeric(df[column])
            col_min, col_max = series.min(), series.max()
            if pd.isna(col_min) or col_max == col_min:
                # Constant or all-null column contributes a neutral 50.
                normalized[column] = 50.0
                if col_max == col_min and not pd.isna(col_min):
                    warnings.append(f"Column '{column}' is constant — scored as neutral (50).")
            else:
                normalized[column] = (series - col_min) / (col_max - col_min) * 100.0

        score = sum(normalized[c].fillna(50.0) * weights[c] for c in score_cols) / weight_total

        out = df.copy()
        out["Score"] = score.round(2)
        out["Tier"] = score.map(self._tier)
        out = out.sort_values("Score", ascending=False).reset_index(drop=True)

        currency_cols = [c for c in out.columns if is_currency_column(c)]
        columns, rows, display_rows = rows_payload(out, currency_cols)
        summary = {
            "scored_columns": score_cols,
            "weights": {c: weights[c] for c in score_cols},
            "method": "min-max normalisation to 0-100, weighted average",
            "tiers": {tier: int((out["Tier"] == tier).sum()) for tier in ("Top", "Good", "Average", "Poor")},
        }
        return self._result(operation, columns, rows, display_rows, warnings, summary_stats=summary, currency_columns=currency_cols)

    @staticmethod
    def _tier(score: Any) -> str:
        number = to_jsonable(score)
        if not isinstance(number, (int, float)):
            return "Poor"
        if number >= 80:
            return "Top"
        if number >= 60:
            return "Good"
        if number >= 40:
            return "Average"
        return "Poor"

    # -- cluster ------------------------------------------------------------

    def _cluster(self, operation, df):
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        warnings: list[str] = []
        if len(df) < 2:
            return self._result(operation, [], [], [], warnings=["Need at least 2 rows to cluster."])

        numeric = numeric_columns(df)
        if not numeric:
            return self._result(operation, [], [], [], warnings=["No numeric columns to cluster on."])

        params = operation.parameters or {}
        requested_k = params.get("n_clusters", params.get("k", 3))
        try:
            n_clusters = int(requested_k)
        except (TypeError, ValueError):
            n_clusters = 3
        n_clusters = max(1, min(n_clusters, len(df)))
        if n_clusters < (int(requested_k) if str(requested_k).isdigit() else n_clusters):
            warnings.append(f"Reduced clusters to {n_clusters} (cannot exceed row count).")

        features = pd.DataFrame({c: coerce_numeric(df[c]) for c in numeric})
        features = features.fillna(features.mean(numeric_only=True))
        features = features.fillna(0.0)

        scaled = StandardScaler().fit_transform(features)
        model = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
        labels = model.fit_predict(scaled)

        out = df.copy()
        out["Cluster"] = labels

        cluster_summary = []
        for cluster_id in sorted(set(int(label) for label in labels)):
            mask = labels == cluster_id
            means = {column: to_jsonable(round(float(features[column][mask].mean()), 2)) for column in numeric}
            cluster_summary.append({"cluster": cluster_id, "size": int(mask.sum()), "mean_values": means})

        currency_cols = [c for c in out.columns if is_currency_column(c)]
        columns, rows, display_rows = rows_payload(out, currency_cols)
        return self._result(
            operation, columns, rows, display_rows, warnings,
            cluster_summary=cluster_summary, currency_columns=currency_cols,
            summary_stats={"n_clusters": n_clusters, "features": numeric},
        )
