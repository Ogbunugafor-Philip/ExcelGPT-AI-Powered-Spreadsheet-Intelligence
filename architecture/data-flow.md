# ExcelGPT — Data Flow

This document traces a single report from upload to download, step by step. It is the canonical description of how the layers in `system-architecture.md` interact at runtime. The recurring theme: **the AI decides intent, Python does the math.**

```
 Browser (React + SheetJS)            Backend (FastAPI)                 External
 ───────────────────────────         ─────────────────────────         ──────────
  upload .xlsx ─────────────────────► POST /upload
   (client-side preview)              pandas reads all sheets
                                      ◄── session_id + preview + brief
  type instruction ─────────────────► POST /analyse
                                      brief + instruction ────────────► Cerebras
                                      ◄────────────────── action plan
                                      computation engine runs
                                      openpyxl builds .xlsx → disk
                                      ◄── preview + download_token
  refine ───────────────────────────► POST /refine (with history) ───► Cerebras ...
  click download ───────────────────► GET /download/{token}
                                      ◄── .xlsx stream
```

---

## Step 1 — Upload & ingest

1. The user drags an Excel file into the upload zone.
2. **SheetJS reads the workbook client-side** to render an immediate local preview and confirm it is a valid spreadsheet (catches corrupt/empty files before upload).
3. The browser sends the file to **`POST /upload`** as `multipart/form-data` (field name `file`).
4. The backend validates size (`MAX_FILE_SIZE_MB`) and extension (`.xlsx`, `.xls`), then **pandas reads all sheets**.
5. The file is persisted under `UPLOAD_DIR`, a `session_id` is minted, and the response returns:
   `{ session_id, preview: { sheets: [{ name, columns, rows, row_count }] }, intelligence_brief }`.

## Step 2 — Profile & build the intelligence brief

1. Python profiles every sheet with pandas to produce the **intelligence brief JSON**:
   - column types (numeric / currency / date / categorical / identifier / percentage),
   - per-sheet row counts,
   - null percentage per column,
   - value ranges (min/max/distinct) for key columns,
   - **sheet relationships** — shared keys such as `branch_code`, `staff_id`, `lga`, `product`.
2. The brief describes *shape, not bulk values*. It is cached against the `session_id` for reuse across `/analyse` and `/refine`.

## Step 3 — Instruction → action plan (AI intent)

1. The user submits a natural-language instruction.
2. **`POST /analyse`** sends `{ intelligence_brief + instruction }` to **Cerebras**.
3. Cerebras returns an **action plan JSON** (schema: `cerebras-schema.md`): `intent_type`, ordered `operations`, `output_sheets_required`, `formatting_tier`, and `nigerian_context`.
4. If the instruction is ambiguous, the plan returns `clarification_needed: true` with a `clarification_question`, and the flow pauses for user input instead of computing.

## Step 4 — Route to the computation engine

1. The backend iterates the `operations` array and routes each to its deterministic executor:
   - **pandas/numpy** → group_sum, group_avg, rank, filter, growth_rate, growth tables.
   - **scipy** → correlation, statistical tests.
   - **statsmodels** → forecast (with confidence bounds).
   - **scikit-learn** → cluster, score.
   - **matplotlib/seaborn** → chart image rendering.
2. Results are assembled into the **computation output JSON** (schema: `computation-output-schema.md`), with each metric carrying its `formula_used`.

## Step 5 — Build the Excel file

1. The computation output is handed to the **Excel generation engine (openpyxl)**.
2. openpyxl builds the **multi-sheet workbook** — Executive Summary, Data, Analysis, Charts, Forecast (only those in `output_sheets_required`) — applies NGN formatting, conditional formatting, embedded chart images, and the chosen `formatting_tier`.
3. The `.xlsx` is **saved to disk** under `UPLOAD_DIR`, keyed to the session and a fresh download token.

## Step 6 — Respond to the frontend

1. **`POST /analyse`** returns `{ action_plan, preview: { sheets, kpi_cards, charts }, download_token, version }`.
2. The frontend renders KPI cards and Recharts charts from `preview` so the user can review the report shape before downloading.

## Step 7 — Refine (iterate)

1. The user gives feedback ("show growth as %, add a pie chart of deposits by LGA").
2. **`POST /refine`** sends `{ session_id, feedback, history, current_version }`; the backend replays history to Cerebras and **repeats from Step 3**.
3. A new `version` is produced and a new `download_token` issued. Previous versions remain retrievable until session expiry.

## Step 8 — Download

1. The user clicks download → **`GET /download/{token}`**.
2. The backend validates the token (and session expiry), then **streams the `.xlsx`** with the appropriate `Content-Disposition` and spreadsheet MIME type.

---

## Session lifecycle & cleanup

- A session is created at Step 1 and lives for `SESSION_EXPIRY_MINUTES`.
- The intelligence brief, action plans, and generated files are associated with the `session_id`.
- Download tokens are one-time/short-lived and tied to a specific `version`.
- A background cleanup prunes expired uploads and generated reports from `UPLOAD_DIR`.

## Error & edge handling (per step)

| Step | Failure | Handling |
|------|---------|----------|
| 1 | File too large / wrong type | Reject at `/upload` with 4xx before pandas reads |
| 2 | Unreadable/empty sheet | Brief flags the sheet; analysis can proceed on valid sheets |
| 3 | Ambiguous instruction | `clarification_needed: true`, pause for user |
| 3 | Cerebras timeout/error | Retry/backoff, then surface a clear error to the client |
| 4 | Operation references missing column | Skip + record warning in computation output |
| 8 | Expired/invalid token | 404/410, prompt user to regenerate via `/refine` |
