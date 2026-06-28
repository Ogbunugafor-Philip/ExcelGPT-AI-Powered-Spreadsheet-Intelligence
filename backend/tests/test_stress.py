"""Phase 9 — stress test: 50,000 rows x 15 columns through the full pipeline."""

from __future__ import annotations

import time

import openpyxl
import pandas as pd

from schemas.cerebras_schema import ActionPlan, NigerianContext, Operation
from services.computation_router import ComputationRouter
from services.data_profiler import DataProfiler
from services.excel_builder import ExcelBuilder
from services.excel_reader import ExcelReader

ROWS = 50_000
COLS = 15


def _build_dataframe() -> pd.DataFrame:
    zones = ["SW", "SS", "SE", "NC", "NW", "NE"]
    data = {
        "branch": [f"BR{i % 500:04d}" for i in range(ROWS)],
        "zone": [zones[i % len(zones)] for i in range(ROWS)],
        "month": [f"2026-{(i % 12) + 1:02d}" for i in range(ROWS)],
        "deposits_ngn": [1_000_000 + (i % 1000) * 1234 for i in range(ROWS)],
    }
    # Pad out to 15 columns total with numeric metric columns.
    for c in range(COLS - len(data)):
        data[f"metric_{c}"] = [(i * (c + 1)) % 100000 for i in range(ROWS)]
    return pd.DataFrame(data)


def test_stress_50k_rows_under_60s(tmp_path):
    df = _build_dataframe()
    assert df.shape == (ROWS, COLS)

    file_path = tmp_path / "stress.xlsx"
    df.to_excel(file_path, sheet_name="Sheet1", index=False)  # setup, not timed

    plan = ActionPlan(
        intent_type="aggregation",
        operations=[
            Operation(
                operation_id="op_1", operation_type="group_sum", target_sheet="Sheet1",
                target_columns=["deposits_ngn"], group_by=["zone"], parameters={},
                output_sheet="analysis", output_label="Deposits by zone",
            ),
            Operation(
                operation_id="op_2", operation_type="rank", target_sheet="Sheet1",
                target_columns=["deposits_ngn"], group_by=[],
                parameters={"by": "deposits_ngn", "order": "desc", "top_n": 20},
                output_sheet="analysis", output_label="Top branches",
            ),
        ],
        output_sheets_required=["executive_summary", "data", "analysis"],
        nigerian_context=NigerianContext(template_type="banking"),
    )

    session = {
        "session_id": "stress-test",
        "file_path": str(file_path),
        "intelligence_brief": {"filename": "stress.xlsx"},
        "instruction": "Aggregate 50k rows by zone and rank branches",
        "version": 1,
    }

    started = time.perf_counter()
    # Profile (data-intelligence) + compute + build — the timed pipeline.
    frames = {name: d for name, d in ExcelReader().read_sheets(str(file_path))}
    profiler = DataProfiler()
    profiles = {name: profiler.profile(d, name) for name, d in frames.items()}
    session["intelligence_brief"] = profiler.generate_intelligence_brief(profiles, "stress.xlsx")

    output = ComputationRouter().route(plan, session)
    output.version = 1
    built = ExcelBuilder().build(output, session["session_id"])
    elapsed = time.perf_counter() - started

    assert elapsed < 60, f"pipeline took {elapsed:.1f}s (>60s)"
    import os
    assert os.path.exists(built) and os.path.getsize(built) > 1000
    openpyxl.load_workbook(built)  # raises if invalid
    print(f"\nstress pipeline completed in {elapsed:.1f}s")
