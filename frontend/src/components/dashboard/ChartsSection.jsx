import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Area,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const CORAL = '#FF5C5C'
const TEAL = '#34D399'
const GOLD = '#F59E0B'
const WARNING = '#FBBF24'
const NEGATIVE = '#F87171'
const TEXT3 = '#52525B'
const PIE_COLORS = [CORAL, TEAL, GOLD, WARNING, NEGATIVE, '#FF8E8E', TEXT3]

const AXIS_PROPS = { tick: { fill: '#52525B', fontSize: 11 }, stroke: 'rgba(255,255,255,0.12)' }
const GRID_PROPS = { stroke: 'rgba(255,255,255,0.06)', strokeDasharray: '3 3' }

const compact = (value) =>
  typeof value === 'number' ? value.toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 1 }) : value

const full = (value, displayName) => {
  if (typeof value !== 'number') return value
  const text = value.toLocaleString('en-US', { maximumFractionDigits: 2 })
  return displayName && displayName.includes('₦') ? `₦${text}` : text
}

// Colour ranking bars: coral primary, muted grey for the rest.
const barColors = (data) => {
  const values = data.map((d) => (typeof d.value === 'number' ? d.value : -Infinity))
  const maxIdx = values.indexOf(Math.max(...values))
  return data.map((_, i) => (i === maxIdx ? CORAL : TEXT3))
}

function DashTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload || {}
  const metric = row.displayName || 'Value'
  const category = row.label || row.name
  return (
    <div className="rounded-lg border border-border-strong bg-card px-3 py-2 text-xs shadow-elevated">
      {category ? <p className="mb-1 font-semibold text-text-1">{category}</p> : null}
      <p>
        <span className="text-text-2">{metric}: </span>
        <span className="font-medium text-text-1">{full(row.value, metric)}</span>
      </p>
    </div>
  )
}

function ChartBody({ chart, type }) {
  const data = chart.recharts_data || []
  if (!data.length) {
    return <div className="flex h-[320px] items-center justify-center text-sm text-text-2">No chart data</div>
  }
  const metric = chart.y_label || data[0]?.displayName || 'Value'

  if (type === 'bar') {
    // Horizontal bars so entity names are readable on the Y axis.
    const colors = barColors(data)
    const height = Math.max(320, data.length * 38)
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 48, bottom: 8, left: 8 }}>
          <CartesianGrid {...GRID_PROPS} horizontal={false} />
          <XAxis type="number" tickFormatter={compact} {...AXIS_PROPS} />
          <YAxis type="category" dataKey="name" width={120} {...AXIS_PROPS} />
          <Tooltip content={<DashTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} name={metric}>
            {data.map((_, i) => (
              <Cell key={i} fill={colors[i]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={data} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="name" {...AXIS_PROPS} />
          <YAxis tickFormatter={compact} {...AXIS_PROPS} />
          <Tooltip content={<DashTooltip />} />
          <Area type="monotone" dataKey="value" stroke="none" fill={CORAL} fillOpacity={0.2} />
          <Line type="monotone" dataKey="value" name={metric} stroke={CORAL} strokeWidth={2.5} dot={{ fill: TEAL, stroke: TEAL, r: 3 }} activeDot={{ fill: CORAL, r: 5 }} />
        </ComposedChart>
      </ResponsiveContainer>
    )
  }

  // pie
  return (
    <ResponsiveContainer width="100%" height={320}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={100}
          labelLine
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip content={<DashTooltip />} />
        <Legend wrapperStyle={{ color: '#A1A1AA', fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}

const TYPES = [
  { key: 'bar', label: 'Bar' },
  { key: 'line', label: 'Line' },
  { key: 'pie', label: 'Pie' },
]

function ChartCard({ chart }) {
  const initial = ['bar', 'line', 'pie'].includes(chart.chart_type) ? chart.chart_type : 'bar'
  const [type, setType] = useState(initial)

  const selector = (
    <div className="flex gap-1 rounded-lg border border-border bg-white/5 p-0.5">
      {TYPES.map((t) => (
        <button
          key={t.key}
          type="button"
          onClick={() => setType(t.key)}
          className={`rounded-md px-2.5 py-1 text-xs font-semibold transition ${
            type === t.key ? 'bg-coral text-white' : 'text-text-2 hover:text-text-1'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )

  return (
    <div className="eg-anim-rise">
      {/* No card wrapper, no title — the question is the title. Toggle only. */}
      <div className="mb-2 flex justify-end">{selector}</div>
      <ChartBody chart={chart} type={type} />
    </div>
  )
}

export default function ChartsSection({ charts }) {
  const items = charts || []
  if (!items.length) return null
  return (
    <div className="grid grid-cols-1 gap-8 xl:grid-cols-2">
      {items.map((chart) => (
        <ChartCard key={chart.chart_id} chart={chart} />
      ))}
    </div>
  )
}
