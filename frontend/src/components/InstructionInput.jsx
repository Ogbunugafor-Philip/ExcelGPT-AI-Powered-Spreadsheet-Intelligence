import { useMemo, useRef, useState } from 'react'
import { AlertCircle, HelpCircle, Send, Wand2 } from 'lucide-react'
import { analyseInstruction } from '../services/api'
import ActionPlanSummary from './ActionPlanSummary'

const DEFAULT_PROMPTS = [
  'Rank branches by deposit growth this quarter and forecast next quarter in NGN',
  'Summarise total deposits by LGA and chart the top 10',
  'Score FSO performance by volume and growth, then rank them',
  'Build an executive summary with KPIs and a deposits trend chart',
]

// Surface a few suggestions tuned to what the upload actually contains.
const buildPrompts = (brief) => {
  const suggested = (brief?.suggested_operations || []).filter(Boolean)
  const merged = [...suggested, ...DEFAULT_PROMPTS]
  return Array.from(new Set(merged)).slice(0, 5)
}

export default function InstructionInput({ sessionId, intelligenceBrief }) {
  const [instruction, setInstruction] = useState('')
  const [isAnalysing, setIsAnalysing] = useState(false)
  const [error, setError] = useState('')
  const [plan, setPlan] = useState(null)
  const [elapsedMs, setElapsedMs] = useState(null)
  const [clarificationAnswer, setClarificationAnswer] = useState('')
  const textareaRef = useRef(null)

  const prompts = useMemo(() => buildPrompts(intelligenceBrief), [intelligenceBrief])
  const clarification = plan?.clarification_needed ? plan.clarification_question : null

  const runAnalyse = async (text) => {
    const trimmed = (text || '').trim()
    if (!trimmed || !sessionId) {
      setError('Type an instruction to generate an action plan.')
      return
    }

    setError('')
    setIsAnalysing(true)
    const startedAt = performance.now()

    try {
      const data = await analyseInstruction(sessionId, trimmed)
      setPlan(data.action_plan)
      setElapsedMs(Math.round(performance.now() - startedAt))
    } catch (err) {
      setError(err.message || 'Could not generate an action plan.')
      setPlan(null)
      setElapsedMs(null)
    } finally {
      setIsAnalysing(false)
    }
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    runAnalyse(instruction)
  }

  const handlePromptClick = (prompt) => {
    setInstruction(prompt)
    textareaRef.current?.focus()
  }

  const handleClarificationSubmit = (event) => {
    event.preventDefault()
    const answer = clarificationAnswer.trim()
    if (!answer) return
    const combined = `${instruction.trim()} — ${answer}`
    setInstruction(combined)
    setClarificationAnswer('')
    runAnalyse(combined)
  }

  return (
    <section className="eg-card p-8" aria-label="Instruction">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-electric/15 text-blue-electric">
            <Wand2 className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-2xl font-semibold">Describe your report</h2>
            <p className="eg-text-muted mt-1">Tell ExcelGPT what you want in plain English — it plans the work for you.</p>
          </div>
        </div>
        {elapsedMs !== null && !isAnalysing ? (
          <span className="rounded-full border border-emerald/30 bg-emerald/10 px-3 py-1 text-sm text-emerald">
            Planned in {elapsedMs} ms
          </span>
        ) : null}
      </div>

      <form className="mt-6" onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          rows={3}
          placeholder="e.g. Rank branches by deposit growth this quarter and forecast next quarter in NGN."
          className="w-full resize-none rounded-2xl border border-white/10 bg-navy px-4 py-3 text-text-primary placeholder:text-text-secondary focus:border-blue-electric focus:outline-none focus:ring-2 focus:ring-blue-electric/40"
        />

        <div className="mt-4 flex flex-wrap gap-2">
          {prompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => handlePromptClick(prompt)}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-text-secondary transition hover:bg-white/10 hover:text-text-primary"
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className="mt-5 flex items-center justify-between gap-4">
          <p className="eg-text-muted text-sm">Cerebras returns intent only — all numbers are computed deterministically.</p>
          <button
            type="submit"
            disabled={isAnalysing || !instruction.trim()}
            className="eg-btn-primary inline-flex items-center gap-2 px-5 py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {isAnalysing ? 'Planning…' : 'Generate action plan'}
          </button>
        </div>
      </form>

      {error ? (
        <div className="mt-5 flex items-center gap-2 rounded-2xl border border-red-alert/30 bg-red-alert/10 px-4 py-3 text-sm text-red-alert">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      ) : null}

      {clarification ? (
        <div className="mt-6 rounded-2xl border border-amber/30 bg-amber/10 p-5">
          <p className="flex items-center gap-2 font-semibold text-amber">
            <HelpCircle className="h-4 w-4" /> One quick question
          </p>
          <p className="mt-2 text-text-primary">{clarification}</p>
          <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={handleClarificationSubmit}>
            <input
              value={clarificationAnswer}
              onChange={(event) => setClarificationAnswer(event.target.value)}
              placeholder="Your answer…"
              className="flex-1 rounded-xl border border-white/10 bg-navy px-4 py-2.5 text-text-primary placeholder:text-text-secondary focus:border-blue-electric focus:outline-none focus:ring-2 focus:ring-blue-electric/40"
            />
            <button
              type="submit"
              disabled={isAnalysing || !clarificationAnswer.trim()}
              className="eg-btn-primary px-5 py-2.5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              Re-plan
            </button>
          </form>
        </div>
      ) : null}

      {plan && !clarification ? (
        <div className="mt-8">
          <ActionPlanSummary plan={plan} />
        </div>
      ) : null}
    </section>
  )
}
