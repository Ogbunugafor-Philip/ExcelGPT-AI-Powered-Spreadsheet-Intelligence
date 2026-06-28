"""Time-series forecasting with statsmodels (ExponentialSmoothing / SARIMAX)."""

from __future__ import annotations

import warnings as _warnings
from typing import Any

import numpy as np
import pandas as pd

from schemas.cerebras_schema import Operation

from .common import coerce_numeric, detect_date_column, to_jsonable

MIN_POINTS = 6
SHORT_SERIES_LIMIT = 24  # below this -> ExponentialSmoothing; at/above -> SARIMAX


class ForecastingModule:
    def execute(self, operation: Operation, df: pd.DataFrame) -> dict[str, Any]:
        params = operation.parameters or {}
        periods = self._int(params.get("periods"), default=3)

        base = {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type,
            "label": operation.output_label,
            "historical": [],
            "projected": [],
            "confidence_upper": [],
            "confidence_lower": [],
            "model_used": None,
            "assumptions": [],
            "warnings": [],
        }

        if df.empty:
            base["error"] = "Empty dataframe — nothing to forecast."
            return base

        date_col = detect_date_column(df, prefer=operation.target_columns)
        value_col = self._value_column(operation, df, exclude=date_col)
        if value_col is None:
            base["error"] = "No numeric value column found to forecast."
            return base

        series, period_labels = self._build_series(df, date_col, value_col, base)
        if len(series) < MIN_POINTS:
            base["error"] = f"Need at least {MIN_POINTS} data points to forecast; got {len(series)}."
            base["historical"] = [
                {"period": p, "value": to_jsonable(v)} for p, v in zip(period_labels, series.tolist())
            ]
            return base

        y = series.astype(float).to_numpy()
        future_labels = self._future_labels(period_labels, periods)

        try:
            mean, lower, upper, model_used, assumptions = self._forecast(y, periods)
        except Exception as exc:  # noqa: BLE001 — fall back to a naive forecast rather than crash
            base["warnings"].append(f"Model fitting failed ({exc}); used naive last-value forecast.")
            mean, lower, upper, model_used, assumptions = self._naive(y, periods)

        base["model_used"] = model_used
        base["assumptions"] = assumptions
        base["historical"] = [{"period": p, "value": to_jsonable(v)} for p, v in zip(period_labels, y.tolist())]
        base["projected"] = [{"period": p, "value": to_jsonable(round(v, 2))} for p, v in zip(future_labels, mean)]
        base["confidence_upper"] = [{"period": p, "value": to_jsonable(round(v, 2))} for p, v in zip(future_labels, upper)]
        base["confidence_lower"] = [{"period": p, "value": to_jsonable(round(v, 2))} for p, v in zip(future_labels, lower)]
        return base

    # -- series construction ------------------------------------------------

    def _value_column(self, operation, df, exclude):
        for column in operation.target_columns:
            if column != exclude and column in df.columns and coerce_numeric(df[column]).notna().sum() > 0:
                return column
        for column in df.columns:
            if column != exclude and coerce_numeric(df[column]).notna().sum() > 0:
                return column
        return None

    def _build_series(self, df, date_col, value_col, base):
        values = coerce_numeric(df[value_col])
        if date_col:
            periods = pd.to_datetime(df[date_col], errors="coerce")
            frame = pd.DataFrame({"period": periods, "value": values}).dropna(subset=["period"])
            # Sum duplicate periods (e.g. many branches per month) into one series point.
            grouped = frame.groupby("period")["value"].sum().sort_index()
            labels = [p.strftime("%Y-%m") for p in grouped.index]
            return grouped.reset_index(drop=True), labels
        base["warnings"].append("No date column detected — treating rows as an ordered sequence.")
        clean = values.dropna().reset_index(drop=True)
        return clean, [f"P{i + 1}" for i in range(len(clean))]

    def _future_labels(self, period_labels, periods):
        last = period_labels[-1] if period_labels else "P0"
        # Try to continue a YYYY-MM monthly sequence; otherwise use P+n labels.
        try:
            last_period = pd.Period(last, freq="M")
            return [str(last_period + i) for i in range(1, periods + 1)]
        except Exception:  # noqa: BLE001
            return [f"P+{i}" for i in range(1, periods + 1)]

    # -- models -------------------------------------------------------------

    def _forecast(self, y, periods):
        from statsmodels.tsa.stattools import adfuller

        # Stationarity check informs SARIMAX differencing.
        try:
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore")
                p_value = adfuller(y, autolag="AIC")[1]
            non_stationary = p_value > 0.05
        except Exception:  # noqa: BLE001
            non_stationary = True

        if len(y) < SHORT_SERIES_LIMIT:
            return self._exponential_smoothing(y, periods, non_stationary)
        return self._sarimax(y, periods, non_stationary)

    def _exponential_smoothing(self, y, periods, non_stationary):
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        trend = "add" if (non_stationary or self._has_trend(y)) else None
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            fit = ExponentialSmoothing(y, trend=trend, seasonal=None, initialization_method="estimated").fit()
            mean = np.asarray(fit.forecast(periods), dtype=float)
            resid = np.asarray(fit.resid, dtype=float)
        std_error = float(np.nanstd(resid, ddof=1)) if np.isfinite(resid).sum() > 1 else 0.0
        margin = 1.96 * std_error
        assumptions = [
            f"Holt-Winters Exponential Smoothing (trend={trend or 'none'})",
            f"{periods} periods ahead",
            "95% confidence (mean ± 1.96·residual std error)",
        ]
        return mean, mean - margin, mean + margin, "ExponentialSmoothing", assumptions

    def _sarimax(self, y, periods, non_stationary):
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        d = 1 if non_stationary else 0
        seasonal_order = (1, 1, 1, 12) if len(y) >= 24 else (0, 0, 0, 0)
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            fit = SARIMAX(
                y, order=(1, d, 1), seasonal_order=seasonal_order,
                enforce_stationarity=False, enforce_invertibility=False,
            ).fit(disp=False)
            forecast = fit.get_forecast(steps=periods)
            mean = np.asarray(forecast.predicted_mean, dtype=float)
            conf = np.asarray(forecast.conf_int(alpha=0.05), dtype=float)
        lower, upper = conf[:, 0], conf[:, 1]
        assumptions = [
            f"SARIMAX(1,{d},1)x{seasonal_order}",
            f"{periods} periods ahead",
            "95% confidence interval",
            "differencing applied" if d else "series treated as stationary",
        ]
        return mean, lower, upper, "SARIMAX", assumptions

    def _naive(self, y, periods):
        last = float(y[-1])
        std_error = float(np.nanstd(np.diff(y), ddof=1)) if len(y) > 2 else 0.0
        margin = 1.96 * std_error
        mean = np.full(periods, last, dtype=float)
        assumptions = ["Naive last-value carry-forward", f"{periods} periods ahead", "95% confidence from period-to-period std"]
        return mean, mean - margin, mean + margin, "naive", assumptions

    @staticmethod
    def _has_trend(y) -> bool:
        if len(y) < 3:
            return False
        slope = np.polyfit(np.arange(len(y)), y, 1)[0]
        return abs(slope) > (np.nanstd(y) / max(len(y), 1)) * 0.1

    @staticmethod
    def _int(value, default):
        try:
            result = int(value)
            return result if result > 0 else default
        except (TypeError, ValueError):
            return default
