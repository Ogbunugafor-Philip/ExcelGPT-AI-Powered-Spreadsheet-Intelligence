"""Charts sheet — embeds the matplotlib-rendered PNGs, 2 per row."""

from __future__ import annotations

import os
from typing import Any

from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter

from . import styles as S

CHARTS_PER_ROW = 2
CHART_W = 400
CHART_H = 280
COL_SPAN = 4          # columns each chart block occupies
ROW_SPAN = 16         # rows each chart block occupies


class ChartsSheet:
    def build(self, ws, charts: list[dict[str, Any]]) -> None:
        S.hide_gridlines(ws)
        ws.sheet_properties.tabColor = S.AMBER
        S.set_column_widths(ws, 20, first=1, last=8)

        max_row = 1
        for index, chart in enumerate(charts or []):
            col_block = index % CHARTS_PER_ROW
            row_block = index // CHARTS_PER_ROW
            start_col = 1 + col_block * COL_SPAN          # A or E
            title_row = 1 + row_block * ROW_SPAN
            letter = get_column_letter(start_col)

            # Title above the chart
            ws.merge_cells(start_row=title_row, start_column=start_col,
                           end_row=title_row, end_column=start_col + COL_SPAN - 1)
            S.style_cell(ws.cell(row=title_row, column=start_col), value=chart.get("title", "Chart"),
                         font_=S.font(12, bold=True, color=S.BLUE_ELECTRIC), align=S.LEFT)

            image_path = chart.get("image_path")
            anchor = f"{letter}{title_row + 1}"
            if image_path and os.path.exists(image_path):
                try:
                    img = XLImage(image_path)
                    img.width = CHART_W
                    img.height = CHART_H
                    ws.add_image(img, anchor)
                except Exception as exc:  # noqa: BLE001
                    self._placeholder(ws, start_col, title_row + 1, f"Chart unavailable ({exc})")
            else:
                self._placeholder(ws, start_col, title_row + 1, "Chart unavailable")

            ws.row_dimensions[title_row + 1].height = 160
            max_row = max(max_row, title_row + ROW_SPAN)

        if not charts:
            S.style_cell(ws["A1"], value="No charts generated for this report.",
                         font_=S.font(11, italic=True, color=S.GREY_TEXT))
            max_row = 2

        S.paint_canvas(ws, max_row=max_row, max_col=8, color=S.NAVY)

    def _placeholder(self, ws, col, row, text):
        S.style_cell(ws.cell(row=row, column=col), value=text,
                     font_=S.font(11, italic=True, color=S.GREY_TEXT), fill_=S.fill(S.NAVY_LIGHT), align=S.CENTER)
