"""Data sheet — the cleaned tabular result with formats, filters and conditional rules."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
from openpyxl.formatting.rule import CellIsRule
from openpyxl.utils import get_column_letter

from . import styles as S

_RULE_OPS = {
    "<": "lessThan", "<=": "lessThanOrEqual", ">": "greaterThan",
    ">=": "greaterThanOrEqual", "==": "equal", "=": "equal", "!=": "notEqual",
}


class DataSheet:
    def build(self, ws, data_sheet: dict[str, Any]) -> None:
        S.hide_gridlines(ws)
        ws.sheet_properties.tabColor = S.EMERALD

        columns = [S.column_name(c) for c in data_sheet.get("columns", [])]
        rows = self._normalise_rows(data_sheet.get("rows", []), columns)
        if not columns:
            S.style_cell(ws["A1"], value="No data available.", font_=S.font(11, italic=True, color=S.GREY_TEXT))
            return

        col_types = {
            col: S.detect_type(col, [row[idx] for row in rows]) for idx, col in enumerate(columns)
        }

        # Header row
        header_border = S.box(S.BLUE_ELECTRIC, "thin")
        for idx, col in enumerate(columns, start=1):
            S.style_cell(ws.cell(row=1, column=idx), value=col, font_=S.font(11, bold=True, color=S.WHITE),
                         fill_=S.fill(S.BLUE_ELECTRIC), align=S.CENTER, border=header_border)
        ws.freeze_panes = "A2"

        last_col_letter = get_column_letter(len(columns))
        last_row = len(rows) + 1
        ws.auto_filter.ref = f"A1:{last_col_letter}{max(last_row, 1)}"

        # Data rows
        for r_index, row in enumerate(rows, start=2):
            bg = S.NAVY_LIGHT if r_index % 2 == 0 else S.NAVY
            for c_index, col in enumerate(columns, start=1):
                value = row[c_index - 1]
                cell = ws.cell(row=r_index, column=c_index)
                self._write_value(cell, value, col_types[col], bg)

        self._autofit(ws, columns, rows)
        self._apply_conditional_formatting(ws, columns, data_sheet.get("conditional_formatting", []), last_row)
        S.paint_canvas(ws, max_row=last_row, max_col=len(columns), color=S.NAVY)

    # -- helpers ------------------------------------------------------------

    def _normalise_rows(self, rows: list[Any], columns: list[str]) -> list[list[Any]]:
        normalised = []
        for row in rows:
            if isinstance(row, dict):
                normalised.append([row.get(col) for col in columns])
            elif isinstance(row, (list, tuple)):
                normalised.append(list(row))
            else:
                normalised.append([row])
        return normalised

    def _write_value(self, cell, value, col_type, bg):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            S.style_cell(cell, value="-", font_=S.font(10, color=S.GREY_TEXT), fill_=S.fill(bg), align=S.CENTER)
            return

        if col_type == "currency":
            cell.value = self._num(value)
            cell.number_format = S.CURRENCY_FORMAT
            align = S.RIGHT
        elif col_type == "percentage":
            cell.value = self._num(value)
            cell.number_format = S.PERCENT_FORMAT
            align = S.RIGHT
        elif col_type == "date":
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.notna(parsed):
                cell.value = parsed.to_pydatetime()
                cell.number_format = S.DATE_FORMAT
            else:
                cell.value = value
            align = S.LEFT
        elif col_type == "number":
            cell.value = self._num(value)
            align = S.RIGHT
        else:
            cell.value = value
            align = S.LEFT

        cell.font = S.font(10, color=S.WHITE)
        cell.fill = S.fill(bg)
        cell.alignment = align

    @staticmethod
    def _num(value):
        if isinstance(value, (int, float)):
            return value
        try:
            return float(str(value).replace(",", "").replace("₦", "").replace("%", "").strip())
        except (TypeError, ValueError):
            return value

    def _autofit(self, ws, columns, rows):
        for idx, col in enumerate(columns):
            max_len = len(str(col))
            for row in rows[:100]:
                max_len = max(max_len, len(str(row[idx])) if row[idx] is not None else 1)
            width = max(10, min(40, max_len * 1.2))
            ws.column_dimensions[get_column_letter(idx + 1)].width = width

    def _apply_conditional_formatting(self, ws, columns, rules, last_row):
        if last_row < 2:
            return
        index_by_name = {name: i for i, name in enumerate(columns)}
        for rule in rules or []:
            column = rule.get("column")
            if column not in index_by_name:
                continue
            letter = get_column_letter(index_by_name[column] + 1)
            cell_range = f"{letter}2:{letter}{last_row}"
            operator, formula = self._parse_rule(rule.get("rule", ""))
            if operator is None:
                continue
            color = (rule.get("color") or S.RED_ALERT).lstrip("#")
            ws.conditional_formatting.add(
                cell_range,
                CellIsRule(operator=operator, formula=[formula], fill=S.fill(color), font=S.font(10, bold=True, color=S.WHITE)),
            )

    @staticmethod
    def _parse_rule(expression: str):
        match = re.search(r"(<=|>=|==|!=|=|<|>)\s*(-?\d+(?:\.\d+)?)", str(expression))
        if not match:
            return None, None
        return _RULE_OPS.get(match.group(1)), match.group(2)
