import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Label,
  LabelList,
  Legend,
  Line,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

// ExcelGPT palette — kept in sync with config.COLOR_PALETTE / the chart PNGs.
const BLUE_ELECTRIC = '#2563EB'
const BLUE_GLOW = '#3B82F6'
const EMERALD = '#10B981'
const GOLD = '#D97706'
const AMBER = '#F59E0B'
const RED_ALERT = '#EF4444'
const GREY = '#9CA3AF'

const PIE_COLORS = [BLUE_ELECTRIC, EMERALD, GOLD, AMBER, RED_ALERT]

const AXIS_PROPS = { tick: { fill: '#F9FAFB', fontSize: 11 }, stroke: GREY }
const GRID_PROPS = { stroke: '#374151', strokeDasharray: '3 3' }
const TOOLTIP_PROPS = {
  contentStyle: { backgroundColor: '#0A0F1E', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 },
  labelStyle: { color: '#F9FAFB' },
  itemStyle: { color: '#F9FAFB' },
  cursor: { fill: 'rgba(255,255,255,0.05)' },
}

const compact = (value) =>
  typeof value === 'number' ? value.toLocaleString('en-US', { notation: 'compact', maximumFractionDigits: 1 }) : value

const linearTrend = (data) => {
  const points = data.filter((d) => typeof d.x === 'number' && typeof d.y === 'number')
  if (points.length < 2) return null
  const n = points.length
  const sx = points.reduce((s, p) => s + p.x, 0)
  const sy = points.reduce((s, p) => s + p.y, 0)
  const sxy = points.reduce((s, p) => s + p.x * p.y, 0)
  const sxx = points.reduce((s, p) => s + p.x * p.x, 0)
  const denom = n * sxx - sx * sx
  if (denom === 0) return null
  const slope = (n * sxy - sx * sy) / denom
  const intercept = (sy - slope * sx) / n
  const xs = points.map((p) => p.x)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  return [
    { x: minX, y: slope * minX + intercept },
    { x: maxX, y: slope * maxX + intercept },
  ]
}

function ChartBody({ chart }) {
  const data = chart.recharts_data || []
  if (!data.length) {
    return <div className="flex h-[300px] items-center justify-center text-sm text-text-secondary">No chart data available</div>
  }

  if (chart.chart_type === 'bar') {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="name" {...AXIS_PROPS} />
          <YAxis tickFormatter={compact} {...AXIS_PROPS} />
          <Tooltip {...TOOLTIP_PROPS} />
          <Bar dataKey="value" fill={BLUE_ELECTRIC} radius={[4, 4, 0, 0]}>
            <LabelList dataKey="value" position="top" formatter={compact} fill="#F9FAFB" fontSize={10} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (chart.chart_type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="name" {...AXIS_PROPS} />
          <YAxis tickFormatter={compact} {...AXIS_PROPS} />
          <Tooltip {...TOOLTIP_PROPS} />
          <Area type="monotone" dataKey="value" stroke="none" fill={BLUE_ELECTRIC} fillOpacity={0.2} />
          <Line type="monotone" dataKey="value" stroke={BLUE_ELECTRIC} strokeWidth={2} dot={{ fill: BLUE_GLOW, r: 3 }} />
        </ComposedChart>
      </ResponsiveContainer>
    )
  }

  if (chart.chart_type === 'pie') {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={90}
            labelLine
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
          >
            {data.map((entry, index) => (
              <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip {...TOOLTIP_PROPS} />
          <Legend wrapperStyle={{ color: '#F9FAFB', fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (chart.chart_type === 'scatter') {
    const trend = linearTrend(data)
    return (
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis type="number" dataKey="x" tickFormatter={compact} {...AXIS_PROPS} />
          <YAxis type="number" dataKey="y" tickFormatter={compact} {...AXIS_PROPS} />
          <Tooltip {...TOOLTIP_PROPS} />
          <Scatter data={data} fill={BLUE_ELECTRIC} />
          {trend ? <ReferenceLine stroke={EMERALD} strokeWidth={2} segment={trend} ifOverflow="extendDomain" /> : null}
        </ScatterChart>
      </ResponsiveContainer>
    )
  }

  return <div className="flex h-[300px] items-center justify-center text-sm text-text-secondary">Unsupported chart type</div>
}

export default function ChartsPreview({ charts }) {
  const items = charts || []
  if (!items.length) {
    return <p className="text-sm text-text-secondary">No charts available.</p>
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {items.map((chart) => (
        <div key={chart.chart_id} className="rounded-2xl border border-white/10 bg-navy p-5">
          <h3 className="mb-4 font-bold text-white">{chart.title}</h3>
          <ChartBody chart={chart} />
        </div>
      ))}
    </div>
  )
}
