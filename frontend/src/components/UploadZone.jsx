import { useCallback, useRef, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { CheckCircle2, FileSpreadsheet, UploadCloud, X } from 'lucide-react'
import { uploadFile } from '../services/api'
import ErrorMessage from './ErrorMessage'

const MAX_BYTES = 50 * 1024 * 1024 // 50MB

const formatSize = (bytes) => `${(bytes / (1024 * 1024)).toFixed(2)} MB`

export default function UploadZone({ onUploadComplete }) {
  const [phase, setPhase] = useState('idle') // idle | accepted | uploading | success | error
  const [errorKey, setErrorKey] = useState(null)
  const [customError, setCustomError] = useState('')
  const [fileMeta, setFileMeta] = useState(null) // { name, size }
  const [progress, setProgress] = useState(0)
  const cancelledRef = useRef(false)

  const reset = () => {
    cancelledRef.current = true
    setPhase('idle')
    setErrorKey(null)
    setCustomError('')
    setFileMeta(null)
    setProgress(0)
  }

  const onDrop = useCallback(async (acceptedFiles, rejectedFiles) => {
    setErrorKey(null)
    setCustomError('')
    cancelledRef.current = false

    if (rejectedFiles?.length) {
      setPhase('error')
      setErrorKey('INVALID_FILE_TYPE')
      return
    }
    const file = acceptedFiles?.[0]
    if (!file) return

    if (file.size > MAX_BYTES) {
      setPhase('error')
      setErrorKey('FILE_TOO_LARGE')
      return
    }
    if (file.size === 0) {
      setPhase('error')
      setErrorKey('EMPTY_FILE')
      return
    }

    setFileMeta({ name: file.name, size: formatSize(file.size) })
    setProgress(0)
    setPhase('accepted')
    // brief accept pulse, then begin uploading
    setTimeout(() => setPhase('uploading'), 320)

    try {
      const data = await uploadFile(file, (pct) => {
        if (!cancelledRef.current) setProgress(pct)
      })
      if (cancelledRef.current) return
      setProgress(100)
      setPhase('success')
      // let the success checkmark play before swapping views
      setTimeout(() => {
        if (!cancelledRef.current) {
          onUploadComplete?.(data.session_id, data.preview, data.intelligence_brief)
        }
      }, 600)
    } catch (err) {
      if (cancelledRef.current) return
      setPhase('error')
      setErrorKey(err.errorKey || 'UNKNOWN')
      setCustomError(err.errorKey ? '' : err.message)
    }
  }, [onUploadComplete])

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
    },
    multiple: false,
    noClick: phase === 'uploading',
  })

  if (phase === 'error') {
    return (
      <section className="mx-auto w-full max-w-[600px]" aria-label="Upload error">
        <ErrorMessage
          errorKey={errorKey}
          customMessage={customError}
          onAction={() => { reset(); open() }}
          onDismiss={reset}
        />
      </section>
    )
  }

  const dragging = isDragActive
  const dropClasses = [
    'relative mt-2 rounded-2xl p-8 sm:p-12 text-center transition-all duration-200 cursor-pointer glass',
    dragging
      ? 'eg-rotating-border border border-solid border-blue-electric bg-blue-electric/[0.08]'
      : 'border-2 border-dashed border-border-subtle hover:border-blue-electric hover:bg-blue-electric/[0.05] hover:glow-blue',
    phase === 'accepted' ? 'eg-anim-accept border-emerald' : '',
  ].join(' ')

  return (
    <section className="mx-auto w-full max-w-[600px]" aria-label="Upload">
      <div {...getRootProps()} className={dropClasses}>
        <input {...getInputProps()} />

        {phase === 'success' ? (
          <div className="flex flex-col items-center">
            <CheckCircle2 className="eg-anim-check h-16 w-16 text-emerald" />
            <p className="text-subheading mt-4 text-emerald">File uploaded successfully</p>
            {fileMeta ? <p className="mt-1 text-small text-text-muted">{fileMeta.name}</p> : null}
          </div>
        ) : phase === 'uploading' ? (
          <div className="flex flex-col items-center">
            <FileSpreadsheet className="h-14 w-14 text-blue-electric" />
            {fileMeta ? (
              <p className="text-subheading mt-4 text-white">{fileMeta.name}</p>
            ) : null}
            <div className="mt-5 h-1 w-full max-w-md overflow-hidden rounded-full bg-navy-light">
              <div className="eg-progress-fill h-full rounded-full transition-all duration-200" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-3 text-small text-text-secondary">Uploading... {progress}%</p>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); reset() }}
              className="mt-3 inline-flex items-center gap-1 text-micro text-text-muted transition hover:text-text-secondary"
            >
              <X className="h-3.5 w-3.5" /> Cancel
            </button>
          </div>
        ) : (
          <div className={`flex flex-col items-center transition-transform duration-200 ${dragging ? 'scale-[1.01]' : ''}`}>
            <UploadCloud className={`h-14 w-14 transition-colors ${dragging ? 'text-blue-electric' : 'text-text-secondary'}`} />
            <p className="text-subheading mt-4 text-white">
              {dragging ? 'Release to upload' : 'Drop your Excel file here'}
            </p>
            <p className="mt-2 text-small text-text-muted">or click to browse — .xlsx and .xls supported</p>
            <p className="mt-3 text-micro text-text-muted">Maximum 50MB</p>

            {fileMeta && phase === 'accepted' ? (
              <div className="eg-anim-slide-up mt-5 flex items-center gap-2 rounded-lg border border-border-subtle bg-navy-light/60 px-3 py-2 text-small">
                <FileSpreadsheet className="h-4 w-4 text-emerald" />
                <span className="font-medium text-text-primary">{fileMeta.name}</span>
                <span className="text-text-muted">• {fileMeta.size}</span>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </section>
  )
}
