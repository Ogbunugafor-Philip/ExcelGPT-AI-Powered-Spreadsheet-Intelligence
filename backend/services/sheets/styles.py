"""
Shared styling primitives for the Excel sheet builders.

Centralises the ExcelGPT colour system and the small openpyxl helpers (fills,
fonts, borders, alignment, column/canvas helpers, column-type detection) so the
five sheet builders stay focused on layout.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# -- ExcelGPT colour system (aRGB hex, no leading '#') ----------------------
NAVY = "0A0F1E"
NAVY_LIGHT = "111827"
BLUE_ELECTRIC = "2563EB"
EMERALD = "10B981"
AMBER = "F59E0B"
RED_ALERT = "EF4444"
GOLD = "D97706"
WHITE = "FFFFFF"
GREY_LIGHT = "F3F4F6"
GREY_TEXT = "6B7280"
TEXT_PRIMARY = "F9FAFB"
BRONZE = "B45309"          # rank-3 medal
GREEN_TINT = "064E3B"      # positive growth cell tint (dark theme)
RED_TINT = "7F1D1D"        # negative growth cell tint (dark theme)

DEFAULT_FONT = "Calibri"

DATE_KEYWORDS = ("date", "month", "period", "year", "day", "quarter", "time")
PCT_KEYWORDS = ("pct", "percent", "growth", "rate", "margin", "ratio", "%", "variance", "change")
CURRENCY_KEYWORDS = (
    "ngn", "naira", "deposit", "loan", "amount", "balance", "revenue", "salary",
    "income", "cost", "price", "value", "fee", "asset", "turnover", "sales", "profit", "spend", "budget",
)

CURRENCY_FORMAT = '"₦"#,##0.00'
PERCENT_FORMAT = '#,##0.00"%"'   # our percentages are stored as whole numbers (20.0 == 20%)
DATE_FORMAT = "DD-MMM-YYYY"


def fill(color: str) -> PatternFill:
    return PatternFill(start_color=color, end_color=color, fill_type="solid")


def font(size: int = 11, bold: bool = False, italic: bool = False, color: str = TEXT_PRIMARY) -> Font:
    return Font(name=DEFAULT_FONT, size=size, bold=bold, italic=italic, color=color)


def side(color: str = BLUE_ELECTRIC, style: str = "thin") -> Side:
    return Side(style=style, color=color)


def box(color: str = BLUE_ELECTRIC, style: str = "thin") -> Border:
    edge = side(color, style)
    return Border(left=edge, right=edge, top=edge, bottom=edge)


CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")


def style_cell(cell, *, value=None, font_=None, fill_=None, align=None, border=None, number_format=None):
    """Apply a bundle of styles to a single cell in one call."""
    if value is not None:
        cell.value = value
    if font_ is not None:
        cell.font = font_
    if fill_ is not None:
        cell.fill = fill_
    if align is not None:
        cell.alignment = align
    if border is not None:
        cell.border = border
    if number_format is not None:
        cell.number_format = number_format
    return cell


def set_column_widths(ws, width: float, first: int = 1, last: int = 8) -> None:
    for index in range(first, last + 1):
        ws.column_dimensions[get_column_letter(index)].width = width


def paint_canvas(ws, max_row: int, max_col: int, color: str = NAVY) -> None:
    """Give the sheet a dark canvas: fill every still-unfilled cell in the box."""
    for row in range(1, max_row + 1):
        for col in range(1, max_col + 1):
            cell = ws.cell(row=row, column=col)
            if cell.fill is None or cell.fill.patternType is None:
                cell.fill = fill(color)


def hide_gridlines(ws) -> None:
    ws.sheet_view.showGridLines = False


# -- column-name / value type detection -------------------------------------

def column_name(column: Any) -> str:
    """Columns may be plain strings or {'name': ..., 'type': ...} dicts."""
    if isinstance(column, dict):
        return str(column.get("name", ""))
    return str(column)


def detect_type(name: str, values: list[Any]) -> str:
    """Classify a column as currency | percentage | date | number | text."""
    lowered = str(name).lower()
    if "ngn" in lowered or "naira" in lowered or any(k in lowered for k in CURRENCY_KEYWORDS):
        # percentage names win over currency when both could match (e.g. 'growth_rate').
        if any(k in lowered for k in PCT_KEYWORDS):
            return "percentage"
        return "currency"
    if any(k in lowered for k in PCT_KEYWORDS):
        return "percentage"
    if any(k in lowered for k in DATE_KEYWORDS):
        return "date"

    non_null = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_null:
        return "text"
    numeric = sum(1 for v in non_null if _is_number(v))
    if numeric / len(non_null) >= 0.8:
        return "number"
    if _date_ratio(non_null) >= 0.8:
        return "date"
    return "text"


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.replace(",", "").replace("₦", "").replace("%", "").strip())
            return True
        except ValueError:
            return False
    return False


def _date_ratio(values: list[Any]) -> float:
    try:
        parsed = pd.to_datetime([str(v) for v in values], errors="coerce")
    except Exception:  # noqa: BLE001
        return 0.0
    return float(parsed.notna().mean())
