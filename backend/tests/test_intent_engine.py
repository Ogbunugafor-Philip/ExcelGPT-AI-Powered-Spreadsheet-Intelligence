"""Tests for the Cerebras AI intent layer.

These exercise the parse + normalize logic that turns a raw model response into a
validated ActionPlan. The network call (`_call_cerebras`) is stubbed so the tests
run offline and deterministically.
"""

import json

import pytest

from schemas.cerebras_schema import ActionPlan
from services.intent_engine import IntentEngine, IntentEngineError

BRIEF = {
    "filename": "branches.xlsx",
    "sheets": [
        {
            "name": "Branch Deposits",
            "row_count": 240,
            "is_time_series": True,
            "column_summary": [
                {"name": "branch_name", "type": "text"},
                {"name": "deposits_ngn", "type": "currency"},
                {"name": "month", "type": "date"},
            ],
        }
    ],
    "potential_join_keys": ["branch_code"],
    "nigerian_context": {"detected": True, "flags": ["branch", "ngn"], "suggested_template": "banking"},
}


def _engine_returning(raw: str) -> IntentEngine:
    engine = IntentEngine(api_key="test-key")
    engine._call_cerebras = lambda _message: raw  # type: ignore[method-assign]
    return engine


def test_classify_returns_validated_plan():
    raw = json.dumps(
        {
            "intent_type": "growth_analysis",
            "clarification_needed": False,
            "clarification_question": None,
            "operations": [
                {
                    "operation_id": "op_1",
                    "operation_type": "growth_rate",
                    "target_sheet": "Branch Deposits",
                    "target_columns": ["deposits_ngn", "month"],
                    "group_by": ["branch_name"],
                    "parameters": {"period": "quarter", "as_percent": True},
                    "output_sheet": "analysis",
                    "output_label": "Quarterly Deposit Growth",
                }
            ],
            "output_sheets_required": ["analysis"],
            "formatting_tier": "executive",
            "nigerian_context": {
                "currency": "NGN",
                "template_type": "banking",
                "fiscal_calendar": "january",
                "lga_analysis": False,
            },
        }
    )
    plan = _engine_returning(raw).classify(BRIEF, "Show quarterly deposit growth by branch")

    assert isinstance(plan, ActionPlan)
    assert plan.intent_type == "growth_analysis"
    assert plan.operations[0].operation_type == "growth_rate"
    assert plan.nigerian_context.template_type == "banking"


def test_chart_output_sheet_is_forced_and_required_list_is_superset():
    raw = json.dumps(
        {
            "intent_type": "aggregation",
            "operations": [
                {
                    "operation_id": "op_1",
                    "operation_type": "chart",
                    "target_sheet": "Branch Deposits",
                    "target_columns": ["branch_name", "deposits_ngn"],
                    "group_by": [],
                    "parameters": {"chart_type": "bar"},
                    "output_sheet": "analysis",  # wrong on purpose
                    "output_label": "Deposits by Branch",
                }
            ],
            "output_sheets_required": [],  # missing on purpose
            "formatting_tier": "standard",
        }
    )
    plan = _engine_returning(raw).classify(BRIEF, "Chart deposits by branch")

    assert plan.operations[0].output_sheet == "charts"
    assert "charts" in plan.output_sheets_required


def test_clarification_question_synthesised_when_missing():
    raw = json.dumps(
        {
            "intent_type": "custom",
            "clarification_needed": True,
            "clarification_question": None,  # model forgot the question
            "operations": [],
            "output_sheets_required": [],
            "formatting_tier": "standard",
        }
    )
    plan = _engine_returning(raw).classify(BRIEF, "do something")

    assert plan.clarification_needed is True
    assert plan.clarification_question


def test_empty_operations_for_non_formatting_intent_triggers_clarification():
    raw = json.dumps(
        {
            "intent_type": "aggregation",
            "clarification_needed": False,
            "operations": [],
            "output_sheets_required": [],
            "formatting_tier": "standard",
        }
    )
    plan = _engine_returning(raw).classify(BRIEF, "totals")

    assert plan.clarification_needed is True
    assert plan.clarification_question


def test_formatting_only_allows_empty_operations():
    raw = json.dumps(
        {
            "intent_type": "formatting_only",
            "clarification_needed": False,
            "operations": [],
            "output_sheets_required": ["data"],
            "formatting_tier": "premium",
        }
    )
    plan = _engine_returning(raw).classify(BRIEF, "Just reformat the data nicely")

    assert plan.clarification_needed is False
    assert plan.operations == []


def test_json_inside_code_fence_is_parsed():
    raw = "```json\n" + json.dumps(
        {"intent_type": "formatting_only", "operations": [], "output_sheets_required": ["data"]}
    ) + "\n```"
    plan = _engine_returning(raw).classify(BRIEF, "reformat")
    assert plan.intent_type == "formatting_only"


def test_invalid_json_falls_back_to_rule_based_plan():
    """When Cerebras never returns valid JSON, the 3-tier system must still
    return a usable plan via the deterministic rule-based fallback (Tier 3)."""
    engine = _engine_returning("Sorry, I cannot help with that.")
    plan, status = engine.classify_with_status(BRIEF, "rank branches by deposits")
    assert isinstance(plan, ActionPlan)
    assert status == "fallback"
    assert plan.operations  # never empty
    # classify() mirrors classify_with_status and also never raises here.
    assert isinstance(engine.classify(BRIEF, "rank branches by deposits"), ActionPlan)


def test_missing_api_key_raises_on_client_access():
    engine = IntentEngine(api_key="")
    with pytest.raises(IntentEngineError):
        _ = engine.client


def test_empty_instruction_raises():
    engine = IntentEngine(api_key="test-key")
    with pytest.raises(IntentEngineError):
        engine.classify(BRIEF, "   ")


def test_regional_question_groups_by_region_not_date():
    """Regression: 'regional performance by deposit and customer onboarding' must
    produce a group_sum BY Region (with the accounts column), never a rank/growth
    keyed on Date. See ExcelGPT 'unusable' bug report."""
    brief = {
        "filename": "fso.xlsx",
        "sheets": [
            {
                "name": "Sheet1",
                "row_count": 53000,
                "column_summary": [
                    {"name": "Date"},
                    {"name": "Region"},
                    {"name": "State"},
                    {"name": "FSO Name"},
                    {"name": "Deposits (₦)"},
                    {"name": "Accounts_Opened"},
                ],
            }
        ],
    }
    engine = IntentEngine(api_key="")  # no network — exercise the rule-based fallback
    plan = engine._rule_based_fallback(
        brief, "show me regional performance by deposit and customer onboarding"
    )

    group_ops = [op for op in plan.operations if op.operation_type == "group_sum"]
    assert any(op.group_by == ["Region"] for op in group_ops), "expected a group_sum BY Region"
    region_op = next(op for op in group_ops if op.group_by == ["Region"])
    assert "Accounts_Opened" in region_op.target_columns, "accounts column must be included"
    # No operation may rank/trend on the Date column.
    assert not any(
        op.operation_type in ("rank", "growth_rate") and "Date" in op.group_by
        for op in plan.operations
    ), "a regional question must not be answered with a date-keyed operation"
