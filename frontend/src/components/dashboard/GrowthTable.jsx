// Growth analysis table with real column display names, a colour-coded change
// column, a large directional arrow, and a mini sparkline bar per row showing
// each entity's current value relative to the strongest performer.

const ARROWS = {
  up: { glyph: '↑', className: 'text-emerald' },
  down: { glyph: '↓', className: 'text-red-alert' },
  neutral: { glyph: '→', className: 'text-amber' },
}

const isPositive = (text) => typeof text === 'string' && text.trim().startsWith('+')
const isNegative = (text) => typeof text === 'string' && text.trim().startsWith('-')

export default function GrowthTable({ rows, meta }) {
  const data = rows || []
  if (!data.length) return <p className="text-sm text-text-secondary">No growth analysis available.</p>

  const entityLabel = meta?.entity_label || 'Entity'
  const previousLabel = meta?.previous_label || 'Previous'
  const currentLabel = meta?.current_label || 'Current'
  const changeLabel = meta?.change_label || 'Change'

  const maxCurrent = Math.max(
    1,
    ...data.map((r) => (typeof r.numeric_current === 'number' ? Math.abs(r.numeric_current) : 0)),
  )

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-text-secondary">
            <th className="px-3 py-2.5 font-semibold">{entityLabel}</th>
            <th className="px-3 py-2.5 text-right font-semibold">{previousLabel}</th>
            <th className="px-3 py-2.5 text-right font-semibold">{currentLabel}</th>
            <th className="px-3 py-2.5 text-right font-semibold">{changeLabel}</th>
            <th className="px-3 py-2.5 w-28 font-semibold">Trend</th>
            <th className="px-3 py-2.5 text-center font-semibold">Dir</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => {
            const arrow = ARROWS[row.direction] || ARROWS.neutral
            const changeClass = isPositive(row.growth_rate)
              ? 'text-emerald'
              : isNegative(row.growth_rate)
                ? 'text-red-alert'
                : 'text-text-primary'
            const barWidth =
              typeof row.numeric_current === 'number'
                ? `${Math.max(4, (Math.abs(row.numeric_current) / maxCurrent) * 100)}%`
                : '0%'
            const barColor =
              row.direction === 'down' ? 'bg-red-alert' : row.direction === 'up' ? 'bg-emerald' : 'bg-blue-electric'
            return (
              <tr key={`${row.label}-${index}`} className="border-b border-white/5 transition hover:bg-white/5">
                <td className="px-3 py-3 font-medium text-white">{row.label}</td>
                <td className="px-3 py-3 text-right tabular-nums text-text-secondary">{row.previous}</td>
                <td className="px-3 py-3 text-right tabular-nums text-white">{row.current}</td>
                <td className={`px-3 py-3 text-right font-semibold tabular-nums ${changeClass}`}>{row.growth_rate}</td>
                <td className="px-3 py-3">
                  <div className="h-2 w-full overflow-hidden rounded-full bg-white/5">
                    <div className={`h-full rounded-full ${barColor}`} style={{ width: barWidth }} />
                  </div>
                </td>
                <td className={`px-3 py-3 text-center text-xl font-bold ${arrow.className}`}>{arrow.glyph}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
