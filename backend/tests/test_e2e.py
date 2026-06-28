"""Phase 9 — end-to-end pipeline tests across realistic Nigerian datasets.

Each test builds a DataFrame, writes it to a temp .xlsx, then runs the full
pipeline exactly as production does:

    ExcelReader -> DataProfiler -> (mock ActionPlan) -> ComputationRouter
                -> OutputPackager (inside route) -> ExcelBuilder

and asserts a valid workbook with >= 1 sheet is produced and nothing raises.
"""

from __future__ import annotations

import openpyxl
import pandas as pd
import pytest

from schemas.cerebras_schema import ActionPlan, NigerianContext, Operation
from services.computation_router import ComputationRouter
from services.data_profiler import DataProfiler
from services.excel_builder import ExcelBuilder
from services.excel_reader import ExcelReader


def _op(operation_type, sheet="Sheet1", **kwargs):
    return Operation(
        operation_id=kwargs.get("operation_id", "op_1"),
        operation_type=operation_type,
        target_sheet=sheet,
        target_columns=kwargs.get("target_columns", []),
        group_by=kwargs.get("group_by", []),
        parameters=kwargs.get("parameters", {}),
        output_sheet=kwargs.get("output_sheet", "analysis"),
        output_label=kwargs.get("output_label", "Test"),
    )


def _plan(operations, required=("executive_summary", "data", "analysis")):
    return ActionPlan(
        intent_type="aggregation",
        operations=list(operations),
        output_sheets_required=list(required),
        nigerian_context=NigerianContext(template_type="banking"),
    )


def run_pipeline(tmp_path, sheets: dict[str, pd.DataFrame], plan: ActionPlan, label: str):
    """Write sheets to xlsx and drive the whole pipeline; return the built path."""
    file_path = tmp_path / f"{label}.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)

    reader = ExcelReader()
    profiler = DataProfiler()

    # Read + profile (exercises the data-intelligence layer end to end).
    reader.read_file(str(file_path))
    frames = {name: df for name, df in reader.read_sheets(str(file_path))}
    profiles = {name: profiler.profile(df, name) for name, df in frames.items()}
    brief = profiler.generate_intelligence_brief(profiles, f"{label}.xlsx")

    session = {
        "session_id": f"e2e-{label}",
        "file_path": str(file_path),
        "intelligence_brief": brief,
        "instruction": f"E2E scenario: {label}",
        "version": 1,
    }

    output = ComputationRouter().route(plan, session)
    output.version = 1
    built = ExcelBuilder().build(output, session["session_id"])
    return built


def assert_valid_workbook(path: str):
    import os
    assert os.path.exists(path), "Excel file was not written"
    assert os.path.getsize(path) > 1000, "Excel file is suspiciously small"
    wb = openpyxl.load_workbook(path)  # raises if not a valid .xlsx
    assert len(wb.sheetnames) >= 1, "workbook has no sheets"


# -- Test 1: Financial report -----------------------------------------------

def test_financial_report(tmp_path):
    df = pd.DataFrame({
        "month": ["2026-01", "2026-02", "2026-03", "2026-01", "2026-02", "2026-03"],
        "revenue": [12_000_000, 13_500_000, 14_200_000, 9_000_000, 9_800_000, 10_500_000],
        "expenses": [7_000_000, 7_200_000, 7_800_000, 5_000_000, 5_100_000, 5_400_000],
        "profit": [5_000_000, 6_300_000, 6_400_000, 4_000_000, 4_700_000, 5_100_000],
    })
    plan = _plan([
        _op("group_sum", target_columns=["revenue", "profit"], group_by=["month"], output_label="Monthly totals"),
        _op("growth_rate", operation_id="op_2", target_columns=["profit"], output_label="Profit growth"),
    ])
    assert_valid_workbook(run_pipeline(tmp_path, {"Sheet1": df}, plan, "financial"))


# -- Test 2: Sales tracker --------------------------------------------------

def test_sales_tracker(tmp_path):
    df = pd.DataFrame({
        "salesperson": ["Ada", "Bola", "Chidi", "Dami", "Efe"],
        "region": ["SW", "SS", "SE", "NC", "NW"],
        "target": [5_000_000, 6_000_000, 4_000_000, 5_500_000, 4_800_000],
        "actual": [5_400_000, 5_200_000, 4_600_000, 6_100_000, 3_900_000],
        "quarter": ["Q1", "Q1", "Q1", "Q1", "Q1"],
    })
    plan = _plan([
        _op("rank", target_columns=["actual"], parameters={"by": "actual", "order": "desc", "top_n": 5}, output_label="Top sellers"),
        _op("variance", operation_id="op_2", target_columns=["actual"], parameters={"actual": "actual", "target": "target"}, output_label="Target vs actual"),
    ])
    assert_valid_workbook(run_pipeline(tmp_path, {"Sheet1": df}, plan, "sales"))


# -- Test 3: HR data --------------------------------------------------------

def test_hr_data(tmp_path):
    df = pd.DataFrame({
        "staff_name": ["Ada", "Bola", "Chidi", "Dami", "Efe", "Femi"],
        "department": ["Ops", "Risk", "Ops", "Risk", "Tech", "Tech"],
        "grade": ["M1", "M2", "M1", "M3", "M2", "M1"],
        "salary": [450_000, 720_000, 480_000, 950_000, 680_000, 510_000],
        "pencom": [36_000, 57_600, 38_400, 76_000, 54_400, 40_800],
    })
    plan = _plan([
        _op("group_avg", target_columns=["salary"], group_by=["department"], output_label="Avg salary by dept"),
    ])
    assert_valid_workbook(run_pipeline(tmp_path, {"Sheet1": df}, plan, "hr"))


