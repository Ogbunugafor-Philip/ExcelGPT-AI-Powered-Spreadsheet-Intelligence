# ExcelGPT — Cerebras Action Plan Schema

The **action plan** is the only thing the Cerebras LLM produces. It is *intent*, not computation: it names operations, target sheets/columns, and where results belong — but it never contains computed values and never receives bulk raw data. The backend validates this JSON against the Pydantic models in `backend/schemas/cerebras_schema.py` before routing it to the computation engine.

---

## Full JSON schema

```json
{
  "intent_type": "aggregation | growth_analysis | statistical_analysis | forecasting | performance_scoring | formatting_only | custom",
  "clarification_needed": false,
  "clarification_question": null,
  "operations": [
    {
      "operation_id": "string",
      "operation_type": "group_sum | group_avg | rank | filter | growth_rate | variance | correlation | outlier | distribution | forecast | cluster | score | chart",
      "target_sheet": "string",
      "target_columns": ["string"],
      "group_by": ["string"],
      "parameters": {},
      "output_sheet": "executive_summary | data | analysis | charts | forecast",
      "output_label": "string"
    }
  ],
  "output_sheets_required": ["executive_summary", "data", "analysis", "charts", "forecast"],
  "formatting_tier": "standard | premium | executive",
  "nigerian_context": {
    "currency": "NGN",
    "template_type": "banking | sales | hr | general",
    "fiscal_calendar": "january | april",
    "lga_analysis": false
  }
}
```

---

## Field reference

### Top level

| Field | Type | Description |
|-------|------|-------------|
| `intent_type` | enum | The overall goal the user expressed. Drives which output sheets and operations are typical. |
| `clarification_needed` | bool | `true` when the instruction is too ambiguous to plan safely. When `true`, the backend pauses and returns the question instead of computing. |
| `clarification_question` | string \| null | The single question to ask the user. `null` unless `clarification_needed` is `true`. |
| `operations` | array | Ordered list of operations to execute (see below). May be empty for `formatting_only`. |
| `output_sheets_required` | array of enum | Which sheets the final workbook must contain. Subset of `executive_summary, data, analysis, charts, forecast`. |
| `formatting_tier` | enum | Visual polish level applied by openpyxl: `standard`, `premium`, `executive`. |
| `nigerian_context` | object | Market context carried end-to-end (see below). |

### `intent_type` values

| Value | Meaning |
|-------|---------|
| `aggregation` | Group/sum/avg/count rollups (e.g. deposits by branch). |
| `growth_analysis` | Period-over-period growth, variance, trend. |
| `statistical_analysis` | Correlations, distributions, hypothesis tests. |
| `forecasting` | Time-series projection with confidence bounds. |
| `performance_scoring` | Composite scoring / ranking of entities (branches, FSOs, staff). |
| `formatting_only` | Restyle / reformat existing data, no new computation. |
| `custom` | Mixed or novel intent expressed via the `operations` list. |

### `operations[]`

| Field | Type | Description |
|-------|------|-------------|
| `operation_id` | string | Unique id within the plan (e.g. `op_1`). Lets refinements reference specific steps. |
| `operation_type` | enum | The deterministic executor to invoke. |
| `target_sheet` | string | Source sheet name from the uploaded workbook. |
| `target_columns` | array of string | Columns the operation reads. |
| `group_by` | array of string | Grouping keys (empty for ungrouped ops). |
| `parameters` | object | Free-form, operation-specific knobs (see below). |
| `output_sheet` | enum | Which output sheet the result is written to. |
| `output_label` | string | Human-readable label for the result block/table/chart. |

### `operation_type` → engine mapping

