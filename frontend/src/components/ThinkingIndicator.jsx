import { useEffect, useState } from 'react'

const MESSAGES = [
  'Reading your data...',
  'Running the analysis...',
  'Computing the numbers...',
  'Building your insight...',
  'Almost there...',
]

// Left-aligned placeholder card shown while an answer is being computed.
export default function ThinkingIndicator() {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % MESSAGES.length), 2000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="eg-anim-slide-up max-w-2xl rounded-2xl border border-border bg-card px-6 py-5">
      <div className="flex items-center gap-1.5">
        <span className="eg-dot" />
        <span className="eg-dot" />
        <span className="eg-dot" />
      </div>
      <p key={index} className="eg-anim-slide-up mt-3 text-small text-text-muted">
        {MESSAGES[index]}
      </p>
    </div>
  )
}
