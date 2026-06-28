"""Aggregation operations: group_sum, group_avg, rank, filter."""

from __future__ import annotations

from typing import Any

import pandas as pd

from schemas.cerebras_schema import Operation

from .common import coerce_numeric, is_currency_column, rows_payload, to_jsonable


class AggregationModule:
    def execute(self, operation: Operation, df: pd.DataFrame) -> dict[str, Any]:
        op_type = operation.operation_type
        if op_type == "group_sum":
            return self._group(operation, df, "sum", "(sum of values per group)")
        if op_type == "group_avg":
            return self._group(operation, df, "mean", "(mean of values per group)")
        if op_type == "rank":
            return self._rank(operation, df)
        if op_type == "filter":
            return self._filter(operation, df)
        return self._result(operation, [], [], [], warnings=[f"Unsupported aggregation type: {op_type}"])

    # -- builders -----------------------------------------------------------

    def _result(self, operation, columns, rows, display_rows, summary_stats=None, warnings=None, **extra):
        result = {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type,
            "label": operation.output_label,
            "columns": columns,
            "rows": rows,
            "display_rows": display_rows,
            "summary_stats": summary_stats or {},
            "warnings": warnings or [],
        }
        result.update(extra)
        return result

    # -- group_sum / group_avg ---------------------------------------------

    def _group(self, operation, df, how, method_note):
        warnings: list[str] = []
        if df.empty:
            return self._result(operation, [], [], [], warnings=["Empty dataframe — nothing to aggregate."])

        group_cols = [c for c in operation.group_by if c in df.columns]
        missing_groups = [c for c in operation.group_by if c not in df.columns]
        if missing_groups:
            warnings.append(f"Group column(s) not found, ignored: {missing_groups}")

        work = df.copy()
        value_cols: list[str] = []
        for column in operation.target_columns:
            if column not in df.columns:
                warnings.append(f"Target column not found: {column}")
                continue
            coerced = coerce_numeric(df[column])
            if coerced.notna().sum() == 0:
                warnings.append(f"Column '{column}' has no numeric data — skipped.")
                continue
            work[column] = coerced
            value_cols.append(column)

        if not value_cols:
            return self._result(operation, group_cols, [], [], warnings=warnings + ["No numeric target columns to aggregate."])

        if group_cols:
            grouped = work.groupby(group_cols, dropna=False)[value_cols].agg(how).reset_index()
        else:
            aggregated = work[value_cols].agg(how)
            grouped = pd.DataFrame([aggregated.to_dict()])

        grouped = grouped.sort_values(value_cols[0], ascending=False).reset_index(drop=True)
        for column in value_cols:
            grouped[column] = grouped[column].round(2)

        currency_cols = [c for c in grouped.columns if is_currency_column(c)]
        columns, rows, display_rows = rows_payload(grouped, currency_cols)

        summary_stats = {"groups": int(len(grouped)), "aggregation": how, "method": method_note}
        for column in value_cols:
            summary_stats[f"total_{column}"] = to_jsonable(coerce_numeric(df[column]).sum())
        return self._result(
            operation, columns, rows, display_rows, summary_stats, warnings,
            currency_columns=currency_cols, value_columns=value_cols,
        )

    # -- rank ---------------------------------------------------------------

    def _rank(self, operation, df):
        warnings: list[str] = []
        if df.empty:
            return self._result(operation, [], [], [], warnings=["Empty dataframe — nothing to rank."])

        params = operation.parameters or {}
        by = params.get("by") or (operation.target_columns[0] if operation.target_columns else None)
        if by not in df.columns:
            numeric = [c for c in df.columns if coerce_numeric(df[c]).notna().sum() > 0]
            if not numeric:
                return self._result(operation, [], [], [], warnings=warnings + ["No numeric column available to rank by."])
            warnings.append(f"Rank column '{by}' not usable; ranking by '{numeric[0]}'.")
            by = numeric[0]

        work = df.copy()
        sort_values = coerce_numeric(df[by])
        if sort_values.notna().sum() == 0:
            return self._result(operation, [], [], [], warnings=warnings + [f"Column '{by}' has no numeric data."])
        work["__sort__"] = sort_values

        order = str(params.get("order", "desc")).lower()
        ascending = order.startswith("asc")
        work = work.sort_values("__sort__", ascending=ascending, na_position="last").reset_index(drop=True)
        work.insert(0, "Rank", range(1, len(work) + 1))

        top_n = params.get("top_n")
        bottom_n = params.get("bottom_n")
        if top_n:
            work = work.head(int(top_n))
        elif bottom_n:
            work = work.tail(int(bottom_n))
        work = work.drop(columns="__sort__")

        currency_cols = [c for c in work.columns if is_currency_column(c)]
        columns, rows, display_rows = rows_payload(work, currency_cols)
        summary_stats = {
            "ranked_by": by,
            "order": "ascending" if ascending else "descending",
            "rows_returned": int(len(work)),
        }
        return self._result(
            operation, columns, rows, display_rows, summary_stats, warnings,
            currency_columns=currency_cols, ranked_by=by,
        )

    # -- filter -------------------------------------------------------------

    def _filter(self, operation, df):
        warnings: list[str] = []
        if df.empty:
            return self._result(operation, [], [], [], warnings=["Empty dataframe — nothing to filter."])

        params = operation.parameters or {}
        work = df.copy()

        condition = params.get("condition") or params.get("where")
        if condition:
            try:
                work = work.query(condition)
            except Exception as exc:  # noqa: BLE001 — user/LLM condition may be malformed
                warnings.append(f"Could not apply condition '{condition}': {exc}")

        threshold = params.get("threshold")
        if threshold is not None:
            column = params.get("column") or (operation.target_columns[0] if operation.target_columns else None)
            operator = str(params.get("operator", ">"))
            if column in work.columns:
                series = coerce_numeric(work[column])
                try:
                    work = work[self._compare(series, operator, float(threshold))]
                except (TypeError, ValueError):
                    warnings.append(f"Invalid threshold '{threshold}' for column '{column}'.")
            else:
                warnings.append(f"Threshold column '{column}' not found.")

        sort_col = operation.target_columns[0] if operation.target_columns else None
        top_n = params.get("top_n")
        bottom_n = params.get("bottom_n")
        if (top_n or bottom_n) and sort_col in work.columns:
            work = work.assign(__s__=coerce_numeric(work[sort_col]))
            work = work.sort_values("__s__", ascending=bool(bottom_n), na_position="last").drop(columns="__s__")
            work = work.head(int(top_n)) if top_n else work.tail(int(bottom_n))

        if work.empty:
            warnings.append("No rows matched the filter.")

        currency_cols = [c for c in work.columns if is_currency_column(c)]
        columns, rows, display_rows = rows_payload(work, currency_cols)
        summary_stats = {"rows_returned": int(len(work)), "rows_in": int(len(df))}
        return self._result(
            operation, columns, rows, display_rows, summary_stats, warnings,
            currency_columns=currency_cols,
        )

    @staticmethod
    def _compare(series: pd.Series, operator: str, value: float) -> pd.Series:
        ops = {
            ">": series > value,
            ">=": series >= value,
            "<": series < value,
            "<=": series <= value,
            "==": series == value,
            "!=": series != value,
        }
        return ops.get(operator, series > value).fillna(False)
