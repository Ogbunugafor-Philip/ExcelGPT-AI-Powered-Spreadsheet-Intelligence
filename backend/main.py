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
    DownloadAllRequest,
    RefineRequest,
    RefineResponse,
    ReportPreview,
    ReportSheetPreview,
    TableMeta,
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
from services.semantics import suggest_display_name
from services.session_manager import SessionManager
from services.sheets.analysis_sheet import clean_formula
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

    # The 3-tier planner is designed to ALWAYS return a plan (Tier 3 is rule-based
    # and never calls the network). We still wrap it so that, no matter what goes
    # wrong, a raw Python exception message can never reach the client — the
    # frontend only ever renders friendly copy from errorMessages.js.
    try:
        action_plan, ai_status = intent_engine.classify_with_status(intelligence_brief, payload.instruction)
    except Exception as exc:  # noqa: BLE001 — never leak raw exception text to the UI
        log_error("/analyse", type(exc).__name__, str(exc), payload.session_id)
        raise HTTPException(
            status_code=500,
            detail="We couldn't analyse that just now. Please try again.",
        ) from exc

    # Ambiguous instruction: surface the question, do not compute.
    if action_plan.clarification_needed:
        log_analysis(payload.session_id, payload.instruction, action_plan.intent_type,
                     (time.perf_counter() - started) * 1000, status="clarification")
        return AnalyseResponse(
            action_plan=action_plan,
            preview=ReportPreview(),
            download_token=None,
            version=int(session.get("version", 0)),
            ai_status=ai_status,
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
        ai_status=ai_status,
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

    display_names = dict(output.display_names or {})

    def display(name) -> str:
        key = str(name)
        return display_names.get(key) or suggest_display_name(key) or key

    sheets: list[ReportSheetPreview] = []
    data_sheet = _data_sheet_preview(output, display)
    if data_sheet is not None:
        sheets.append(data_sheet)

    charts = [
        ChartPreview(
            chart_id=c.chart_id,
            chart_type=c.chart_type,
            title=c.title,
            recharts_data=c.recharts_data,
            x_label=_chart_axis(c.recharts_data, "categoryName"),
            y_label=_chart_axis(c.recharts_data, "displayName"),
        )
        for c in output.charts
    ]

    metrics = [
        MetricPreview(label=m.label, value=m.value, formula_used=clean_formula(m.formula_used))
        for m in output.analysis_sheet.metrics
    ]
    rankings, rankings_meta = _rankings_preview(output.analysis_sheet.rankings, display)
    growth_table, growth_meta = _growth_preview(output.analysis_sheet.growth_table, display)
    forecast = _forecast_preview(output)

    return ReportPreview(
        executive_summary=executive_summary,
        sheets=sheets,
        charts=charts,
        forecast=forecast,
        metrics=metrics,
        rankings=rankings,
        growth_table=growth_table,
        rankings_meta=rankings_meta,
        growth_meta=growth_meta,
        display_names=display_names,
        kpi_cards=kpi_cards,
    )


def _chart_axis(recharts_data, key: str) -> str:
    for point in recharts_data or []:
        if isinstance(point, dict) and point.get(key):
            return str(point[key])
    return ""


def _as_row(row) -> list:
    if isinstance(row, (list, tuple)):
        return list(row)
    if isinstance(row, dict):
        return list(row.values())
    return [row]


def _data_sheet_preview(output: ComputationOutput, display) -> ReportSheetPreview | None:
    data_sheet = output.data_sheet
    if not data_sheet.columns:
        return None

    rows = [_as_row(r) for r in data_sheet.rows[:_PREVIEW_ROW_LIMIT]]
    columns = []
    for idx, raw_col in enumerate(data_sheet.columns):
        raw_name = column_name(raw_col)
        name = display(raw_name)
        sample = [row[idx] for row in rows if idx < len(row)]
        # Type detection keyed on the RAW name (its keyword hints drive currency/%).
        columns.append(PreviewColumn(name=name, type=detect_type(raw_name, sample)))

    formatting = [
        ConditionalFormatPreview(column=display(column_name(rule.column)), rule=rule.rule, color=rule.color)
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


def _ranking_keys(rows: list) -> tuple[str | None, str | None, str | None]:
    """Identify the entity, primary-value, and change columns from ranking rows."""
    for row in rows:
        if not isinstance(row, dict):
            continue
        entity_key = next(
            (k for k, v in row.items() if k not in ("Rank", "rank") and isinstance(v, str)),
            None,
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
        return entity_key, value_key, change_key
    return None, None, None


def _tier_of(value, mean) -> str:
    """Performance tier vs the mean: excellent | good | average | below."""
    if not _is_number(value) or not _is_number(mean) or mean == 0:
        return "none"
    ratio = value / mean
    if ratio >= 1.25:
        return "excellent"
    if ratio >= 1.0:
        return "good"
    if ratio >= 0.75:
        return "average"
    return "below"


def _rankings_preview(rankings: list, display) -> tuple[list[RankingPreview], TableMeta]:
    entity_key, value_key, change_key = _ranking_keys(rankings)
    numeric_values = [
        row.get(value_key) for row in rankings
        if isinstance(row, dict) and value_key and _is_number(row.get(value_key))
    ]
    mean = sum(numeric_values) / len(numeric_values) if numeric_values else None

    meta = TableMeta(
        entity_label=display(entity_key) if entity_key else "Entity",
        value_label=display(value_key) if value_key else "Value",
        change_label=display(change_key) if change_key else "",
    )

    out: list[RankingPreview] = []
    for row in rankings:
        if not isinstance(row, dict):
            continue
        rank = row.get("Rank", row.get("rank"))
        label = str(row.get(entity_key)) if entity_key and row.get(entity_key) is not None else ""
        raw_value = row.get(value_key) if value_key else None
        value = _format_value(value_key, raw_value) if value_key else ""
        change = _format_value(change_key, row.get(change_key)) if change_key else ""
        direction = row.get("direction") if row.get("direction") in ("up", "down", "neutral") else _direction_of(row.get(change_key))

        out.append(RankingPreview(
            rank=int(rank) if isinstance(rank, (int, float)) and not isinstance(rank, bool) else None,
            label=label,
            value=value,
            change=change,
            direction=direction,
            tier=_tier_of(raw_value, mean),
            numeric_value=float(raw_value) if _is_number(raw_value) else None,
        ))
    return out, meta


def _growth_preview(growth_table: list, display) -> tuple[list[GrowthRowPreview], TableMeta]:
    out: list[GrowthRowPreview] = []
    entity_label = "Entity"
    current_label = "Current"
    previous_label = "Previous"
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
            current_label, previous_label = display(actual_key), display(target_key)
        elif len(numeric_keys) >= 2:
            current_name, current_val, previous_val = numeric_keys[-1], row.get(numeric_keys[-1]), row.get(numeric_keys[0])
            current_label, previous_label = display(numeric_keys[-1]), display(numeric_keys[0])
        elif numeric_keys:
            current_name = numeric_keys[0]
            current_val = row.get(current_name)
            current_label = display(current_name)
            if _is_number(rate_value) and rate_value != -100:
                previous_val = current_val / (1 + rate_value / 100.0)

        label_parts = []
        entity_key = next((k for k, v in row.items() if isinstance(v, str) and k not in ("direction", "status", "period")), None)
        if entity_key and row.get(entity_key):
            label_parts.append(str(row[entity_key]))
            entity_label = display(entity_key)
        if row.get("period") is not None:
            label_parts.append(str(row["period"]))
        label = " · ".join(label_parts) or "—"

        out.append(GrowthRowPreview(
            label=label,
            current=_format_value(current_name, current_val),
            previous=_format_value(current_name, previous_val),
            growth_rate=growth_rate,
            direction=direction,
            numeric_current=float(current_val) if _is_number(current_val) else None,
            numeric_previous=float(previous_val) if _is_number(previous_val) else None,
            numeric_change_pct=float(rate_value) if _is_number(rate_value) else None,
        ))
    meta = TableMeta(
        entity_label=entity_label,
        current_label=current_label,
        previous_label=previous_label,
        change_label="Change",
    )
    return out, meta


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
        action_plan, ai_status = intent_engine.classify_with_status(intelligence_brief, refinement_context)
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
            ai_status=ai_status,
        )

    version = int(session.get("version", payload.current_version)) + 1
    computation_output, download_token = _compute_version(session, action_plan, version, payload.feedback)
    log_refinement(payload.session_id, payload.feedback, version, (time.perf_counter() - started) * 1000)

    return RefineResponse(
        action_plan=action_plan,
        preview=_build_preview(computation_output),
        download_token=download_token,
        version=version,
        ai_status=ai_status,
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


@app.post("/download-all")
async def download_all(payload: DownloadAllRequest) -> FileResponse:
    """Package several insight tokens into ONE workbook — a sheet per insight.

    Missing/expired tokens are skipped (never crash); at least one valid token
    is required, otherwise 404.
    """
    items: list[tuple[str, dict]] = []
    session_id: str | None = None
    for token in payload.tokens or []:
        found_session, output_data = session_manager.find_download(token)
        if output_data is None:
            log_error("/download-all", "TokenSkipped", f"token not found: {token}", found_session or "")
            continue
        session_id = session_id or found_session
        label = ((output_data.get("executive_summary") or {}).get("title")) or "Insight"
        items.append((label, output_data))

    if not items or session_id is None:
        raise HTTPException(status_code=404, detail="No valid insights to download.")

    try:
        file_path = excel_builder.build_combined(items, session_id)
    except Exception as exc:  # noqa: BLE001 — surface build failures as 500
        log_error("/download-all", "ExcelBuildError", str(exc), session_id)
        raise HTTPException(status_code=500, detail="Failed to build the combined Excel report.") from exc

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return FileResponse(
        path=file_path,
        media_type=config.XLSX_MEDIA_TYPE,
        filename=f"ExcelGPT_Insights_{timestamp}.xlsx",
        headers={"Content-Disposition": f'attachment; filename="ExcelGPT_Insights_{timestamp}.xlsx"'},
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
