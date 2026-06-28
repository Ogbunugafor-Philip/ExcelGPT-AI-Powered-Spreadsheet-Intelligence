// Analysis surface — key metrics, the rich RankingsTable, and the GrowthTable,
// each wrapped in an InsightCard. Column headers come from the real data
// display names carried in rankings_meta / growth_meta.
import InsightCard from '../dashboard/InsightCard'
import RankingsTable from '../dashboard/RankingsTable'
import GrowthTable from '../dashboard/GrowthTable'

export default function AnalysisPreview({ metrics, rankings, growth_table, rankings_meta, growth_meta }) {
  const metricRows = metrics || []
  const rankRows = rankings || []
  const growthRows = growth_table || []

  if (!metricRows.length && !rankRows.length && !growthRows.length) {
    return <p className="text-sm text-text-secondary">No analysis available.</p>
  }

  return (
    <div className="space-y-6">
      {metricRows.length ? (
        <InsightCard title="Key Metrics" subtitle="Headline figures from this analysis">
          <div className="overflow-hidden rounded-xl border border-white/10">
            {metricRows.map((metric, index) => (
              <div
                key={`${metric.label}-${index}`}
                className={`flex items-start justify-between gap-4 px-5 py-3 ${index % 2 === 0 ? 'bg-white/[0.03]' : ''}`}
              >
                <div>
                  <p className="font-semibold text-white">{metric.label}</p>
                  {metric.formula_used ? (
                    <p className="mt-0.5 text-xs italic text-text-secondary">{metric.formula_used}</p>
                  ) : null}
                </div>
                <p className="shrink-0 text-right font-semibold tabular-nums text-white">{metric.value}</p>
              </div>
            ))}
          </div>
        </InsightCard>
      ) : null}

      {rankRows.length ? (
        <InsightCard title="Performance Rankings" subtitle="Ranked by primary metric, tiered against the average">
          <RankingsTable rows={rankRows} meta={rankings_meta} />
        </InsightCard>
      ) : null}

      {growthRows.length ? (
        <InsightCard title="Growth Analysis" subtitle="Period-over-period movement">
          <GrowthTable rows={growthRows} meta={growth_meta} />
        </InsightCard>
      ) : null}
    </div>
  )
}
