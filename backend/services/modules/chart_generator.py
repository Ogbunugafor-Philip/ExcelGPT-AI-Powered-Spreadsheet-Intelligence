"""Render charts to PNG (matplotlib) and emit Recharts-ready data for the frontend."""

from __future__ import annotations

import os  # noqa: E402
import re  # noqa: E402
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless rendering — MUST be set before pyplot is imported.

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402

from .common import coerce_numeric, is_currency_column, numeric_columns, to_jsonable  # noqa: E402
from ..semantics import suggest_display_name  # noqa: E402

PALETTE = config.COLOR_PALETTE

# Dark "navy" chart theme (PROBLEM 6).
NAVY = "#0A0F1E"       # figure + axes background
WHITE = "#F9FAFB"      # text
GRID = "#1F2937"       # subtle grid lines
SPINE = "#374151"      # axis spines
BLUE = PALETTE["blue_electric"]   # deposits / primary series
AMBER = PALETTE["amber"]          # target series
EMERALD = PALETTE["emerald"]
RED = PALETTE["red_alert"]


def naira_fmt(x, pos=None) -> str:
    """Format an axis/label value as compact Naira: ₦1.4B, ₦573M, ₦25K."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return str(x)
    sign = "-" if x < 0 else ""
    v = abs(x)
    if v >= 1_000_000_000:
        return f"{sign}₦{v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{sign}₦{v / 1_000_000:.0f}M"
    if v >= 1_000:
        return f"{sign}₦{v / 1_000:.0f}K"
    return f"{sign}₦{v:.0f}"


def clean_title(title: Any) -> str:
    """Strip a redundant chart-type suffix and trailing currency tag.

    "Top 5 Branches by Deposits (₦)"     -> "Top 5 Branches by Deposits"
    "Top 5 Branch Deposits Bar Chart"     -> "Top 5 Branch Deposits"
    """
    text = str(title or "Chart").strip()
    text = re.sub(r"\s*\(₦\)\s*$", "", text)
    text = re.sub(r"\s*(bar|line|pie|scatter|area|column|horizontal|vertical)?\s*chart\s*$", "", text, flags=re.I)
    return text.strip() or "Chart"


def style_axes(fig, ax) -> None:
    """Apply the navy theme: dark canvas, white text, subtle grid, grey spines."""
    fig.patch.set_facecolor(NAVY)
    ax.set_facecolor(NAVY)
    for spine in ax.spines.values():
        spine.set_color(SPINE)
    ax.tick_params(colors=WHITE)
    ax.title.set_color(WHITE)
    ax.xaxis.label.set_color(WHITE)
    ax.yaxis.label.set_color(WHITE)
    ax.grid(True, color=GRID, alpha=0.5)


class ChartGenerator:
    def execute(self, operation, df: pd.DataFrame, output_dir: str) -> dict[str, Any]:
        params = operation.parameters or {}
        chart_type = str(params.get("chart_type", "bar")).lower()
        if chart_type not in ("bar", "line", "pie", "scatter"):
            chart_type = "bar"

        result: dict[str, Any] = {
            "operation_id": operation.operation_id,
            "operation_type": "chart",
            "chart_type": chart_type,
            "title": clean_title(operation.output_label or "Chart"),
            "image_path": None,
            "recharts_data": [],
            "warnings": [],
        }

        if df.empty:
            result["warnings"].append("Empty dataframe — no chart rendered.")
            return result

        x_col, y_col = self._resolve_axes(operation, df, chart_type, result)
        if y_col is None:
            result["warnings"].append("No numeric column available to plot.")
            return result

        x_label = suggest_display_name(x_col) if x_col else ""
        y_label = suggest_display_name(y_col) if y_col else ""
        # A clean fallback title if the planner did not supply a human label.
        if not operation.output_label:
            result["title"] = clean_title(f"{y_label} by {x_label}".strip(" by"))
        result["x_label"] = x_label
        result["y_label"] = y_label

        # PROBLEM 1 — respect the rank's top_n so the chart shows the top N only.
        top_n = params.get("top_n")
        limit = int(top_n) if isinstance(top_n, (int, float)) and top_n else 20

        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        image_path = os.path.join(output_dir, f"{operation.operation_id}.png")

        try:
            diverging = bool(params.get("diverging"))
            recharts = self._render(chart_type, df, x_col, y_col, result["title"], image_path,
                                    x_label, y_label, diverging=diverging, limit=limit)
            # Verify the PNG actually landed, and is not an empty/blank file.
            if not os.path.exists(image_path):
                raise RuntimeError(f"Chart file was not created: {image_path}")
            file_size = os.path.getsize(image_path)
            if file_size < 1000:
                raise RuntimeError(f"Chart file too small ({file_size} bytes), likely empty: {image_path}")
            print(f"[chart_generator] Saved chart: {image_path} ({file_size:,} bytes)")
            result["image_path"] = image_path  # absolute path for openpyxl embedding
            result["recharts_data"] = recharts
        except Exception as exc:  # noqa: BLE001 — a chart failure must not abort the report
            plt.close("all")
            result["warnings"].append(f"Chart rendering failed: {exc}")
            print(f"[chart_generator] FAILED for {operation.operation_id}: {exc}")
        return result

    # -- axis resolution ----------------------------------------------------

    def _resolve_axes(self, operation, df, chart_type, result):
        params = operation.parameters or {}
        numeric = numeric_columns(df)
        x_col = params.get("x")
        y_col = params.get("y")

        if y_col not in df.columns or y_col not in numeric:
            y_col = next((c for c in operation.target_columns if c in numeric), None) or (numeric[0] if numeric else None)
        if x_col not in df.columns:
            non_numeric = [c for c in df.columns if c not in numeric]
            x_col = non_numeric[0] if non_numeric else (df.columns[0] if len(df.columns) else None)
        return x_col, y_col

    # -- rendering ----------------------------------------------------------

    def _prepare_xy(self, df, x_col, y_col, limit=20):
        y = coerce_numeric(df[y_col])
        frame = pd.DataFrame({"x": df[x_col].astype(str) if x_col else range(len(df)), "y": y}).dropna(subset=["y"])
        if x_col and frame["x"].duplicated().any():
            frame = frame.groupby("x", as_index=False)["y"].sum()
        frame = frame.sort_values("y", ascending=False).head(limit)
        return frame

    def _render(self, chart_type, df, x_col, y_col, title, image_path, x_label="", y_label="", diverging=False, limit=20) -> list[dict[str, Any]]:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        style_axes(fig, ax)
        ax.set_title(title, fontsize=13, fontweight="bold")
        is_currency = is_currency_column(y_col)

        if chart_type == "pie":
            recharts = self._pie(ax, df, x_col, y_col, x_label, y_label, limit=min(limit, 8))
        elif chart_type == "line":
            recharts = self._line(ax, df, x_col, y_col, x_label, y_label, is_currency=is_currency)
        elif chart_type == "scatter":
            recharts = self._scatter(ax, df, x_col, y_col, x_label, y_label)
        else:
            recharts = self._bar(ax, df, x_col, y_col, x_label, y_label, diverging=diverging,
                                 limit=limit, is_currency=is_currency)

        fig.tight_layout()
        fig.savefig(image_path, dpi=150, bbox_inches="tight", facecolor=NAVY)
        plt.close("all")
        return recharts

    @staticmethod
    def _rank_colors(values: list[float]) -> list[str]:
        """Top performer gold, bottom red, the rest electric blue."""
        colors = [PALETTE["blue_electric"]] * len(values)
        if not values:
            return colors
        top = int(np.argmax(values))
        bottom = int(np.argmin(values))
        colors[top] = PALETTE["gold"]
        if bottom != top:
            colors[bottom] = PALETTE["red_alert"]
        return colors

    def _point(self, name, value, x_label, y_label):
        """Recharts-ready point carrying both raw values and display labels."""
        return {
            "name": str(name),
            "label": str(name),
            "value": to_jsonable(value),
            "displayName": y_label or "Value",
            "categoryName": x_label or "Category",
        }

    def _bar(self, ax, df, x_col, y_col, x_label="", y_label="", diverging=False, limit=20, is_currency=True):
        # Rankings read best as HORIZONTAL bars — entity names sit on the Y axis.
        frame = self._prepare_xy(df, x_col, y_col, limit=limit).sort_values("y")
        if diverging:
            # Variance charts: positive bars green, negative bars red.
            colors = [EMERALD if v >= 0 else RED for v in frame["y"]]
            ax.axvline(0, color=WHITE, linewidth=0.8)
        else:
            colors = self._rank_colors(list(frame["y"]))
        bars = ax.barh(frame["x"], frame["y"], color=colors)
        ax.set_xlabel(y_label or y_col)
        if is_currency:
            ax.xaxis.set_major_formatter(mticker.FuncFormatter(naira_fmt))
        # Formatted data labels at the end of each bar.
        for bar in bars:
            width = bar.get_width()
            label = naira_fmt(width) if is_currency else f"{width:,.0f}"
            ax.text(width, bar.get_y() + bar.get_height() / 2, f" {label}",
                    ha="left", va="center", color=WHITE, fontsize=9, fontweight="bold")
        return [self._point(name, value, x_label, y_label) for name, value in zip(frame["x"], frame["y"])]

    def _line(self, ax, df, x_col, y_col, x_label="", y_label="", is_currency=True):
        y = coerce_numeric(df[y_col])
        frame = pd.DataFrame({"x": df[x_col].astype(str) if x_col else range(len(df)), "y": y}).dropna(subset=["y"])
        ax.plot(frame["x"], frame["y"], marker="o", color=BLUE, linewidth=2)
        ax.fill_between(range(len(frame)), frame["y"], color=BLUE, alpha=0.18)
        ax.set_xlabel(x_label or x_col or "index")
        ax.set_ylabel(y_label or y_col)
        if is_currency:
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(naira_fmt))
        if len(frame) > 8:
            ax.set_xticks(ax.get_xticks()[::2])
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
        return [self._point(name, value, x_label, y_label) for name, value in zip(frame["x"], frame["y"])]

    def _pie(self, ax, df, x_col, y_col, x_label="", y_label="", limit=8):
        frame = self._prepare_xy(df, x_col, y_col, limit=limit)
        values = frame["y"].clip(lower=0)
        explode = [0.08 if i == int(np.argmax(values.to_numpy())) else 0 for i in range(len(values))]
        colors = [PALETTE["blue_electric"], PALETTE["blue_glow"], PALETTE["emerald"], PALETTE["gold"],
                  PALETTE["amber"], PALETTE["red_alert"], PALETTE["text_secondary"], PALETTE["navy_light"]]
        ax.pie(values, labels=frame["x"], autopct="%1.1f%%", startangle=90, explode=explode,
               colors=colors[: len(values)], textprops={"color": PALETTE["text_primary"], "fontsize": 8})
        ax.axis("equal")
        return [self._point(name, value, x_label, y_label) for name, value in zip(frame["x"], frame["y"])]

    def _scatter(self, ax, df, x_col, y_col, x_label="", y_label=""):
        x_numeric = coerce_numeric(df[x_col]) if x_col else pd.Series(range(len(df)))
        y_numeric = coerce_numeric(df[y_col])
        frame = pd.DataFrame({"x": x_numeric, "y": y_numeric}).dropna()
        ax.scatter(frame["x"], frame["y"], color=PALETTE["blue_glow"], alpha=0.7)
        if len(frame) >= 2:
            slope, intercept = np.polyfit(frame["x"], frame["y"], 1)
            line_x = np.linspace(frame["x"].min(), frame["x"].max(), 50)
            ax.plot(line_x, slope * line_x + intercept, color=PALETTE["emerald"], linewidth=2, label="trend")
            ax.legend(facecolor=PALETTE["navy_light"], labelcolor=PALETTE["text_primary"])
        ax.grid(True, color=GRID, alpha=0.5)
        ax.set_xlabel(x_label or x_col or "index")
        ax.set_ylabel(y_label or y_col)
        return [
            {"x": to_jsonable(xv), "y": to_jsonable(yv), "displayName": y_label or "Value", "categoryName": x_label or "X"}
            for xv, yv in zip(frame["x"], frame["y"])
        ]

    # -- comparison line chart (deposits vs target) -------------------------

    def comparison(self, operation, df: pd.DataFrame, output_dir: str,
                   entity_col: str, value_col: str, target_col: str) -> dict[str, Any]:
        """Public entry for the auto-generated Deposits-vs-Target line chart."""
        result: dict[str, Any] = {
            "operation_id": operation.operation_id,
            "operation_type": "chart",
            "chart_type": "line",
            "title": clean_title(operation.output_label or "Deposits vs Target"),
            "image_path": None,
            "recharts_data": [],
            "warnings": [],
        }
        if df.empty or entity_col not in df.columns or value_col not in df.columns or target_col not in df.columns:
            result["warnings"].append("Comparison chart needs entity, value and target columns.")
            return result

        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        image_path = os.path.join(output_dir, f"{operation.operation_id}.png")
        try:
            recharts = self._build_comparison_line_chart(df, entity_col, value_col, target_col,
                                                         result["title"], image_path)
            if not os.path.exists(image_path):
                raise RuntimeError(f"Chart file was not created: {image_path}")
            file_size = os.path.getsize(image_path)
            if file_size < 1000:
                raise RuntimeError(f"Chart file too small ({file_size} bytes): {image_path}")
            print(f"[chart_generator] Saved comparison chart: {image_path} ({file_size:,} bytes)")
            result["image_path"] = image_path
            result["recharts_data"] = recharts
        except Exception as exc:  # noqa: BLE001
            plt.close("all")
            result["warnings"].append(f"Comparison chart failed: {exc}")
            print(f"[chart_generator] FAILED comparison for {operation.operation_id}: {exc}")
        return result

    def _build_comparison_line_chart(self, df, entity_col, value_col, target_col, title, output_path) -> list[dict[str, Any]]:
        names = [str(v) for v in df[entity_col].tolist()]
        deposits = coerce_numeric(df[value_col]).to_numpy(dtype=float)
        targets = coerce_numeric(df[target_col]).to_numpy(dtype=float)
        idx = list(range(len(names)))

        fig, ax = plt.subplots(figsize=(9, 5))
        style_axes(fig, ax)
        ax.set_title(title, fontsize=13, fontweight="bold")

        ax.plot(idx, deposits, marker="o", color=BLUE, linewidth=2.2, label="Deposits", zorder=3)
        ax.plot(idx, targets, marker="s", color=AMBER, linewidth=2, linestyle="--", label="Target", zorder=3)

        # Shade the gap: green where deposits beat target, red where they fall short.
        ax.fill_between(idx, deposits, targets, where=deposits >= targets, interpolate=True,
                        color=EMERALD, alpha=0.25, zorder=1)
        ax.fill_between(idx, deposits, targets, where=deposits < targets, interpolate=True,
                        color=RED, alpha=0.25, zorder=1)

        ax.set_xticks(idx)
        ax.set_xticklabels(names, rotation=30, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(naira_fmt))
        legend = ax.legend(facecolor=NAVY, edgecolor=SPINE, labelcolor=WHITE, loc="best")
        legend.get_frame().set_alpha(0.9)

        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=NAVY)
        plt.close("all")
        return [
            {"name": n, "label": n, "Deposits": to_jsonable(d), "Target": to_jsonable(t),
             "displayName": "Deposits vs Target", "categoryName": entity_col}
            for n, d, t in zip(names, deposits.tolist(), targets.tolist())
        ]
