"""
Assemble individual module results into the ComputationOutput hand-off object.

The ComputationOutput is what the Excel-generation engine (openpyxl) consumes.
data_sheet rows keep RAW numeric values (openpyxl applies Naira number formats);
KPI cards and analysis metrics carry pre-formatted Naira/percentage strings.
"""

from __future__ import annotations

import re
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

# Words stripped from the front of an instruction when building a clean title.
_TITLE_FILLER = {
    "show", "me", "the", "calculate", "please", "can", "you", "i", "want", "give",
    "us", "display", "list", "find", "a", "an", "what", "which", "is", "are", "that",
    "compute", "analyse", "analyze", "get", "provide", "generate", "create", "produce",
    "make", "report", "tell", "kindly", "could", "would", "how", "do", "does",
}
# Prepositions that end a tight title once enough words are captured.
_TITLE_STOPS = {"from", "between", "during", "over", "within", "starting", "based", "where", "with"}
# Small words kept lowercase mid-title.
_TITLE_SMALL = {"by", "per", "of", "vs", "to", "and", "in", "for", "on", "the", "a", "an"}


def title_from_instruction(instruction: str) -> str:
    """Extract a clean 4–6 word title from a plain-English instruction.

    "Show me the top 5 branches by deposits…"  -> "Top 5 Branches by Deposits"
    "Calculate the monthly growth trend…"        -> "Monthly Growth Trend"
    """
    text = (instruction or "").strip().rstrip(".!?").replace("\n", " ")
    if not text:
        return "ExcelGPT Report"
    raw = re.findall(r"[A-Za-z0-9%₦]+", text)
    words = list(raw)
    while words and words[0].lower() in _TITLE_FILLER:
        words.pop(0)
    if not words:
        words = list(raw)

    selected: list[str] = []
    for word in words:
        lowered = word.lower()
        if len(selected) >= 3 and lowered in _TITLE_STOPS:
            break
        if selected and lowered in {"is", "are", "the", "a", "an", "of"} and len(selected) < 2:
            continue
        selected.append(word)
        if len(selected) >= 6:
            break
    if not selected:
        selected = words[:6]

    out: list[str] = []
    for index, word in enumerate(selected):
        lowered = word.lower()
        if index > 0 and lowered in _TITLE_SMALL:
            out.append(lowered)
        elif word.isupper() and len(word) <= 4:
            out.append(word)  # acronym (e.g. NGN, HQ)
        elif word.isalpha():
            out.append(word[:1].upper() + word[1:].lower())
        else:
            out.append(word)
    title = " ".join(out)
    return title if len(title) <= 80 else title[:77] + "…"


