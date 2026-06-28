// Board-facing summary: a navy header plus a responsive grid of KPI cards.
// Mirrors the Executive Summary sheet in the downloaded workbook.

const DIRECTION = {
  up: { arrow: '↑', className: 'text-emerald' },
  down: { arrow: '↓', className: 'text-red-alert' },
  neutral: { arrow: '→', className: 'text-amber' },
}

export default function ExecutiveSummaryPreview({ title, period, data_source, kpi_cards }) {
  const cards = kpi_cards || []

  return (
    <div className="space-y-6">
      <header className="rounded-2xl border border-white/10 bg-navy px-6 py-8">
        <h2 className="text-3xl font-bold text-white">{title || 'Executive Summary'}</h2>
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-text-secondary">
          {period ? <span>{period}</span> : null}
          {data_source ? <span>{data_source}</span> : null}
        </div>
      </header>

      {cards.length ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {cards.map((card, index) => {
            const dir = DIRECTION[card.direction] || DIRECTION.neutral
            return (
              <div
                key={`${card.label}-${index}`}
                className="group rounded-2xl border border-white/10 bg-navy-light p-5 transition hover:border-blue-glow/60 hover:shadow-glow"
              >
                <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">{card.label}</p>
                <p className="mt-3 text-2xl font-bold text-white">{card.value}</p>
                {card.change ? (
                  <p className={`mt-2 flex items-center gap-1 text-sm font-medium ${dir.className}`}>
                    <span aria-hidden="true">{dir.arrow}</span>
                    <span>{card.change}</span>
                  </p>
                ) : null}
              </div>
            )
          })}
        </div>
      ) : (
        <p className="text-sm text-text-secondary">No KPI cards available.</p>
      )}
    </div>
  )
}
