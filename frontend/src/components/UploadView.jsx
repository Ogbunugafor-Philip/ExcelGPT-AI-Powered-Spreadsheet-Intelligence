import { useCallback, useRef, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { AlertCircle, CheckCircle2, FileSpreadsheet, Upload } from 'lucide-react'
import { uploadFile } from '../services/api'
import { resolveError } from '../utils/errorMessages'

const MAX_BYTES = 50 * 1024 * 1024

// Full-screen, centered upload. Clean and minimal: logo, subtitle, drop zone.
export default function UploadView({ onUpload }) {
  const [phase, setPhase] = useState('idle') // idle | uploading | success | error
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null) // { title, message }
  const [fileName, setFileName] = useState('')
  const cancelled = useRef(false)

  const onDrop = useCallback(
    async (accepted, rejected) => {
      setError(null)
      cancelled.current = false

      if (rejected?.length) {
        setPhase('error')
        setError(resolveError('INVALID_FILE_TYPE'))
        return
      }
      const file = accepted?.[0]
      if (!file) return
      if (file.size > MAX_BYTES) {
        setPhase('error')
        setError(resolveError('FILE_TOO_LARGE'))
        return
      }
      if (file.size === 0) {
        setPhase('error')
        setError(resolveError('EMPTY_FILE'))
        return
      }

      setFileName(file.name)
      setProgress(0)
      setPhase('uploading')
      try {
        const data = await uploadFile(file, (pct) => {
          if (!cancelled.current) setProgress(pct)
        })
        if (cancelled.current) return
        setProgress(100)
        setPhase('success')
        setTimeout(() => {
          if (!cancelled.current) onUpload?.(file, data)
        }, 500)
      } catch (err) {
        if (cancelled.current) return
        setPhase('error')
        setError(resolveError(err.errorKey || 'UNKNOWN', err.errorKey ? '' : err.message))
      }
    },
    [onUpload],
  )

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
    },
    multiple: false,
    noClick: phase === 'uploading',
  })

  const zoneClasses = [
    'relative w-full max-w-[520px] cursor-pointer rounded-3xl bg-card p-10 sm:p-14 text-center transition-all duration-200',
    isDragActive
      ? 'border-2 border-solid border-coral eg-anim-coral-pulse'
      : 'border-2 border-dashed border-coral/60 hover:border-coral hover:shadow-glow-coral',
  ].join(' ')

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-base px-6 py-12">
      <header className="mb-10 text-center">
        <h1 className="font-display text-[32px] font-extrabold">
          <span className="text-text-primary">Excel</span>
          <span className="text-coral">GPT</span>
        </h1>
        <p className="mt-2 text-body text-text-muted">Your data. Your questions. Instant answers.</p>
      </header>

      <div {...getRootProps()} className={zoneClasses}>
        <input {...getInputProps()} />

        {phase === 'success' ? (
          <div className="flex flex-col items-center">
            <CheckCircle2 className="eg-anim-check h-12 w-12 text-teal" />
            <p className="mt-4 text-subheading text-teal">Uploaded</p>
            <p className="mt-1 text-small text-text-muted">{fileName}</p>
          </div>
        ) : phase === 'uploading' ? (
          <div className="flex flex-col items-center">
            <FileSpreadsheet className="h-12 w-12 text-coral" />
            <p className="mt-4 text-subheading text-text-primary">{fileName}</p>
            <div className="mt-5 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-hover">
              <div className="eg-progress-fill h-full rounded-full transition-all duration-200" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-3 text-small text-text-secondary">Uploading… {progress}%</p>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            <Upload className={`h-12 w-12 transition-colors ${isDragActive ? 'text-coral-light' : 'text-coral'}`} />
            <p className="mt-4 text-lg font-bold text-text-primary">
              {isDragActive ? 'Release to upload' : 'Drop your Excel file here'}
            </p>
            <p className="mt-1.5 text-small text-text-muted">or click to browse</p>
            <p className="mt-3 text-micro text-text-muted">.xlsx and .xls · up to 50MB</p>
          </div>
        )}
      </div>

      {phase === 'error' && error ? (
        <div className="mt-6 w-full max-w-[520px] rounded-2xl border border-red-alert/30 bg-red-alert/10 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-alert" />
            <div className="min-w-0">
              <p className="font-semibold text-red-alert">{error.title}</p>
              <p className="mt-1 text-small text-text-secondary">{error.message}</p>
              <button
                type="button"
                onClick={() => {
                  setPhase('idle')
                  setError(null)
                  open()
                }}
                className="mt-3 inline-flex items-center gap-2 rounded-lg border border-coral px-4 py-2 text-small font-semibold text-coral transition hover:bg-coral/10"
              >
                Try another file
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
