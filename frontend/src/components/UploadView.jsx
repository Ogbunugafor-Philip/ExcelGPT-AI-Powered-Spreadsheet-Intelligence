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
    'relative w-full max-w-[480px] cursor-pointer overflow-hidden rounded-2xl bg-card px-8 py-12 text-center transition-all duration-200',
    isDragActive
      ? 'scale-[1.01] border-[1.5px] border-solid border-coral bg-coral/5'
      : 'border-[1.5px] border-dashed border-border-strong hover:border-coral hover:bg-coral/5',
  ].join(' ')

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-base px-6 py-12">
      <header className="text-center">
        <h1 className="font-display text-[28px] font-bold">
          <span className="text-text-1">Excel</span>
          <span className="text-coral">GPT</span>
        </h1>
        <p className="mt-2 text-base text-text-2">Ask your data anything.</p>
      </header>

      <div {...getRootProps()} className={`mt-12 ${zoneClasses}`}>
        <input {...getInputProps()} />

        {phase === 'success' ? (
          <div className="flex flex-col items-center">
            <CheckCircle2 className="eg-anim-check h-8 w-8 text-positive" />
            <p className="mt-4 text-[16px] font-semibold text-positive">Uploaded</p>
            <p className="mt-1 text-[14px] text-text-2">{fileName}</p>
          </div>
        ) : phase === 'uploading' ? (
          <div className="flex flex-col items-center">
            <FileSpreadsheet className="h-8 w-8 text-coral" />
            <p className="mt-4 text-[16px] font-semibold text-text-1">{fileName}</p>
            <p className="mt-2 text-[14px] text-text-2">Uploading… {progress}%</p>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            <Upload className={`h-8 w-8 transition-colors ${isDragActive ? 'text-coral' : 'text-text-3'}`} />
            <p className="mt-4 text-[16px] font-semibold text-text-1">
              {isDragActive ? 'Release to upload' : 'Drop your Excel file'}
            </p>
            <p className="mt-1 text-[14px] text-text-2">or click to browse</p>
            <p className="mt-2 text-[12px] text-text-3">.xlsx · .xls · up to 50MB</p>
          </div>
        )}

        {/* Coral progress bar pinned to the bottom edge of the zone. */}
        {phase === 'uploading' ? (
          <div className="absolute inset-x-0 bottom-0 h-1 bg-hover">
            <div
              className="eg-progress-fill h-full rounded-br-2xl transition-all duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
        ) : null}
      </div>

      {phase === 'error' && error ? (
        <div className="mt-6 w-full max-w-[480px] rounded-xl border border-negative/30 bg-negative/10 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-negative" />
            <div className="min-w-0">
              <p className="font-semibold text-negative">{error.title}</p>
              <p className="mt-1 text-[14px] text-text-2">{error.message}</p>
              <button
                type="button"
                onClick={() => {
                  setPhase('idle')
                  setError(null)
                  open()
                }}
                className="mt-3 inline-flex items-center gap-2 rounded-lg border border-coral px-4 py-2 text-[13px] font-semibold text-coral transition hover:bg-coral/10"
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
