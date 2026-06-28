// The base surface for every dashboard section. Gives the whole page a single
// consistent card language: navy-card background, soft border, title + subtitle.

export default function InsightCard({ title, subtitle, action, children, fullWidth = false, className = '' }) {
  return (
    <section
      className={`eg-anim-rise rounded-2xl border border-white/10 bg-navy-card p-5 lg:p-6 ${
        fullWidth ? 'col-span-full' : ''
      } ${className}`}
    >
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title ? <h3 className="text-base font-bold text-white">{title}</h3> : null}
            {subtitle ? <p className="mt-0.5 text-sm text-text-secondary">{subtitle}</p> : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </header>
      )}
      {children}
    </section>
  )
}
