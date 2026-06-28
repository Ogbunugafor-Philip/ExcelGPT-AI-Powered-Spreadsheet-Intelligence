import { useEffect, useMemo, useState } from 'react'
import { Disclosure } from '@headlessui/react'
import { ChevronDown } from 'lucide-react'
import { downloadFile } from '../services/api'
import DashboardHeader from './dashboard/DashboardHeader'
import KPIStrip from './dashboard/KPIStrip'
import InsightCard from './dashboard/InsightCard'
import RankingsTable from './dashboard/RankingsTable'
import GrowthTable from './dashboard/GrowthTable'
import ChartsSection from './dashboard/ChartsSection'
import DataTablePreview from './preview/DataTablePreview'
import ForecastPreview from './preview/ForecastPreview'

// A single, top-to-bottom analytics dashboard (no tabs). Everything the user
// would find in the downloaded workbook is laid out on one scrollable page:
// sticky header → KPIs → charts → rankings/growth → forecast → raw data.
export default function PreviewPanel({ preview, downloadToken, version, onDownload }) {
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')

  // Cross-fade between versions on refinement.
  const [displayPreview, setDisplayPreview] = useState(preview)
  const [visible, setVisible] = useState(true)
  useEffect(() => {
    if (preview === displayPreview) return undefined
    setVisible(false)
    const timer = setTimeout(() => {
      setDisplayPreview(preview)
      setVisible(true)
    }, 150)
    return () => clearTimeout(timer)
  }, [preview, displayPreview])

  const summary = displayPreview?.executive_summary
  const kpiCards = summary?.kpi_cards || displayPreview?.kpi_cards || []
  const charts = displayPreview?.charts || []
  const metrics = displayPreview?.metrics || []
  const rankings = displayPreview?.rankings || []
  const growth = displayPreview?.growth_table || []
  const forecast = displayPreview?.forecast
  const dataSheet = useMemo(
    () => (displayPreview?.sheets || []).find((sheet) => sheet.sheet_name === 'data'),
    [displayPreview],
  )
  const hasForecast = forecast && (forecast.historical?.length || forecast.projected?.length)

  const handleDownload = async () => {
    setDownloadError('')
    setDownloading(true)
    try {
      if (onDownload) await onDownload()
      else if (downloadToken) await downloadFile(downloadToken)
    } catch (err) {
      setDownloadError(err.message || 'Download failed.')
    } finally {
      setDownloading(false)
    }
  }

  if (!displayPreview) return null

  return (
    <div className={`flex flex-col gap-6 transition-opacity duration-150 ${visible ? 'opacity-100' : 'opacity-0'}`} aria-label="Report dashboard">
      <DashboardHeader
        title={summary?.title}
        period={summary?.period}
        dataSource={summary?.data_source}
        version={version}
        onDownload={handleDownload}
        downloading={downloading}
        downloadDisabled={!downloadToken && !onDownload}
      />

      {downloadError ? <p className="text-sm text-red-alert">{downloadError}</p> : null}

      {kpiCards.length ? <KPIStrip cards={kpiCards} /> : null}

      {charts.length ? <ChartsSection charts={charts} /> : null}

      {metrics.length ? (
        <InsightCard title="Key Metrics" subtitle="Headline figures from this analysis">
          <div className="overflow-hidden rounded-xl border border-white/10">
            {metrics.map((metric, index) => (
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

      {rankings.length ? (
        <InsightCard title="Performance Rankings" subtitle="Ranked by primary metric, tiered against the average">
          <RankingsTable rows={rankings} meta={displayPreview?.rankings_meta} />
        </InsightCard>
      ) : null}

      {growth.length ? (
        <InsightCard title="Growth Analysis" subtitle="Period-over-period movement">
          <GrowthTable rows={growth} meta={displayPreview?.growth_meta} />
        </InsightCard>
      ) : null}

      {hasForecast ? (
        <InsightCard>
          <ForecastPreview
            historical={forecast.historical}
            projected={forecast.projected}
            confidence_upper={forecast.confidence_upper}
            confidence_lower={forecast.confidence_lower}
            assumptions={forecast.assumptions}
          />
        </InsightCard>
      ) : null}

      {dataSheet?.columns?.length ? (
        <Disclosure>
          {({ open }) => (
            <div className="rounded-2xl border border-white/10 bg-navy-card">
              <Disclosure.Button className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left">
                <div>
                  <h3 className="text-base font-bold text-white">Raw Data</h3>
                  <p className="mt-0.5 text-sm text-text-secondary">
                    {dataSheet.rows?.length || 0} rows · {dataSheet.columns.length} columns
                  </p>
                </div>
                <ChevronDown className={`h-5 w-5 shrink-0 text-text-secondary transition-transform ${open ? 'rotate-180' : ''}`} />
              </Disclosure.Button>
              <Disclosure.Panel className="px-5 pb-5">
                <DataTablePreview
                  columns={dataSheet.columns}
                  rows={dataSheet.rows}
                  conditional_formatting={dataSheet.conditional_formatting}
                />
              </Disclosure.Panel>
            </div>
          )}
        </Disclosure>
      ) : null}
    </div>
  )
}
