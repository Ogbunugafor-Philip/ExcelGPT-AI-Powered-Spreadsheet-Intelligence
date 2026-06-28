# ExcelGPT — AI-Powered Spreadsheet Intelligence

> *"Copilot makes Excel smarter. ExcelGPT makes Excel Nigerian."*

[![Live Demo](https://img.shields.io/badge/Live-excelgpt.store-2563EB?style=for-the-badge)](https://excelgpt.store)
[![Backend](https://img.shields.io/badge/FastAPI-Backend-10B981?style=for-the-badge)](https://excelgpt.store/api/health)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)](https://react.dev)

---

## What is ExcelGPT?

ExcelGPT is a conversational AI system that transforms any Excel file into a professionally formatted, mathematically computed business report — in seconds.

Built specifically for the Nigerian market, ExcelGPT understands Nigerian banking workflows, HR and payroll structures (PENCOM, NHF, PAYE), LGA-level territory analysis, FSO and DSA sales hierarchies, and Naira currency formatting conventions.

**Upload. Describe. Download.**

---

## The Problem

Microsoft Excel is the most widely used business tool across Nigerian banks, SMEs, government institutions, and sales organisations. Yet most users operate at a fraction of its true capability.

- Raw data sits in spreadsheets for weeks without meaningful analysis
- Reports are built manually, consuming hours of productive time
- Formatting is inconsistent and unprofessional
- Statistical insights that could drive better decisions are never extracted
- Hiring a professional Excel consultant is expensive and inaccessible

---

## How ExcelGPT is Different

| Area | Microsoft Copilot | ExcelGPT |
|------|------------------|----------|
| Nigerian business context | None | Designed around Nigerian business needs |
| CBN regulatory formats | Not available | Supports Nigerian banking reporting workflows |
| Nigerian HR rules (PENCOM, NHF) | Not available | Built-in Nigerian payroll templates |
| LGA and ward level intelligence | Not available | Nigerian geographic structures supported |
| Naira formatting | Not available | Built-in Naira currency formatting |
| Requires Microsoft 365 | Yes | No — works independently |
| In-app preview | Not available | Full preview before download |
| Python-powered computation | Not available | Real mathematical computation |

---

## How It Works

ExcelGPT separates **intent** from **computation**. The Cerebras LLM is used *only* to translate your instruction (plus a structural "intelligence brief" of your data) into a typed **action plan** — it never sees raw values and never does arithmetic. Every number is then computed deterministically in Python, so results are auditable and reproducible.

```
 ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌────────────┐   ┌──────────┐   ┌──────────┐
 │ Upload  │──▶│ Profile  │──▶│  Intent  │──▶│  Compute   │──▶│  Build   │──▶│ Preview  │
 │  .xlsx  │   │ (pandas) │   │(Cerebras)│   │(py engine) │   │(openpyxl)│   │ & Refine │
 └─────────┘   └──────────┘   └──────────┘   └────────────┘   └──────────┘   └──────────┘
```

1. **Upload** — drag in any `.xlsx`/`.xls`. The file is validated and read.
2. **Profile** — pandas builds an *intelligence brief*: column types, ranges, Nigerian context (currency, LGA, templates) — structure only, never bulk raw values.
3. **Intent** — Cerebras returns a strictly-typed action plan (operations, target columns, output sheets). Ambiguous? It asks a clarifying question instead of guessing.
4. **Compute** — a deterministic engine (pandas, numpy, scipy, statsmodels, scikit-learn) runs every aggregation, ranking, growth, variance, correlation, forecast, and score.
5. **Build** — openpyxl assembles a styled multi-sheet workbook (Executive Summary, Data, Analysis, Charts, Forecast) with NGN formatting and conditional rules.
6. **Preview & Refine** — the in-app preview mirrors the workbook; give plain-English feedback and the report recomputes in place, version after version.

---

## Features

- 🇳🇬 **Nigerian-first** — Naira formatting, PENCOM/NHF/PAYE payroll, CBN-style banking summaries, LGA/zone territory analysis, FSO/DSA sales hierarchies.
- 🧮 **Real computation** — auditable maths in Python; every metric carries the formula used.
- 💬 **Conversational refinement** — iterate with follow-up instructions; each version keeps its own download.
- 👁️ **Live preview** — KPI cards, formatted tables, interactive charts, and forecast bands before you download.
- ⚡ **Powered by Cerebras** — fast intent classification with `gpt-oss-120b`.
- 📊 **World-class Excel output** — executive-tier styling, embedded charts, conditional formatting.

---

## Tech Stack

**Frontend** — React 18 · Vite · Tailwind CSS · Recharts · Axios · react-dropzone · canvas-confetti
**Backend** — FastAPI · Uvicorn · Pydantic · python-multipart
**Data & Compute** — pandas · numpy · scipy · statsmodels · scikit-learn · matplotlib
**Excel** — openpyxl
**AI** — Cerebras Cloud API (`gpt-oss-120b`)
**Infra** — Contabo VPS · Nginx (reverse proxy + TLS) · Let's Encrypt · systemd

---

## API

Base URL: `https://excelgpt.store/api`

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/upload` | Upload a workbook → `session_id`, preview, intelligence brief |
| `POST` | `/analyse` | Instruction → action plan, computed preview, download token |
| `POST` | `/refine` | Feedback + history → new version, preview, download token |
| `GET`  | `/download/{token}` | Stream the generated `.xlsx` |
| `GET`  | `/status/{session_id}` | Processing status |
| `GET`  | `/health` | Liveness + version |

Full contract: [`architecture/api-contract.md`](architecture/api-contract.md).

```bash
curl https://excelgpt.store/api/health
# {"status":"ok","version":"1.0.0","timestamp":"..."}
```

---

## Local Development

**Backend**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your CEREBRAS_API_KEY
uvicorn main:app --reload --port 8003
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

---

## Testing

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/ -v
```

Coverage includes the computation engine, intent engine, Excel builder, the refinement loop, **10 end-to-end dataset scenarios** (financial, sales, HR, banking, empty sheets, headerless, mixed types, single-column, 30+ columns, Unicode), and a **50,000-row stress test** (full pipeline under 60s). **47 tests, all passing.**

---

## Deployment

ExcelGPT runs on a Contabo VPS:

- **Nginx** serves the built frontend (`/var/www/excelgpt`) and reverse-proxies `/api/` to Uvicorn on `127.0.0.1:8003`, with TLS terminated by a Let's Encrypt certificate (auto-renewing via `certbot.timer`).
- **systemd** (`excelgpt-backend.service`) supervises the FastAPI backend with auto-restart.

```bash
# rebuild & redeploy the frontend
cd frontend && npm run build
sudo cp -r dist/. /var/www/excelgpt/ && sudo chown -R www-data:www-data /var/www/excelgpt

# backend service
sudo systemctl restart excelgpt-backend
sudo systemctl status  excelgpt-backend
tail -f backend/logs/service.log
```

> **Scaling note:** sessions are held in-memory, so the backend runs a single Uvicorn worker. Running multiple workers (or multiple hosts) requires moving session/download state to a shared store such as Redis.

---

## Project Structure

```
excelgpt/
├── architecture/        # system design, API contract, schemas (source of truth)
├── backend/
│   ├── main.py          # FastAPI app: upload, analyse, refine, download, status, health
│   ├── logger.py        # structured rotating logs + request timing
│   ├── config.py        # env-driven configuration
│   ├── schemas/         # Pydantic models (API, Cerebras, computation)
│   ├── services/        # reader, profiler, intent engine, computation modules, sheet builders
│   └── tests/           # unit, e2e, stress
└── frontend/
    ├── src/             # React app: upload, preview, charts, refinement
    ├── vite.config.js   # @vitejs/plugin-react (JSX automatic runtime)
    └── postcss.config.js# Tailwind + autoprefixer
```

---

## License

Proprietary — © ExcelGPT. All rights reserved.

---

<p align="center"><em>Upload. Describe. Download. — <a href="https://excelgpt.store">excelgpt.store</a></em></p>
