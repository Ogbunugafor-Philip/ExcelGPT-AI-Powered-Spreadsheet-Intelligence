"""Render charts to PNG (matplotlib) and emit Recharts-ready data for the frontend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless rendering — no display needed on the server.

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402

from .common import coerce_numeric, numeric_columns, to_jsonable  # noqa: E402
from ..semantics import suggest_display_name  # noqa: E402

PALETTE = config.COLOR_PALETTE


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
            "title": operation.output_label or "Chart",
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
            result["title"] = f"{y_label} by {x_label}".strip(" by")
        result["x_label"] = x_label
        result["y_label"] = y_label

        charts_dir = Path(output_dir).resolve()
        charts_dir.mkdir(parents=True, exist_ok=True)
        image_path = (charts_dir / f"{operation.operation_id}.png").resolve()

        try:
            recharts = self._render(chart_type, df, x_col, y_col, result["title"], str(image_path), x_label, y_label)
            # Verify the PNG actually landed before handing the path downstream.
            assert image_path.exists(), f"chart PNG was not written: {image_path}"
            print(f"Chart saved: {image_path} ({image_path.stat().st_size} bytes)")
            result["image_path"] = str(image_path)  # absolute path for openpyxl embedding
            result["recharts_data"] = recharts
        except Exception as exc:  # noqa: BLE001 — a chart failure must not abort the report
            plt.close("all")
            result["warnings"].append(f"Chart rendering failed: {exc}")
            print(f"Chart FAILED for {operation.operation_id}: {exc}")
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

    def _render(self, chart_type, df, x_col, y_col, title, image_path, x_label="", y_label="") -> list[dict[str, Any]]:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        fig.patch.set_facecolor(PALETTE["navy"])
        ax.set_facecolor(PALETTE["navy"])
        for spine in ax.spines.values():
            spine.set_color(PALETTE["text_secondary"])
        ax.tick_params(colors=PALETTE["text_secondary"])
        ax.title.set_color(PALETTE["text_primary"])
        ax.xaxis.label.set_color(PALETTE["text_secondary"])
        ax.yaxis.label.set_color(PALETTE["text_secondary"])
        ax.set_title(title, fontsize=13, fontweight="bold")

        if chart_type == "pie":
            recharts = self._pie(ax, df, x_col, y_col, x_label, y_label)
        elif chart_type == "line":
            recharts = self._line(ax, df, x_col, y_col, x_label, y_label)
        elif chart_type == "scatter":
            recharts = self._scatter(ax, df, x_col, y_col, x_label, y_label)
        else:
            recharts = self._bar(ax, df, x_col, y_col, x_label, y_label)

        fig.tight_layout()
        fig.savefig(image_path, dpi=130, facecolor=fig.get_facecolor())
        plt.close(fig)
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

    def _bar(self, ax, df, x_col, y_col, x_label="", y_label=""):
        # Rankings read best as HORIZONTAL bars — entity names sit on the Y axis.
        frame = self._prepare_xy(df, x_col, y_col).sort_values("y")
        colors = self._rank_colors(list(frame["y"]))
        ax.barh(frame["x"], frame["y"], color=colors)
        ax.set_xlabel(y_label or y_col)
        for index, value in enumerate(frame["y"]):
            ax.text(value, index, f" {value:,.0f}", va="center", color=PALETTE["text_primary"], fontsize=8)
        return [self._point(name, value, x_label, y_label) for name, value in zip(frame["x"], frame["y"])]

    def _line(self, ax, df, x_col, y_col, x_label="", y_label=""):
        y = coerce_numeric(df[y_col])
        frame = pd.DataFrame({"x": df[x_col].astype(str) if x_col else range(len(df)), "y": y}).dropna(subset=["y"])
        ax.plot(frame["x"], frame["y"], marker="o", color=PALETTE["blue_glow"], linewidth=2)
        ax.fill_between(range(len(frame)), frame["y"], color=PALETTE["blue_electric"], alpha=0.18)
        ax.grid(True, color=PALETTE["text_secondary"], alpha=0.2)
        ax.set_xlabel(x_label or x_col or "index")
        ax.set_ylabel(y_label or y_col)
        if len(frame) > 8:
            ax.set_xticks(ax.get_xticks()[::2])
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
        return [self._point(name, value, x_label, y_label) for name, value in zip(frame["x"], frame["y"])]

    def _pie(self, ax, df, x_col, y_col, x_label="", y_label=""):
        frame = self._prepare_xy(df, x_col, y_col, limit=8)
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
        ax.grid(True, color=PALETTE["text_secondary"], alpha=0.2)
        ax.set_xlabel(x_label or x_col or "index")
        ax.set_ylabel(y_label or y_col)
        return [
            {"x": to_jsonable(xv), "y": to_jsonable(yv), "displayName": y_label or "Value", "categoryName": x_label or "X"}
            for xv, yv in zip(frame["x"], frame["y"])
        ]
