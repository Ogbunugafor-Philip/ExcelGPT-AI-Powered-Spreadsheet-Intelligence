import { useEffect, useRef, useState } from 'react'

// Small version indicator for the PreviewPanel header. Pulses the badge when the
// version increments and offers a (placeholder) link to browse previous versions.
export default function VersionTracker({ version }) {
  const [pulse, setPulse] = useState(false)
  const previous = useRef(version)

  useEffect(() => {
    if (version !== previous.current) {
      previous.current = version
      setPulse(true)
      const timer = setTimeout(() => setPulse(false), 300)
      return () => clearTimeout(timer)
    }
  }, [version])

  if (!version) return null

  return (
    <div className="flex items-center gap-2">
      <span
        title={`Version ${version} of your report`}
        className={`inline-block rounded-full bg-white/5 px-2.5 py-1 text-xs font-semibold text-text-secondary transition-transform duration-300 ${
          pulse ? 'scale-125 text-blue-electric' : 'scale-100'
        }`}
      >
        v{version}
      </span>
      {version > 1 ? (
        <button
          type="button"
          disabled
          title="Version history browsing coming soon"
          className="cursor-default text-xs text-text-secondary/60 transition hover:text-text-secondary"
        >
          ← Previous
        </button>
      ) : null}
    </div>
  )
}
