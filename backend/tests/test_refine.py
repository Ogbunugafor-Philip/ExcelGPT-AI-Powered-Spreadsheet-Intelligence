"""Tests for the Phase 7 feedback & refinement loop (POST /refine)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main
from schemas.cerebras_schema import ActionPlan, NigerianContext, Operation


def _op(operation_type, **kwargs):
    return Operation(
        operation_id=kwargs.get("operation_id", "op_1"),
        operation_type=operation_type,
        target_sheet="Branch Data",
        target_columns=kwargs.get("target_columns", []),
        group_by=kwargs.get("group_by", []),
        parameters=kwargs.get("parameters", {}),
        output_sheet=kwargs.get("output_sheet", "analysis"),
        output_label=kwargs.get("output_label", "Test"),
    )


def _plan(operations, intent_type="aggregation", required=("executive_summary", "analysis")):
    return ActionPlan(
        intent_type=intent_type,
        operations=operations,
        output_sheets_required=list(required),
        nigerian_context=NigerianContext(template_type="banking"),
    )


# Canned plans so /analyse and /refine never touch the real Cerebras service.
RANK_PLAN = _plan([
    _op("rank", operation_id="op_1", target_columns=["deposits_ngn"],
        parameters={"by": "deposits_ngn", "order": "desc", "top_n": 5}, output_label="Top branches"),
])
GROWTH_PLAN = _plan([
    _op("rank", operation_id="op_1", target_columns=["deposits_ngn"],
        parameters={"by": "deposits_ngn", "order": "desc", "top_n": 5}, output_label="Top branches"),
    _op("growth_rate", operation_id="op_2", target_columns=["deposits_ngn"],
        group_by=["branch"], output_label="Monthly growth"),
])
FORECAST_PLAN = _plan([
    _op("forecast", operation_id="op_1", target_columns=["deposits_ngn"],
        parameters={"periods": 3}, output_sheet="forecast", output_label="3-month forecast"),
], intent_type="forecasting", required=("executive_summary", "forecast"))


@pytest.fixture
def banking_file(tmp_path):
    months = pd.date_range("2024-01-01", periods=12, freq="MS").strftime("%Y-%m").tolist()
    rows = []
    for i, month in enumerate(months):
        rows.append({"branch": "Lagos Island", "deposits_ngn": 150_000_000 + i * 5_000_000, "month": month})
        rows.append({"branch": "Abuja", "deposits_ngn": 120_000_000 + i * 3_000_000, "month": month})
    df = pd.DataFrame(rows)
    path = tmp_path / "branch_performance.xlsx"
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="Branch Data", index=False)
    return str(path)


@pytest.fixture
def session(banking_file):
    session_id = main.session_manager.create_session(
        file_path=banking_file,
        intelligence_brief={"filename": "branch_performance.xlsx"},
        sheet_data={},
        session_id="refine-test",
    )
    return session_id


@pytest.fixture
def client():
    return TestClient(main.app)


def _set_plans(monkeypatch, *plans):
    """Make intent_engine.classify return the given plans in order, repeating the last."""
    calls = {"n": 0}

    def fake_classify(_brief, _instruction):
        index = min(calls["n"], len(plans) - 1)
        calls["n"] += 1
        return plans[index]

    monkeypatch.setattr(main.intent_engine, "classify", fake_classify)


def _analyse(client, session_id, instruction="Top 5 branches by deposit volume"):
    return client.post("/analyse", json={"session_id": session_id, "instruction": instruction})


def _refine(client, session_id, feedback, history=None, current_version=1):
    return client.post("/refine", json={
        "session_id": session_id,
        "feedback": feedback,
        "history": history or [],
        "current_version": current_version,
    })


def test_refine_valid_session_returns_version_2(client, session, monkeypatch):
    _set_plans(monkeypatch, RANK_PLAN, GROWTH_PLAN)
    assert _analyse(client, session).json()["version"] == 1

    response = _refine(client, session, "Now add monthly growth rates", current_version=1)
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 2
    assert body["download_token"]
    # The refinement added growth data to the preview.
    assert body["preview"]["growth_table"]


def test_refine_invalid_session_returns_404(client):
    response = _refine(client, "does-not-exist", "add a forecast", current_version=1)
    assert response.status_code == 404


def test_version_increments_across_multiple_refinements(client, session, monkeypatch):
    _set_plans(monkeypatch, RANK_PLAN, GROWTH_PLAN, GROWTH_PLAN, FORECAST_PLAN)
    assert _analyse(client, session).json()["version"] == 1

    versions = []
    for i, feedback in enumerate(["add growth", "highlight underperformers", "add a 3-month forecast"], start=1):
        body = _refine(client, session, feedback, current_version=i).json()
        versions.append(body["version"])
    assert versions == [2, 3, 4]


def test_session_stores_multiple_versions_independently(client, session, monkeypatch):
    _set_plans(monkeypatch, RANK_PLAN, GROWTH_PLAN, FORECAST_PLAN)
    tokens = [_analyse(client, session).json()["download_token"]]
    tokens.append(_refine(client, session, "add growth", current_version=1).json()["download_token"])
    tokens.append(_refine(client, session, "add a 3-month forecast", current_version=2).json()["download_token"])

    # Three versions stored, each with a unique download token.
    assert main.session_manager.get_version_count(session) == 3
    assert len(set(tokens)) == 3

    v1 = main.session_manager.get_version(session, 1)
    v2 = main.session_manager.get_version(session, 2)
    v3 = main.session_manager.get_version(session, 3)
    assert v1.version == 1 and v2.version == 2 and v3.version == 3
    # Versions are independent objects: v2 has growth that v1 does not.
    assert not v1.analysis_sheet.growth_table
    assert v2.analysis_sheet.growth_table
    # v3 carries a forecast series that v1 lacks.
    assert v3.forecast_sheet.projected
    assert not v1.forecast_sheet.projected


def test_refine_download_token_resolves_to_its_version(client, session, monkeypatch):
    _set_plans(monkeypatch, RANK_PLAN, FORECAST_PLAN)
    _analyse(client, session)
    token = _refine(client, session, "add a 3-month forecast", current_version=1).json()["download_token"]

    # The forecast version downloads as a workbook containing a Forecast sheet.
    response = client.get(f"/download/{token}")
    assert response.status_code == 200
    assert response.content[:2] == b"PK"
