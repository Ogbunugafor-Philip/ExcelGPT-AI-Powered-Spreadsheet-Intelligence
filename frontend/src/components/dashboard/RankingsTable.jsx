// Rich performance-rankings table. Column headers use the ACTUAL data display
// names (from rankings_meta), rows carry rank indicators, change arrows, and a
// performance tier pill derived server-side from each value vs. the mean.

const ARROWS = {
  up: { glyph: '↑', className: 'text-positive' },
  down: { glyph: '↓', className: 'text-negative' },
  neutral: { glyph: '→', className: 'text-warning' },
}

// Performance tiers map the existing server keys to the new pill language.
const TIER = {
  excellent: { label: 'Elite', className: 'bg-gold/20 text-gold' },
  good: { label: 'On Track', className: 'bg-positive/15 text-positive' },
  average: { label: 'At Risk', className: 'bg-warning/15 text-warning' },
  below: { label: 'Below Target', className: 'bg-negative/15 text-negative' },
}

// Rank cell: #1 gold dot + bold, #2/#3 a muted dot, others a plain muted number.
function RankCell({ rank }) {
  if (rank === 1) {
    return (
      <span className="inline-flex items-center gap-2 font-bold text-text-1">
        <span className="h-2 w-2 rounded-full bg-gold" />1
      </span>
    )
  }
  if (rank === 2 || rank === 3) {
    return (
      <span className="inline-flex items-center gap-2 text-text-2">
        <span className="h-2 w-2 rounded-full bg-text-2" />
        {rank}
      </span>
    )
  }
  return <span className="text-text-3">{rank ?? '—'}</span>
}

export default function RankingsTable({ rows, meta }) {
  const data = rows || []
  if (!data.length) return <p className="text-[14px] text-text-2">No rankings available.</p>

  const entityLabel = meta?.entity_label || 'Entity'
  const valueLabel = meta?.value_label || 'Value'
  const changeLabel = meta?.change_label || ''
  const hasChange = data.some((r) => r.change)
  const hasTier = data.some((r) => r.tier && r.tier !== 'none')

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse">
        <thead>
          <tr className="border-b border-border text-left text-[11px] uppercase tracking-[0.06em] text-text-3">
            <th className="px-3 py-2.5 font-semibold">Rank</th>
            <th className="px-3 py-2.5 font-semibold">{entityLabel}</th>
            <th className="px-3 py-2.5 text-right font-semibold">{valueLabel}</th>
            {hasChange ? <th className="px-3 py-2.5 text-right font-semibold">{changeLabel || 'Change'}</th> : null}
            {hasTier ? <th className="px-3 py-2.5 text-center font-semibold">Performance</th> : null}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => {
            const arrow = ARROWS[row.direction] || ARROWS.neutral
            const tier = TIER[row.tier]
            const isLast = index === data.length - 1
            return (
              <tr
                key={`${row.label}-${index}`}
                className={`text-[14px] transition hover:bg-card-hover ${isLast ? '' : 'border-b border-border'}`}
              >
                <td className="px-3 py-3">
                  <RankCell rank={row.rank} />
                </td>
                <td className="px-3 py-3 text-text-1">{row.label || '—'}</td>
                <td className="px-3 py-3 text-right font-semibold tabular-nums text-text-1">{row.value}</td>
                {hasChange ? (
                  <td className={`px-3 py-3 text-right font-medium tabular-nums ${arrow.className}`}>
                    {row.change ? (
                      <span className="inline-flex items-center justify-end gap-1">
                        <span aria-hidden="true">{arrow.glyph}</span>
                        {row.change}
                      </span>
                    ) : (
                      ''
                    )}
                  </td>
                ) : null}
                {hasTier ? (
                  <td className="px-3 py-3 text-center">
                    {tier ? (
                      <span className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-semibold ${tier.className}`}>
                        {tier.label}
                      </span>
                    ) : null}
                  </td>
                ) : null}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
