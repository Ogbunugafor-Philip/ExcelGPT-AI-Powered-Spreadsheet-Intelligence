"""Charts sheet — embeds the matplotlib-rendered PNGs, one per row, stacked."""

from __future__ import annotations

import os
from typing import Any

from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from . import styles as S


class ChartsSheet:
    def build(self, ws, charts: list[dict[str, Any]]) -> None:
        if not charts:
            ws["A1"] = "No charts generated for this analysis."
            ws.sheet_view.showGridLines = False
            return

        current_row = 1
        charts_embedded = 0

        for i, chart in enumerate(charts):
            image_path = chart.get("image_path", "")
            title = chart.get("title", f"Chart {i + 1}")

            # Title band above the image.
            title_cell = ws.cell(row=current_row, column=1, value=title)
            title_cell.font = Font(bold=True, color="FFFFFF", size=13)
            title_cell.fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
            current_row += 1

            if image_path and os.path.exists(image_path):
                try:
                    img = XLImage(image_path)
                    img.width = 600
                    img.height = 350
                    ws.add_image(img, f"A{current_row}")
                    # Reserve rows for the image (~350px / ~15px per row ≈ 24 rows).
                    current_row += 24
                    charts_embedded += 1
                    print(f"[charts_sheet] Embedded chart: {image_path}")
                except Exception as e:  # noqa: BLE001
                    ws.cell(row=current_row, column=1, value=f"Chart error: {e}")
                    current_row += 2
            else:
                ws.cell(row=current_row, column=1, value=f"Chart image not found: {image_path}")
                print(f"[charts_sheet] WARNING: Chart not found: {image_path}")
                current_row += 2

            current_row += 2  # gap between charts

        print(f"[charts_sheet] Embedded {charts_embedded} of {len(charts)} charts")

        # Column widths for chart display.
        for col in range(1, 9):
            ws.column_dimensions[get_column_letter(col)].width = 18
        ws.sheet_view.showGridLines = False
        ws.sheet_properties.tabColor = S.AMBER
