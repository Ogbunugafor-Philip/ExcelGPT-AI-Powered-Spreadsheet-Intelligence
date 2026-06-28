import { useCallback, useMemo, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { CheckCircle2, UploadCloud, AlertCircle } from 'lucide-react'
import { uploadFile } from '../services/api'

export default function UploadZone({ onUploadComplete }) {
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState('')
  const [fileName, setFileName] = useState('')
  const [fileSize, setFileSize] = useState('')
  const [isSuccess, setIsSuccess] = useState(false)

  const onDrop = useCallback(async (acceptedFiles, rejectedFiles) => {
    setError('')
    setIsSuccess(false)
    if (rejectedFiles.length) {
      setError('Please upload a valid .xlsx or .xls file.')
      return
    }

    const file = acceptedFiles[0]
    if (!file) {
      return
    }

    setFileName(file.name)
    setFileSize(`${(file.size / (1024 * 1024)).toFixed(2)} MB`)
    setIsUploading(true)

    try {
      const data = await uploadFile(file)
      setIsSuccess(true)
      onUploadComplete?.(data.session_id, data.preview, data.intelligence_brief)
    } catch (err) {
      setError(err.message || 'Upload failed.')
    } finally {
      setIsUploading(false)
    }
  }, [onUploadComplete])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
    },
    multiple: false,
  })

  const statusTone = useMemo(() => {
    if (error) return 'border-red-alert text-red-alert'
    if (isSuccess) return 'border-emerald text-emerald'
    if (isUploading) return 'border-blue-electric text-text-primary'
    return 'border-blue-electric/60 text-text-primary'
  }, [error, isSuccess, isUploading])

  return (
    <section className="eg-card p-8" aria-label="Upload">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Upload your workbook</h2>
          <p className="eg-text-muted mt-2">Drop an .xlsx or .xls file to start the data intelligence layer.</p>
        </div>
        <div className="rounded-full border border-blue-electric/40 bg-blue-electric/10 px-3 py-1 text-sm text-blue-electric">
          Phase 2
        </div>
      </div>

      <div
        {...getRootProps()}
        className={`mt-6 rounded-2xl border-2 border-dashed bg-navy p-8 text-center transition-all duration-200 ${statusTone} ${isDragActive ? 'scale-[1.01] shadow-glow' : 'hover:shadow-glow'}`}
      >
        <input {...getInputProps()} />
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-blue-electric/15">
          {error ? <AlertCircle className="h-8 w-8" /> : isSuccess ? <CheckCircle2 className="h-8 w-8" /> : <UploadCloud className="h-8 w-8" />}
        </div>
        <p className="mt-4 text-lg font-semibold">
          {isUploading ? 'Uploading and profiling your workbook…' : isDragActive ? 'Drop the workbook here' : 'Drag & drop your Excel file'}
        </p>
        <p className="eg-text-muted mt-2">Accepted formats: .xlsx and .xls</p>

        {isUploading ? (
          <div className="mx-auto mt-6 h-2 w-full max-w-md overflow-hidden rounded-full bg-white/10">
            <div className="h-full w-full animate-pulse rounded-full bg-blue-electric" />
          </div>
        ) : null}

        {fileName ? (
          <div className="mt-5 text-sm text-text-secondary">
            <span className="font-medium text-text-primary">{fileName}</span> • {fileSize}
          </div>
        ) : null}

        {error ? <p className="mt-4 text-sm text-red-alert">{error}</p> : null}
      </div>
    </section>
  )
}
