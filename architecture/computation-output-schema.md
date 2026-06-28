# ExcelGPT — Computation Output Schema

This is the hand-off contract **from the computation engine to the Excel generation engine**. Every value here has already been computed deterministically in Python (pandas/numpy/scipy/statsmodels/scikit-learn). openpyxl consumes this JSON and renders the multi-sheet workbook — it performs no math, only layout and formatting. The Pydantic models are in `backend/schemas/computation_schema.py`.

---

## Full JSON schema

```json
{
  "session_id": "string",
  "version": 1,
  "executive_summary": {
    "title": "string",
    "period": "string",
    "data_source": "string",
    "kpi_cards": [
      { "label": "string", "value": "string", "change": "string", "direction": "up | down | neutral" }
    ]
  },
  "data_sheet": {
    "columns": [],
    "rows": [],
    "conditional_formatting": [
      { "column": "string", "rule": "string", "color": "string" }
    ]
  },
  "analysis_sheet": {
    "metrics": [
      { "label": "string", "value": "string", "formula_used": "string" }
    ],
    "rankings": [],
    "growth_table": []
  },
  "charts": [
    { "chart_id": "string", "chart_type": "bar | line | pie | scatter", "title": "string", "image_path": "string", "recharts_data": [] }
  ],
  "forecast_sheet": {
    "historical": [],
    "projected": [],
    "confidence_upper": [],
    "confidence_lower": [],
    "assumptions": []
  }
}
```

---

## Field reference

### Top level

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session this output belongs to. |
| `version` | int | Report version (incremented per `/analyse` or `/refine`). |
| `executive_summary` | object | The board-facing summary sheet content. |
| `data_sheet` | object | The cleaned/transformed tabular data. |
| `analysis_sheet` | object | Derived metrics, rankings, growth tables. |
| `charts` | array | Chart definitions + rendered image paths. |
| `forecast_sheet` | object | Time-series forecast with confidence bands. |

### `executive_summary`

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Report title (e.g. "Q1 2026 Branch Performance"). |
| `period` | string | Reporting period (e.g. "Jan–Mar 2026"). |
| `data_source` | string | Source workbook/sheet description. |
| `kpi_cards[]` | array | Headline KPIs rendered as cards on the summary sheet and in the frontend preview. |

**`kpi_cards[]` item**

| Field | Type | Description |
|-------|------|-------------|
| `label` | string | KPI name (e.g. "Total Deposits"). |
| `value` | string | Pre-formatted value (e.g. "₦4.21B"). |
| `change` | string | Period delta (e.g. "+12.4%"). |
| `direction` | enum | `up`, `down`, or `neutral` — drives color (emerald/red/secondary). |

### `data_sheet`

| Field | Type | Description |
|-------|------|-------------|
| `columns` | array | Ordered column headers. |
| `rows` | array | Row arrays aligned to `columns`. |
| `conditional_formatting[]` | array | Rules openpyxl applies (e.g. highlight cells below target). |

**`conditional_formatting[]` item**

| Field | Type | Description |
|-------|------|-------------|
| `column` | string | Column the rule targets. |
| `rule` | string | Condition expression (e.g. "value < target"). |
| `color` | string | Fill color hex (from the ExcelGPT palette). |

### `analysis_sheet`

| Field | Type | Description |
|-------|------|-------------|
| `metrics[]` | array | Each derived metric with its `formula_used` for auditability. |
| `rankings` | array | Ranked rows (e.g. top branches/FSOs by score). |
| `growth_table` | array | Period-over-period growth rows. |

**`metrics[]` item**

| Field | Type | Description |
|-------|------|-------------|
| `label` | string | Metric name. |
| `value` | string | Pre-formatted computed value. |
| `formula_used` | string | Human-readable formula/method (e.g. "(curr − prev) / prev × 100"). |

### `charts[]`

| Field | Type | Description |
|-------|------|-------------|
| `chart_id` | string | Stable id (e.g. `c1`). |
| `chart_type` | enum | `bar`, `line`, `pie`, `scatter`. |
| `title` | string | Chart title. |
| `image_path` | string | Path to the matplotlib-rendered PNG for openpyxl embedding. |
| `recharts_data` | array | Same data shaped for the frontend Recharts preview. |

### `forecast_sheet`

| Field | Type | Description |
|-------|------|-------------|
| `historical` | array | Observed series points. |
| `projected` | array | Forecasted points (statsmodels). |
| `confidence_upper` | array | Upper confidence band. |
| `confidence_lower` | array | Lower confidence band. |
| `assumptions` | array | Stated modelling assumptions (model, periods, confidence level). |

---

## Example (abridged)

```json
{
  "session_id": "f3c2a9e1-7b54-4d2a-9c10-2b8e5a1f0d44",
  "version": 1,
  "executive_summary": {
    "title": "Q1 2026 Branch Deposit Performance",
    "period": "Jan–Mar 2026",
    "data_source": "Branch Deposits (240 rows, 36 branches)",
    "kpi_cards": [
      { "label": "Total Deposits", "value": "₦4.21B", "change": "+12.4%", "direction": "up" },
      { "label": "Avg. Branch Growth", "value": "8.7%", "change": "+1.9pp", "direction": "up" },
      { "label": "Branches Below Target", "value": "6", "change": "-2", "direction": "down" }
    ]
  },
  "data_sheet": {
    "columns": ["branch_name", "lga", "deposits_ngn", "growth_pct"],
    "rows": [["Lagos Island", "Lagos Island", 154000000, 14.2]],
    "conditional_formatting": [
      { "column": "growth_pct", "rule": "value < 0", "color": "#EF4444" }
    ]
  },
  "analysis_sheet": {
    "metrics": [
      { "label": "Quarterly Growth", "value": "12.4%", "formula_used": "(Q1 − Q0) / Q0 × 100" }
    ],
    "rankings": [{ "rank": 1, "branch_name": "Lagos Island", "growth_pct": 14.2 }],
    "growth_table": [{ "branch_name": "Lagos Island", "q0": 134800000, "q1": 154000000, "growth_pct": 14.2 }]
  },
  "charts": [
    { "chart_id": "c1", "chart_type": "bar", "title": "Deposit Growth by Branch",
      "image_path": "./storage/uploads/f3c2.../c1.png", "recharts_data": [] }
  ],
  "forecast_sheet": {
    "historical": [134800000, 154000000],
    "projected": [171200000, 188400000, 205900000],
    "confidence_upper": [178000000, 199000000, 221000000],
    "confidence_lower": [164400000, 177800000, 190800000],
    "assumptions": ["ARIMA(1,1,1)", "3 periods ahead", "95% confidence"]
  }
}
```

## Notes

- Only sheets listed in the action plan's `output_sheets_required` are populated; others may be empty/omitted.
- Numeric raw values live here; the frontend preview receives the pre-formatted string versions.
- `image_path` files live under `UPLOAD_DIR` and are cleaned up with the session.
