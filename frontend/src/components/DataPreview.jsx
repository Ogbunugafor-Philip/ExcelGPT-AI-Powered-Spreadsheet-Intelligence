import { useMemo, useState } from 'react'
import { ChevronDown, Loader2 } from 'lucide-react'
import { useVirtualRows } from '../utils/useVirtualRows'

const ROW_HEIGHT = 40

const formatCell = (value, type) => {
  if (value === null || value === undefined || value === '') return '—'
  if (type === 'currency' && typeof value === 'number') return `₦${value.toLocaleString()}`
  return value
}

export default function DataPreview({ preview, intelligenceBrief }) {
  const [activeSheet, setActiveSheet] = useState(0)
  const [briefOpen, setBriefOpen] = useState(false)
  const sheet = preview?.sheets?.[activeSheet]

  const summary = useMemo(() => ({
    totalRows: preview?.sheets?.reduce((sum, item) => sum + (item?.row_count || 0), 0) || 0,
    totalSheets: preview?.sheets?.length || 0,
  }), [preview])

  const rows = sheet?.rows || []
  const v = useVirtualRows(rows.length, { rowHeight: ROW_HEIGHT, maxHeight: 420 })

  if (!preview?.sheets?.length) {
    return null
  }

  const visibleRows = v.enabled ? rows.slice(v.start, v.end) : rows

  return (
    <section className="eg-card p-6 sm:p-8" aria-label="Data preview">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-heading">Data intelligence preview</h2>
          <p className="eg-text-muted mt-2 text-small">A clean preview of your workbook with intelligent structure and context.</p>
        </div>
        <div className="rounded-full border border-blue-electric/30 bg-blue-electric/10 px-3 py-1 text-small text-blue-electric">
          {summary.totalSheets} sheets • {summary.totalRows} rows
        </div>
      </div>

      <div className="mt-6 flex gap-2 overflow-x-auto pb-1">
        {preview.sheets.map((item, index) => (
          <button
            key={item.name}
            type="button"
            onClick={() => setActiveSheet(index)}
            className={`shrink-0 whitespace-nowrap rounded-full px-4 py-2 text-small font-medium transition ${activeSheet === index ? 'bg-blue-electric text-white' : 'glass text-text-secondary hover:text-text-primary'}`}
          >
            {item.name}
          </button>
        ))}
      </div>

      {sheet ? (
        <div className="mt-6 overflow-hidden rounded-2xl border border-white/10 bg-navy">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div>
              <p className="text-small text-text-secondary">Active sheet</p>
              <p className="font-semibold">{sheet.name}</p>
            </div>
            <div className="rounded-full bg-white/10 px-3 py-1 text-small text-text-secondary">
              Showing {rows.length} of {sheet.row_count} rows
            </div>
          </div>

          <div ref={v.ref} onScroll={v.onScroll} className="relative max-h-[420px] overflow-auto">
            <table className="min-w-full border-collapse text-small">
              <thead className="sticky top-0 z-10 bg-navy-light text-left">
                <tr>
                  {sheet.columns.map((column, index) => (
                    <th key={`${column}-${index}`} className="whitespace-nowrap border-b border-white/10 px-4 py-3 font-semibold text-text-primary">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {v.enabled && v.topPad > 0 ? (
                  <tr style={{ height: v.topPad }}><td colSpan={sheet.columns.length} /></tr>
                ) : null}
                {visibleRows.map((row, i) => {
                  const rowIndex = v.enabled ? v.start + i : i
                  return (
                    <tr key={`${rowIndex}-${sheet.name}`} style={{ height: ROW_HEIGHT }} className={rowIndex % 2 === 0 ? 'bg-navy-light/70' : 'bg-navy'}>
                      {sheet.columns.map((column, columnIndex) => {
                        const value = row?.[column]
                        return (
                          <td key={`${column}-${columnIndex}`} className="border-b border-white/5 px-4 text-text-primary">
                            <div className={`truncate ${typeof value === 'number' ? 'text-right font-medium tabular-nums' : 'text-left'}`}>
                              {formatCell(value, 'text')}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
                {v.enabled && v.bottomPad > 0 ? (
                  <tr style={{ height: v.bottomPad }}><td colSpan={sheet.columns.length} /></tr>
                ) : null}
              </tbody>
            </table>

            {v.enabled && v.end < rows.length ? (
              <div className="pointer-events-none sticky bottom-0 flex items-center justify-center gap-2 bg-gradient-to-t from-navy to-transparent py-2 text-micro text-text-muted">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading more rows…
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Intelligence brief — collapsible on mobile, always open on desktop. */}
      <div className="mt-8">
        <button
          type="button"
          onClick={() => setBriefOpen((open) => !open)}
          className="flex w-full items-center justify-between md:hidden"
        >
          <h3 className="text-subheading">Intelligence brief</h3>
          <ChevronDown className={`h-5 w-5 text-text-secondary transition-transform ${briefOpen ? 'rotate-180' : ''}`} />
        </button>

        <div className={`${briefOpen ? 'grid' : 'hidden'} mt-4 gap-6 md:mt-0 md:grid lg:grid-cols-[1.15fr_0.85fr]`}>
          <div className="rounded-2xl border border-white/10 bg-navy-light/70 p-4">
            <h3 className="hidden text-subheading md:block">Intelligence brief</h3>
            <p className="eg-text-muted mt-1 text-small">Detected context and suggested next actions.</p>
            <div className="mt-4 space-y-4">
              <div>
                <p className="text-small font-semibold text-text-secondary">Nigerian context</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {intelligenceBrief?.nigerian_context?.detected ? (
                    intelligenceBrief.nigerian_context.flags.map((flag) => (
                      <span key={flag} className="rounded-full bg-emerald/15 px-3 py-1 text-small text-emerald">{flag}</span>
                    ))
                  ) : (
                    <span className="text-small text-text-secondary">No explicit Nigerian markers detected.</span>
                  )}
                </div>
              </div>
              <div>
                <p className="text-small font-semibold text-text-secondary">Suggested template</p>
                <p className="mt-2 text-small text-text-primary">{intelligenceBrief?.nigerian_context?.suggested_template || 'general'}</p>
              </div>
              <div>
                <p className="text-small font-semibold text-text-secondary">Potential join keys</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {intelligenceBrief?.potential_join_keys?.length ? intelligenceBrief.potential_join_keys.map((value) => (
                    <span key={value} className="rounded-full border border-blue-electric/30 px-3 py-1 text-small text-blue-electric">{value}</span>
                  )) : <span className="text-small text-text-secondary">None identified.</span>}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-navy-light/70 p-4">
            <h3 className="text-subheading">Suggested operations</h3>
            <div className="mt-4 flex flex-wrap gap-2">
              {intelligenceBrief?.suggested_operations?.map((operation) => (
                <span key={operation} className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-small text-text-primary">
                  {operation}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
