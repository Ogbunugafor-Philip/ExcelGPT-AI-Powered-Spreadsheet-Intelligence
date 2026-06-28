# ExcelGPT — REST API Contract

Base URL (dev): `http://localhost:8000`
Content type: `application/json` unless noted (uploads use `multipart/form-data`).
All responses are JSON unless noted (downloads stream a binary `.xlsx`).

The Pydantic models backing this contract live in `backend/schemas/api_schema.py`.

---

## POST /upload

Upload an Excel workbook to start a session.

**Request** — `multipart/form-data`
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | file | yes | `.xlsx` / `.xls`, ≤ `MAX_FILE_SIZE_MB` |

**Response** — `200 OK`
```json
{
  "session_id": "f3c2a9e1-7b54-4d2a-9c10-2b8e5a1f0d44",
  "preview": {
    "sheets": [
      {
        "name": "Branch Deposits",
        "columns": ["branch_code", "branch_name", "lga", "deposits_ngn", "month"],
        "rows": [
          ["BR001", "Lagos Island", "Lagos Island", 154000000, "2026-01"],
          ["BR002", "Ikeja", "Ikeja", 98700000, "2026-01"]
        ],
        "row_count": 240
      }
    ]
  },
  "intelligence_brief": {
    "sheets": [
      {
        "name": "Branch Deposits",
        "row_count": 240,
        "columns": [
          { "name": "deposits_ngn", "type": "currency", "null_pct": 0.0,
            "min": 1200000, "max": 420000000, "distinct": 238 }
        ]
      }
    ],
    "relationships": [
      { "from": "Branch Deposits.branch_code", "to": "Branch Loans.branch_code", "kind": "shared_key" }
    ]
  }
}
```

**Errors**
| Code | When |
|------|------|
| 400 | No file / unsupported extension |
| 413 | File exceeds `MAX_FILE_SIZE_MB` |
| 422 | File is not a readable workbook |

---

## POST /analyse

Turn a natural-language instruction into an action plan and a generated report.

**Request** — `application/json`
```json
{
  "session_id": "f3c2a9e1-7b54-4d2a-9c10-2b8e5a1f0d44",
  "instruction": "Rank branches by deposit growth this quarter and forecast next quarter in NGN."
}
```

**Response** — `200 OK`
```json
{
  "action_plan": { "...": "see architecture/cerebras-schema.md" },
  "preview": {
    "sheets": [ { "name": "Analysis", "columns": ["branch_name", "growth_pct"], "rows": [], "row_count": 36 } ],
    "kpi_cards": [
      { "label": "Total Deposits", "value": "₦4.21B", "change": "+12.4%", "direction": "up" }
    ],
    "charts": [
      { "chart_id": "c1", "chart_type": "bar", "title": "Deposit Growth by Branch", "recharts_data": [] }
    ]
  },
  "download_token": "dl_8a1f0d44c2e9",
  "version": 1
}
```

If clarification is required, `action_plan.clarification_needed` is `true` and `action_plan.clarification_question` is populated; `download_token` may be `null` and no file is generated until the user responds.

**Errors**
| Code | When |
|------|------|
| 404 | Unknown/expired `session_id` |
| 422 | Empty/invalid instruction |
| 502 | Cerebras intent service unavailable |

---

## POST /refine

Iterate on an existing report using conversation history.

**Request** — `application/json`
```json
{
  "session_id": "f3c2a9e1-7b54-4d2a-9c10-2b8e5a1f0d44",
  "feedback": "Show growth as a percentage and add a pie chart of deposits by LGA.",
  "history": [
    { "role": "user", "content": "Rank branches by deposit growth and forecast next quarter." },
    { "role": "assistant", "content": "Generated ranking + ARIMA forecast (version 1)." }
  ],
  "current_version": 1
}
```

**Response** — `200 OK` — same shape as `/analyse`, with an incremented `version` and a new `download_token`.
```json
{
  "action_plan": { "...": "updated plan" },
  "preview": { "sheets": [], "kpi_cards": [], "charts": [] },
  "download_token": "dl_9b2e1f55d3fa",
  "version": 2
}
```

**Errors**
| Code | When |
|------|------|
| 404 | Unknown/expired `session_id` |
| 409 | `current_version` does not match server state |
| 502 | Cerebras intent service unavailable |

---

## GET /download/{token}

Download the generated workbook.

**Path params**
| Param | Type | Notes |
|-------|------|-------|
| `token` | string | One-time/short-lived download token from `/analyse` or `/refine` |

**Response** — `200 OK`
- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `Content-Disposition: attachment; filename="excelgpt-report-v{version}.xlsx"`
- Body: binary `.xlsx` stream.

**Errors**
| Code | When |
|------|------|
| 404 | Unknown token |
| 410 | Token/session expired |

---

## GET /health

Liveness and version probe (used by Nginx/uptime checks).

**Response** — `200 OK`
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-06-28T10:15:30Z"
}
```

---

## Conventions

- **Errors** use a consistent body: `{ "detail": "<human-readable message>" }` (FastAPI default).
- **Timestamps** are ISO-8601 UTC.
- **Currency** values in previews are pre-formatted strings (`"₦4.21B"`); raw numbers live in the generated `.xlsx`.
- **CORS** is restricted to `ALLOWED_ORIGINS`.
- **Versioning** increments per successful `/analyse` or `/refine`; each version has its own download token until session expiry.
