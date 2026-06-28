# ExcelGPT — System Architecture

ExcelGPT is a layered system that converts raw Excel files plus a natural-language instruction into a polished, multi-sheet Excel report tailored to Nigerian business reporting. The guiding principle is a strict separation between **intent** (decided by the LLM) and **computation** (executed deterministically in Python). The LLM never touches raw data values and never does arithmetic; it only produces a structured *action plan*. This makes every number in the final report auditable and reproducible — a hard requirement for finance, banking, and regulatory reporting in Nigeria.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER  (Vercel)                            │
│   React • Tailwind • SheetJS • Recharts • Axios • react-dropzone           │
└───────────────────────────────┬──────────────────────────────────────────┘
                                 │ HTTPS / JSON + multipart
┌───────────────────────────────▼──────────────────────────────────────────┐
│                  BACKEND LAYER  (Contabo VPS • Nginx • Uvicorn)            │
│                       FastAPI • python-multipart                           │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ DATA INTELLIGENCE LAYER   pandas profiling → intelligence brief     │  │
│  ├────────────────────────────────────────────────────────────────────┤  │
│  │ AI INTENT LAYER           Cerebras API → action plan (intent only)  │  │
│  ├────────────────────────────────────────────────────────────────────┤  │
│  │ COMPUTATION LAYER         pandas • numpy • scipy • statsmodels •     │  │
│  │                           scikit-learn • matplotlib → output JSON   │  │
│  ├────────────────────────────────────────────────────────────────────┤  │
│  │ EXCEL GENERATION LAYER    openpyxl → multi-sheet .xlsx on disk      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Frontend layer

**Stack:** React 18, Tailwind CSS, SheetJS (`xlsx`), Recharts, Axios, react-dropzone, framer-motion, lucide-react.
**Hosting:** Vercel.

Responsibilities:
- **Upload UX.** `react-dropzone` provides the drag-and-drop upload zone. SheetJS reads the workbook *client-side* first to render an instant local preview and validate that the file is a real spreadsheet before any bytes leave the browser.
- **Instruction capture.** A plain-English instruction box ("Rank branches by deposit growth this quarter and forecast next quarter") is the primary input.
- **Live preview.** The preview panel renders KPI cards and Recharts charts from the `preview` payload returned by `/analyse` and `/refine`, so the user sees the report shape before downloading the real `.xlsx`.
- **Refinement loop.** Conversation history is held in the client and replayed to `/refine`.
- **Download.** A download token is exchanged at `/download/{token}` for the final file.

The frontend holds **no business logic and does no computation** — it is a thin, fast presentation layer styled with the navy / electric-blue executive design system (see `frontend/src/design-system.md`).

---

## 2. Backend layer

**Stack:** FastAPI, Uvicorn (ASGI server), python-multipart (file parsing).
**Hosting:** Contabo VPS, reverse-proxied by Nginx.

The backend is the orchestrator. It owns session state, enforces upload limits and CORS, and routes each request through the four internal layers below. FastAPI's Pydantic integration gives request/response validation for free — the models live in `backend/schemas/`. Uvicorn runs the ASGI app; in production Nginx terminates TLS, serves as a reverse proxy, and applies rate limiting and upload size caps as a first line of defence.

---

## 3. Data intelligence layer

**Stack:** pandas (+ numpy).

When a workbook arrives, pandas reads **all sheets** and profiles them into an **intelligence brief** — a compact JSON description of the data *shape* (never the AI's view of raw values in bulk). The brief includes, per sheet:
- column names and inferred semantic types (numeric, currency, date, categorical, identifier, percentage),
- row counts and null percentage per column,
- value ranges / min-max / distinct counts for key columns,
- detected relationships between sheets (shared keys, e.g. `branch_code`, `staff_id`, `lga`).

This brief is what the AI intent layer reasons over. By sending *structure* rather than *raw rows*, ExcelGPT keeps prompts small, fast, cheap, and privacy-preserving, while giving Cerebras enough context to choose correct operations and target columns.

---

## 4. AI intent layer

**Stack:** Cerebras Cloud API (via `cerebras-cloud-sdk`).

The intelligence brief + the user instruction are sent to Cerebras, which returns a strictly-typed **action plan** (schema: `architecture/cerebras-schema.md`). The action plan declares:
- the overall `intent_type` (aggregation, growth analysis, statistical analysis, forecasting, performance scoring, formatting-only, or custom),
- an ordered list of `operations` (each naming an `operation_type`, `target_sheet`, `target_columns`, `group_by`, `parameters`, and where its output belongs),
- which output sheets are required,
- a `formatting_tier`, and
- a `nigerian_context` block (currency, template type, fiscal calendar, LGA analysis flag).

**Critical constraint:** the AI produces *intent only*. It selects operations and columns; it does **not** compute results, and it does not receive bulk raw data. If the instruction is ambiguous it can set `clarification_needed: true` and return a `clarification_question` instead of guessing.

---

## 5. Computation layer

**Stack:** pandas, numpy, scipy, statsmodels, scikit-learn, matplotlib.

The backend routes each operation in the action plan to a deterministic Python executor:
- **pandas / numpy** — grouping, aggregation, ranking, filtering, growth tables.
- **scipy** — correlations, hypothesis tests, distributions.
- **statsmodels** — time-series forecasting (ARIMA/ETS) with confidence intervals.
- **scikit-learn** — clustering (territory/customer segmentation) and performance scoring models.
- **matplotlib / seaborn** — render chart images for embedding into the Excel file.

The layer emits a single **computation output JSON** (schema: `architecture/computation-output-schema.md`) containing the executive summary, data sheet, analysis sheet, charts, and forecast sheet. Every metric carries the `formula_used` so results stay auditable.

---

## 6. Excel generation layer

**Stack:** openpyxl.

openpyxl consumes the computation output JSON and builds the final multi-sheet workbook: `Executive Summary`, `Data`, `Analysis`, `Charts`, and `Forecast` (only the sheets the action plan requires). It applies the ExcelGPT visual identity — NGN currency formatting, conditional formatting rules, KPI card styling, embedded chart images, and the selected `formatting_tier` (standard / premium / executive). The finished `.xlsx` is written to `UPLOAD_DIR` and referenced by a one-time download token.

---

## 7. Infrastructure

- **Contabo VPS** — hosts the FastAPI/Uvicorn backend and the on-disk upload/report storage.
- **Nginx** — reverse proxy in front of Uvicorn: TLS termination, gzip, request size limits, rate limiting, and static error pages.
- **Vercel** — hosts and globally distributes the React frontend; environment-scoped to point at the production API origin (enforced by `ALLOWED_ORIGINS`).
- **Sessions & storage** — sessions and download tokens expire after `SESSION_EXPIRY_MINUTES`; a cleanup routine prunes expired uploads/reports from `UPLOAD_DIR`.

---

## Design rationale

1. **Intent/computation split** → trustworthy, reproducible numbers for regulated Nigerian reporting.
2. **Client-side pre-read (SheetJS)** → instant feedback and fewer wasted round-trips.
3. **Structure-only prompts (intelligence brief)** → fast, cheap, privacy-preserving AI calls.
4. **Schema-validated boundaries (Pydantic)** → every layer hand-off is typed and verifiable.
5. **Nigerian context as a first-class field** → currency, fiscal calendar, and template norms travel with the request instead of being bolted on at the end.
