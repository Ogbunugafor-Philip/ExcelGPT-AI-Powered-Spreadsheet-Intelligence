"""
ExcelGPT — FastAPI application.

The upload route now validates, persists, profiles, and returns a preview plus
an intelligence brief for the frontend.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import config
from schemas.api_schema import (
    AnalyseRequest,
    AnalyseResponse,
    HealthResponse,
    RefineRequest,
    RefineResponse,
    ReportPreview,
    UploadPreview,
    UploadResponse,
)
from services.data_profiler import DataProfiler
from services.excel_reader import ExcelReader
from services.file_validator import FileValidator
from services.intent_engine import IntentEngine, IntentEngineError
from services.session_manager import SessionManager

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

validator = FileValidator()
reader = ExcelReader()
profiler = DataProfiler()
session_manager = SessionManager()
intent_engine = IntentEngine()


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

    return UploadResponse(
        session_id=session_id,
        preview=UploadPreview(**preview_payload),
        intelligence_brief=intelligence_brief,
    )


@app.post("/analyse", response_model=AnalyseResponse)
async def analyse(payload: AnalyseRequest) -> AnalyseResponse:
    """Turn a plain-English instruction into a structured action plan (Phase 3).

    Computation and report generation arrive in a later phase; for now this
    returns the validated action plan so the user can confirm intent before any
    numbers are produced. If Cerebras needs more information, the plan carries a
    single clarification question instead of operations.
    """
    session = session_manager.get_session(payload.session_id)
    intelligence_brief = session.get("intelligence_brief", {})

    try:
        action_plan = intent_engine.classify(intelligence_brief, payload.instruction)
    except IntentEngineError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AnalyseResponse(
        action_plan=action_plan,
        preview=ReportPreview(),
        download_token=None,
        version=1,
    )


@app.post("/refine", response_model=RefineResponse)
async def refine(payload: RefineRequest) -> RefineResponse:
    raise HTTPException(status_code=501, detail="Not implemented (Phase 1 skeleton).")


@app.get("/download/{token}")
async def download(token: str) -> FileResponse:
    raise HTTPException(status_code=501, detail="Not implemented (Phase 1 skeleton).")


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
