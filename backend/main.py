"""
ExcelGPT — FastAPI application.

The upload route now validates, persists, profiles, and returns a preview plus
an intelligence brief for the frontend.
"""

from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import config
from logger import (
    log_analysis,
    log_download,
    log_error,
    log_refinement,
    log_request,
    log_upload,
)
from schemas.api_schema import (
    AnalyseRequest,
    AnalyseResponse,
    ChartPreview,
    ConditionalFormatPreview,
    ExecutiveSummaryPreview,
    ForecastPointPreview,
    ForecastPreview,
    GrowthRowPreview,
    HealthResponse,
    KpiCardPreview,
    MetricPreview,
    PreviewColumn,
    RankingPreview,
    RefineRequest,
    RefineResponse,
    ReportPreview,
    ReportSheetPreview,
    UploadPreview,
    UploadResponse,
)
from schemas.computation_schema import ComputationOutput
from services.computation_router import ComputationRouter
from services.excel_builder import ExcelBuilder
from services.data_profiler import DataProfiler
from services.excel_reader import ExcelReader
from services.file_validator import FileValidator
from services.intent_engine import IntentEngine, IntentEngineError
from services.modules.common import format_naira, format_pct, is_currency_column
from services.session_manager import SessionManager
from services.sheets.styles import column_name, detect_type

app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="AI-powered Excel transformation and report generation for the Nigerian market.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Time every request, expose X-Process-Time, and log method/path/status."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0
    response.headers["X-Process-Time"] = f"{duration_ms:.1f}"
    log_request(request.method, request.url.path, response.status_code, duration_ms)
    return response

validator = FileValidator()
reader = ExcelReader()
profiler = DataProfiler()
session_manager = SessionManager()
intent_engine = IntentEngine()
computation_router = ComputationRouter()
excel_builder = ExcelBuilder()


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    validator.validate(file)

    validated_path = getattr(file, "_validated_temp_path", None)
    if not validated_path:
        raise HTTPException(status_code=400, detail="The uploaded file could not be validated.")

    filename = Path(file.filename or "workbook.xlsx").name
    session_id = str(uuid4())
    upload_dir = Path(config.UPLOAD_DIR) / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / filename

    shutil.copy2(validated_path, upload_path)
    validated_path.unlink(missing_ok=True)

    preview_payload = reader.read_file(str(upload_path))
    sheet_frames = reader.read_sheets(str(upload_path))
    sheet_profiles = {
        sheet_name: profiler.profile(df, sheet_name)
        for sheet_name, df in sheet_frames
    }
    intelligence_brief = profiler.generate_intelligence_brief(
        sheet_profiles,
        filename,
    )

    session_manager.create_session(
        str(upload_path),
        intelligence_brief,
        {"preview": preview_payload, "profiles": sheet_profiles},
        session_id=session_id,
    )

    sheets = preview_payload.get("sheets", [])
    log_upload(
        filename=filename,
        size_mb=upload_path.stat().st_size / (1024 * 1024),
        sheet_count=len(sheets),
        row_count=sum(s.get("row_count", 0) for s in sheets),
        session_id=session_id,
    )

    return UploadResponse(
        session_id=session_id,
        preview=UploadPreview(**preview_payload),
        intelligence_brief=intelligence_brief,
    )