| `operation_type` | Engine | Typical `parameters` |
|------------------|--------|----------------------|
| `group_sum` | pandas | `{ "agg": "sum" }` |
| `group_avg` | pandas | `{ "agg": "mean" }` |
| `rank` | pandas/numpy | `{ "by": "deposits_ngn", "order": "desc", "top_n": 10 }` |
| `filter` | pandas | `{ "where": "deposits_ngn > 100000000" }` |
| `growth_rate` | pandas/numpy | `{ "period": "quarter", "as_percent": true }` |
| `variance` | pandas/numpy | `{ "actual": "actual_col", "target": "target_col" }` |
| `correlation` | scipy | `{ "method": "pearson" }` |
| `outlier` | scipy/numpy | `{ "method": "iqr" }` |
| `distribution` | scipy.stats | `{ }` |
| `forecast` | statsmodels | `{ "model": "arima", "periods": 3, "confidence": 0.95 }` |
| `cluster` | scikit-learn | `{ "algorithm": "kmeans", "k": 4 }` |
| `score` | scikit-learn | `{ "weights": { "growth": 0.5, "volume": 0.5 } }` |
| `chart` | matplotlib | `{ "chart_type": "bar", "x": "branch_name", "y": "growth_pct" }` |

### `nigerian_context`

| Field | Type | Description |
|-------|------|-------------|
| `currency` | string | Default `"NGN"`; controls openpyxl number formatting (₦). |
| `template_type` | enum | `banking`, `sales`, `hr`, or `general` — selects the template family. |
| `fiscal_calendar` | enum | `january` (calendar-year) or `april` (govt/some-corporate fiscal year start). |
| `lga_analysis` | bool | When `true`, enables LGA/state-level breakdowns and geographic grouping. |

---

## Example — "Rank branches by deposit growth and forecast next quarter"

```json
{
  "intent_type": "growth_analysis",
  "clarification_needed": false,
  "clarification_question": null,
  "operations": [
    {
      "operation_id": "op_1",
      "operation_type": "growth_rate",
      "target_sheet": "Branch Deposits",
      "target_columns": ["deposits_ngn", "month"],
      "group_by": ["branch_name"],
      "parameters": { "period": "quarter", "as_percent": true },
      "output_sheet": "analysis",
      "output_label": "Quarterly Deposit Growth by Branch"
    },
    {
      "operation_id": "op_2",
      "operation_type": "rank",
      "target_sheet": "Branch Deposits",
      "target_columns": ["deposits_ngn"],
      "group_by": ["branch_name"],
      "parameters": { "by": "growth_pct", "order": "desc", "top_n": 10 },
      "output_sheet": "analysis",
      "output_label": "Top 10 Branches by Growth"
    },
    {
      "operation_id": "op_3",
      "operation_type": "forecast",
      "target_sheet": "Branch Deposits",
      "target_columns": ["deposits_ngn", "month"],
      "group_by": [],
      "parameters": { "model": "arima", "periods": 3, "confidence": 0.95 },
      "output_sheet": "forecast",
      "output_label": "Next-Quarter Deposit Forecast"
    },
    {
      "operation_id": "op_4",
      "operation_type": "chart",
      "target_sheet": "Branch Deposits",
      "target_columns": ["branch_name", "growth_pct"],
      "group_by": [],
      "parameters": { "chart_type": "bar", "x": "branch_name", "y": "growth_pct" },
      "output_sheet": "charts",
      "output_label": "Deposit Growth by Branch"
    }
  ],
  "output_sheets_required": ["executive_summary", "analysis", "charts", "forecast"],
  "formatting_tier": "executive",
  "nigerian_context": {
    "currency": "NGN",
    "template_type": "banking",
    "fiscal_calendar": "january",
    "lga_analysis": false
  }
}
```

## Validation rules

1. `clarification_question` MUST be non-null iff `clarification_needed` is `true`.
2. Every `operation.output_sheet` MUST appear in `output_sheets_required`.
3. `operation_type: chart` MUST set `output_sheet: charts`.
4. `nigerian_context.currency` defaults to `"NGN"` if omitted.
5. An empty `operations` array is only valid when `intent_type` is `formatting_only`.
