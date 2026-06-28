# ExcelGPT

**AI-powered Excel transformation and report generation — built for the Nigerian market.**

ExcelGPT turns raw Excel spreadsheets and a plain-English instruction into a polished, multi-sheet Excel report: executive summaries, KPI dashboards, analysis tables, charts, and forecasts. It is purpose-built for Nigerian business contexts — banking (CBN returns, branch performance), sales (FSO/DSA hierarchies, territory analysis), HR & payroll (PENCOM, NHF, PAYE), executive board packs, and LGA/territory intelligence — with NGN currency formatting and Nigerian fiscal-calendar awareness throughout.

> **Phase 1 status:** This repository is the *blueprint*. It contains the full architecture, API contracts, JSON schemas, Pydantic models, and skeleton application shells. **No business logic is implemented yet** — every endpoint and component is a documented placeholder.

---

## Architecture at a glance

ExcelGPT separates **intent** from **computation**. The Cerebras LLM is used *only* to translate a user's instruction (plus a data "intelligence brief") into a structured **action plan** — it never sees raw data values and never performs math. All numerical work happens deterministically in a Python computation engine (pandas, numpy, scipy, statsmodels, scikit-learn). This keeps results auditable, reproducible, and trustworthy for finance-grade reporting.

```
React + Tailwind (Vercel)
        │  SheetJS reads client-side, Axios calls API
        ▼
FastAPI + Uvicorn (Contabo VPS, behind Nginx)
        │
        ├─ Data Intelligence Layer   → pandas profiling → intelligence brief JSON
        ├─ AI Intent Layer           → Cerebras API → action plan JSON (intent only)
        ├─ Computation Layer         → pandas/numpy/scipy/statsmodels/sklearn → computation output JSON
        └─ Excel Generation Layer    → openpyxl → multi-sheet .xlsx
```

See [architecture/system-architecture.md](architecture/system-architecture.md) for the full description and [architecture/data-flow.md](architecture/data-flow.md) for the end-to-end request lifecycle.

---

## Tech stack

### Frontend
- **React 18** + **Vite** — SPA shell
- **Tailwind CSS** + `@tailwindcss/forms` — design system (navy / electric-blue theme)
- **SheetJS (xlsx)** — client-side Excel reading and preview
- **Recharts** — KPI charts in the preview panel
- **Axios** — API client
- **react-dropzone** — upload zone
- **framer-motion** — transitions
- **lucide-react** — icons
- Hosted on **Vercel**

### Backend
- **FastAPI** + **Uvicorn** — REST API
- **python-multipart** — file uploads
- **pandas / numpy** — data handling and intelligence brief
- **scipy / statsmodels / scikit-learn** — statistics, forecasting, scoring, clustering
- **matplotlib / seaborn** — chart image rendering for Excel embedding
- **openpyxl** — multi-sheet Excel generation
- **cerebras-cloud-sdk** — AI intent layer
- **pydantic** — schema validation
- **python-dotenv** — configuration
- Hosted on a **Contabo VPS** behind **Nginx**

---

## Repository layout

```
excelgpt/
├── README.md
├── .env.example
├── architecture/            # The blueprint: design docs, contracts, schemas
├── frontend/                # React shell (no logic yet)
└── backend/                 # FastAPI shell (endpoints defined, not implemented)
```

---

## Getting started

### Prerequisites
- Node.js ≥ 18 and npm
- Python ≥ 3.10 and pip
- A Cerebras API key (https://cloud.cerebras.ai)

### 1. Environment setup
Copy the example environment file and fill in your values:

```bash
cp .env.example backend/.env
```

Then edit `backend/.env`. Every variable is documented in
[architecture/environment-variables.md](architecture/environment-variables.md).

### 2. Run the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173` (Vite default).

---

## API summary

| Method | Path                | Purpose                                              |
|--------|---------------------|------------------------------------------------------|
| POST   | `/upload`           | Upload Excel, get `session_id` + preview + brief     |
| POST   | `/analyse`          | Send instruction, get action plan + preview + token  |
| POST   | `/refine`           | Iterate on a report with conversation history        |
| GET    | `/download/{token}` | Stream the generated `.xlsx` file                    |
| GET    | `/health`           | Liveness/version check                               |

Full request/response contracts: [architecture/api-contract.md](architecture/api-contract.md).

---

## Nigerian market focus

ExcelGPT ships with five template families tuned to Nigerian reporting norms — Banking & Finance, Sales Performance, HR & Payroll, Executive Reports, and LGA/Territory Intelligence. See [architecture/nigerian-templates.md](architecture/nigerian-templates.md). Currency defaults to **NGN (₦)**, and the action plan carries a `nigerian_context` block (currency, template type, fiscal calendar, LGA analysis flag) end-to-end.

---

## License

Proprietary — © ExcelGPT. All rights reserved.
