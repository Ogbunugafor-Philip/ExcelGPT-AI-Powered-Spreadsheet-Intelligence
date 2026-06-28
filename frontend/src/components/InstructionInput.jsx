import { useMemo, useRef, useState } from 'react'
import { HelpCircle, Send, Wand2 } from 'lucide-react'
import { analyseInstruction } from '../services/api'
import ActionPlanSummary from './ActionPlanSummary'
import ErrorMessage from './ErrorMessage'

// Context-aware suggestions keyed to the detected Nigerian business template.
const TEMPLATE_PROMPTS = {
  banking: [
    'Show top 5 branches by deposit volume this quarter',
    'Calculate loan-to-deposit ratio by zone',
    'Identify underperforming branches and flag them red',
    'Prepare a CBN-style performance summary',
    'Forecast next quarter deposit growth',
  ],
  sales: [
    'Rank FSOs by revenue and show target vs actual',
    'Show monthly growth rates by territory',
    'Identify bottom 3 performers for coaching',
    'Create a zone-level performance scorecard',
    'Forecast next month sales by region',
  ],
  hr: [
    'Show headcount by department and grade level',
    'Calculate average salary by zone',
    'Identify staff due for promotion review',
    'Summarise PENCOM and NHF deductions',
    'Show attrition trend over the last 6 months',
  ],
  general: [
    'Summarise the key metrics from this data',
    'Show the top 10 rows ranked by the main value column',
    'Calculate growth rates between time periods',
    'Find outliers and anomalies in the data',
    'Create an executive summary with KPI cards',
  ],
}

// Pick the prompt set for the detected template, defaulting to general.
const buildPrompts = (brief) => {
  const template = brief?.nigerian_context?.suggested_template
  return TEMPLATE_PROMPTS[template] || TEMPLATE_PROMPTS.general
}

export default function InstructionInput({ sessionId, intelligenceBrief, onAnalyse, onAnalyzeStart, onAnalyzeEnd }) {
  const [instruction, setInstruction] = useState('')
  const [isAnalysing, setIsAnalysing] = useState(false)
  const [error, setError] = useState(null) // { key, message } | null
  const [plan, setPlan] = useState(null)
  const [elapsedMs, setElapsedMs] = useState(null)
  const [clarificationAnswer, setClarificationAnswer] = useState('')
  const textareaRef = useRef(null)

  const prompts = useMemo(() => buildPrompts(intelligenceBrief), [intelligenceBrief])
  const clarification = plan?.clarification_needed ? plan.clarification_question : null

  const runAnalyse = async (text) => {
    const trimmed = (text || '').trim()
    if (!trimmed || !sessionId) {
      setError({ key: 'UNKNOWN', message: 'Type an instruction to generate an action plan.' })
      return
    }

    setError(null)
    setIsAnalysing(true)
    onAnalyzeStart?.()
    const startedAt = performance.now()
    let success = false

    try {
      const data = await analyseInstruction(sessionId, trimmed)
      setPlan(data.action_plan)
      setElapsedMs(Math.round(performance.now() - startedAt))
      // Lift the computed report preview up to App unless a clarification is needed.
      if (!data.action_plan?.clarification_needed) {
        success = true
        onAnalyse?.(data, trimmed)
      }
    } catch (err) {
      setError({ key: err.errorKey || 'UNKNOWN', message: err.errorKey ? '' : err.message })
      setPlan(null)
      setElapsedMs(null)
    } finally {
      setIsAnalysing(false)
      onAnalyzeEnd?.(success)
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

        <div className="mt-4 flex gap-2 overflow-x-auto pb-1 md:flex-wrap md:overflow-visible">
          {prompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => handlePromptClick(prompt)}
              className="glass shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-small text-text-secondary transition hover:border-blue-electric hover:bg-blue-electric/10 hover:text-text-primary md:whitespace-normal"
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
        <div className="mt-5">
          <ErrorMessage
            errorKey={error.key}
            customMessage={error.message}
            onAction={() => { setError(null); textareaRef.current?.focus() }}
            onDismiss={() => setError(null)}
          />
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
