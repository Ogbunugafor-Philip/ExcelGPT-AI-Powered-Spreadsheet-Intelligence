import { useMemo, useState } from 'react'

const formatCell = (value, type) => {
  if (value === null || value === undefined || value === '') return '—'
  if (type === 'currency' && typeof value === 'number') return `₦${value.toLocaleString()}`
  return value
}

export default function DataPreview({ preview, intelligenceBrief }) {
  const [activeSheet, setActiveSheet] = useState(0)
  const sheet = preview?.sheets?.[activeSheet]

  const summary = useMemo(() => ({
    totalRows: preview?.sheets?.reduce((sum, item) => sum + (item?.row_count || 0), 0) || 0,
    totalSheets: preview?.sheets?.length || 0,
  }), [preview])

  if (!preview?.sheets?.length) {
    return null
  }

  return (
    <section className="eg-card p-8" aria-label="Data preview">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Data intelligence preview</h2>
          <p className="eg-text-muted mt-2">A clean preview of your workbook with intelligent structure and context.</p>
        </div>
        <div className="rounded-full border border-blue-electric/30 bg-blue-electric/10 px-3 py-1 text-sm text-blue-electric">
          {summary.totalSheets} sheets • {summary.totalRows} rows
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {preview.sheets.map((item, index) => (
          <button
            key={item.name}
            type="button"
            onClick={() => setActiveSheet(index)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${activeSheet === index ? 'bg-blue-electric text-white' : 'bg-white/5 text-text-secondary hover:bg-white/10'}`}
          >
            {item.name}
          </button>
        ))}
      </div>

      {sheet ? (
        <div className="mt-6 overflow-hidden rounded-2xl border border-white/10 bg-navy">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div>
              <p className="text-sm text-text-secondary">Active sheet</p>
              <p className="font-semibold">{sheet.name}</p>
            </div>
            <div className="rounded-full bg-white/10 px-3 py-1 text-sm text-text-secondary">
              Showing 100 of {sheet.row_count} rows
            </div>
          </div>

          <div className="max-h-[420px] overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-navy-light text-left">
                <tr>
                  {sheet.columns.map((column, index) => (
                    <th key={`${column}-${index}`} className="border-b border-white/10 px-4 py-3 font-semibold text-text-primary">
                      <div className="flex items-center gap-2">
                        <span>{column}</span>
                        <span className="rounded-full bg-blue-electric/10 px-2 py-0.5 text-[11px] text-blue-electric">
                          text
                        </span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sheet.rows.map((row, rowIndex) => (
                  <tr key={`${rowIndex}-${sheet.name}`} className={rowIndex % 2 === 0 ? 'bg-navy-light/70' : 'bg-navy'}>
                    {sheet.columns.map((column, columnIndex) => {
                      const value = row?.[column]
                      return (
                        <td key={`${column}-${columnIndex}`} className="border-b border-white/5 px-4 py-3 text-text-primary">
                          <div className={`truncate ${typeof value === 'number' ? 'text-right font-medium' : 'text-left'}`}>
                            {formatCell(value, 'text')}
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-2xl border border-white/10 bg-navy-light/70 p-4">
          <h3 className="text-lg font-semibold">Intelligence brief</h3>
          <p className="eg-text-muted mt-1">Detected context and suggested next actions.</p>
          <div className="mt-4 space-y-4">
            <div>
              <p className="text-sm font-semibold text-text-secondary">Nigerian context</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {intelligenceBrief?.nigerian_context?.detected ? (
                  intelligenceBrief.nigerian_context.flags.map((flag) => (
                    <span key={flag} className="rounded-full bg-emerald/15 px-3 py-1 text-sm text-emerald">{flag}</span>
                  ))
                ) : (
                  <span className="text-sm text-text-secondary">No explicit Nigerian markers detected.</span>
                )}
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-text-secondary">Suggested template</p>
              <p className="mt-2 text-sm text-text-primary">{intelligenceBrief?.nigerian_context?.suggested_template || 'general'}</p>
            </div>
            <div>
              <p className="text-sm font-semibold text-text-secondary">Potential join keys</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {intelligenceBrief?.potential_join_keys?.length ? intelligenceBrief.potential_join_keys.map((value) => (
                  <span key={value} className="rounded-full border border-blue-electric/30 px-3 py-1 text-sm text-blue-electric">{value}</span>
                )) : <span className="text-sm text-text-secondary">None identified.</span>}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-navy-light/70 p-4">
          <h3 className="text-lg font-semibold">Suggested operations</h3>
          <div className="mt-4 flex flex-wrap gap-2">
            {intelligenceBrief?.suggested_operations?.map((operation) => (
              <button key={operation} type="button" className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-sm text-text-primary hover:bg-white/10">
                {operation}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
