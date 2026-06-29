import { useEffect, useRef, useState } from 'react'

// Direction indicator styling for the change line.
const DIRECTION = {
  up: { arrow: '↑', className: 'text-positive' },
  down: { arrow: '↓', className: 'text-negative' },
  neutral: { arrow: '→', className: 'text-warning' },
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
      className="eg-anim-rise rounded-lg border border-border bg-surface p-4 transition hover:border-border-strong hover:shadow-elevated"
      style={{ animationDelay: `${Math.min(index, 6) * 60}ms` }}
    >
      <p className="truncate text-[11px] font-semibold uppercase tracking-[0.06em] text-text-3" title={card.label}>
        {card.label}
      </p>
      <p className="mt-1 text-[28px] font-semibold leading-tight tabular-nums text-text-1">{value}</p>
      {card.change ? (
        <p className={`mt-1 flex items-center gap-1 text-[13px] font-medium ${dir.className}`}>
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
    <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))' }}>
      {items.map((card, index) => (
        <KpiCard key={`${card.label}-${index}`} card={card} index={index} />
      ))}
    </div>
  )
}
