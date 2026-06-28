from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from openpyxl import load_workbook


class ExcelReader:
    """Read workbook contents, profile sheet structure, and build preview payloads."""

    def read_file(self, file_path: str) -> dict[str, Any]:
        sheet_rows: list[dict[str, Any]] = []
        for sheet_name, df in self.read_sheets(file_path):
            preview_rows = self._build_preview_rows(df)
            sheet_rows.append(
                {
                    "name": sheet_name,
                    "columns": list(df.columns),
                    "rows": preview_rows,
                    "row_count": int(len(df)),
                }
            )
        return {"sheets": sheet_rows}

    def read_sheets(self, file_path: str) -> list[tuple[str, pd.DataFrame]]:
        file_path = str(file_path)
        engine = self._get_engine(file_path)
        excel_file = pd.ExcelFile(file_path, engine=engine)
        sheets: list[tuple[str, pd.DataFrame]] = []
        for sheet_name in excel_file.sheet_names:
            if self._should_use_large_chunking(file_path, sheet_name):
                dataframe = self.handle_large_file(file_path, sheet_name)
            else:
                dataframe = self._read_sheet_dataframe(file_path, sheet_name)
            sheets.append((sheet_name, dataframe))
        return sheets

    def detect_column_types(self, series: pd.Series) -> str:
        values = series.dropna()
        if values.empty:
            return "text"

        if values.dtype == bool or values.apply(lambda v: isinstance(v, (bool, np.bool_))).all():
            return "boolean"

        numeric_values = []
        for value in values:
            numeric = self._coerce_numeric(value)
            if numeric is not None:
                numeric_values.append(numeric)

        text_like = any(isinstance(v, str) and not self._coerce_numeric(v) for v in values)
        if len(numeric_values) / len(values) > 0.8:
            if any(isinstance(v, str) and ("₦" in v or "NGN" in v.lower()) for v in values):
                return "currency"
            if self._looks_currency(values, numeric_values):
                return "currency"
            if self._looks_percentage(values):
                return "percentage"
            if self._looks_integer(numeric_values):
                return "integer"
            if self._looks_float(numeric_values):
                return "float"

        if self._looks_date(values):
            return "date"

        if self._looks_id(values):
            return "id"

        if text_like and self._is_mixed(values):
            return "text"

        return "text"

    def handle_large_file(self, file_path: str, sheet_name: str) -> pd.DataFrame:
        # NOTE: pandas/openpyxl cannot stream .xlsx — read_excel has no chunksize
        # (that's read_csv only). So we read the sheet in a single pass; large-file
        # safety comes from downstream caps (preview rows, aggregation, virtualised
        # tables) rather than row chunking here.
        return self._read_sheet_dataframe(file_path, sheet_name)

    def _read_sheet_dataframe(self, file_path: str, sheet_name: str) -> pd.DataFrame:
        engine = self._get_engine(file_path)
        raw_df = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine, header=None)
        return self._prepare_dataframe(raw_df)

    def _prepare_dataframe(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        if raw_df is None or raw_df.empty:
            return pd.DataFrame()

        cleaned_df = raw_df.copy()
        cleaned_df = cleaned_df.dropna(how="all", axis=0).reset_index(drop=True)
        if cleaned_df.empty:
            return pd.DataFrame()
        cleaned_df = cleaned_df.dropna(how="all", axis=1)
        if cleaned_df.empty:
            return pd.DataFrame()

        first_row = cleaned_df.iloc[0].tolist()
        first_row_values = [self._clean_scalar(value) for value in first_row]
        if self._first_row_looks_like_data(first_row_values):
            columns = [f"Column_{idx + 1}" for idx in range(cleaned_df.shape[1])]
            dataframe = cleaned_df.copy()
            dataframe.columns = columns
            dataframe = dataframe.applymap(self._clean_scalar)
            return dataframe

        dataframe = cleaned_df.iloc[1:].copy() if len(cleaned_df) > 1 else pd.DataFrame()
        if dataframe.empty:
            dataframe = pd.DataFrame(columns=[self._sanitize_column_name(value) for value in first_row_values])
            return dataframe

        headers = [self._sanitize_column_name(value) for value in first_row_values]
        seen: dict[str, int] = {}
        normalized_headers: list[str] = []
        for header in headers:
            count = seen.get(header, 0)
            seen[header] = count + 1
            if count:
                normalized_headers.append(f"{header}_{count}")
            else:
                normalized_headers.append(header)
        dataframe.columns = normalized_headers
        dataframe = dataframe.applymap(self._clean_scalar)
        return dataframe

    def _build_preview_rows(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        if df.empty:
            return []
        preview = df.head(100).copy()
        preview = preview.applymap(self._clean_scalar)
        return preview.to_dict(orient="records")

    def _should_use_large_chunking(self, file_path: str, sheet_name: str) -> bool:
        try:
            sample = pd.read_excel(file_path, sheet_name=sheet_name, engine=self._get_engine(file_path), nrows=10001)
        except Exception:
            return False
        return len(sample) > 10000

    def _get_engine(self, file_path: str) -> str | None:
        suffix = Path(file_path).suffix.lower()
        if suffix == ".xlsx":
            return "openpyxl"
        if suffix == ".xls":
            return "xlrd"
        return None

    def _first_row_looks_like_data(self, values: list[Any]) -> bool:
        cleaned_values = [value for value in values if value is not None and str(value).strip() != ""]
        if not cleaned_values:
            return False
        numeric_count = 0
        for value in cleaned_values:
            if self._coerce_numeric(value) is not None:
                numeric_count += 1
        return numeric_count / len(cleaned_values) >= 0.8

    def _sanitize_column_name(self, value: Any) -> str:
        if value is None:
            return "Column"
        text = str(value).strip()
        if not text:
            return "Column"
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"\s+", "_", text).strip("_")
        if not text:
            text = "Column"
        return text

    def _clean_scalar(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (np.integer, int)):
            return int(value)
        if isinstance(value, (np.floating, float)):
            if not math.isfinite(float(value)):
                return None
            return float(value)
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    def _coerce_numeric(self, value: Any) -> float | None:
        if value is None or isinstance(value, (bool, np.bool_)):
            return None
        if isinstance(value, (int, float, np.integer, np.floating)):
            number = float(value)
            return number if math.isfinite(number) else None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            text = text.replace(",", "").replace("₦", "").replace("$", "")
            text = text.replace("NGN", "").replace("ngn", "")
            text = text.replace("%", "")
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
        if not numeric_values:
            return False
        return any(0 <= value <= 100 for value in numeric_values) and len(numeric_values) >= 2

    def _looks_integer(self, numeric_values: list[float]) -> bool:
        return bool(numeric_values) and all(value.is_integer() for value in numeric_values)

    def _looks_float(self, numeric_values: list[float]) -> bool:
        return bool(numeric_values)

    def _looks_date(self, values: pd.Series) -> bool:
        cleaned_values = [str(v).strip() for v in values if str(v).strip()]
        if len(cleaned_values) < 3:
            return False
        try:
            parsed = pd.to_datetime(cleaned_values, errors="coerce")
        except Exception:
            return False
        return parsed.notna().sum() / len(cleaned_values) >= 0.8

    def _looks_id(self, values: pd.Series) -> bool:
        if len(values) < 3:
            return False
        unique_ratio = values.nunique(dropna=True) / len(values)
        if unique_ratio <= 0.95:
            return False
        alphanumeric = [str(v) for v in values.dropna() if re.search(r"[A-Za-z]", str(v)) and re.search(r"\d", str(v))]
        return len(alphanumeric) >= 2

    def _is_mixed(self, values: pd.Series) -> bool:
        cleaned = [self._clean_scalar(v) for v in values.dropna()]
        if len(cleaned) < 2:
            return False
        first_type = type(cleaned[0]).__name__
        return any(type(v).__name__ != first_type for v in cleaned[1:])