@app.post("/analyse", response_model=AnalyseResponse)
async def analyse(payload: AnalyseRequest) -> AnalyseResponse:
    """Turn a plain-English instruction into real computed results (Phases 3 + 4).

    Cerebras returns an intent-only action plan; the deterministic computation
    engine then executes every operation and the result is packaged for the
    frontend preview and (later) the Excel writer. If Cerebras needs more
    information, the plan carries a clarification question and nothing is computed.
    """
    session = session_manager.get_session(payload.session_id)
    intelligence_brief = session.get("intelligence_brief", {})
    started = time.perf_counter()

    try:
        action_plan = intent_engine.classify(intelligence_brief, payload.instruction)
    except IntentEngineError as exc:
        log_error("/analyse", "IntentEngineError", str(exc), payload.session_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Ambiguous instruction: surface the question, do not compute.
    if action_plan.clarification_needed:
        log_analysis(payload.session_id, payload.instruction, action_plan.intent_type,
                     (time.perf_counter() - started) * 1000, status="clarification")
        return AnalyseResponse(
            action_plan=action_plan,
            preview=ReportPreview(),
            download_token=None,
            version=int(session.get("version", 0)),
        )

    version = int(session.get("version", 0)) + 1
    computation_output, download_token = _compute_version(session, action_plan, version, payload.instruction)
    log_analysis(payload.session_id, payload.instruction, action_plan.intent_type,
                 (time.perf_counter() - started) * 1000)

    return AnalyseResponse(
        action_plan=action_plan,
        preview=_build_preview(computation_output),
        download_token=download_token,
        version=version,
    )


def _compute_version(session, action_plan, version: int, instruction: str):
    """Run the deterministic engine for a new version and persist it.

    Stores the ComputationOutput under ``version`` and mints a download token
    bound to that version, so every /analyse and /refine has its own report.
    """
    session_id = session["session_id"]
    session["instruction"] = instruction
    session["version"] = version

    computation_output = computation_router.route(action_plan, session)
    computation_output.version = version

    session_manager.store_version(session_id, version, computation_output)
    download_token = str(uuid4())
    session_manager.register_download(session_id, download_token, version, computation_output)
    session.setdefault("version_history", []).append({"version": version, "download_token": download_token})
    return computation_output, download_token


# ---------------------------------------------------------------------------
# Phase 6 — map the ComputationOutput into the in-app preview shape.
# The preview mirrors what the Excel writer renders so the user sees, before
# downloading, the same KPIs / tables / charts / rankings / growth / forecast.
# ---------------------------------------------------------------------------

_PREVIEW_ROW_LIMIT = 200
_PCT_NAME_HINTS = ("pct", "percent", "rate", "growth", "margin", "ratio", "variance", "change")


def _build_preview(output: ComputationOutput) -> ReportPreview:
    kpi_cards = [
        KpiCardPreview(label=c.label, value=c.value, change=c.change, direction=c.direction)
        for c in output.executive_summary.kpi_cards
    ]
    executive_summary = ExecutiveSummaryPreview(
        title=output.executive_summary.title,
        period=output.executive_summary.period,
        data_source=output.executive_summary.data_source,
        kpi_cards=kpi_cards,
    )

    sheets: list[ReportSheetPreview] = []
    data_sheet = _data_sheet_preview(output)
    if data_sheet is not None:
        sheets.append(data_sheet)

    charts = [
        ChartPreview(chart_id=c.chart_id, chart_type=c.chart_type, title=c.title, recharts_data=c.recharts_data)
        for c in output.charts
    ]

    metrics = [
        MetricPreview(label=m.label, value=m.value, formula_used=m.formula_used)
        for m in output.analysis_sheet.metrics
    ]
    rankings = _rankings_preview(output.analysis_sheet.rankings)
    growth_table = _growth_preview(output.analysis_sheet.growth_table)
    forecast = _forecast_preview(output)

    return ReportPreview(
        executive_summary=executive_summary,
        sheets=sheets,
        charts=charts,
        forecast=forecast,
        metrics=metrics,
        rankings=rankings,
        growth_table=growth_table,
        kpi_cards=kpi_cards,
    )


def _as_row(row) -> list:
    if isinstance(row, (list, tuple)):
        return list(row)
    if isinstance(row, dict):
        return list(row.values())
    return [row]


def _data_sheet_preview(output: ComputationOutput) -> ReportSheetPreview | None:
    data_sheet = output.data_sheet
    if not data_sheet.columns:
        return None

    rows = [_as_row(r) for r in data_sheet.rows[:_PREVIEW_ROW_LIMIT]]
    columns = []
    for idx, raw_col in enumerate(data_sheet.columns):
        name = column_name(raw_col)
        sample = [row[idx] for row in rows if idx < len(row)]
        columns.append(PreviewColumn(name=name, type=detect_type(name, sample)))

    formatting = [
        ConditionalFormatPreview(column=column_name(rule.column), rule=rule.rule, color=rule.color)
        for rule in data_sheet.conditional_formatting
    ]
    return ReportSheetPreview(
        sheet_name="data",
        display_name="Data",
        columns=columns,
        rows=rows,
        conditional_formatting=formatting,
    )


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _looks_pct(name: str) -> bool:
    lowered = str(name).lower()
    return any(hint in lowered for hint in _PCT_NAME_HINTS)


def _format_value(name: str, value) -> str:
    if value is None:
        return "—"
    if _is_number(value):
        if is_currency_column(name) and not _looks_pct(name):
            return format_naira(value)
        if _looks_pct(name):
            return format_pct(value)
        return f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
    return str(value)


def _rankings_preview(rankings: list) -> list[RankingPreview]:
    out: list[RankingPreview] = []
    for row in rankings:
        if not isinstance(row, dict):
            continue
        rank = row.get("Rank", row.get("rank"))

        label = next(
            (str(v) for k, v in row.items() if k not in ("Rank", "rank") and isinstance(v, str)),
            "",
        )
        change_key = next((k for k in row if k not in ("Rank", "rank") and _looks_pct(k)), None)
        value_key = next(
            (k for k, v in row.items() if k not in ("Rank", "rank") and k != change_key and _is_number(v) and is_currency_column(k)),
            None,
        )
        if value_key is None:
            value_key = next(
                (k for k, v in row.items() if k not in ("Rank", "rank") and k != change_key and _is_number(v)),
                None,
            )

        value = _format_value(value_key, row.get(value_key)) if value_key else ""
        change = _format_value(change_key, row.get(change_key)) if change_key else ""
        direction = row.get("direction") if row.get("direction") in ("up", "down", "neutral") else _direction_of(row.get(change_key))

        out.append(RankingPreview(
            rank=int(rank) if isinstance(rank, (int, float)) and not isinstance(rank, bool) else None,
            label=label,
            value=value,
            change=change,
            direction=direction,
        ))
    return out


def _growth_preview(growth_table: list) -> list[GrowthRowPreview]:
    out: list[GrowthRowPreview] = []
    for row in growth_table:
        if not isinstance(row, dict):
            continue
        direction = row.get("direction") if row.get("direction") in ("up", "down", "neutral") else "neutral"

        rate_key = next((k for k in row if k.lower() in ("growth_pct", "variance_pct")), None) \
            or next((k for k in row if _looks_pct(k)), None)
        rate_value = row.get(rate_key) if rate_key else None
        growth_rate = format_pct(rate_value, signed=True) if _is_number(rate_value) else "—"

        numeric_keys = [
            k for k, v in row.items()
            if _is_number(v) and k not in ("Rank", "rank", rate_key)
        ]
        actual_key = next((k for k in numeric_keys if any(t in k.lower() for t in ("actual", "achieved", "result"))), None)
        target_key = next((k for k in numeric_keys if any(t in k.lower() for t in ("target", "budget", "plan", "goal", "forecast"))), None)

        current_val = previous_val = None
        current_name = ""
        if actual_key and target_key:
            current_name, current_val, previous_val = actual_key, row.get(actual_key), row.get(target_key)
        elif len(numeric_keys) >= 2:
            current_name, current_val, previous_val = numeric_keys[-1], row.get(numeric_keys[-1]), row.get(numeric_keys[0])
        elif numeric_keys:
            current_name = numeric_keys[0]
            current_val = row.get(current_name)
            if _is_number(rate_value) and rate_value != -100:
                previous_val = current_val / (1 + rate_value / 100.0)

        label_parts = []
        entity = next((str(v) for k, v in row.items() if isinstance(v, str) and k not in ("direction", "status", "period")), None)
        if entity:
            label_parts.append(entity)
        if row.get("period") is not None:
            label_parts.append(str(row["period"]))
        label = " · ".join(label_parts) or "—"

        out.append(GrowthRowPreview(
            label=label,
            current=_format_value(current_name, current_val),
            previous=_format_value(current_name, previous_val),
            growth_rate=growth_rate,
            direction=direction,
        ))
    return out


def _direction_of(value) -> str:
    if not _is_number(value):
        return "neutral"
    return "up" if value > 0 else "down" if value < 0 else "neutral"


def _forecast_preview(output: ComputationOutput) -> ForecastPreview | None:
    forecast = output.forecast_sheet
    if not forecast.historical and not forecast.projected:
        return None

    def points(series) -> list[ForecastPointPreview]:
        result = []
        for item in series or []:
            if isinstance(item, dict):
                result.append(ForecastPointPreview(period=str(item.get("period", "")), value=_num_or_none(item.get("value"))))
            else:
                result.append(ForecastPointPreview(period="", value=_num_or_none(item)))
        return result

    return ForecastPreview(
        historical=points(forecast.historical),
        projected=points(forecast.projected),
        confidence_upper=points(forecast.confidence_upper),
        confidence_lower=points(forecast.confidence_lower),
        assumptions=[str(a) for a in forecast.assumptions],
    )


def _num_or_none(value):
    return float(value) if _is_number(value) else None


@app.post("/refine", response_model=RefineResponse)
async def refine(payload: RefineRequest) -> RefineResponse:
    """Iterate on an existing report using the conversation so far (Phase 7).

    The previous turns and the new feedback are folded into a single user message
    so Cerebras refines the prior plan rather than starting over. The deterministic
    engine then recomputes, a new version is stored, and a fresh download token and
    preview are returned — mirroring the /analyse response shape.
    """
    session = session_manager.get_session(payload.session_id)  # 404 if unknown/expired
    intelligence_brief = session.get("intelligence_brief", {})
    started = time.perf_counter()

    refinement_context = _build_refinement_context(payload.history, payload.feedback)

    try:
        action_plan = intent_engine.classify(intelligence_brief, refinement_context)
    except IntentEngineError as exc:
        log_error("/refine", "IntentEngineError", str(exc), payload.session_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Ambiguous refinement: surface the question, keep the current version intact.
    if action_plan.clarification_needed:
        return RefineResponse(
            action_plan=action_plan,
            preview=ReportPreview(),
            download_token=None,
            version=int(session.get("version", payload.current_version)),
        )

    version = int(session.get("version", payload.current_version)) + 1
    computation_output, download_token = _compute_version(session, action_plan, version, payload.feedback)
    log_refinement(payload.session_id, payload.feedback, version, (time.perf_counter() - started) * 1000)

    return RefineResponse(
        action_plan=action_plan,
        preview=_build_preview(computation_output),
        download_token=download_token,
        version=version,
    )


def _build_refinement_context(history, feedback: str) -> str:
    """Fold prior turns + the new feedback into one instruction for the planner."""
    lines: list[str] = []
    for turn in history or []:
        speaker = "User" if turn.role == "user" else "Assistant"
        lines.append(f"{speaker}: {turn.content}")
    conversation = "\n".join(lines)

    parts = [
        "This is a REFINEMENT of an existing report. Build on the previous "
        "analysis. Do not start from scratch.",
    ]
    if conversation:
        parts.append("CONVERSATION SO FAR:\n" + conversation)
    parts.append("LATEST USER FEEDBACK:\n" + feedback)
    return "\n\n".join(parts)


@app.get("/download/{token}")
async def download(token: str) -> FileResponse:
    """Build the .xlsx report for a download token and stream it (Phase 5)."""
    session_id, output_data = session_manager.find_download(token)
    if session_id is None or output_data is None:
        raise HTTPException(status_code=404, detail="Download token not found or expired.")

    try:
        computation_output = ComputationOutput.model_validate(output_data)
        file_path = excel_builder.build(computation_output, session_id)
    except Exception as exc:  # noqa: BLE001 — surface build failures as 500
        log_error("/download", "ExcelBuildError", str(exc), session_id)
        raise HTTPException(status_code=500, detail=f"Failed to build the Excel report: {exc}") from exc

    try:
        log_download(session_id, computation_output.version, Path(file_path).stat().st_size / 1024)
    except Exception:  # noqa: BLE001 — logging must not break the download
        pass

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return FileResponse(
        path=file_path,
        media_type=config.XLSX_MEDIA_TYPE,
        filename=f"ExcelGPT_Report_{timestamp}.xlsx",
        headers={"Content-Disposition": f'attachment; filename="ExcelGPT_Report_{timestamp}.xlsx"'},
    )


@app.get("/status/{session_id}")
async def status(session_id: str) -> dict[str, object]:
    """Processing status for a session (Phase 8).

    Uploads complete synchronously today, so an existing session is always
    ``ready``; the endpoint exists so the frontend can poll large-file reads
    without changing the contract once background ingestion is enabled.
    """
    session = session_manager.get_session(session_id)  # 404 if unknown/expired
    return {
        "status": session.get("status", "ready"),
        "progress": int(session.get("progress", 100)),
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=config.APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=config.BACKEND_PORT, reload=True)
