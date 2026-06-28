import { useEffect, useMemo, useState } from 'react'
import { Download, Loader2 } from 'lucide-react'
import { downloadFile } from '../services/api'
import VersionTracker from './VersionTracker'
import ExecutiveSummaryPreview from './preview/ExecutiveSummaryPreview'
import DataTablePreview from './preview/DataTablePreview'
import AnalysisPreview from './preview/AnalysisPreview'
import ChartsPreview from './preview/ChartsPreview'
import ForecastPreview from './preview/ForecastPreview'

// Master preview container: a tab bar over the report's sections plus a fixed
// Download button. Tabs only appear when their section has data, so what the
// user sees here mirrors the sheets that will be in the downloaded workbook.
// On refinement the preview cross-fades to the new version.
export default function PreviewPanel({ preview, downloadToken, version, onDownload }) {
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')

  // Cross-fade: hold the currently displayed preview and swap it after a fade-out.
  const [displayPreview, setDisplayPreview] = useState(preview)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    if (preview === displayPreview) return
    setVisible(false) // fade out the old preview
    const timer = setTimeout(() => {
      setDisplayPreview(preview) // swap in the new content
      setVisible(true) // fade in
    }, 150)
    return () => clearTimeout(timer)
  }, [preview, displayPreview])

  const summary = displayPreview?.executive_summary
  const dataSheet = useMemo(
    () => (displayPreview?.sheets || []).find((sheet) => sheet.sheet_name === 'data'),
    [displayPreview],
  )
  const hasAnalysis =
    (displayPreview?.metrics?.length || 0) +
      (displayPreview?.rankings?.length || 0) +
      (displayPreview?.growth_table?.length || 0) >
    0
  const charts = displayPreview?.charts || []
  const forecast = displayPreview?.forecast

  // Build the tab list, skipping empty sections.
  const tabs = useMemo(() => {
    const list = []
    if (summary && (summary.title || summary.kpi_cards?.length)) list.push({ key: 'summary', label: 'Summary' })
    if (dataSheet?.columns?.length) list.push({ key: 'data', label: 'Data' })
    if (hasAnalysis) list.push({ key: 'analysis', label: 'Analysis' })
    if (charts.length) list.push({ key: 'charts', label: 'Charts' })
    if (forecast && (forecast.historical?.length || forecast.projected?.length)) {
      list.push({ key: 'forecast', label: 'Forecast' })
    }
    return list
  }, [summary, dataSheet, hasAnalysis, charts.length, forecast])

  const [activeTab, setActiveTab] = useState('summary')
  // Keep the active tab valid as the preview changes across refinements.
  const currentTab = tabs.some((tab) => tab.key === activeTab) ? activeTab : tabs[0]?.key

  const handleDownload = async () => {
    setDownloadError('')
    setDownloading(true)
    try {
      if (onDownload) {
        await onDownload()
      } else if (downloadToken) {
        await downloadFile(downloadToken)
      }
    } catch (err) {
      setDownloadError(err.message || 'Download failed.')
    } finally {
      setDownloading(false)
    }
  }

  if (!displayPreview || !tabs.length) {
    return null
  }

  return (
    <section className="eg-card p-6 lg:p-8" aria-label="Report preview">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex flex-wrap gap-1">
            {tabs.map((tab) => {
              const active = tab.key === currentTab
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={`relative px-4 py-2 text-sm font-semibold transition-colors ${
                    active ? 'text-white' : 'text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {tab.label}
                  {active ? (
                    <span className="absolute inset-x-2 -bottom-[17px] h-0.5 rounded-full bg-blue-electric" />
                  ) : null}
                </button>
              )
            })}
          </div>
          <VersionTracker version={version} />
        </div>

        <button
          type="button"
          onClick={handleDownload}
          disabled={downloading || (!downloadToken && !onDownload)}
          className="inline-flex items-center gap-2 rounded-lg bg-emerald px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          {downloading ? 'Preparing…' : 'Download Excel'}
        </button>
      </div>

      {downloadError ? <p className="mt-3 text-sm text-red-alert">{downloadError}</p> : null}

      <div className={`mt-6 transition-opacity duration-150 ${visible ? 'opacity-100' : 'opacity-0'}`}>
        {currentTab === 'summary' && summary ? (
          <ExecutiveSummaryPreview
            title={summary.title}
            period={summary.period}
            data_source={summary.data_source}
            kpi_cards={summary.kpi_cards}
          />
        ) : null}

        {currentTab === 'data' && dataSheet ? (
          <DataTablePreview
            columns={dataSheet.columns}
            rows={dataSheet.rows}
            conditional_formatting={dataSheet.conditional_formatting}
          />
        ) : null}

        {currentTab === 'analysis' ? (
          <AnalysisPreview
            metrics={displayPreview.metrics}
            rankings={displayPreview.rankings}
            growth_table={displayPreview.growth_table}
          />
        ) : null}

        {currentTab === 'charts' ? <ChartsPreview charts={charts} /> : null}

        {currentTab === 'forecast' && forecast ? (
          <ForecastPreview
            historical={forecast.historical}
            projected={forecast.projected}
            confidence_upper={forecast.confidence_upper}
            confidence_lower={forecast.confidence_lower}
            assumptions={forecast.assumptions}
          />
        ) : null}
      </div>
    </section>
  )
}
