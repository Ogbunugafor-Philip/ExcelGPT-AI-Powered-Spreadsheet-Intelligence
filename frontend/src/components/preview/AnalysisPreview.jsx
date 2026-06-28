// Analysis tab: key metrics, performance rankings (with medal styling), and a
// growth analysis table — matching the Analysis sheet in the workbook.

const ARROWS = {
  up: { glyph: '↑', className: 'text-emerald' },
  down: { glyph: '↓', className: 'text-red-alert' },
  neutral: { glyph: '→', className: 'text-amber' },
}

// Rank medal styling: 1 gold, 2 silver/grey, 3 bronze/amber.
const MEDALS = {
  1: 'border-l-4 border-gold bg-gold/10',
  2: 'border-l-4 border-gray-300 bg-white/5',
  3: 'border-l-4 border-amber bg-amber/10',
}

const SectionHeader = ({ children }) => (
  <h3 className="text-sm font-bold uppercase tracking-wider text-blue-electric">{children}</h3>
)

const isPositiveRate = (text) => typeof text === 'string' && text.trim().startsWith('+')
const isNegativeRate = (text) => typeof text === 'string' && text.trim().startsWith('-')

export default function AnalysisPreview({ metrics, rankings, growth_table }) {
  const metricRows = metrics || []
  const rankRows = rankings || []
  const growthRows = growth_table || []

  if (!metricRows.length && !rankRows.length && !growthRows.length) {
    return <p className="text-sm text-text-secondary">No analysis available.</p>
  }

  return (
    <div className="space-y-8">
      {metricRows.length ? (
        <section className="space-y-3">
          <SectionHeader>Key Metrics</SectionHeader>
          <div className="overflow-hidden rounded-2xl border border-white/10">
            {metricRows.map((metric, index) => (
              <div
                key={`${metric.label}-${index}`}
                className={`flex items-start justify-between gap-4 px-5 py-3 ${index % 2 === 0 ? 'bg-navy-light' : 'bg-navy'}`}
              >
                <div>
                  <p className="font-semibold text-white">{metric.label}</p>
                  {metric.formula_used ? (
                    <p className="mt-0.5 text-xs italic text-text-secondary">{metric.formula_used}</p>
                  ) : null}
                </div>
                <p className="shrink-0 text-right font-semibold text-white tabular-nums">{metric.value}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {rankRows.length ? (
        <section className="space-y-3">
          <SectionHeader>Performance Rankings</SectionHeader>
          <div className="space-y-1.5">
            {rankRows.map((row, index) => {
              const arrow = ARROWS[row.direction] || ARROWS.neutral
              const medal = MEDALS[row.rank] || (index % 2 === 0 ? 'bg-navy-light' : 'bg-navy')
              return (
                <div
                  key={`${row.label}-${index}`}
                  className={`flex items-center gap-4 rounded-lg px-4 py-3 ${medal}`}
                >
                  <span className="w-8 shrink-0 text-center text-lg font-bold text-white">{row.rank ?? '—'}</span>
                  <span className="flex-1 truncate font-medium text-white">{row.label}</span>
                  <span className="shrink-0 font-semibold text-white tabular-nums">{row.value}</span>
                  {row.change ? (
                    <span className={`flex shrink-0 items-center gap-1 text-sm font-medium ${arrow.className}`}>
                      <span aria-hidden="true">{arrow.glyph}</span>
                      {row.change}
                    </span>
                  ) : null}
                </div>
              )
            })}
          </div>
        </section>
      ) : null}

      {growthRows.length ? (
        <section className="space-y-3">
          <SectionHeader>Growth Analysis</SectionHeader>
          <div className="overflow-hidden rounded-2xl border border-white/10">
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr className="bg-blue-electric text-left text-white">
                  <th className="px-4 py-2.5 font-bold">Item</th>
                  <th className="px-4 py-2.5 text-right font-bold">Previous</th>
                  <th className="px-4 py-2.5 text-right font-bold">Current</th>
                  <th className="px-4 py-2.5 text-right font-bold">Growth</th>
                  <th className="px-4 py-2.5 text-center font-bold">Trend</th>
                </tr>
              </thead>
              <tbody>
                {growthRows.map((row, index) => {
                  const arrow = ARROWS[row.direction] || ARROWS.neutral
                  const rateClass = isPositiveRate(row.growth_rate)
                    ? 'text-emerald'
                    : isNegativeRate(row.growth_rate)
                      ? 'text-red-alert'
                      : 'text-text-primary'
                  return (
                    <tr key={`${row.label}-${index}`} className={index % 2 === 0 ? 'bg-navy-light' : 'bg-navy'}>
                      <td className="px-4 py-2.5 text-text-primary">{row.label}</td>
                      <td className="px-4 py-2.5 text-right text-text-secondary tabular-nums">{row.previous}</td>
                      <td className="px-4 py-2.5 text-right text-white tabular-nums">{row.current}</td>
                      <td className={`px-4 py-2.5 text-right font-semibold tabular-nums ${rateClass}`}>{row.growth_rate}</td>
                      <td className={`px-4 py-2.5 text-center text-lg font-bold ${arrow.className}`}>{arrow.glyph}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  )
}
