import { useEffect, useRef, useState } from 'react'
import confetti from 'canvas-confetti'
import { Download, FileSpreadsheet, Loader2, X } from 'lucide-react'

// Celebration modal shown when the user downloads their report. Fires a brand-
// coloured confetti burst from the button on click, then runs the real download.
export default function DownloadModal({ open, onClose, onDownload, sheetCount, version }) {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState('')
  const buttonRef = useRef(null)

  // Close on Escape.
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const timestamp = new Date()
    .toISOString()
    .slice(0, 16)
    .replace('T', '_')
    .replace(/[-:]/g, '')

  const fireConfetti = () => {
    const rect = buttonRef.current?.getBoundingClientRect()
    const origin = rect
      ? { x: (rect.left + rect.width / 2) / window.innerWidth, y: rect.top / window.innerHeight }
      : { y: 0.6 }
    confetti({
      particleCount: 80,
      spread: 70,
      origin,
      colors: ['#2563EB', '#10B981', '#F59E0B'],
    })
  }

  const handleDownload = async () => {
    setError('')
    setDownloading(true)
    fireConfetti()
    try {
      await onDownload?.()
    } catch (err) {
      setError(err?.message || 'Could not prepare your Excel file.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-navy/70 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="eg-anim-slide-up relative w-full max-w-md rounded-[20px] border border-border-subtle bg-navy-card p-6 shadow-card sm:p-8"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 text-text-muted transition hover:text-text-secondary"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex flex-col items-center text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald/15 text-emerald">
            <FileSpreadsheet className="h-9 w-9" />
          </div>
          <h2 className="text-heading mt-4 text-white">Your report is ready</h2>

          <div className="mt-4 w-full rounded-xl border border-border-subtle bg-navy-light/60 p-4 text-small">
            <p className="break-all font-medium text-text-primary">{`ExcelGPT_Report_${timestamp}.xlsx`}</p>
            <div className="mt-2 flex items-center justify-center gap-4 text-text-secondary">
              <span>{sheetCount || 0} sheet{sheetCount === 1 ? '' : 's'}</span>
              <span className="text-text-muted">•</span>
              <span>Version {version || 1}</span>
            </div>
          </div>

          <button
            ref={buttonRef}
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald px-5 py-3 font-semibold text-white transition hover:bg-emerald/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {downloading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Download className="h-5 w-5" />}
            {downloading ? 'Preparing…' : 'Download Excel File'}
          </button>

          {error ? <p className="mt-3 text-small text-red-alert">{error}</p> : null}
          <p className="mt-3 text-small text-text-muted">or refine further below</p>
        </div>
      </div>
    </div>
  )
}