# -- Test 4: Bank performance ----------------------------------------------

def test_bank_performance(tmp_path):
    df = pd.DataFrame({
        "branch": ["Lagos Island", "Abuja", "PH", "Kano", "Ibadan"],
        "zone": ["SW", "NC", "SS", "NW", "SW"],
        "deposits_ngn": [187_500_000, 142_000_000, 573_750_000, 98_000_000, 210_000_000],
        "loans_ngn": [95_000_000, 71_000_000, 280_000_000, 45_000_000, 105_000_000],
        "npls": [2_000_000, 1_400_000, 9_500_000, 800_000, 3_100_000],
    })
    plan = _plan([
        _op("rank", target_columns=["deposits_ngn"], parameters={"by": "deposits_ngn", "order": "desc", "top_n": 5}, output_label="Top branches"),
        _op("group_sum", operation_id="op_2", target_columns=["deposits_ngn", "loans_ngn"], group_by=["zone"], output_label="By zone"),
    ])
    assert_valid_workbook(run_pipeline(tmp_path, {"Sheet1": df}, plan, "bank"))


# -- Test 5: Empty sheet handling ------------------------------------------

def test_empty_and_data_sheets(tmp_path):
    empty = pd.DataFrame()
    data = pd.DataFrame({
        "branch": ["A", "B", "C"],
        "deposits_ngn": [1_000_000, 2_000_000, 3_000_000],
    })
    plan = _plan([
        _op("rank", sheet="Data", target_columns=["deposits_ngn"], parameters={"by": "deposits_ngn", "order": "desc"}, output_label="Rank"),
    ])
    # ExcelWriter cannot write a truly empty frame as a sheet cleanly; give the
    # empty sheet a header-only frame to simulate "one empty + one data sheet".
    empty = pd.DataFrame({"placeholder": []})
    assert_valid_workbook(run_pipeline(tmp_path, {"Empty": empty, "Data": data}, plan, "empty"))


# -- Test 6: No headers (first row is numeric data) -------------------------

def test_no_headers(tmp_path):
    # Header=None style content: the reader should synthesise Column_N names.
    df = pd.DataFrame([
        [101, 250000, 12.5],
        [102, 310000, 8.2],
        [103, 198000, 15.1],
        [104, 420000, 5.0],
    ])
    plan = _plan([
        _op("group_sum", target_columns=["Column_2"], group_by=["Column_1"], output_label="Sum"),
    ])
    assert_valid_workbook(run_pipeline(tmp_path, {"Sheet1": df}, plan, "noheaders"))


# -- Test 7: Mixed data types ----------------------------------------------

def test_mixed_data_types(tmp_path):
    df = pd.DataFrame({
        "code": ["A1", "B2", "C3", "D4", "E5"],
        "mixed": ["100", "free text", "300", "n/a", "500"],
        "amount_ngn": [100000, 200000, 300000, 400000, 500000],
    })
    plan = _plan([
        _op("rank", target_columns=["amount_ngn"], parameters={"by": "amount_ngn", "order": "desc"}, output_label="Rank"),
        _op("distribution", operation_id="op_2", output_sheet="analysis", output_label="Distribution"),
    ])
    assert_valid_workbook(run_pipeline(tmp_path, {"Sheet1": df}, plan, "mixed"))


# -- Test 8: Single column file --------------------------------------------

def test_single_column(tmp_path):
    df = pd.DataFrame({"deposits_ngn": [1_000_000, 2_500_000, 1_800_000, 3_200_000, 900_000]})
    plan = _plan([
        _op("group_sum", target_columns=["deposits_ngn"], group_by=[], output_label="Total"),
    ])
    assert_valid_workbook(run_pipeline(tmp_path, {"Sheet1": df}, plan, "singlecol"))


# -- Test 9: Large column count (30+ columns) ------------------------------

def test_large_column_count(tmp_path):
    data = {"entity": [f"E{i}" for i in range(20)]}
    for c in range(35):
        data[f"metric_{c}"] = list(range(20))
    df = pd.DataFrame(data)
    plan = _plan([
        _op("group_sum", target_columns=["metric_0", "metric_1"], group_by=["entity"], output_label="Wide"),
    ])
    assert_valid_workbook(run_pipeline(tmp_path, {"Sheet1": df}, plan, "wide"))


# -- Test 10: Unicode (Yoruba / Igbo / Hausa) ------------------------------

def test_unicode_columns(tmp_path):
    df = pd.DataFrame({
        "ọmọ_iṣẹ́": ["Àdé", "Bọ́lá", "Chídí"],          # Yoruba (staff)
        "ụlọ_ọrụ": ["Èkó", "Abuja", "Kanọ"],            # Igbo (office)
        "kuɗin_ajiya": [1_500_000, 2_300_000, 1_900_000],  # Hausa (deposits)
    })
    plan = _plan([
        _op("rank", target_columns=["kuɗin_ajiya"], parameters={"by": "kuɗin_ajiya", "order": "desc"}, output_label="Ipò"),
    ])
    assert_valid_workbook(run_pipeline(tmp_path, {"Sheet1": df}, plan, "unicode"))
