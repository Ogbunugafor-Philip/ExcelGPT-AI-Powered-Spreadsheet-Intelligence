import { useEffect, useRef, useState } from 'react'
import { Loader2, RefreshCw, Sparkles } from 'lucide-react'

const MAX_REFINEMENTS = 10

// Conversational refinement panel shown below the PreviewPanel. Renders the turn
// history as chat bubbles and lets the user submit follow-up feedback that
// recomputes the report in place. After 10 refinements it nudges a fresh start.
export default function RefinementInput({
  history = [],
  version,
  refinementCount = 0,
  isRefining = false,
  onRefine,
  onStartFresh,
}) {
  const [feedback, setFeedback] = useState('')
  const scrollRef = useRef(null)

  // Smooth-scroll the conversation to the newest message.
  useEffect(() => {
    const node = scrollRef.current
    if (node) {
      node.scrollTo({ top: node.scrollHeight, behavior: 'smooth' })
    }
  }, [history.length, isRefining])

  const limitReached = refinementCount >= MAX_REFINEMENTS

  const submit = () => {
    const trimmed = feedback.trim()
    if (!trimmed || isRefining) return
    onRefine?.(trimmed)
    setFeedback('')
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    submit()
  }

  const handleKeyDown = (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      submit()
    }
  }

  return (
    <section className="eg-card p-6 lg:p-8" aria-label="Refine report">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-electric/15 text-blue-electric">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-xl font-semibold">Refine your report</h2>
          <p className="eg-text-muted text-sm">Give feedback and ExcelGPT recomputes — your report updates in place.</p>
        </div>
      </div>

      {history.length ? (
        <div
          ref={scrollRef}
          className="mt-6 max-h-[300px] space-y-3 overflow-y-auto rounded-2xl border border-white/10 bg-navy p-4"
        >
          {history.map((turn, index) => {
            const isUser = turn.role === 'user'
            return (
              <div key={index} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                    isUser
                      ? 'bg-blue-electric text-white'
                      : 'border border-white/10 bg-navy-light text-text-secondary'
                  }`}
                >
                  {turn.content}
                </div>
              </div>
            )
          })}
          {isRefining ? (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-navy-light px-4 py-2.5 text-sm text-text-secondary">
                <Loader2 className="h-4 w-4 animate-spin" />
                Recomputing…
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {limitReached ? (
        <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-amber/30 bg-amber/10 p-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-amber">
            You have made 10 refinements. Consider starting fresh with a new instruction for best results.
          </p>
          <button
            type="button"
            onClick={onStartFresh}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-amber/40 px-4 py-2 text-sm font-semibold text-amber transition hover:bg-amber/15"
          >
            <RefreshCw className="h-4 w-4" />
            Start Fresh
          </button>
        </div>
      ) : null}

      <p className="mt-6 text-sm text-text-secondary">Version {version} — Refine to update</p>

      <form className="mt-2" onSubmit={handleSubmit}>
        <textarea
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          disabled={isRefining}
          placeholder="Refine your report... e.g. Add a forecast for the next 3 months"
          className="w-full resize-none rounded-2xl border border-white/10 bg-navy px-4 py-3 text-text-primary placeholder:text-text-secondary focus:border-blue-electric focus:outline-none focus:ring-2 focus:ring-blue-electric/40 disabled:opacity-60"
        />
        <div className="mt-3 flex items-center justify-between gap-4">
          <p className="eg-text-muted text-xs">Press ⌘/Ctrl + Enter to refine</p>
          <button
            type="submit"
            disabled={isRefining || !feedback.trim()}
            className="eg-btn-primary inline-flex items-center gap-2 px-5 py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRefining ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {isRefining ? 'Recomputing…' : 'Refine'}
          </button>
        </div>
      </form>
    </section>
  )
}
