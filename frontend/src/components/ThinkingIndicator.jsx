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
    <div className="eg-anim-slide-up mb-8 flex flex-col gap-2">
      <div className="flex items-center gap-1.5">
        <span className="eg-dot" />
        <span className="eg-dot" />
        <span className="eg-dot" />
      </div>
      <p key={index} className="eg-anim-slide-up text-[13px] text-text-3">
        {MESSAGES[index]}
      </p>
    </div>
  )
}
