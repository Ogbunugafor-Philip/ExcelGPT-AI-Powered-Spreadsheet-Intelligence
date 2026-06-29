"""Growth operations: period-over-period growth_rate and target-vs-actual variance."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from schemas.cerebras_schema import Operation

from statistics import mean

from .common import (
    coerce_numeric,
    detect_date_column,
    direction_from,
    is_currency_column,
    rows_payload,
    to_jsonable,
)


def _pct(current, previous):
    """(current - previous) / previous * 100, guarding zero/None -> None."""
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    if previous == 0:
        return None
    return round((current - previous) / previous * 100.0, 2)


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

        # Wide-format detection: two or more numeric period columns (e.g. Jan..Jun)
        # spread across the COLUMNS rather than down a single date column. This is
        # the common "monthly trend" layout — pivot it into a month-over-month table.
        period_cols = [
            c for c in operation.target_columns
            if c in df.columns and coerce_numeric(df[c]).notna().sum() > 0
        ]
        if len(period_cols) >= 2:
            return self._wide_growth(operation, df, period_cols, warnings)

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

    # -- wide-format growth (Jan..Jun across columns) -----------------------

    def _wide_growth(self, operation, df, period_cols, warnings):
        group_col = next((c for c in operation.group_by if c in df.columns), None)
        if group_col is None:
            group_col = next(
                (c for c in df.columns
                 if c not in period_cols and coerce_numeric(df[c]).notna().sum() == 0),
                None,
            )
        label_key = group_col or "Group"
        numeric = {c: coerce_numeric(df[c]) for c in period_cols}
        step_labels = [f"{period_cols[i - 1]}→{period_cols[i]}" for i in range(1, len(period_cols))]

        value_rows: list[dict[str, Any]] = []   # wide values + total growth (Data sheet)
        step_rows: list[dict[str, Any]] = []     # month-over-month growth (Analysis sheet)
        long_cols = [label_key, "period", "Amount", "growth_pct", "direction"]
        long_rows: list[list[Any]] = []
        per_step: dict[str, list[float]] = {lbl: [] for lbl in step_labels}
        branch_totals: list[tuple[str, float | None]] = []
        max_value = 0.0

        for i in range(len(df)):
            label = str(df[group_col].iloc[i]) if group_col else f"Row {i + 1}"
            values = [to_jsonable(numeric[c].iloc[i]) for c in period_cols]
            max_value = max([max_value] + [abs(v) for v in values if isinstance(v, (int, float))])

            first, last = values[0], values[-1]
            total = _pct(last, first)
            branch_totals.append((label, total))

            vrow: dict[str, Any] = {label_key: label}
            for col, val in zip(period_cols, values):
                vrow[col] = val
            vrow["Total Growth %"] = total
            vrow["Direction"] = direction_from(total)
            vrow["direction"] = direction_from(total)
            value_rows.append(vrow)

            srow: dict[str, Any] = {label_key: label}
            for k in range(1, len(values)):
                step = _pct(values[k], values[k - 1])
                lbl = step_labels[k - 1]
                srow[lbl] = step
                if step is not None:
                    per_step[lbl].append(step)
                long_rows.append([label, period_cols[k], values[k], step, direction_from(step)])
            srow["direction"] = direction_from(total)
            step_rows.append(srow)

        all_steps = [g for vs in per_step.values() for g in vs]
        step_avgs = {lbl: round(mean(vs), 2) for lbl, vs in per_step.items() if vs}
        totals = [t for _, t in branch_totals if t is not None]
        best = max((bt for bt in branch_totals if bt[1] is not None), key=lambda x: x[1], default=(None, None))
        worst = min((bt for bt in branch_totals if bt[1] is not None), key=lambda x: x[1], default=(None, None))

        directional_summary = {
            "mode": "wide",
            "value_column": "",
            "group_column": group_col,
            "periods": period_cols,
            "step_labels": step_labels,
            "up": sum(1 for g in all_steps if g > 0),
            "down": sum(1 for g in all_steps if g < 0),
            "neutral": sum(1 for g in all_steps if g == 0),
            "average_growth_pct": round(mean(all_steps), 2) if all_steps else None,
            "highest_growth_month": max(step_avgs, key=step_avgs.get) if step_avgs else None,
            "highest_growth_value": max(step_avgs.values()) if step_avgs else None,
            "lowest_growth_month": min(step_avgs, key=step_avgs.get) if step_avgs else None,
            "lowest_growth_value": min(step_avgs.values()) if step_avgs else None,
            "total_growth_avg": round(mean(totals), 2) if totals else None,
            "best_branch": best[0],
            "best_branch_growth": best[1],
            "worst_branch": worst[0],
            "worst_branch_growth": worst[1],
            "positive_branches": sum(1 for _, t in branch_totals if t is not None and t > 0),
            "branch_count": len(branch_totals),
        }
        wide_growth = {
            "group_col": label_key,
            "periods": period_cols,
            "step_labels": step_labels,
            "value_rows": value_rows,
            "step_rows": step_rows,
            "is_currency": max_value > 100_000 or any(is_currency_column(c) for c in df.columns),
        }
        return self._result(
            operation, long_cols, long_rows, long_rows, directional_summary, warnings,
            wide_growth=wide_growth, currency_columns=[],
        )

    # -- variance -----------------------------------------------------------

    def _variance(self, operation, df):
        warnings: list[str] = []
        if df.empty:
            return self._result(operation, [], [], [], warnings=["Empty dataframe — nothing to compute."])

        params = operation.parameters or {}
        explicit_actual = params.get("actual") or params.get("actual_column") or self._find_named(df, ["actual", "achieved", "result"])
        target_col = params.get("target") or params.get("target_column") or self._find_named(df, ["target", "budget", "plan", "forecast", "goal"])

        # Wide-format variance: actual is the SUM of monthly columns vs a Target.
        period_cols = [
            c for c in operation.target_columns
            if c in df.columns and c != target_col and coerce_numeric(df[c]).notna().sum() > 0
        ]
        if explicit_actual is None and target_col in df.columns and len(period_cols) >= 2:
            return self._wide_variance(operation, df, period_cols, target_col, warnings)

        actual_col = explicit_actual
        if actual_col is None and operation.target_columns:
            actual_col = operation.target_columns[0]

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

    def _wide_variance(self, operation, df, period_cols, target_col, warnings):
        group_col = next((c for c in operation.group_by if c in df.columns), None)
        if group_col is None:
            group_col = next(
                (c for c in df.columns
                 if c not in period_cols and c != target_col and coerce_numeric(df[c]).notna().sum() == 0),
                None,
            )
        label_key = group_col or "Entity"

        target = coerce_numeric(df[target_col])
        actual = sum(coerce_numeric(df[c]) for c in period_cols)

        rows: list[dict[str, Any]] = []
        for i in range(len(df)):
            label = str(df[group_col].iloc[i]) if group_col else f"Row {i + 1}"
            tgt = to_jsonable(target.iloc[i])
            act = to_jsonable(actual.iloc[i])
            var_amount = round(act - tgt, 2) if isinstance(act, (int, float)) and isinstance(tgt, (int, float)) else None
            var_pct = _pct(act, tgt)
            rows.append({
                label_key: label,
                "Target (₦)": tgt,
                "Actual (₦)": act,
                "Variance (₦)": var_amount,
                "Variance (%)": var_pct,
                "Status": self._variance_status(var_pct),
                "direction": direction_from(var_pct),
            })

        columns = [label_key, "Target (₦)", "Actual (₦)", "Variance (₦)", "Variance (%)", "Status", "direction"]
        data_rows = [[r[c] for c in columns] for r in rows]
        valid = [r["Variance (%)"] for r in rows if r["Variance (%)"] is not None]
        directional_summary = {
            "mode": "wide",
            "actual_column": "Actual (₦)",
            "target_column": target_col,
            "overperformers": sum(1 for r in rows if r["Status"] == "overperformer"),
            "underperformers": sum(1 for r in rows if r["Status"] == "underperformer"),
            "on_track": sum(1 for r in rows if r["Status"] == "on_track"),
            "average_variance_pct": round(mean(valid), 2) if valid else None,
            "above_target": sum(1 for r in rows if isinstance(r["Variance (₦)"], (int, float)) and r["Variance (₦)"] > 0),
            "below_target": sum(1 for r in rows if isinstance(r["Variance (₦)"], (int, float)) and r["Variance (₦)"] < 0),
        }
        currency_cols = ["Target (₦)", "Actual (₦)", "Variance (₦)"]
        return self._result(
            operation, columns, data_rows, data_rows, directional_summary, warnings,
            currency_columns=currency_cols, variance_table=rows,
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
