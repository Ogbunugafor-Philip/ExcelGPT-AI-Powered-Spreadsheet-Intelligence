"""Tests for the Phase 4 computation engine — accuracy and edge cases."""

import numpy as np
import pandas as pd
import pytest

from schemas.cerebras_schema import ActionPlan, NigerianContext, Operation
from services.computation_router import ComputationRouter
from services.modules.aggregation import AggregationModule
from services.modules.forecasting import ForecastingModule
from services.modules.growth import GrowthModule
from services.modules.scoring import ScoringModule
from services.modules.statistical import StatisticalModule


def op(operation_type, **kwargs):
    defaults = dict(
        operation_id="op_1",
        operation_type=operation_type,
        target_sheet="Sheet1",
        target_columns=kwargs.pop("target_columns", []),
        group_by=kwargs.pop("group_by", []),
        parameters=kwargs.pop("parameters", {}),
        output_sheet=kwargs.pop("output_sheet", "analysis"),
        output_label=kwargs.pop("output_label", "Test"),
    )
    return Operation(**defaults)


@pytest.fixture
def banking_df():
    return pd.DataFrame({
        "branch": ["Lagos", "Abuja", "PH", "Lagos", "Abuja", "PH"],
        "zone": ["SW", "NC", "SS", "SW", "NC", "SS"],
        "deposits_ngn": [5_000_000, 3_200_000, 8_100_000, 6_000_000, 3_500_000, 9_000_000],
        "month": ["2026-01", "2026-01", "2026-01", "2026-02", "2026-02", "2026-02"],
    })


# -- aggregation ------------------------------------------------------------

def test_group_sum_totals_are_correct(banking_df):
    result = AggregationModule().execute(op("group_sum", target_columns=["deposits_ngn"], group_by=["branch"]), banking_df)
    totals = {row[0]: row[1] for row in result["rows"]}
    assert totals["Lagos"] == 11_000_000
    assert totals["PH"] == 17_100_000
    assert result["summary_stats"]["total_deposits_ngn"] == 34_800_000


def test_rank_top_n_and_rank_column(banking_df):
    result = AggregationModule().execute(
        op("rank", target_columns=["deposits_ngn"], parameters={"by": "deposits_ngn", "order": "desc", "top_n": 2}),
        banking_df,
    )
    assert len(result["rows"]) == 2
    assert result["columns"][0] == "Rank"
    assert result["rows"][0][0] == 1  # first rank
    # highest single deposit row is PH 9,000,000
    assert result["rows"][0][result["columns"].index("deposits_ngn")] == 9_000_000


def test_aggregation_empty_dataframe_warns():
    result = AggregationModule().execute(op("group_sum", target_columns=["x"], group_by=["g"]), pd.DataFrame())
    assert result["rows"] == []
    assert result["warnings"]


# -- growth -----------------------------------------------------------------

def test_growth_rate_matches_formula(banking_df):
    result = GrowthModule().execute(op("growth_rate", target_columns=["deposits_ngn"], group_by=["branch"]), banking_df)
    cols = result["columns"]
    lagos = [dict(zip(cols, r)) for r in result["rows"] if r[cols.index("branch")] == "Lagos"]
    feb = next(r for r in lagos if r["period"] == "2026-02")
    # (6,000,000 - 5,000,000) / 5,000,000 * 100 = 20.0
    assert feb["growth_pct"] == 20.0
    assert feb["direction"] == "up"


def test_growth_division_by_zero_is_none():
    df = pd.DataFrame({"entity": ["a", "a"], "value": [0, 50], "month": ["2026-01", "2026-02"]})
    result = GrowthModule().execute(op("growth_rate", target_columns=["value"], group_by=["entity"]), df)
    feb = next(dict(zip(result["columns"], r)) for r in result["rows"] if dict(zip(result["columns"], r))["period"] == "2026-02")
    assert feb["growth_pct"] is None  # previous was 0 -> None, not an error


def test_variance_flags_under_and_over():
    df = pd.DataFrame({"branch": ["a", "b"], "target": [100, 100], "actual": [80, 130]})
    result = GrowthModule().execute(op("variance", target_columns=["actual"], parameters={"actual": "actual", "target": "target"}), df)
    rows = [dict(zip(result["columns"], r)) for r in result["rows"]]
    by_branch = {r["branch"]: r for r in rows}
    assert by_branch["a"]["variance_pct"] == -20.0 and by_branch["a"]["status"] == "underperformer"
    assert by_branch["b"]["variance_pct"] == 30.0 and by_branch["b"]["status"] == "overperformer"


# -- statistical ------------------------------------------------------------

