from __future__ import annotations

import math
from typing import Any

import pandas as pd


class DataProfiler:
    """Profile workbook sheets and build an intelligence brief for the frontend and Cerebras."""

    def profile(self, df: pd.DataFrame, sheet_name: str) -> dict[str, Any]:
        normalized_df = df.copy()
        if normalized_df.empty:
            return {
                "sheet_name": sheet_name,
                "row_count": 0,
                "columns": {},
                "join_key_candidates": [],
                "is_time_series": False,
                "nigerian_context_flags": [],
            }

        normalized_df = normalized_df.applymap(self._clean_scalar)
        column_profiles: dict[str, dict[str, Any]] = {}
        for column in normalized_df.columns:
            series = normalized_df[column]
            non_null = series.dropna()
            unique_count = int(non_null.nunique(dropna=True))
            null_count = int(series.isna().sum())
            null_percentage = round((null_count / len(series)) * 100, 2) if len(series) else 0.0
            infer_type = self._infer_type(series, column)
            profile = {
                "name": column,
                "null_count": null_count,
                "null_percentage": null_percentage,
                "unique_count": unique_count,
                "unique_ratio": round(unique_count / len(non_null), 4) if len(non_null) else 0.0,
                "min": self._safe_stat(series, "min"),
                "max": self._safe_stat(series, "max"),
                "mean": self._safe_stat(series, "mean"),
                "most_frequent_value": self._most_frequent_value(series),
                "inferred_type": infer_type,
            }
            column_profiles[column] = profile

        join_key_candidates = [column for column in normalized_df.columns if self._looks_like_join_key(column)]
        is_time_series = self._looks_like_time_series(normalized_df)
        nigerian_context_flags = [flag for flag in self._detect_nigerian_context(normalized_df.columns)]

        return {
            "sheet_name": sheet_name,
            "row_count": int(len(normalized_df)),
            "columns": column_profiles,
            "join_key_candidates": join_key_candidates,
            "is_time_series": is_time_series,
            "nigerian_context_flags": nigerian_context_flags,
        }

    def generate_intelligence_brief(self, all_sheet_profiles: dict[str, dict[str, Any]], filename: str) -> dict[str, Any]:
        total_rows = sum(profile.get("row_count", 0) for profile in all_sheet_profiles.values())
        sheets: list[dict[str, Any]] = []
        join_counts: dict[str, int] = {}
        flags: set[str] = set()

        for sheet_name, profile in all_sheet_profiles.items():
            column_summary = []
            for column_name, column_profile in profile.get("columns", {}).items():
                column_summary.append(
                    {
                        "name": column_name,
                        "type": column_profile.get("inferred_type", "text"),
                        "null_pct": column_profile.get("null_percentage", 0.0),
                        "unique_ratio": column_profile.get("unique_ratio", 0.0),
                        "sample_values": self._sample_values(column_profile),
                    }
                )
            sheets.append(
                {
                    "name": sheet_name,
                    "row_count": profile.get("row_count", 0),
                    "is_time_series": profile.get("is_time_series", False),
                    "column_summary": column_summary,
                }
            )
            for key in profile.get("join_key_candidates", []):
                join_counts[key] = join_counts.get(key, 0) + 1
            flags.update(profile.get("nigerian_context_flags", []))

        potential_join_keys = [key for key, count in join_counts.items() if count > 1]
        nigerian_context_flags = sorted(flags)
        detected = bool(nigerian_context_flags)
        suggested_template = self._suggest_template(nigerian_context_flags)
        suggested_operations = self._suggest_operations(sheets, potential_join_keys)

        return {
            "filename": filename,
            "total_sheets": len(sheets),
            "total_rows": total_rows,
            "sheets": sheets,
            "potential_join_keys": potential_join_keys,
            "nigerian_context": {
                "detected": detected,
                "flags": nigerian_context_flags,
                "suggested_template": suggested_template,
            },
            "suggested_operations": suggested_operations,
        }

    def _infer_type(self, series: pd.Series, column_name: str) -> str:
        values = series.dropna()
        if values.empty:
            return "text"

        if values.dtype == bool or values.apply(lambda v: isinstance(v, bool)).all():
            return "boolean"

        numeric_values = [self._coerce_numeric(value) for value in values if self._coerce_numeric(value) is not None]
        if numeric_values:
            if self._looks_percentage(values) or "%" in str(column_name).lower():
                return "percentage"
            if self._looks_currency(values, numeric_values):
                return "currency"
            if self._looks_integer(numeric_values):
                return "integer"
            if self._looks_float(numeric_values):
                return "float"

        if self._looks_date(values):
            return "date"
        if self._looks_id(values):
            return "id"
        return "text"

    def _looks_like_join_key(self, column_name: str) -> bool:
        lower = column_name.lower()
        keywords = ["id", "code", "branch", "lga", "state", "zone", "fso", "dsa", "staff", "customer", "product"]
        return any(keyword in lower for keyword in keywords)

    def _looks_like_time_series(self, df: pd.DataFrame) -> bool:
        if df.empty:
            return False
        date_columns = [col for col in df.columns if self._infer_type(df[col], col) == "date"]
        if not date_columns:
            return False
        for col in date_columns:
            values = df[col].dropna()
            if values.nunique() >= 3:
                return True
        return False

    def _detect_nigerian_context(self, columns: list[str]) -> list[str]:
        flags: list[str] = []
        lowered = [col.lower() for col in columns]
        for keyword in ["branch", "zone", "lga", "state", "fso", "dsa", "pencom", "nhf", "naira", "ngn"]:
            if any(keyword in col for col in lowered):
                flags.append(keyword)
        return flags

    def _suggest_template(self, flags: list[str]) -> str:
        if any(flag in {"branch", "lga", "naira", "ngn"} for flag in flags):
            return "banking"
        if any(flag in {"sales", "customer", "revenue"} for flag in flags):
            return "sales"
        if any(flag in {"staff", "employee", "hr"} for flag in flags):
            return "hr"
        return "general"

    def _suggest_operations(self, sheets: list[dict[str, Any]], potential_join_keys: list[str]) -> list[str]:
        operations: list[str] = []
        if sheets:
            operations.append("Profile workbook structure and missing values")
        if potential_join_keys:
            operations.append("Join sheets on shared identifiers")
        if any(sheet.get("is_time_series") for sheet in sheets):
            operations.append("Trend analysis across time-based columns")
        operations.append("Generate a Nigerian-market executive summary")
        return operations

    def _sample_values(self, column_profile: dict[str, Any]) -> list[Any]:
        values = column_profile.get("sample_values", [])
        return values[:3]

    def _clean_scalar(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                return None
            return value
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    def _safe_stat(self, series: pd.Series, stat: str) -> Any:
        numeric_series = pd.to_numeric(series, errors="coerce")
        if numeric_series.empty:
            return None
        if stat == "min":
            return float(numeric_series.min()) if not numeric_series.dropna().empty else None
        if stat == "max":
            return float(numeric_series.max()) if not numeric_series.dropna().empty else None
        if stat == "mean":
            return float(numeric_series.mean()) if not numeric_series.dropna().empty else None
        return None

    def _most_frequent_value(self, series: pd.Series) -> Any:
        non_null = series.dropna()
        if non_null.empty:
            return None
        return non_null.mode().iloc[0] if not non_null.mode().empty else None

    def _coerce_numeric(self, value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip().replace(",", "").replace("₦", "").replace("$", "").replace("NGN", "").replace("ngn", "").replace("%", "")
            try:
                return float(text)
            except ValueError:
                return None
        return None

    def _looks_currency(self, values: pd.Series, numeric_values: list[float]) -> bool:
        if not numeric_values:
            return False
        if any(isinstance(v, str) and ("₦" in v or "NGN" in v.lower()) for v in values):
            return True
        return any(value > 1000 and value.is_integer() for value in numeric_values)

    def _looks_percentage(self, values: pd.Series) -> bool:
        text_values = [str(v).lower() for v in values if isinstance(v, str)]
        if any("%" in value for value in text_values):
            return True
        numeric_values = [self._coerce_numeric(v) for v in values if self._coerce_numeric(v) is not None]
        return bool(numeric_values) and all(0 <= value <= 100 for value in numeric_values)

    def _looks_integer(self, numeric_values: list[float]) -> bool:
        return bool(numeric_values) and all(value.is_integer() for value in numeric_values)

    def _looks_float(self, numeric_values: list[float]) -> bool:
        return bool(numeric_values)

    def _looks_date(self, values: pd.Series) -> bool:
        cleaned = [str(v).strip() for v in values if str(v).strip()]
        if len(cleaned) < 3:
            return False
        try:
            parsed = pd.to_datetime(cleaned, errors="coerce")
        except Exception:
            return False
        return parsed.notna().sum() / len(cleaned) >= 0.8

    def _looks_id(self, values: pd.Series) -> bool:
        if len(values) < 3:
            return False
        unique_ratio = values.nunique(dropna=True) / len(values)
        if unique_ratio <= 0.95:
            return False
        alphanumeric = [str(v) for v in values.dropna() if any(char.isdigit() for char in str(v)) and any(char.isalpha() for char in str(v))]
        return len(alphanumeric) >= 2
