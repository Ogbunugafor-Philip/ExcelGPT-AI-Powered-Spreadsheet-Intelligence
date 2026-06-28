// Charts surface — delegates to the dashboard ChartsSection, which renders
// horizontal ranking bars, per-chart type switching, colour-coded performers,
// and display-name tooltips ("Deposits (₦): ₦187,500,000").
import ChartsSection from '../dashboard/ChartsSection'

export default function ChartsPreview({ charts }) {
  const items = charts || []
  if (!items.length) return <p className="text-sm text-text-secondary">No charts available.</p>
  return <ChartsSection charts={items} />
}