def test_correlation_detects_strong_positive():
    rng = np.arange(50)
    df = pd.DataFrame({"a": rng + np.random.RandomState(0).normal(0, 0.01, 50), "b": rng * 2})
    result = StatisticalModule().execute(op("correlation"), df)
    assert result["result_type"] == "correlation"
    assert any(c["type"] == "strong_positive" for c in result["data"]["strong_correlations"])


def test_distribution_reports_stats():
    df = pd.DataFrame({"x": list(range(100))})
    result = StatisticalModule().execute(op("distribution"), df)
    dist = result["data"]["distributions"][0]
    assert dist["column"] == "x"
    assert "mean" in dist and "skewness" in dist and dist["shape"] in ("normal", "bimodal", "left_skewed", "right_skewed")


def test_outlier_iqr_flags_extreme_value():
    df = pd.DataFrame({"v": [10, 11, 12, 13, 12, 11, 10, 500]})
    result = StatisticalModule().execute(op("outlier"), df)
    assert result["data"]["outlier_count"] >= 1
    assert any(o["direction"] == "high" for o in result["data"]["outliers"])


# -- scoring ----------------------------------------------------------------

def test_score_assigns_tiers(banking_df):
    result = ScoringModule().execute(op("score", target_columns=["deposits_ngn"]), banking_df)
    assert "Score" in result["columns"] and "Tier" in result["columns"]
    top = result["rows"][0]
    assert top[result["columns"].index("Tier")] == "Top"  # highest deposits -> normalised 100


def test_cluster_reduces_k_to_row_count():
    df = pd.DataFrame({"a": [1.0, 100.0], "b": [2.0, 200.0]})
    result = ScoringModule().execute(op("cluster", parameters={"n_clusters": 5}), df)
    assert "Cluster" in result["columns"]
    assert result["summary_stats"]["n_clusters"] == 2  # reduced to 2 rows


# -- forecasting ------------------------------------------------------------

def test_forecast_requires_six_points():
    df = pd.DataFrame({"month": ["2026-01", "2026-02", "2026-03"], "value": [1, 2, 3]})
    result = ForecastingModule().execute(op("forecast", target_columns=["value"]), df)
    assert "error" in result and result["projected"] == []


def test_forecast_projects_three_periods():
    months = pd.date_range("2024-01-01", periods=18, freq="MS").strftime("%Y-%m").tolist()
    df = pd.DataFrame({"month": months, "value": [100 + i * 10 for i in range(18)]})
    result = ForecastingModule().execute(op("forecast", target_columns=["value"], parameters={"periods": 3}), df)
    assert len(result["projected"]) == 3
    assert len(result["confidence_upper"]) == 3 and len(result["confidence_lower"]) == 3
    assert result["model_used"] in ("ExponentialSmoothing", "SARIMAX", "naive")


# -- router + packager end-to-end (offline, no Cerebras) --------------------

def test_router_end_to_end(tmp_path):
    df = pd.DataFrame({
        "branch": ["Lagos", "Abuja", "PH", "Lagos", "Abuja", "PH"],
        "deposits_ngn": [5_000_000, 3_200_000, 8_100_000, 6_000_000, 3_500_000, 9_000_000],
        "month": ["2026-01", "2026-01", "2026-01", "2026-02", "2026-02", "2026-02"],
    })
    file_path = tmp_path / "branches.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)

    plan = ActionPlan(
        intent_type="aggregation",
        operations=[
            op("rank", operation_id="op_1", target_columns=["deposits_ngn"],
               parameters={"by": "deposits_ngn", "order": "desc", "top_n": 5}, output_label="Top branches"),
            op("growth_rate", operation_id="op_2", target_columns=["deposits_ngn"],
               group_by=["branch"], output_label="Monthly growth"),
            op("chart", operation_id="op_3", target_columns=["branch", "deposits_ngn"],
               parameters={"chart_type": "bar", "x": "branch", "y": "deposits_ngn"},
               output_sheet="charts", output_label="Deposits by branch"),
        ],
        output_sheets_required=["executive_summary", "analysis", "charts"],
        nigerian_context=NigerianContext(template_type="banking"),
    )
    session = {
        "session_id": "test-session",
        "file_path": str(file_path),
        "intelligence_brief": {"filename": "branches.xlsx"},
        "instruction": "Top 5 branches by deposits and monthly growth",
        "version": 1,
    }

    output = ComputationRouter().route(plan, session)

    assert output.executive_summary.kpi_cards, "expected KPI cards"
    assert output.analysis_sheet.rankings, "expected ranked rows"
    assert output.analysis_sheet.growth_table, "expected growth rows"
    assert any(r.get("direction") in ("up", "down", "neutral") for r in output.analysis_sheet.growth_table)
    assert len(output.charts) == 1
    assert output.charts[0].image_path and output.charts[0].recharts_data
