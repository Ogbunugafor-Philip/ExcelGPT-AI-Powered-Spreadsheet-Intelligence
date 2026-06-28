import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const BLUE_ELECTRIC = '#2563EB'
const AMBER = '#F59E0B'
const GREY = '#9CA3AF'

const AXIS_PROPS = { tick: { fill: '#F9FAFB', fontSize: 11 }, stroke: GREY }

// Heuristic: large magnitudes are Naira amounts; prefix the axis/tooltip with ₦.
const looksCurrency = (values) => values.some((v) => typeof v === 'number' && Math.abs(v) >= 1000)

const makeFormatter = (currency) => (value) => {
  if (typeof value !== 'number') return value
  const text = value.toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 1 })
  return currency ? `₦${text}` : text
}

function CustomTooltip({ active, payload, label, format }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload || {}
  const line = (name, value) =>
    value === undefined || value === null ? null : (
      <p key={name} className="text-xs text-text-primary">
        <span className="text-text-secondary">{name}: </span>
        {format(value)}
      </p>
    )
  return (
    <div className="rounded-lg border border-white/10 bg-navy px-3 py-2">
      <p className="mb-1 text-xs font-semibold text-white">{label}</p>
      {line('Historical', row.historical)}
      {line('Forecast', row.forecast)}
      {line('Upper', row.upper)}
      {line('Lower', row.lower)}
    </div>
  )
}

export default function ForecastPreview({ historical, projected, confidence_upper, confidence_lower, assumptions }) {
  const hist = historical || []
  const proj = projected || []
  if (!hist.length && !proj.length) return null

  const upByPeriod = Object.fromEntries((confidence_upper || []).map((p) => [p.period, p.value]))
  const lowByPeriod = Object.fromEntries((confidence_lower || []).map((p) => [p.period, p.value]))

  const data = [
    ...hist.map((p) => ({ period: p.period, historical: p.value })),
    ...proj.map((p) => ({
      period: p.period,
      forecast: p.value,
      upper: upByPeriod[p.period],
      lower: lowByPeriod[p.period],
      confidence:
        lowByPeriod[p.period] !== undefined && upByPeriod[p.period] !== undefined
          ? [lowByPeriod[p.period], upByPeriod[p.period]]
          : undefined,
    })),
  ]

  // Bridge the historical and forecast lines at the boundary so they connect.
  const lastHist = hist[hist.length - 1]
  if (lastHist) {
    const boundary = data.find((d) => d.period === lastHist.period)
    if (boundary) boundary.forecast = lastHist.value
  }

  const currency = looksCurrency([...hist, ...proj].map((p) => p.value))
  const format = makeFormatter(currency)
  const angled = data.length > 8

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-bold uppercase tracking-wider text-white">Forecast Analysis</h3>

      <div className="rounded-2xl border border-white/10 bg-navy p-5">
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={data} margin={{ top: 16, right: 24, bottom: angled ? 40 : 8, left: 8 }}>
            <CartesianGrid stroke="#374151" strokeDasharray="3 3" />
            <XAxis
              dataKey="period"
              {...AXIS_PROPS}
              angle={angled ? -45 : 0}
              textAnchor={angled ? 'end' : 'middle'}
              height={angled ? 50 : 30}
              interval="preserveStartEnd"
            />
            <YAxis tickFormatter={format} {...AXIS_PROPS} />
            <Tooltip content={<CustomTooltip format={format} />} />
            <Legend wrapperStyle={{ color: '#F9FAFB', fontSize: 12 }} />
            <Area
              name="Confidence Interval"
              type="monotone"
              dataKey="confidence"
              stroke="none"
              fill={AMBER}
              fillOpacity={0.18}
              connectNulls
            />
            <Line
              name="Historical"
              type="monotone"
              dataKey="historical"
              stroke={BLUE_ELECTRIC}
              strokeWidth={2.5}
              dot={{ fill: BLUE_ELECTRIC, r: 3 }}
              connectNulls
            />
            <Line
              name="Forecast"
              type="monotone"
              dataKey="forecast"
              stroke={BLUE_ELECTRIC}
              strokeWidth={2.5}
              strokeDasharray="6 4"
              dot={{ fill: BLUE_ELECTRIC, r: 3 }}
              connectNulls
            />
            {lastHist ? (
              <ReferenceLine x={lastHist.period} stroke={GREY} strokeDasharray="4 4" />
            ) : null}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {assumptions?.length ? (
        <div className="rounded-2xl border border-white/10 bg-navy-light p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-secondary">Model assumptions</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-text-primary">
            {assumptions.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
