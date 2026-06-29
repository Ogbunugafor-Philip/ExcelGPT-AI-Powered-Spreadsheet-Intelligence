import { Suspense, lazy, useState } from 'react'
import { AlertCircle, Check, Copy, Download, HelpCircle, Loader2 } from 'lucide-react'
import KPIStrip from './dashboard/KPIStrip'
import RankingsTable from './dashboard/RankingsTable'
import GrowthTable from './dashboard/GrowthTable'

// Recharts is heavy — load the chart surfaces only when an answer actually has them.
const ChartsSection = lazy(() => import('./dashboard/ChartsSection'))
const ForecastPreview = lazy(() => import('./preview/ForecastPreview'))

const ChartFallback = () => (
  <div className="flex h-[280px] items-center justify-center text-small text-text-muted">Loading chart…</div>
)

const RANKING_PREVIEW = 20

const Section = ({ label, children }) => (
  <div className="space-y-3">
    {label ? (
      <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-text-3">{label}</p>
    ) : null}
    {children}
  </div>
)

// Build a plain-text summary of an answer for the clipboard.
const buildSummary = (title, kpiCards, rankings) => {
  const lines = []
  if (title) lines.push(title)
  kpiCards.forEach((c) => lines.push(`${c.label}: ${c.value}${c.change ? ` (${c.change})` : ''}`))
  rankings.slice(0, 10).forEach((r) => lines.push(`#${r.rank ?? '-'} ${r.label} — ${r.value}${r.change ? ` (${r.change})` : ''}`))
  return lines.join('\n')
}

export default function ChatExchange({ item, onDownload }) {
  const [copied, setCopied] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [showAllRankings, setShowAllRankings] = useState(false)

  const time = item.timestamp
    ? new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''

  const answer = item.answer
  const preview = answer?.preview
  const clarification = answer?.action_plan?.clarification_needed ? answer.action_plan.clarification_question : null

  const kpiCards = preview?.executive_summary?.kpi_cards?.length
    ? preview.executive_summary.kpi_cards
    : preview?.kpi_cards || []
  const charts = preview?.charts || []
  const rankings = preview?.rankings || []
  const growth = preview?.growth_table || []
  const metrics = preview?.metrics || []
  const forecast = preview?.forecast
  const hasForecast = forecast && (forecast.historical?.length || forecast.projected?.length)
  const title = preview?.executive_summary?.title
  const hasContent = kpiCards.length || charts.length || rankings.length || growth.length || metrics.length || hasForecast

  const handleDownload = async () => {
    if (!item.downloadToken || downloading) return
    setDownloading(true)
    try {
      await onDownload?.(item.downloadToken)
    } finally {
      setDownloading(false)
    }
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(buildSummary(title, kpiCards, rankings) || item.question)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable — ignore */
    }
  }

  const rankingRows = showAllRankings ? rankings : rankings.slice(0, RANKING_PREVIEW)

  return (
    <div id={`exchange-${item.id}`} className="scroll-mt-8">
      {/* Question — a simple text line, not a bubble. */}
      <div className="mb-4 flex items-start gap-2.5">
        <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-coral" />
        <p className="min-w-0 flex-1 text-[15px] font-semibold leading-snug text-text-1">{item.question}</p>
        {time ? <span className="mt-0.5 shrink-0 text-[11px] text-text-3">{time}</span> : null}
      </div>

      {/* Answer card */}
      <div className="eg-anim-slide-up mb-8 rounded-xl border border-border bg-card p-6 shadow-card">
        {item.error ? (
          <div className="flex items-start gap-3 text-small text-red-alert">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{item.error}</p>
          </div>
        ) : clarification ? (
          <div className="flex items-start gap-3">
            <HelpCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber" />
            <div>
              <p className="font-semibold text-amber">One quick question</p>
              <p className="mt-1 text-small text-text-primary">{clarification}</p>
              <p className="mt-2 text-micro text-text-muted">Rephrase with a bit more detail and ask again.</p>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {kpiCards.length ? (
              <Section label="Key figures">
                <KPIStrip cards={kpiCards} />
              </Section>
            ) : null}

            {charts.length ? (
              <Section label="Charts">
                <Suspense fallback={<ChartFallback />}>
                  <ChartsSection charts={charts} />
                </Suspense>
              </Section>
            ) : null}

            {rankings.length ? (
              <Section label="Rankings">
                <RankingsTable rows={rankingRows} meta={preview?.rankings_meta} />
                {rankings.length > RANKING_PREVIEW ? (
                  <button
                    type="button"
                    onClick={() => setShowAllRankings((v) => !v)}
                    className="text-small font-semibold text-coral transition hover:text-coral-light"
                  >
                    {showAllRankings ? 'Show fewer' : `Show all ${rankings.length}`}
                  </button>
                ) : null}
              </Section>
            ) : null}

            {growth.length ? (
              <Section label="Growth">
                <GrowthTable rows={growth} meta={preview?.growth_meta} />
              </Section>
            ) : null}

            {hasForecast ? (
              <Section label="Forecast">
                <Suspense fallback={<ChartFallback />}>
                  <ForecastPreview
                    historical={forecast.historical}
                    projected={forecast.projected}
                    confidence_upper={forecast.confidence_upper}
                    confidence_lower={forecast.confidence_lower}
                    assumptions={forecast.assumptions}
                  />
                </Suspense>
              </Section>
            ) : null}

            {metrics.length ? (
              <Section label="Key metrics">
                <div className="overflow-hidden rounded-xl border border-border">
                  {metrics.map((metric, index) => (
                    <div
                      key={`${metric.label}-${index}`}
                      className={`flex items-start justify-between gap-4 px-4 py-2.5 ${index % 2 === 0 ? 'bg-hover/40' : ''}`}
                    >
                      <div>
                        <p className="text-small font-semibold text-text-primary">{metric.label}</p>
                        {metric.formula_used ? (
                          <p className="mt-0.5 text-xs italic text-text-secondary">{metric.formula_used}</p>
                        ) : null}
                      </div>
                      <p className="shrink-0 text-right text-small font-semibold tabular-nums text-text-primary">{metric.value}</p>
                    </div>
                  ))}
                </div>
              </Section>
            ) : null}

            {!hasContent ? (
              <p className="text-small text-text-secondary">
                No structured result for that one — try rephrasing your question.
              </p>
            ) : null}
          </div>
        )}

        {/* Card actions — coral text link + dot separator + copy link. */}
        {!item.error && !clarification && item.downloadToken ? (
          <div className="mt-4 flex items-center gap-3 border-t border-border pt-3">
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              className="inline-flex items-center gap-1.5 text-[13px] font-medium text-coral transition hover:text-coral-light disabled:opacity-50"
            >
              {downloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              Download
            </button>
            <span className="h-1 w-1 rounded-full bg-text-3" aria-hidden="true" />
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 text-[13px] font-medium text-text-2 transition hover:text-text-1"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-positive" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
