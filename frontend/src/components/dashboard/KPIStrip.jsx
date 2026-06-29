import { useEffect, useRef, useState } from 'react'

// Direction indicator styling for the change line.
const DIRECTION = {
  up: { arrow: '↑', className: 'text-emerald' },
  down: { arrow: '↓', className: 'text-red-alert' },
  neutral: { arrow: '→', className: 'text-amber' },
}

const NUMBER_RE = /-?\d[\d,]*(?:\.\d+)?/

// Animate the numeric portion of a pre-formatted value ("₦4.21B", "+12.4%")
// from zero to its final value, preserving any prefix/suffix (₦, %, B, …).
function useCountUp(formatted, duration = 900) {
  const [display, setDisplay] = useState(formatted)
  const frame = useRef(0)

  useEffect(() => {
    const match = NUMBER_RE.exec(formatted || '')
    if (!match) {
      setDisplay(formatted)
      return undefined
    }
    const raw = match[0]
    const target = parseFloat(raw.replace(/,/g, ''))
    if (!Number.isFinite(target)) {
      setDisplay(formatted)
      return undefined
    }
    const decimals = raw.includes('.') ? raw.split('.')[1].length : 0
    const grouped = raw.includes(',')
    const start = performance.now()

    const render = (value) => {
      const fixed = value.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
        useGrouping: grouped,
      })
      setDisplay(formatted.replace(raw, fixed))
    }

    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic
      render(target * eased)
      if (t < 1) frame.current = requestAnimationFrame(tick)
    }
    frame.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame.current)
  }, [formatted, duration])

  return display
}

function KpiCard({ card, index }) {
  const value = useCountUp(card.value)
  const dir = DIRECTION[card.direction] || DIRECTION.neutral
  return (
    <div
      className="eg-anim-rise rounded-2xl border border-white/10 border-t-[3px] border-t-coral bg-card p-5 transition hover:border-coral/40 hover:shadow-glow-coral"
      style={{ animationDelay: `${Math.min(index, 6) * 60}ms` }}
    >
      <p className="truncate text-xs font-semibold uppercase tracking-wider text-text-secondary" title={card.label}>
        {card.label}
      </p>
      <p className="mt-3 text-2xl font-bold tabular-nums text-white">{value}</p>
      {card.change ? (
        <p className={`mt-2 flex items-center gap-1 text-sm font-medium ${dir.className}`}>
          <span aria-hidden="true">{dir.arrow}</span>
          <span>{card.change}</span>
        </p>
      ) : null}
    </div>
  )
}

export default function KPIStrip({ cards }) {
  const items = cards || []
  if (!items.length) return null
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-6">
      {items.map((card, index) => (
        <KpiCard key={`${card.label}-${index}`} card={card} index={index} />
      ))}
    </div>
  )
}
