"""Analysis sheet — computed metrics, ranking table (with medals), growth table (with arrows)."""

from __future__ import annotations

from typing import Any

from openpyxl.utils import get_column_letter

from . import styles as S

MEDALS = {1: S.GOLD, 2: S.GREY_LIGHT, 3: S.AMBER}
MEDAL_TEXT = {1: S.NAVY, 2: S.NAVY, 3: S.NAVY}
ARROWS = {"up": ("↑", S.EMERALD), "down": ("↓", S.RED_ALERT), "neutral": ("→", S.AMBER)}


class AnalysisSheet:
    def build(self, ws, analysis: dict[str, Any]) -> None:
        S.hide_gridlines(ws)
        ws.sheet_properties.tabColor = S.GOLD
        S.set_column_widths(ws, 22, first=1, last=8)

        row = 1
        row = self._metrics(ws, analysis.get("metrics", []), row)
        row = self._rankings(ws, analysis.get("rankings", []), row + 1)
        row = self._growth(ws, analysis.get("growth_table", []), row + 1)

        ws.freeze_panes = "A2"
        S.paint_canvas(ws, max_row=max(row, 2), max_col=8, color=S.NAVY)

    def _section_header(self, ws, text, row, span=8):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
        S.style_cell(ws.cell(row=row, column=1), value=text,
                     font_=S.font(13, bold=True, color=S.BLUE_ELECTRIC), align=S.LEFT)
        return row + 1

    # -- metrics ------------------------------------------------------------

    def _metrics(self, ws, metrics, row):
        row = self._section_header(ws, "KEY METRICS", row)
        if not metrics:
            S.style_cell(ws.cell(row=row, column=1), value="No metrics computed.",
                         font_=S.font(10, italic=True, color=S.GREY_TEXT), fill_=S.fill(S.NAVY))
            return row + 1
        for i, metric in enumerate(metrics):
            bg = S.NAVY_LIGHT if i % 2 == 0 else S.NAVY
            S.style_cell(ws.cell(row=row, column=1), value=metric.get("label", ""),
                         font_=S.font(11, bold=True, color=S.WHITE), fill_=S.fill(bg), align=S.LEFT)
            S.style_cell(ws.cell(row=row, column=2), value=metric.get("value", ""),
                         font_=S.font(11, color=S.WHITE), fill_=S.fill(bg), align=S.RIGHT)
            ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=8)
            S.style_cell(ws.cell(row=row, column=3), value=metric.get("formula_used", ""),
                         font_=S.font(9, italic=True, color=S.GREY_TEXT), fill_=S.fill(bg), align=S.LEFT)
            row += 1
        return row

    # -- rankings -----------------------------------------------------------

    def _rankings(self, ws, rankings, row):
        if not rankings:
            return row
        row = self._section_header(ws, "PERFORMANCE RANKINGS", row)
        columns = list(rankings[0].keys())
        row = self._table_header(ws, columns, row)
        for record in rankings:
            rank = record.get("Rank")
            medal = MEDALS.get(rank)
            bg = medal or (S.NAVY_LIGHT if row % 2 == 0 else S.NAVY)
            text_color = MEDAL_TEXT.get(rank, S.WHITE)
            for c_index, col in enumerate(columns, start=1):
                S.style_cell(ws.cell(row=row, column=c_index), value=self._fmt(record.get(col)),
                             font_=S.font(10, bold=bool(medal), color=text_color), fill_=S.fill(bg),
                             align=S.RIGHT if isinstance(record.get(col), (int, float)) else S.LEFT)
            row += 1
        return row

    # -- growth -------------------------------------------------------------

    def _growth(self, ws, growth_table, row):
        if not growth_table:
            return row
        row = self._section_header(ws, "GROWTH ANALYSIS", row)
        columns = [c for c in growth_table[0].keys() if c != "direction"]
        display_cols = columns + ["Trend"]
        row = self._table_header(ws, display_cols, row)

        growth_col_index = next((i for i, c in enumerate(columns, start=1) if "growth" in c.lower() or "variance" in c.lower()), None)
        first_data_row = row
        for record in growth_table:
            bg = S.NAVY_LIGHT if row % 2 == 0 else S.NAVY
            for c_index, col in enumerate(columns, start=1):
                value = record.get(col)
                S.style_cell(ws.cell(row=row, column=c_index), value=self._fmt(value),
                             font_=S.font(10, color=S.WHITE), fill_=S.fill(bg),
                             align=S.RIGHT if isinstance(value, (int, float)) else S.LEFT)
            arrow, color = ARROWS.get(record.get("direction", "neutral"), ARROWS["neutral"])
            S.style_cell(ws.cell(row=row, column=len(columns) + 1), value=arrow,
                         font_=S.font(12, bold=True, color=color), fill_=S.fill(bg), align=S.CENTER)
            row += 1

        # Conditional tints on the growth/variance numeric column.
        if growth_col_index and row > first_data_row:
            from openpyxl.formatting.rule import CellIsRule
            letter = get_column_letter(growth_col_index)
            cell_range = f"{letter}{first_data_row}:{letter}{row - 1}"
            ws.conditional_formatting.add(cell_range, CellIsRule(operator="greaterThan", formula=["0"], fill=S.fill(S.GREEN_TINT)))
            ws.conditional_formatting.add(cell_range, CellIsRule(operator="lessThan", formula=["0"], fill=S.fill(S.RED_TINT)))
        return row

    # -- shared -------------------------------------------------------------

    def _table_header(self, ws, columns, row):
        border = S.box(S.BLUE_ELECTRIC, "thin")
        for c_index, col in enumerate(columns, start=1):
            S.style_cell(ws.cell(row=row, column=c_index), value=str(col),
                         font_=S.font(10, bold=True, color=S.WHITE), fill_=S.fill(S.BLUE_ELECTRIC),
                         align=S.CENTER, border=border)
        return row + 1

    @staticmethod
    def _fmt(value):
        if value is None:
            return "-"
        if isinstance(value, float):
            return round(value, 2)
        return value
