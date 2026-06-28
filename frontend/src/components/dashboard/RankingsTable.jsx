// Rich performance-rankings table. Column headers use the ACTUAL data display
// names (from rankings_meta), rows carry medal badges, change indicators, and a
// performance tier badge derived server-side from each value vs. the mean.

const ARROWS = {
  up: { glyph: '↑', className: 'text-emerald' },
  down: { glyph: '↓', className: 'text-red-alert' },
  neutral: { glyph: '→', className: 'text-amber' },
}

// Medal styling for the top three; everyone else gets a neutral chip.
const MEDAL_BADGE = {
  1: 'bg-gold/20 text-gold',
  2: 'bg-gray-300/20 text-gray-200',
  3: 'bg-[#B45309]/25 text-[#D9A066]',
}
const MEDAL_BORDER = {
  1: 'border-l-4 border-l-gold',
  2: 'border-l-4 border-l-gray-300',
  3: 'border-l-4 border-l-[#B45309]',
}

const TIER = {
  excellent: { label: 'Excellent', className: 'bg-emerald/15 text-emerald' },
  good: { label: 'Good', className: 'bg-blue-electric/15 text-blue-glow' },
  average: { label: 'Average', className: 'bg-amber/15 text-amber' },
  below: { label: 'Below Target', className: 'bg-red-alert/15 text-red-alert' },
}

export default function RankingsTable({ rows, meta }) {
  const data = rows || []
  if (!data.length) return <p className="text-sm text-text-secondary">No rankings available.</p>

  const entityLabel = meta?.entity_label || 'Entity'
  const valueLabel = meta?.value_label || 'Value'
  const changeLabel = meta?.change_label || ''
  const hasChange = data.some((r) => r.change)
  const hasTier = data.some((r) => r.tier && r.tier !== 'none')

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-text-secondary">
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
            const badge = MEDAL_BADGE[row.rank] || 'bg-white/5 text-text-secondary'
            const tier = TIER[row.tier]
            return (
              <tr
                key={`${row.label}-${index}`}
                className={`group border-b border-white/5 transition hover:bg-white/5 ${MEDAL_BORDER[row.rank] || ''}`}
              >
                <td className="px-3 py-3">
                  <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${badge}`}>
                    {row.rank ?? '—'}
                  </span>
                </td>
                <td className="px-3 py-3 font-medium text-white">{row.label || '—'}</td>
                <td className="px-3 py-3 text-right font-semibold tabular-nums text-white">{row.value}</td>
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
                      <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${tier.className}`}>
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
