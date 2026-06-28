# ExcelGPT — Environment Variables

Every environment variable, its purpose, valid values, default, and which component reads it. The template lives in `.env.example`; copy it to `backend/.env`. Values are loaded into `backend/config.py` via `python-dotenv`.

---

## CEREBRAS_API_KEY

- **Purpose:** Authenticates calls to the Cerebras Cloud API in the AI intent layer (action plan generation).
- **Valid values:** A secret API key string from https://cloud.cerebras.ai.
- **Default:** none (required).
- **Used by:** Backend → AI intent layer (`cerebras-cloud-sdk` client).
- **Notes:** Secret. Never commit. Without it, `/analyse` and `/refine` cannot generate action plans.

## CEREBRAS_MODEL

- **Purpose:** Selects the Cerebras model used to generate the action plan.
- **Valid values:** Any Cerebras-hosted model id (e.g. `llama-3.3-70b`, `llama3.1-8b`).
- **Default:** `llama-3.3-70b`.
- **Used by:** Backend → AI intent layer (`IntentEngine`).
- **Notes:** Pick a model with sub-second latency to meet the Phase 3 milestone. Larger models give more reliable plans at slightly higher latency.

## CEREBRAS_TIMEOUT_SECONDS

- **Purpose:** Hard timeout on a single Cerebras request before `/analyse` fails with `502`.
- **Valid values:** Positive number (seconds). e.g. `20`.
- **Default:** `20`.
- **Used by:** Backend → AI intent layer (`Cerebras` client timeout).

## CEREBRAS_TEMPERATURE

- **Purpose:** Sampling temperature for action-plan generation.
- **Valid values:** Float `0.0`–`2.0`.
- **Default:** `0.1` (near-deterministic plans).
- **Used by:** Backend → AI intent layer.

## CEREBRAS_MAX_TOKENS

- **Purpose:** Upper bound on the generated action-plan JSON length.
- **Valid values:** Positive integer (tokens). e.g. `1200`.
- **Default:** `1200`.
- **Used by:** Backend → AI intent layer.

## ALLOWED_ORIGINS

- **Purpose:** Whitelist of origins permitted by CORS — locks the API to the ExcelGPT frontend.
- **Valid values:** Comma-separated list of origin URLs. e.g. `https://excelgpt.vercel.app,http://localhost:5173`.
- **Default:** `http://localhost:5173` (Vite dev server).
- **Used by:** Backend → FastAPI CORS middleware.
- **Notes:** In production include the Vercel URL. Avoid `*` in production.

## MAX_FILE_SIZE_MB

- **Purpose:** Upper bound on uploaded workbook size; rejects oversized files at `/upload`.
- **Valid values:** Positive integer (megabytes). e.g. `25`.
- **Default:** `25`.
- **Used by:** Backend → ingest (`/upload` validation). Mirror in Nginx `client_max_body_size`.
- **Notes:** Converted to bytes in `config.py` (`MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024`).

## UPLOAD_DIR

- **Purpose:** Filesystem directory for uploaded workbooks, rendered chart PNGs, and generated `.xlsx` reports.
- **Valid values:** Absolute or relative path. e.g. `./storage/uploads` or `/var/excelgpt/uploads`.
- **Default:** `./storage/uploads`.
- **Used by:** Backend → ingest, Excel generation, download, cleanup.
- **Notes:** Must be writable by the Uvicorn process. Pruned on session expiry.

## SESSION_EXPIRY_MINUTES

- **Purpose:** Lifetime of a session and its download tokens before expiry and cleanup.
- **Valid values:** Positive integer (minutes). e.g. `60`.
- **Default:** `60`.
- **Used by:** Backend → session manager, `/download/{token}` validation, cleanup job.
- **Notes:** After expiry, `/download` returns `410 Gone`; the user must re-run `/refine`.

## BACKEND_PORT

- **Purpose:** TCP port Uvicorn binds to.
- **Valid values:** Valid port integer (1024–65535). e.g. `8000`.
- **Default:** `8000`.
- **Used by:** Backend → Uvicorn startup; Nginx upstream config.
- **Notes:** Nginx proxies public 443 → this port on the Contabo VPS.

## ENVIRONMENT

- **Purpose:** Selects environment-specific behaviour (logging verbosity, docs exposure, error detail).
- **Valid values:** `development` | `staging` | `production`.
- **Default:** `development`.
- **Used by:** Backend → app startup, logging, error handling.
- **Notes:** In `production`, suppress stack traces in responses and consider disabling `/docs`.

---

## Quick reference

| Variable | Type | Default | Required | Component |
|----------|------|---------|:--------:|-----------|
| `CEREBRAS_API_KEY` | secret string | — | ✅ | AI intent layer |
| `CEREBRAS_MODEL` | string | `llama-3.3-70b` | — | AI intent layer |
| `CEREBRAS_TIMEOUT_SECONDS` | float (s) | `20` | — | AI intent layer |
| `CEREBRAS_TEMPERATURE` | float | `0.1` | — | AI intent layer |
| `CEREBRAS_MAX_TOKENS` | int | `1200` | — | AI intent layer |
| `ALLOWED_ORIGINS` | csv urls | `http://localhost:5173` | ✅ | CORS middleware |
| `MAX_FILE_SIZE_MB` | int (MB) | `25` | — | Upload validation |
| `UPLOAD_DIR` | path | `./storage/uploads` | — | Storage / Excel gen |
| `SESSION_EXPIRY_MINUTES` | int (min) | `60` | — | Session / download |
| `BACKEND_PORT` | int (port) | `8000` | — | Uvicorn / Nginx |
| `ENVIRONMENT` | enum | `development` | — | App startup |

## Loading order

1. `.env` (copied from `.env.example`) sits in `backend/`.
2. `python-dotenv` loads it at process start.
3. `config.py` reads each variable, applies defaults, and derives constants (e.g. `MAX_FILE_SIZE`).
4. FastAPI/Uvicorn and all layers read configuration from `config.py` — never from `os.environ` directly.
