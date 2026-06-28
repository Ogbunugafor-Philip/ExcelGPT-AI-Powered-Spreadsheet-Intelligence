import { ArrowRight, FileSpreadsheet, ListChecks, Sparkles } from 'lucide-react'

const INTENT_LABELS = {
  aggregation: 'Aggregation',
  growth_analysis: 'Growth analysis',
  statistical_analysis: 'Statistical analysis',
  forecasting: 'Forecasting',
  performance_scoring: 'Performance scoring',
  formatting_only: 'Formatting only',
  custom: 'Custom',
}

const SHEET_LABELS = {
  executive_summary: 'Executive Summary',
  data: 'Data',
  analysis: 'Analysis',
  charts: 'Charts',
  forecast: 'Forecast',
}

const TIER_TONE = {
  standard: 'border-blue-electric/30 bg-blue-electric/10 text-blue-electric',
  premium: 'border-blue-glow/40 bg-blue-glow/10 text-blue-glow',
  executive: 'border-gold/40 bg-gold/10 text-gold',
}

const prettyOperation = (type) =>
  (type || '').replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())

export default function ActionPlanSummary({ plan }) {
  if (!plan) return null

  const context = plan.nigerian_context || {}
  const operations = plan.operations || []
  const sheets = plan.output_sheets_required || []
  const tierTone = TIER_TONE[plan.formatting_tier] || TIER_TONE.standard

  return (
    <section className="eg-card p-8" aria-label="Action plan">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-electric/15 text-blue-electric">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-2xl font-semibold">Action plan</h2>
            <p className="eg-text-muted mt-1">Confirm what ExcelGPT will build before any numbers are computed.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-blue-electric/30 bg-blue-electric/10 px-3 py-1 text-sm font-medium text-blue-electric">
            {INTENT_LABELS[plan.intent_type] || plan.intent_type}
          </span>
          <span className={`rounded-full border px-3 py-1 text-sm font-medium capitalize ${tierTone}`}>
            {plan.formatting_tier} tier
          </span>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Template', value: context.template_type || 'general' },
          { label: 'Currency', value: context.currency || 'NGN' },
          { label: 'Fiscal calendar', value: context.fiscal_calendar || 'january' },
          { label: 'LGA analysis', value: context.lga_analysis ? 'Enabled' : 'Off' },
        ].map((item) => (
          <div key={item.label} className="rounded-2xl border border-white/10 bg-navy-light/70 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">{item.label}</p>
            <p className="mt-1 font-semibold capitalize text-text-primary">{item.value}</p>
          </div>
        ))}
      </div>

      <div className="mt-6">
        <p className="flex items-center gap-2 text-sm font-semibold text-text-secondary">
          <FileSpreadsheet className="h-4 w-4" /> Output sheets
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {sheets.length ? (
            sheets.map((sheet) => (
              <span key={sheet} className="rounded-full border border-blue-electric/30 px-3 py-1 text-sm text-blue-electric">
                {SHEET_LABELS[sheet] || sheet}
              </span>
            ))
          ) : (
            <span className="text-sm text-text-secondary">No output sheets specified.</span>
          )}
        </div>
      </div>

      <div className="mt-6">
        <p className="flex items-center gap-2 text-sm font-semibold text-text-secondary">
          <ListChecks className="h-4 w-4" /> Operations ({operations.length})
        </p>
        <ol className="mt-3 space-y-3">
          {operations.length ? (
            operations.map((operation, index) => (
              <li
                key={operation.operation_id || index}
                className="rounded-2xl border border-white/10 bg-navy-light/70 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-text-primary">
                    {operation.output_label || prettyOperation(operation.operation_type)}
                  </p>
                  <span className="rounded-full bg-blue-electric/10 px-2.5 py-0.5 text-xs font-medium text-blue-electric">
                    {prettyOperation(operation.operation_type)}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-text-secondary">
                  <span className="font-medium text-text-primary">{operation.target_sheet}</span>
                  {operation.target_columns?.length ? (
                    <span>· {operation.target_columns.join(', ')}</span>
                  ) : null}
                  {operation.group_by?.length ? (
                    <span>· grouped by {operation.group_by.join(', ')}</span>
                  ) : null}
                  <span className="inline-flex items-center gap-1">
                    <ArrowRight className="h-3.5 w-3.5" />
                    {SHEET_LABELS[operation.output_sheet] || operation.output_sheet}
                  </span>
                </div>
              </li>
            ))
          ) : (
            <li className="rounded-2xl border border-white/10 bg-navy-light/70 p-4 text-sm text-text-secondary">
              No computation — formatting only.
            </li>
          )}
        </ol>
      </div>
    </section>
  )
}