class OutputPackager:
    def package(
        self,
        action_plan: ActionPlan,
        all_results: list[dict[str, Any]],
        session: dict[str, Any],
        sheets: dict[str, pd.DataFrame] | None = None,
    ) -> ComputationOutput:
        # Defensive: if handed an already-assembled ComputationOutput (e.g. the
        # router's return value passed straight back in), don't try to re-package
        # it — just return it.
        if isinstance(all_results, ComputationOutput):
            return all_results
        if isinstance(all_results, list) and len(all_results) == 1 and isinstance(all_results[0], ComputationOutput):
            return all_results[0]

        sheets = sheets or {}
        session_id = session.get("session_id", "")
        version = int(session.get("version", 1))
        instruction = session.get("instruction", "")
        filename = (session.get("intelligence_brief", {}) or {}).get("filename") or session.get("filename") or "workbook.xlsx"

        results = [r for r in all_results if r]
        by_type: dict[str, list[dict[str, Any]]] = {}
        for result in results:
            by_type.setdefault(result.get("operation_type", ""), []).append(result)

        executive_summary = self._executive_summary(action_plan, instruction, filename, results, sheets)
        data_sheet = self._data_sheet(action_plan, results, sheets)
        analysis_sheet = self._analysis_sheet(action_plan, results)
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

    def _executive_summary(self, action_plan, instruction, filename, results, sheets):
        title = self._title(instruction)
        period = self._detect_period(results, sheets)
        rows_total = sum(int(df.shape[0]) for df in sheets.values()) if sheets else 0
        data_source = f"{filename} ({rows_total} rows)" if rows_total else filename
        return ExecutiveSummary(
            title=title,
            period=period,
            data_source=data_source,
            kpi_cards=self._kpi_cards(action_plan, results),
        )

    def _title(self, instruction: str) -> str:
        return title_from_instruction(instruction)

    # -- rank + variance combo (top-N branches vs target) -------------------

    @staticmethod
    def _plural(word: str, n: int) -> str:
        """Pluralise an entity noun correctly: Branch -> Branches, Zone -> Zones."""
        if n == 1:
            return word
        lowered = word.lower()
        if lowered.endswith("y") and not lowered.endswith(("ay", "ey", "oy", "uy")):
            return word[:-1] + "ies"
        if lowered.endswith(("s", "x", "z", "ch", "sh")):
            return word + "es"
        return word + "s"

    def _top_variance(self, action_plan, results):
        """For a 'top-N by metric + variance vs target' question, compute the
        per-branch variance for exactly the ranked top-N branches.

        Returns (records, meta) or None when this is not that kind of question.
        """
        if action_plan is None:
            return None
        rank_op = next((op for op in action_plan.operations if op.operation_type == "rank"), None)
        var_op = next((op for op in action_plan.operations if op.operation_type == "variance"), None)
        if rank_op is None or var_op is None:
            return None
        rank = next((r for r in results if r.get("operation_type") == "rank" and r.get("rows")), None)
        if rank is None:
            return None

        cols = rank.get("columns", [])
        rows = rank.get("rows", [])
        ranked_by = rank.get("ranked_by")
        if ranked_by not in cols or not rows:
            return None

        target_col = var_op.parameters.get("target_column") or var_op.parameters.get("target")
        if target_col not in cols:
            target_col = next((c for c in cols if str(c).lower() in ("target", "budget", "goal", "plan")), None)
        if target_col not in cols:
            return None

        dep_i = cols.index(ranked_by)
        tgt_i = cols.index(target_col)
        rank_i = cols.index("Rank") if "Rank" in cols else None
        ent_i = next((i for i, c in enumerate(cols)
                      if c not in ("Rank", ranked_by, target_col) and isinstance(rows[0][i], str)), None)
        zone_i = next((i for i, c in enumerate(cols) if str(c).lower() == "zone"), None)

        records = []
        for idx, row in enumerate(rows, start=1):
            dep = to_jsonable(row[dep_i])
            tgt = to_jsonable(row[tgt_i])
            numeric = isinstance(dep, (int, float)) and isinstance(tgt, (int, float))
            var = round(dep - tgt, 2) if numeric else None
            vpct = round((dep - tgt) / tgt * 100.0, 2) if numeric and tgt else None
            status = "Above Target" if (var or 0) > 0 else "Below Target" if (var or 0) < 0 else "On Target"
            records.append({
                "rank": to_jsonable(row[rank_i]) if rank_i is not None else idx,
                "branch": row[ent_i] if ent_i is not None else None,
                "zone": row[zone_i] if zone_i is not None else None,
                "deposits": dep, "target": tgt, "variance": var, "variance_pct": vpct, "status": status,
                "direction": "up" if (var or 0) > 0 else "down" if (var or 0) < 0 else "neutral",
            })
        meta = {
            "ranked_by": ranked_by,
            "metric_label": self._pretty(ranked_by),
            "target_col": target_col,
            "has_zone": zone_i is not None,
            "is_currency": ranked_by in set(rank.get("currency_columns", [])) or is_currency_column(ranked_by),
            "top_n": rank_op.parameters.get("top_n") or len(records),
            "entity_label": self._pretty(cols[ent_i]) if ent_i is not None else "Branch",
        }
        return records, meta

    def _kpi_cards(self, action_plan, results) -> list[KpiCard]:
        combo = self._top_variance(action_plan, results)
        if combo:
            return self._kpi_from_combo(*combo)

        # Lead with the cards that match the question's primary intent so the
        # Executive Summary opens on growth KPIs for a growth question, etc.
        ordered = sorted(results, key=lambda r: self._kpi_priority(r.get("operation_type")))
        cards: list[KpiCard] = []
        for result in ordered:
            op_type = result.get("operation_type")
            if op_type in ("group_sum", "group_avg"):
                cards.extend(self._kpi_from_aggregation(result))
            elif op_type == "rank":
                cards.extend(self._kpi_from_rank(result))
            elif op_type == "growth_rate":
                cards.extend(self._kpi_from_growth(result))
            elif op_type == "variance":
                cards.extend(self._kpi_from_variance(result))
            if len(cards) >= 8:
                break
        return cards[:8]

    @staticmethod
    def _kpi_priority(op_type: str) -> int:
        order = {"growth_rate": 0, "variance": 1, "rank": 2, "group_sum": 3, "group_avg": 3}
        return order.get(op_type, 9)

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

    def _kpi_from_rank(self, result) -> list[KpiCard]:
        """Rankings question KPIs: Top Branch, Total, Average per branch, Count."""
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        if not rows:
            return []
        ranked_by = result.get("ranked_by")
        currency_cols = set(result.get("currency_columns", []))
        is_currency = ranked_by in currency_cols or is_currency_column(ranked_by)
        metric_idx = columns.index(ranked_by) if ranked_by in columns else None
        entity_idx = next(
            (i for i, c in enumerate(columns) if c not in ("Rank", ranked_by) and isinstance(rows[0][i], str)),
            None,
        )
        top_entity = str(rows[0][entity_idx]) if entity_idx is not None else "—"
        values = [r[metric_idx] for r in rows if metric_idx is not None and isinstance(r[metric_idx], (int, float))]
        total = sum(values) if values else None
        average = (total / len(values)) if values else None
        entity_label = self._pretty(columns[entity_idx]) if entity_idx is not None else "Entity"

        def money(v):
            return format_naira(v, compact=True) if is_currency else (f"{v:,.0f}" if isinstance(v, (int, float)) else "—")

        cards = [KpiCard(label=f"Top {entity_label}", value=top_entity,
                         change=money(rows[0][metric_idx]) if metric_idx is not None else "", direction="up")]
        if total is not None:
            cards.append(KpiCard(label=f"Total {self._pretty(ranked_by)}", value=money(total),
                                 change=f"{len(values)} {self._plural(entity_label, len(values)).lower()}", direction="neutral"))
            cards.append(KpiCard(label=f"Average per {entity_label}", value=money(average), change="", direction="neutral"))
        cards.append(KpiCard(label=f"Number of {self._plural(entity_label, len(rows))}", value=f"{len(rows):,}", change="", direction="neutral"))
        return cards

    def _kpi_from_growth(self, result) -> list[KpiCard]:
        summary = result.get("directional_summary", {})
        if summary.get("mode") == "wide":
            avg = summary.get("average_growth_pct")
            best_growth = summary.get("best_branch_growth")
            cards = [
                KpiCard(
                    label="Highest Growth Month",
                    value=str(summary.get("highest_growth_month") or "—"),
                    change=format_pct(summary.get("highest_growth_value"), signed=True)
                    if summary.get("highest_growth_value") is not None else "",
                    direction="up",
                ),
                KpiCard(
                    label="Avg Monthly Growth",
                    value=format_pct(avg, signed=True) if avg is not None else "—",
                    change=f"{summary.get('up', 0)}↑ / {summary.get('down', 0)}↓",
                    direction="up" if (avg or 0) > 0 else "down" if (avg or 0) < 0 else "neutral",
                ),
                KpiCard(
                    label="Best Performing Branch",
                    value=str(summary.get("best_branch") or "—"),
                    change=format_pct(best_growth, signed=True) if best_growth is not None else "",
                    direction="up",
                ),
                KpiCard(
                    label="Branches with Positive Growth",
                    value=f"{summary.get('positive_branches', 0)}/{summary.get('branch_count', 0)}",
                    change="over the period", direction="up",
                ),
            ]
            return cards

        avg = summary.get("average_growth_pct")
        if avg is None:
            return []
        return [KpiCard(
            label=f"Avg Growth — {self._pretty(summary.get('value_column', ''))}".rstrip(" —"),
            value=format_pct(avg, signed=True),
            change=f"{summary.get('up', 0)}↑ / {summary.get('down', 0)}↓",
            direction="up" if avg > 0 else "down" if avg < 0 else "neutral",
        )]

    def _kpi_from_variance(self, result) -> list[KpiCard]:
        summary = result.get("directional_summary", {})
        table = result.get("variance_table") or []
        if summary.get("mode") == "wide" and table:
            best = max((r for r in table if r.get("Variance (%)") is not None), key=lambda r: r["Variance (%)"], default=None)
            worst = min((r for r in table if r.get("Variance (%)") is not None), key=lambda r: r["Variance (%)"], default=None)
            label_key = next((k for k in table[0] if k not in ("Target (₦)", "Actual (₦)", "Variance (₦)", "Variance (%)", "Status", "direction")), "Entity")
            return [
                KpiCard(label="Branches Above Target", value=f"{summary.get('above_target', 0)}",
                        change=f"of {len(table)}", direction="up"),
                KpiCard(label="Branches Below Target", value=f"{summary.get('below_target', 0)}",
                        change=f"of {len(table)}", direction="down" if summary.get("below_target") else "neutral"),
                KpiCard(label="Best vs Target", value=str(best.get(label_key)) if best else "—",
                        change=format_pct(best.get("Variance (%)"), signed=True) if best else "", direction="up"),
                KpiCard(label="Worst vs Target", value=str(worst.get(label_key)) if worst else "—",
                        change=format_pct(worst.get("Variance (%)"), signed=True) if worst else "", direction="down"),
            ]

        avg = summary.get("average_variance_pct")
        if avg is None:
            return []
        return [KpiCard(
            label="Avg Variance vs Target",
            value=format_pct(avg, signed=True),
            change=f"{summary.get('underperformers', 0)} under target",
            direction="up" if avg > 0 else "down" if avg < 0 else "neutral",
        )]

    def _kpi_from_combo(self, records, meta) -> list[KpiCard]:
        """The 4 KPI cards that directly answer a top-N + variance question."""
        from statistics import mean

        entity = meta["entity_label"]
        metric = meta["metric_label"]
        is_currency = meta["is_currency"]
        top_n = meta["top_n"]
        above = [r for r in records if r["variance"] is not None and r["variance"] > 0]
        below = [r for r in records if r["variance"] is not None and r["variance"] < 0]
        top = records[0] if records else {}
        total_dep = sum(r["deposits"] for r in records if isinstance(r["deposits"], (int, float)))
        total_tgt = sum(r["target"] for r in records if isinstance(r["target"], (int, float)))

        def avg_pct(group):
            vals = [r["variance_pct"] for r in group if r["variance_pct"] is not None]
            return mean(vals) if vals else None

        aa, ab = avg_pct(above), avg_pct(below)

        def money(v, compact=False):
            if not isinstance(v, (int, float)):
                return "—"
            if not is_currency:
                return f"{v:,.0f}"
            return format_naira(v, compact=True) if compact else self._naira0(v)

        return [
            KpiCard(label=f"Top {entity}", value=str(top.get("branch") or "—"),
                    change=money(top.get("deposits")), direction="up"),
            KpiCard(label="Above Target", value=f"{len(above)} {self._plural(entity, len(above))}",
                    change=f"avg {format_pct(aa, signed=True)}" if aa is not None else "", direction="up"),
            KpiCard(label="Below Target", value=f"{len(below)} {self._plural(entity, len(below))}",
                    change=f"avg {format_pct(ab, signed=True)}" if ab is not None else "",
                    direction="down" if below else "neutral"),
            KpiCard(label=f"Total {metric} (Top {top_n})", value=money(total_dep, compact=True),
                    change=f"vs {money(total_tgt, compact=True)} target",
                    direction="up" if total_dep >= total_tgt else "down"),
        ]

    # -- data sheet ---------------------------------------------------------

    def _data_sheet(self, action_plan, results, sheets) -> DataSheet:
        """The Data sheet shows the PRIMARY result of what was actually asked.

        Priority: top-N + variance combo → growth table → variance table →
        rankings → grouped aggregation → raw rows as a last resort.
        """
        combo = self._top_variance(action_plan, results)
        if combo:
            columns, rows = self._combo_data_sheet(*combo)
            return DataSheet(columns=columns, rows=rows, conditional_formatting=self._conditional_formatting(columns))

        growth = next((r for r in results if r.get("operation_type") == "growth_rate" and r.get("wide_growth")), None)
        variance = next((r for r in results if r.get("operation_type") == "variance" and r.get("variance_table")), None)
        rank = next((r for r in results if r.get("operation_type") == "rank" and r.get("rows")), None)
        group = next((r for r in results if r.get("operation_type") in ("group_sum", "group_avg") and r.get("rows")), None)

        if growth is not None:
            columns, rows = self._growth_data_sheet(growth["wide_growth"])
        elif variance is not None:
            columns, rows = self._variance_data_sheet(variance)
        elif rank is not None:
            columns, rows = rank.get("columns", []), rank.get("rows", [])
        elif group is not None:
            columns, rows = self._group_data_sheet(group, sheets)
        else:
            primary = next((r for r in results if r.get("operation_type") in AGG_TYPES and r.get("rows")), None)
            if primary is None:
                primary = next((r for r in results if r.get("rows")), None)
            if primary is not None:
                columns, rows = primary.get("columns", []), primary.get("rows", [])
            elif sheets:
                _, df = next(iter(sheets.items()))
                head = df.head(500)
                columns = list(head.columns)
                rows = [[to_jsonable(v) for v in row] for row in head.to_numpy().tolist()]
            else:
                columns, rows = [], []

        return DataSheet(columns=columns, rows=rows, conditional_formatting=self._conditional_formatting(columns))

    def _combo_data_sheet(self, records, meta) -> tuple[list[str], list[list[Any]]]:
        """Rank | Branch | [Zone] | <Metric> (₦) | Target (₦) | Variance (₦) | Variance % | Status."""
        entity = meta["entity_label"]
        metric = meta["metric_label"]
        suffix = " (₦)" if meta["is_currency"] else ""
        columns = ["Rank", entity]
        if meta["has_zone"]:
            columns.append("Zone")
        columns += [f"{metric}{suffix}", f"Target{suffix}", "Variance (₦)", "Variance %", "Status"]

        rows = []
        for r in records:
            row = [r["rank"], r["branch"]]
            if meta["has_zone"]:
                row.append(r["zone"])
            row += [r["deposits"], r["target"], r["variance"], r["variance_pct"], r["status"]]
            rows.append(row)
        return columns, rows

    def _growth_data_sheet(self, wide) -> tuple[list[str], list[list[Any]]]:
        group_col = wide.get("group_col", "Group")
        periods = wide.get("periods", [])
        columns = [group_col] + periods + ["Total Growth %", "Direction"]
        rows = [
            [r.get(group_col)] + [r.get(p) for p in periods] + [r.get("Total Growth %"), r.get("Direction")]
            for r in wide.get("value_rows", [])
        ]
        return columns, rows

    def _variance_data_sheet(self, result) -> tuple[list[str], list[list[Any]]]:
        table = result.get("variance_table", [])
        if not table:
            return result.get("columns", []), result.get("rows", [])
        label_key = next((k for k in table[0] if k not in ("Target (₦)", "Actual (₦)", "Variance (₦)", "Variance (%)", "Status", "direction")), "Entity")
        columns = [label_key, "Target (₦)", "Actual (₦)", "Variance (₦)", "Variance (%)", "Status"]
        rows = [[r.get(c) for c in columns] for r in table]
        return columns, rows

    def _group_data_sheet(self, result, sheets) -> tuple[list[str], list[list[Any]]]:
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        if not columns or not rows:
            return columns, rows
        group_col = columns[0]
        value_col = columns[1] if len(columns) > 1 else None

        # Re-derive Count & Average from the raw frame when available; otherwise
        # fall back to Total + % of Total computed from the aggregated rows.
        df = next((d for d in (sheets or {}).values() if group_col in d.columns and value_col in (d.columns if value_col else [])), None)
        if df is not None and value_col is not None:
            series = coerce_numeric(df[value_col])
            work = pd.DataFrame({group_col: df[group_col], "__v__": series})
            grouped = work.groupby(group_col, dropna=False)["__v__"]
            agg = grouped.agg(["sum", "count", "mean"]).reset_index().sort_values("sum", ascending=False)
            grand = float(agg["sum"].sum()) or 1.0
            suffix = " (₦)" if is_currency_column(value_col) else ""
            out_cols = [group_col, f"Total{suffix}", "Count", f"Average{suffix}", "% of Total"]
            out_rows = [
                [to_jsonable(r[group_col]), round(float(r["sum"]), 2), int(r["count"]),
                 round(float(r["mean"]), 2), round(float(r["sum"]) / grand * 100.0, 2)]
                for _, r in agg.iterrows()
            ]
            return out_cols, out_rows

        if value_col is not None:
            total = sum(r[1] for r in rows if isinstance(r[1], (int, float))) or 1.0
            out_cols = [group_col, value_col, "% of Total"]
            out_rows = [[r[0], r[1], round(r[1] / total * 100.0, 2) if isinstance(r[1], (int, float)) else None] for r in rows]
            return out_cols, out_rows
        return columns, rows

    def _conditional_formatting(self, columns) -> list[ConditionalFormatRule]:
        rules = []
        for column in columns:
            lowered = str(column).lower()
            if "growth" in lowered or "variance" in lowered:
                rules.append(ConditionalFormatRule(column=column, rule="value < 0", color=config.COLOR_PALETTE["red_alert"]))
        return rules

    # -- analysis sheet -----------------------------------------------------

    def _analysis_sheet(self, action_plan, results) -> AnalysisSheet:
        combo = self._top_variance(action_plan, results)
        if combo:
            return self._combo_analysis(*combo)

        metrics: list[Metric] = []
        rankings: list[Any] = []
        growth_table: list[Any] = []
        insights: list[str] = []

        for result in results:
            op_type = result.get("operation_type")
            if op_type == "rank":
                rankings.extend(self._rows_as_dicts(result))
                insights.extend(self._rank_insights(result))
            elif op_type == "growth_rate":
                wide = result.get("wide_growth")
                if wide:
                    growth_table.extend(wide.get("step_rows", []))
                else:
                    growth_table.extend(self._rows_as_dicts(result))
                metrics.extend(self._growth_metrics(result))
                insights.extend(self._growth_insights(result))
            elif op_type == "variance":
                table = result.get("variance_table")
                if table:
                    growth_table.extend(table)
                else:
                    growth_table.extend(self._rows_as_dicts(result))
                metrics.extend(self._variance_metrics(result))
                insights.extend(self._variance_insights(result))
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

        return AnalysisSheet(metrics=metrics, rankings=rankings, growth_table=growth_table, insights=insights[:5])

    def _combo_analysis(self, records, meta) -> AnalysisSheet:
        """Analysis sheet for a top-N + variance question — already limited to the
        ranked top-N branches, with human-readable column names."""
        entity = meta["entity_label"]
        metric = meta["metric_label"]
        suffix = " (₦)" if meta["is_currency"] else ""
        above = [r for r in records if r["variance"] is not None and r["variance"] > 0]
        below = [r for r in records if r["variance"] is not None and r["variance"] < 0]
        total_dep = sum(r["deposits"] for r in records if isinstance(r["deposits"], (int, float)))
        total_tgt = sum(r["target"] for r in records if isinstance(r["target"], (int, float)))
        best = max((r for r in records if r["variance_pct"] is not None), key=lambda r: r["variance_pct"], default=None)
        worst = min((r for r in records if r["variance_pct"] is not None), key=lambda r: r["variance_pct"], default=None)

        metrics = [
            Metric(label="Above target", value=f"{len(above)} of {len(records)}", formula_used=f"{metric} > Target"),
            Metric(label="Below target", value=f"{len(below)} of {len(records)}", formula_used=f"{metric} < Target"),
            Metric(label=f"Total {metric} (Top {meta['top_n']})", value=self._naira0(total_dep) if meta["is_currency"] else f"{total_dep:,.0f}",
                   formula_used=f"sum of top {meta['top_n']} {metric.lower()}"),
            Metric(label="Total target", value=self._naira0(total_tgt) if meta["is_currency"] else f"{total_tgt:,.0f}",
                   formula_used="sum of targets"),
        ]
        if best:
            metrics.append(Metric(label="Best vs target", value=f"{best['branch']} ({format_pct(best['variance_pct'], signed=True)})", formula_used="max (metric − target) / target"))
        if worst and worst["variance_pct"] is not None and worst["variance_pct"] < 0:
            metrics.append(Metric(label="Worst vs target", value=f"{worst['branch']} ({format_pct(worst['variance_pct'], signed=True)})", formula_used="min (metric − target) / target"))

        # Human-readable, top-N-limited variance table (rendered by AnalysisSheet._growth).
        table = []
        for r in records:
            row = {"Rank": r["rank"], entity: r["branch"]}
            if meta["has_zone"]:
                row["Zone"] = r["zone"]
            row[f"{metric}{suffix}"] = r["deposits"]
            row[f"Target{suffix}"] = r["target"]
            row["Variance (₦)"] = r["variance"]
            row["Variance %"] = r["variance_pct"]
            row["Status"] = r["status"]
            row["direction"] = r["direction"]
            table.append(row)

        return AnalysisSheet(metrics=metrics, rankings=[], growth_table=table,
                             insights=self._combo_insights(records, meta)[:5])

    def _combo_insights(self, records, meta) -> list[str]:
        entity = meta["entity_label"].lower()
        top_n = meta["top_n"]
        cur = meta["is_currency"]
        above = [r for r in records if r["variance"] is not None and r["variance"] > 0]
        below = [r for r in records if r["variance"] is not None and r["variance"] < 0]
        best = max((r for r in records if r["variance_pct"] is not None), key=lambda r: r["variance_pct"], default=None)
        worst = min((r for r in records if r["variance_pct"] is not None), key=lambda r: r["variance_pct"], default=None)
        total_dep = sum(r["deposits"] for r in records if isinstance(r["deposits"], (int, float)))
        total_tgt = sum(r["target"] for r in records if isinstance(r["target"], (int, float)))

        def nc(v):
            if not isinstance(v, (int, float)):
                return "—"
            return format_naira(v, compact=True).replace(".00", "") if cur else f"{v:,.0f}"

        out: list[str] = []
        if best and best["variance"] is not None:
            out.append(f"{best['branch']} exceeds its {nc(best['target'])} target by {nc(best['variance'])} ({format_pct(best['variance_pct'], signed=True)}), the strongest performance in this group.")
        out.append(f"{len(above)} of the top {top_n} {self._plural(entity, len(records))} are above target; {len(below)} fell short.")
        if below and worst and worst["variance"] is not None:
            only = "the only branch below target" if len(below) == 1 else "the weakest performer"
            out.append(f"{worst['branch']} is {only}, falling short by {nc(abs(worst['variance']))} ({format_pct(worst['variance_pct'], signed=True)}).")
        if total_tgt:
            gap_pct = (total_dep - total_tgt) / total_tgt * 100.0
            out.append(f"Together the top {top_n} {self._plural(entity, top_n)} hold {nc(total_dep)} against a {nc(total_tgt)} target ({format_pct(gap_pct, signed=True)}).")
        return out

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
        if summary.get("mode") == "wide":
            metrics: list[Metric] = []
            avg = summary.get("average_growth_pct")
            if avg is not None:
                metrics.append(Metric(label="Avg monthly growth", value=format_pct(avg, signed=True),
                                      formula_used="mean of all month-over-month growth rates"))
            if summary.get("highest_growth_month"):
                metrics.append(Metric(label="Highest growth month", value=f"{summary['highest_growth_month']} ({format_pct(summary.get('highest_growth_value'), signed=True)})",
                                      formula_used="period with the highest average growth"))
            if summary.get("lowest_growth_month"):
                metrics.append(Metric(label="Lowest growth month", value=f"{summary['lowest_growth_month']} ({format_pct(summary.get('lowest_growth_value'), signed=True)})",
                                      formula_used="period with the lowest average growth"))
            total = summary.get("total_growth_avg")
            if total is not None:
                metrics.append(Metric(label="Total growth (first→last)", value=format_pct(total, signed=True),
                                      formula_used="(last period − first period) / first period × 100, averaged"))
            return metrics

        avg = summary.get("average_growth_pct")
        if avg is None:
            return []
        return [Metric(label=f"Average growth — {self._pretty(summary.get('value_column', ''))}".rstrip(" —"), value=format_pct(avg, signed=True), formula_used="(current − previous) / previous × 100")]

    def _variance_metrics(self, result) -> list[Metric]:
        summary = result.get("directional_summary", {})
        if summary.get("mode") == "wide":
            table = result.get("variance_table", [])
            best = max((r for r in table if r.get("Variance (%)") is not None), key=lambda r: r["Variance (%)"], default=None)
            worst = min((r for r in table if r.get("Variance (%)") is not None), key=lambda r: r["Variance (%)"], default=None)
            label_key = next((k for k in table[0] if k not in ("Target (₦)", "Actual (₦)", "Variance (₦)", "Variance (%)", "Status", "direction")), "Entity") if table else "Entity"
            metrics = [
                Metric(label="Total above target", value=str(summary.get("above_target", 0)), formula_used="count where actual > target"),
                Metric(label="Total below target", value=str(summary.get("below_target", 0)), formula_used="count where actual < target"),
            ]
            if best:
                metrics.append(Metric(label="Best performer vs target", value=f"{best.get(label_key)} ({format_pct(best.get('Variance (%)'), signed=True)})", formula_used="max (actual − target) / target"))
            if worst:
                metrics.append(Metric(label="Worst performer vs target", value=f"{worst.get(label_key)} ({format_pct(worst.get('Variance (%)'), signed=True)})", formula_used="min (actual − target) / target"))
            return metrics

        avg = summary.get("average_variance_pct")
        if avg is None:
            return []
        return [Metric(label="Average variance vs target", value=format_pct(avg, signed=True), formula_used="(actual − target) / target × 100")]

    # -- insights (real computed observations) ------------------------------

    @staticmethod
    def _naira0(value) -> str:
        """Whole-naira display for prose insights: ₦573,750,000 (no kobo)."""
        number = to_jsonable(value)
        if not isinstance(number, (int, float)):
            return "—"
        return f"₦{number:,.0f}"

    def _money(self, value, is_currency: bool) -> str:
        number = to_jsonable(value)
        if not isinstance(number, (int, float)):
            return "—"
        return self._naira0(number) if is_currency else f"{number:,.0f}"

    def _growth_insights(self, result) -> list[str]:
        summary = result.get("directional_summary", {})
        wide = result.get("wide_growth", {})
        if summary.get("mode") != "wide":
            avg = summary.get("average_growth_pct")
            if avg is None:
                return []
            return [f"Average period-over-period growth was {format_pct(avg, signed=True)} across {summary.get('up', 0)} rising and {summary.get('down', 0)} falling periods."]

        is_currency = bool(wide.get("is_currency"))
        periods = wide.get("periods", [])
        value_rows = wide.get("value_rows", [])
        group_col = wide.get("group_col", "Group")
        out: list[str] = []

        best = summary.get("best_branch")
        best_row = next((r for r in value_rows if str(r.get(group_col)) == str(best)), None)
        if best_row and periods:
            first_v = self._money(best_row.get(periods[0]), is_currency)
            last_v = self._money(best_row.get(periods[-1]), is_currency)
            out.append(f"{best} recorded the strongest growth at {format_pct(summary.get('best_branch_growth'), signed=True)}, rising from {first_v} in {periods[0]} to {last_v} in {periods[-1]}.")
        if summary.get("average_growth_pct") is not None:
            out.append(f"Average month-over-month growth across all {summary.get('branch_count', 0)} branches was {format_pct(summary['average_growth_pct'], signed=True)}.")
        if summary.get("highest_growth_month") and summary.get("lowest_growth_month"):
            out.append(f"Growth peaked in {summary['highest_growth_month']} ({format_pct(summary.get('highest_growth_value'), signed=True)}) and was weakest in {summary['lowest_growth_month']} ({format_pct(summary.get('lowest_growth_value'), signed=True)}).")
        pos, count = summary.get("positive_branches", 0), summary.get("branch_count", 0)
        out.append(f"{pos} of {count} branches grew over the period; {count - pos} were flat or declining.")
        worst = summary.get("worst_branch")
        if worst and worst != best:
            out.append(f"{worst} lagged the field with overall growth of {format_pct(summary.get('worst_branch_growth'), signed=True)}.")
        return out

    def _variance_insights(self, result) -> list[str]:
        summary = result.get("directional_summary", {})
        table = result.get("variance_table") or []
        if summary.get("mode") != "wide" or not table:
            return []
        label_key = next((k for k in table[0] if k not in ("Target (₦)", "Actual (₦)", "Variance (₦)", "Variance (%)", "Status", "direction")), "Entity")
        total = len(table)
        below = summary.get("below_target", 0)
        out: list[str] = []
        best = max((r for r in table if r.get("Variance (%)") is not None), key=lambda r: r["Variance (%)"], default=None)
        worst = min((r for r in table if r.get("Variance (%)") is not None), key=lambda r: r["Variance (%)"], default=None)
        if best:
            out.append(f"{best.get(label_key)} leads with {self._naira0(best.get('Actual (₦)'))} in actuals, {format_pct(best.get('Variance (%)'), signed=True)} versus its {self._naira0(best.get('Target (₦)'))} target.")
        out.append(f"{below} of {total} branches are below target.")
        if worst and worst.get("Variance (%)") is not None and worst["Variance (%)"] < 0:
            out.append(f"{worst.get(label_key)} has the largest gap at {format_pct(worst.get('Variance (%)'), signed=True)} ({self._naira0(worst.get('Variance (₦)'))}).")
        if summary.get("average_variance_pct") is not None:
            out.append(f"Average variance vs target across all branches is {format_pct(summary['average_variance_pct'], signed=True)}.")
        return out

    def _rank_insights(self, result) -> list[str]:
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        ranked_by = result.get("ranked_by")
        if not rows or ranked_by not in columns:
            return []
        is_currency = ranked_by in set(result.get("currency_columns", [])) or is_currency_column(ranked_by)
        m_idx = columns.index(ranked_by)
        e_idx = next((i for i, c in enumerate(columns) if c not in ("Rank", ranked_by) and isinstance(rows[0][i], str)), None)
        if e_idx is None:
            return []
        values = [r[m_idx] for r in rows if isinstance(r[m_idx], (int, float))]
        total = sum(values) if values else 0
        out = [f"{rows[0][e_idx]} leads with {self._money(rows[0][m_idx], is_currency)} in {self._pretty(ranked_by)}."]
        if total and isinstance(rows[0][m_idx], (int, float)):
            out.append(f"The top entry alone represents {rows[0][m_idx] / total * 100:.1f}% of the {self._money(total, is_currency)} total across {len(rows)} entries.")
        if len(rows) > 1 and isinstance(rows[-1][m_idx], (int, float)):
            out.append(f"{rows[-1][e_idx]} sits at the bottom with {self._money(rows[-1][m_idx], is_currency)}.")
        return out

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
            image_path = result.get("image_path") or ""
            print(f"[packager] Chart path: {image_path}")
            charts.append(Chart(
                chart_id=result.get("operation_id", "chart"),
                chart_type=result.get("chart_type", "bar"),
                title=result.get("title", ""),
                image_path=image_path,
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
