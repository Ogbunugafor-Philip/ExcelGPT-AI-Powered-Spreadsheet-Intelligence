import { useMemo } from 'react'
import { Loader2 } from 'lucide-react'
import { useVirtualRows } from '../../utils/useVirtualRows'

const ROW_HEIGHT = 40

// Formatted preview of the computed Data sheet. Values are raw; we format by the
// column type exactly as the Excel writer does (₦ currency, % suffix, right-aligned
// numbers) and apply the same conditional-formatting tints. Large tables are
// virtualised so only on-screen rows render.

const RULE_RE = /(<=|>=|==|!=|=|<|>)\s*(-?\d+(?:\.\d+)?)/

const isNumber = (value) => typeof value === 'number' && Number.isFinite(value)

const formatCell = (value, type) => {
  if (value === null || value === undefined || value === '') return '—'
  if (type === 'currency' && isNumber(value)) {
    return `₦${value.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
  }
  if (type === 'percentage' && isNumber(value)) {
    return `${value.toLocaleString('en-US', { maximumFractionDigits: 2 })}%`
  }
  if (type === 'number' && isNumber(value)) {
    return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
  return String(value)
}

const isRightAligned = (type) => type === 'currency' || type === 'percentage' || type === 'number'

// Evaluate a "value < 0" style rule against a numeric cell value.
const matchesRule = (rule, value) => {
  if (!isNumber(value)) return false
  const match = RULE_RE.exec(rule || '')
  if (!match) return false
  const threshold = parseFloat(match[2])
  switch (match[1]) {
    case '<': return value < threshold
    case '<=': return value <= threshold
    case '>': return value > threshold
    case '>=': return value >= threshold
    case '==':
    case '=': return value === threshold
    case '!=': return value !== threshold
    default: return false
  }
}

export default function DataTablePreview({ columns, rows, conditional_formatting }) {
  const cols = columns || []
  const data = rows || []

  // column name -> list of conditional rules targeting it
  const rulesByColumn = useMemo(() => {
    const map = {}
    for (const rule of conditional_formatting || []) {
      if (!map[rule.column]) map[rule.column] = []
      map[rule.column].push(rule)
    }
    return map
  }, [conditional_formatting])

  const v = useVirtualRows(data.length, { rowHeight: ROW_HEIGHT, maxHeight: 520 })

  if (!cols.length) {
    return <p className="text-small text-text-secondary">No data available.</p>
  }

  const cellTint = (columnName, value) => {
    const rules = rulesByColumn[columnName]
    if (!rules) return null
    const hit = rules.find((rule) => matchesRule(rule.rule, value))
    if (!hit) return null
    // Apply the palette colour as a subtle ~22% tint behind the cell.
    return { backgroundColor: `${hit.color}38` }
  }

  const visibleRows = v.enabled ? data.slice(v.start, v.end) : data

  const renderRow = (row, rowIndex) => (
    <tr key={rowIndex} style={{ height: ROW_HEIGHT }} className={rowIndex % 2 === 0 ? 'bg-navy-light' : 'bg-navy'}>
      {cols.map((column, colIndex) => {
        const value = row?.[colIndex]
        const tint = cellTint(column.name, value)
        const empty = value === null || value === undefined || value === ''
        return (
          <td
            key={`${column.name}-${colIndex}`}
            style={tint || undefined}
            className={`whitespace-nowrap border-b border-white/5 px-4 ${isRightAligned(column.type) ? 'text-right tabular-nums' : 'text-left'} ${empty ? 'text-text-secondary' : 'text-text-primary'}`}
          >
            {formatCell(value, column.type)}
          </td>
        )
      })}
    </tr>
  )

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <span className="rounded-full bg-white/10 px-3 py-1 text-small text-text-secondary">
          Showing {data.length} rows
        </span>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-navy">
        <div ref={v.ref} onScroll={v.onScroll} className="relative max-h-[520px] overflow-auto">
          <table className="min-w-full border-collapse text-small">
            <thead className="sticky top-0 z-10">
              <tr>
                {cols.map((column, index) => (
                  <th
                    key={`${column.name}-${index}`}
                    className={`whitespace-nowrap bg-blue-electric px-4 py-3 font-bold text-white ${isRightAligned(column.type) ? 'text-right' : 'text-left'}`}
                  >
                    {column.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {v.enabled && v.topPad > 0 ? (
                <tr style={{ height: v.topPad }}><td colSpan={cols.length} /></tr>
              ) : null}
              {visibleRows.map((row, i) => renderRow(row, v.enabled ? v.start + i : i))}
              {v.enabled && v.bottomPad > 0 ? (
                <tr style={{ height: v.bottomPad }}><td colSpan={cols.length} /></tr>
              ) : null}
            </tbody>
          </table>

          {v.enabled && v.end < data.length ? (
            <div className="pointer-events-none sticky bottom-0 flex items-center justify-center gap-2 bg-gradient-to-t from-navy to-transparent py-2 text-micro text-text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading more rows…
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
