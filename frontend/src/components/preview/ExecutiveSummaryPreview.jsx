// Executive summary surface — now just the dashboard masthead + KPI strip.
// Kept as a thin wrapper so older callers keep working; the dashboard renders
// DashboardHeader/KPIStrip directly.
import DashboardHeader from '../dashboard/DashboardHeader'
import KPIStrip from '../dashboard/KPIStrip'

export default function ExecutiveSummaryPreview({ title, period, data_source, kpi_cards, version, onDownload }) {
  return (
    <div className="space-y-6">
      <DashboardHeader
        title={title}
        period={period}
        dataSource={data_source}
        version={version}
        onDownload={onDownload}
        downloadDisabled={!onDownload}
      />
      <KPIStrip cards={kpi_cards} />
    </div>
  )
}
