import { useEffect, useState } from 'react'
import { Check, Loader2, Info } from 'lucide-react'

// Subtle amber notice shown when the AI planner fell back to rule-based analysis.
// Honest about what happened without alarming the user.
export function FallbackBanner() {
  return (
    <div
      role="status"
      className="mb-4 flex items-start gap-3 rounded-xl border border-amber/30 bg-amber/10 px-4 py-3 text-small text-amber"
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0" />
      <p>
        AI planning timed out — used smart rule-based analysis instead. Results may differ from your exact wording.
      </p>
    </div>
  )
}

// Four-step pipeline stepper with contextual, rotating loading messages.
// Horizontal on desktop, vertical stack on mobile.
const STEPS = [
  {
    label: 'Analysing your data',
    messages: (rows, sheets) => [
      'Reading your spreadsheet structure...',
      'Detecting column types and patterns...',
      'Identifying Nigerian business context...',
      `Profiling ${rows || 0} rows across ${sheets || 0} sheet${sheets === 1 ? '' : 's'}...`,
    ],
  },
  {
    label: 'Planning operations',
    messages: () => [
      'Sending your instruction to Cerebras...',
      'Classifying intent and selecting operations...',
      'Building your custom analysis plan...',
      'Routing to the right computation modules...',
    ],
  },
  {
    label: 'Computing results',
    messages: () => [
      'Running aggregations and rankings...',
      'Calculating growth rates and variances...',
      'Generating performance scores...',
      'Building charts from your data...',
    ],
  },
  {
    label: 'Formatting report',
    messages: () => [
      'Applying Nigerian currency formatting...',
      'Building your Executive Summary...',
      'Embedding charts into Excel sheets...',
      'Polishing your professional report...',
    ],
  },
]

export default function ProgressIndicator({ currentStep = 1, rowCount, sheetCount, aiStatus }) {
  const activeIndex = Math.min(Math.max(currentStep, 1), STEPS.length) - 1
  const [messageIndex, setMessageIndex] = useState(0)

  // Rotate the active step's messages every 2.5s; reset when the step changes.
  useEffect(() => {
    setMessageIndex(0)
    const id = setInterval(() => setMessageIndex((i) => i + 1), 2500)
    return () => clearInterval(id)
  }, [activeIndex])

  const messages = STEPS[activeIndex].messages(rowCount, sheetCount)
  const activeMessage = messages[messageIndex % messages.length]

  return (
    <section className="eg-card p-6 lg:p-8" aria-label="Processing">
      {aiStatus === 'fallback' ? <FallbackBanner /> : null}
      <ol className="flex flex-col gap-6 md:flex-row md:items-start md:gap-0">
        {STEPS.map((step, index) => {
          const status = index < activeIndex ? 'complete' : index === activeIndex ? 'active' : 'pending'
          const isLast = index === STEPS.length - 1
          return (
            <li key={step.label} className="flex flex-1 items-start gap-3 md:flex-col md:items-center md:gap-0">
              <div className="flex items-center md:w-full md:flex-col">
                <div className="flex items-center md:w-full md:flex-row md:justify-center">
                  {/* circle */}
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-small font-bold transition-colors ${
                      status === 'complete'
                        ? 'border-emerald bg-emerald text-white'
                        : status === 'active'
                          ? 'eg-anim-pulse-glow border-blue-electric bg-blue-electric text-white'
                          : 'border-white/10 bg-navy-card text-text-muted'
                    }`}
                  >
                    {status === 'complete' ? (
                      <Check className="h-5 w-5" />
                    ) : status === 'active' ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      index + 1
                    )}
                  </div>

                  {/* connector (desktop only, between circles) */}
                  {!isLast ? (
                    <div className="mx-2 hidden h-0.5 flex-1 overflow-hidden rounded-full bg-white/10 md:block">
                      <div
                        className={`h-full transition-all duration-500 ${
                          index < activeIndex ? 'w-full bg-emerald' : 'w-0 bg-emerald'
                        }`}
                      />
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="md:mt-3 md:text-center">
                <p
                  className={`text-small font-semibold md:px-2 ${
                    status === 'pending' ? 'text-text-muted' : 'text-text-primary'
                  } truncate`}
                >
                  {step.label}
                </p>
                {status === 'active' ? (
                  <p key={activeMessage} className="eg-anim-slide-up mt-1 text-micro text-blue-glow md:max-w-[12rem]">
                    {activeMessage}
                  </p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
