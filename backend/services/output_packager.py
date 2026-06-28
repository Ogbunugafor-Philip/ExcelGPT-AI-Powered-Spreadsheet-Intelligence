"""
Assemble individual module results into the ComputationOutput hand-off object.

The ComputationOutput is what the Excel-generation engine (openpyxl) consumes.
data_sheet rows keep RAW numeric values (openpyxl applies Naira number formats);
KPI cards and analysis metrics carry pre-formatted Naira/percentage strings.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

import config
from schemas.cerebras_schema import ActionPlan
from schemas.computation_schema import (
    AnalysisSheet,
    Chart,
    ComputationOutput,
    ConditionalFormatRule,
    DataSheet,
    ExecutiveSummary,
    ForecastSheet,
    KpiCard,
    Metric,
)

from .modules.common import (
    coerce_numeric,
    detect_date_column,
    format_naira,
    format_pct,
    is_currency_column,
    to_jsonable,
)
from .semantics import suggest_display_name

AGG_TYPES = {"group_sum", "group_avg", "rank", "filter"}


class OutputPackager:
    def package(
        self,
        action_plan: ActionPlan,
        all_results: list[dict[str, Any]],
        session: dict[str, Any],
        sheets: dict[str, pd.DataFrame] | None = None,
    ) -> ComputationOutput:
        sheets = sheets or {}
        session_id = session.get("session_id", "")
        version = int(session.get("version", 1))
        instruction = session.get("instruction", "")
        filename = (session.get("intelligence_brief", {}) or {}).get("filename") or session.get("filename") or "workbook.xlsx"

        results = [r for r in all_results if r]
        by_type: dict[str, list[dict[str, Any]]] = {}
        for result in results:
            by_type.setdefault(result.get("operation_type", ""), []).append(result)

        executive_summary = self._executive_summary(instruction, filename, results, sheets)
        data_sheet = self._data_sheet(results, sheets)
        analysis_sheet = self._analysis_sheet(results)
        charts = self._charts(results)
        forecast_sheet = self._forecast_sheet(by_type.get("forecast", []))
        display_names = self._display_names(session, results, sheets, data_sheet)

        return ComputationOutput(
            session_id=session_id,
            version=version,
            executive_summary=executive_summary,
            data_sheet=data_sheet,
            analysis_sheet=analysis_sheet,
            charts=charts,
            forecast_sheet=forecast_sheet,
            display_names=display_names,
        )

    # -- display names ------------------------------------------------------

    def _display_names(self, session, results, sheets, data_sheet) -> dict[str, str]:
        """Raw column name -> display name, spanning source columns and computed ones.

        Seeds from the intelligence brief (which already profiled every source
        column) and then fills in any computed/derived columns that only appear
        in operation results (Rank, growth_pct, period, …).
        """
        mapping: dict[str, str] = {}
        brief = session.get("intelligence_brief", {}) or {}
        for raw, display in (brief.get("display_names") or {}).items():
            if raw:
                mapping[str(raw)] = display or suggest_display_name(raw)

        def add(name: Any) -> None:
            key = str(name)
            if key and key not in mapping:
                mapping[key] = suggest_display_name(key)

        for result in results:
            for column in result.get("columns", []) or []:
                add(column)
        for column in data_sheet.columns or []:
            add(column if not isinstance(column, dict) else column.get("name", ""))
        for df in (sheets or {}).values():
            for column in df.columns:
                add(column)
        return mapping

    # -- executive summary --------------------------------------------------

    def _executive_summary(self, instruction, filename, results, sheets):
        title = self._title(instruction)
        period = self._detect_period(results, sheets)
        rows_total = sum(int(df.shape[0]) for df in sheets.values()) if sheets else 0
        data_source = f"{filename} ({rows_total} rows)" if rows_total else filename
        return ExecutiveSummary(
            title=title,
            period=period,
            data_source=data_source,
            kpi_cards=self._kpi_cards(results),
        )

    def _title(self, instruction: str) -> str:
        text = (instruction or "").strip().rstrip(".")
        if not text:
            return "ExcelGPT Report"
        clean = text[0].upper() + text[1:]
        return clean if len(clean) <= 80 else clean[:77] + "…"

    def _kpi_cards(self, results) -> list[KpiCard]:
        cards: list[KpiCard] = []
        for result in results:
            op_type = result.get("operation_type")
            if op_type in ("group_sum", "group_avg"):
                cards.extend(self._kpi_from_aggregation(result))
            elif op_type == "rank":
                card = self._kpi_from_rank(result)
                if card:
                    cards.append(card)
            elif op_type == "growth_rate":
                cards.extend(self._kpi_from_growth(result))
            elif op_type == "variance":
                cards.extend(self._kpi_from_variance(result))
            if len(cards) >= 6:
                break
        return cards[:6]

    def _kpi_from_aggregation(self, result) -> list[KpiCard]:
        cards = []
        stats = result.get("summary_stats", {})
        currency_cols = set(result.get("currency_columns", []))
        for column in result.get("value_columns", []):
            total = stats.get(f"total_{column}")
            if total is None:
                continue
            value = format_naira(total, compact=True) if column in currency_cols else f"{to_jsonable(total):,.2f}"
            cards.append(KpiCard(label=f"Total {self._pretty(column)}", value=value, change=f"{stats.get('groups', 0)} groups", direction="neutral"))
        return cards

    def _kpi_from_rank(self, result) -> KpiCard | None:
        columns = result.get("columns", [])
        rows = result.get("display_rows") or result.get("rows", [])
        if not rows:
            return None
        top = dict(zip(columns, rows[0]))
        ranked_by = result.get("ranked_by")
        entity = next((str(top[c]) for c in columns if c not in ("Rank", ranked_by) and isinstance(top.get(c), str)), None)
        entity = entity or "—"
        metric = top.get(ranked_by)
        return KpiCard(label=f"Top by {self._pretty(ranked_by)}", value=str(entity), change=str(metric) if metric is not None else "", direction="up")

    def _kpi_from_growth(self, result) -> list[KpiCard]:
        summary = result.get("directional_summary", {})
        avg = summary.get("average_growth_pct")
        if avg is None:
            return []
        return [KpiCard(
            label=f"Avg Growth — {self._pretty(summary.get('value_column', ''))}",
            value=format_pct(avg),
            change=f"{summary.get('up', 0)}↑ / {summary.get('down', 0)}↓",
            direction="up" if avg > 0 else "down" if avg < 0 else "neutral",
        )]

    def _kpi_from_variance(self, result) -> list[KpiCard]:
        summary = result.get("directional_summary", {})
        avg = summary.get("average_variance_pct")
        if avg is None:
            return []
        return [KpiCard(
            label="Avg Variance vs Target",
            value=format_pct(avg, signed=True),
            change=f"{summary.get('underperformers', 0)} under target",
            direction="up" if avg > 0 else "down" if avg < 0 else "neutral",
        )]

    # -- data sheet ---------------------------------------------------------

    def _data_sheet(self, results, sheets) -> DataSheet:
        primary = next((r for r in results if r.get("operation_type") in AGG_TYPES and r.get("rows")), None)
        if primary is None:
            primary = next((r for r in results if r.get("rows")), None)

        if primary is not None:
            columns = primary.get("columns", [])
            rows = primary.get("rows", [])
        elif sheets:
            name, df = next(iter(sheets.items()))
            head = df.head(500)
            columns = list(head.columns)
            rows = [[to_jsonable(v) for v in row] for row in head.to_numpy().tolist()]
        else:
            columns, rows = [], []

        return DataSheet(columns=columns, rows=rows, conditional_formatting=self._conditional_formatting(columns))

    def _conditional_formatting(self, columns) -> list[ConditionalFormatRule]:
        rules = []
        for column in columns:
            lowered = str(column).lower()
            if "growth" in lowered or "variance" in lowered:
                rules.append(ConditionalFormatRule(column=column, rule="value < 0", color=config.COLOR_PALETTE["red_alert"]))
        return rules

    # -- analysis sheet -----------------------------------------------------

    def _analysis_sheet(self, results) -> AnalysisSheet:
        metrics: list[Metric] = []
        rankings: list[Any] = []
        growth_table: list[Any] = []

        for result in results:
            op_type = result.get("operation_type")
            if op_type == "rank":
                rankings.extend(self._rows_as_dicts(result))
            elif op_type == "growth_rate":
                growth_table.extend(self._rows_as_dicts(result))
                metrics.extend(self._growth_metrics(result))
            elif op_type == "variance":
                growth_table.extend(self._rows_as_dicts(result))
                metrics.extend(self._variance_metrics(result))
            elif op_type in ("group_sum", "group_avg"):
                metrics.extend(self._aggregation_metrics(result))
            elif op_type == "correlation":
                metrics.extend(self._correlation_metrics(result))
            elif op_type == "distribution":
                metrics.extend(self._distribution_metrics(result))
            elif op_type == "outlier":
                metrics.append(Metric(
                    label="Outliers detected",
                    value=str(result.get("data", {}).get("outlier_count", 0)),
                    formula_used="IQR method: value < Q1 − 1.5·IQR or > Q3 + 1.5·IQR",
                ))

        return AnalysisSheet(metrics=metrics, rankings=rankings, growth_table=growth_table)

    def _aggregation_metrics(self, result) -> list[Metric]:
        metrics = []
        stats = result.get("summary_stats", {})
        currency_cols = set(result.get("currency_columns", []))
        how = stats.get("aggregation", "sum")
        for column in result.get("value_columns", []):
            total = stats.get(f"total_{column}")
            if total is None:
                continue
            value = format_naira(total, compact=True) if column in currency_cols else f"{to_jsonable(total):,.2f}"
            metrics.append(Metric(label=f"Total {self._pretty(column)}", value=value, formula_used=f"{how} over {stats.get('groups', 0)} groups"))
        return metrics

    def _growth_metrics(self, result) -> list[Metric]:
        summary = result.get("directional_summary", {})
        avg = summary.get("average_growth_pct")
        if avg is None:
            return []
        return [Metric(label=f"Average growth — {self._pretty(summary.get('value_column', ''))}", value=format_pct(avg, signed=True), formula_used="(current − previous) / previous × 100")]

    def _variance_metrics(self, result) -> list[Metric]:
        summary = result.get("directional_summary", {})
        avg = summary.get("average_variance_pct")
        if avg is None:
            return []
        return [Metric(label="Average variance vs target", value=format_pct(avg, signed=True), formula_used="(actual − target) / target × 100")]

    def _correlation_metrics(self, result) -> list[Metric]:
        metrics = []
        for pair in result.get("data", {}).get("strong_correlations", []):
            cols = pair.get("pair", ["", ""])
            metrics.append(Metric(label=f"{self._pretty(cols[0])} ↔ {self._pretty(cols[1])}", value=f"r = {pair.get('correlation')}", formula_used=f"Pearson correlation ({pair.get('type')})"))
        return metrics

    def _distribution_metrics(self, result) -> list[Metric]:
        metrics = []
        for dist in result.get("data", {}).get("distributions", []):
            metrics.append(Metric(label=f"{self._pretty(dist.get('column', ''))} distribution", value=f"{dist.get('shape')} (skew {dist.get('skewness')})", formula_used="scipy.stats skewness & excess kurtosis"))
        return metrics

    # -- charts & forecast --------------------------------------------------

    def _charts(self, results) -> list[Chart]:
        charts = []
        for result in results:
            if result.get("operation_type") != "chart":
                continue
            charts.append(Chart(
                chart_id=result.get("operation_id", "chart"),
                chart_type=result.get("chart_type", "bar"),
                title=result.get("title", ""),
                image_path=result.get("image_path") or "",
                recharts_data=result.get("recharts_data", []),
            ))
        return charts

    def _forecast_sheet(self, forecast_results) -> ForecastSheet:
        if not forecast_results:
            return ForecastSheet()
        result = forecast_results[0]
        assumptions = list(result.get("assumptions", []))
        if result.get("error"):
            assumptions.append(result["error"])
        return ForecastSheet(
            historical=result.get("historical", []),
            projected=result.get("projected", []),
            confidence_upper=result.get("confidence_upper", []),
            confidence_lower=result.get("confidence_lower", []),
            assumptions=assumptions,
        )

    # -- helpers ------------------------------------------------------------

    def _rows_as_dicts(self, result) -> list[dict[str, Any]]:
        columns = result.get("columns", [])
        return [dict(zip(columns, row)) for row in result.get("rows", [])]

    def _detect_period(self, results, sheets) -> str:
        for df in sheets.values():
            date_col = detect_date_column(df)
            if date_col:
                parsed = pd.to_datetime(df[date_col], errors="coerce").dropna()
                if not parsed.empty:
                    start, end = parsed.min(), parsed.max()
                    if start == end:
                        return start.strftime("%b %Y")
                    return f"{start.strftime('%b %Y')} – {end.strftime('%b %Y')}"
        for result in results:
            historical = result.get("historical")
            if historical:
                periods = [point.get("period") for point in historical if point.get("period")]
                if periods:
                    return f"{periods[0]} – {periods[-1]}"
        return "Current Period"

    @staticmethod
    def _pretty(name: Any) -> str:
        return suggest_display_name(name) or str(name).replace("_", " ").strip().title()
