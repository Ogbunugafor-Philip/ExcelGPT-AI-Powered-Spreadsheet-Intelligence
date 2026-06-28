"""
ExcelBuilder — assemble the multi-sheet .xlsx workbook from a ComputationOutput.

Each output sheet is delegated to a dedicated builder under services/sheets/.
Empty sheets are skipped. The finished workbook is written under the session's
output directory and the path is returned for the /download endpoint to stream.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, NamedStyle, PatternFill

import config
from schemas.computation_schema import ComputationOutput

from .sheets import styles as S
from .sheets.analysis_sheet import AnalysisSheet
from .sheets.charts_sheet import ChartsSheet
from .sheets.data_sheet import DataSheet
from .sheets.executive_summary_sheet import ExecutiveSummarySheet
from .sheets.forecast_sheet import ForecastSheet


class ExcelBuilder:
    def __init__(self) -> None:
        self.executive = ExecutiveSummarySheet()
        self.data = DataSheet()
        self.analysis = AnalysisSheet()
        self.charts = ChartsSheet()
        self.forecast = ForecastSheet()

    def build(self, output: ComputationOutput, session_id: str) -> str:
        data = output.model_dump() if isinstance(output, ComputationOutput) else dict(output)

        wb = Workbook()
        wb.remove(wb.active)  # drop the default empty sheet
        self.apply_global_styles(wb)

        # Executive Summary — always present.
        ws = wb.create_sheet("Executive Summary")
        self.executive.build(ws, data.get("executive_summary", {}))

        # Data — skip when there are no columns.
        data_sheet = data.get("data_sheet", {})
        if data_sheet.get("columns"):
            self.data.build(wb.create_sheet("Data"), data_sheet)

        # Analysis — skip when nothing derived.
        analysis = data.get("analysis_sheet", {})
        if analysis.get("metrics") or analysis.get("rankings") or analysis.get("growth_table"):
            self.analysis.build(wb.create_sheet("Analysis"), analysis)

        # Charts — skip when none rendered.
        charts = data.get("charts", [])
        if charts:
            self.charts.build(wb.create_sheet("Charts"), charts)

        # Forecast — skip when no series.
        forecast = data.get("forecast_sheet", {})
        if ForecastSheet.has_content(forecast):
            self.forecast.build(wb.create_sheet("Forecast"), forecast)

        output_dir = Path(config.UPLOAD_DIR) / session_id / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / "report.xlsx"
        wb.save(file_path)
        return str(file_path)

    def apply_global_styles(self, wb: Workbook) -> None:
        """Register the ExcelGPT named styles and set a sane default font."""
        # Default font for any cell that doesn't override it.
        wb._default_font = Font(name=S.DEFAULT_FONT, size=11)  # noqa: SLF001 — openpyxl has no public setter

        styles: dict[str, dict[str, Any]] = {
            "header_style": dict(font=Font(name="Calibri", size=11, bold=True, color=S.WHITE),
                                 fill=PatternFill("solid", fgColor=S.BLUE_ELECTRIC),
                                 alignment=Alignment(horizontal="center", vertical="center")),
            "data_style": dict(font=Font(name="Calibri", size=10, color=S.WHITE),
                               fill=PatternFill("solid", fgColor=S.NAVY)),
            "currency_style": dict(font=Font(name="Calibri", size=10, color=S.WHITE),
                                   fill=PatternFill("solid", fgColor=S.NAVY),
                                   alignment=Alignment(horizontal="right", vertical="center"),
                                   number_format=S.CURRENCY_FORMAT),
            "kpi_value_style": dict(font=Font(name="Calibri", size=18, bold=True, color=S.WHITE),
                                    fill=PatternFill("solid", fgColor=S.NAVY_LIGHT),
                                    alignment=Alignment(horizontal="center", vertical="center")),
            "section_header_style": dict(font=Font(name="Calibri", size=13, bold=True, color=S.BLUE_ELECTRIC)),
        }

        for name, spec in styles.items():
            if name in wb.named_styles:
                continue
            style = NamedStyle(name=name)
            style.font = spec["font"]
            if "fill" in spec:
                style.fill = spec["fill"]
            if "alignment" in spec:
                style.alignment = spec["alignment"]
            if "number_format" in spec:
                style.number_format = spec["number_format"]
            wb.add_named_style(style)
