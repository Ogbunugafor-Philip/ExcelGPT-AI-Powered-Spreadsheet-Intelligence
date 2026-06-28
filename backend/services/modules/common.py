"""
Shared helpers for the computation modules.

Every module produces plain-Python, JSON-serialisable results: NaN/inf become
None, numpy scalars become Python scalars, and monetary columns get a Naira
display string alongside their raw numeric value.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

# Column-name hints that mark a value as Nigerian-Naira currency.
CURRENCY_KEYWORDS = (
    "ngn",
    "naira",
    "deposit",
    "loan",
    "amount",
    "balance",
    "revenue",
    "salary",
    "income",
    "cost",
    "price",
    "value",
    "fee",
    "asset",
    "turnover",
    "sales",
    "profit",
    "spend",
    "budget",
)


def is_currency_column(name: Any) -> bool:
    """Heuristically decide whether a column holds Naira amounts (by name)."""
    lowered = str(name).lower()
    if "ngn" in lowered or "naira" in lowered:
        return True
    return any(keyword in lowered for keyword in CURRENCY_KEYWORDS)


def _strip_numeric(value: Any) -> Any:
    """Strip currency/grouping symbols so a string like '₦1,200' parses to a number."""
    if isinstance(value, str):
        text = value.strip()
        for token in ("₦", ",", "NGN", "ngn", "%", "$"):
            text = text.replace(token, "")
        return text.strip()
    return value


def coerce_numeric(series: pd.Series) -> pd.Series:
    """Coerce a Series to floats, tolerating currency strings; non-numeric -> NaN."""
    return pd.to_numeric(series.map(_strip_numeric), errors="coerce")


def numeric_columns(df: pd.DataFrame, min_ratio: float = 0.8) -> list[str]:
    """Columns that are at least `min_ratio` numeric after coercion."""
    cols: list[str] = []
    for column in df.columns:
        coerced = coerce_numeric(df[column])
        if len(coerced) and coerced.notna().mean() >= min_ratio and coerced.notna().sum() > 0:
            cols.append(column)
    return cols


def all_null(series: pd.Series) -> bool:
    return series.isna().all()


def to_jsonable(obj: Any) -> Any:
    """Recursively convert numpy/pandas/NaN values into JSON-safe Python values."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {key: to_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(value) for value in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        number = float(obj)
        return number if math.isfinite(number) else None
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if obj is pd.NaT:
        return None
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def format_naira(value: Any, compact: bool = False) -> str:
    """Format a number as Naira. compact -> ₦4.21B; otherwise ₦1,234,567.00."""
    number = to_jsonable(value)
    if not isinstance(number, (int, float)):
        return "—"
    if compact:
        return "₦" + _compact(float(number))
    return f"₦{float(number):,.2f}"


def _compact(number: float) -> str:
    magnitude = abs(number)
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if magnitude >= divisor:
            return f"{number / divisor:.2f}{suffix}"
    return f"{number:,.2f}"


def format_pct(value: Any, signed: bool = False) -> str:
    number = to_jsonable(value)
    if not isinstance(number, (int, float)):
        return "—"
    sign = "+" if signed and number > 0 else ""
    return f"{sign}{number:.2f}%"


def direction_from(value: Any) -> str:
    """Map a growth/variance number to an up/down/neutral indicator."""
    number = to_jsonable(value)
    if not isinstance(number, (int, float)):
        return "neutral"
    if number > 0:
        return "up"
    if number < 0:
        return "down"
    return "neutral"


def rows_payload(df: pd.DataFrame, currency_cols: list[str] | None = None) -> tuple[list[str], list[list[Any]], list[list[Any]]]:
    """Return (columns, raw_rows, display_rows). Currency cols get Naira strings in display_rows."""
    currency_cols = set(currency_cols or [])
    columns = list(df.columns)
    raw_rows: list[list[Any]] = []
    display_rows: list[list[Any]] = []
    for _, row in df.iterrows():
        raw_row = [to_jsonable(row[col]) for col in columns]
        display_row = []
        for col, raw_value in zip(columns, raw_row):
            if col in currency_cols and isinstance(raw_value, (int, float)):
                display_row.append(format_naira(raw_value))
            else:
                display_row.append(raw_value)
        raw_rows.append(raw_row)
        display_rows.append(display_row)
    return columns, raw_rows, display_rows


def detect_date_column(df: pd.DataFrame, prefer: list[str] | None = None) -> str | None:
    """Find the most date-like column. Honour `prefer` (e.g. operation target columns) first."""
    candidates = list(prefer or []) + [c for c in df.columns if c not in (prefer or [])]
    best: tuple[float, str] | None = None
    for column in candidates:
        if column not in df.columns:
            continue
        series = df[column].dropna()
        if series.empty:
            continue
        name = str(column).lower()
        # Pure numeric columns are values, not dates — skip unless the name says otherwise.
        if coerce_numeric(series).notna().mean() > 0.9 and not any(
            token in name for token in ("date", "month", "period", "year", "day", "quarter", "time")
        ):
            continue
        parsed = pd.to_datetime(series, errors="coerce")
        ratio = parsed.notna().mean()
        if ratio >= 0.8:
            score = ratio + (0.5 if any(t in name for t in ("date", "month", "period", "year", "quarter")) else 0)
            if best is None or score > best[0]:
                best = (score, column)
    return best[1] if best else None
