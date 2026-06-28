import { Download, Loader2 } from 'lucide-react'

// Sticky dashboard masthead: report title + meta on the left, a prominent
// emerald "Download Excel" action and version badge on the right. Navy gradient
// with a backdrop blur so it reads as a real analytics-product header.
export default function DashboardHeader({
  title,
  period,
  dataSource,
  version,
  onDownload,
  downloading = false,
  downloadDisabled = false,
}) {
  return (
    <header
      className="sticky top-16 z-30 -mx-1 overflow-hidden rounded-2xl border border-white/10 px-6 py-5 shadow-card"
      style={{
        background: 'linear-gradient(120deg, rgba(10,15,30,0.92) 0%, rgba(26,34,53,0.92) 55%, rgba(17,24,39,0.92) 100%)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
      }}
    >
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="truncate text-2xl font-extrabold text-white lg:text-3xl">{title || 'ExcelGPT Report'}</h1>
            {version ? (
              <span className="shrink-0 rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-xs font-semibold text-text-secondary">
                v{version}
              </span>
            ) : null}
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-text-secondary">
            {period ? <span>{period}</span> : null}
            {period && dataSource ? <span className="text-text-muted">•</span> : null}
            {dataSource ? <span className="truncate">{dataSource}</span> : null}
          </div>
        </div>

        <button
          type="button"
          onClick={onDownload}
          disabled={downloading || downloadDisabled}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-emerald px-5 py-2.5 text-sm font-semibold text-white shadow-card transition hover:bg-emerald/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          {downloading ? 'Preparing…' : 'Download Excel'}
        </button>
      </div>
    </header>
  )
}
