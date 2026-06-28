import { useState } from 'react'
import './index.css'
import UploadZone from './components/UploadZone'
import DataPreview from './components/DataPreview'
import InstructionInput from './components/InstructionInput'
import PreviewPanel from './components/PreviewPanel'
import RefinementInput from './components/RefinementInput'
import { downloadFile, refineReport } from './services/api'

// Turn an action plan into a short assistant-style summary for the chat history.
const OP_LABELS = {
  rank: 'ranking',
  group_sum: 'totals',
  group_avg: 'averages',
  filter: 'filtering',
  growth_rate: 'growth rates',
  variance: 'variance vs target',
  correlation: 'correlation',
  outlier: 'outlier detection',
  distribution: 'distribution',
  forecast: 'forecast',
  cluster: 'clustering',
  score: 'scoring',
  chart: 'charts',
}

const summariseActionPlan = (plan) => {
  if (!plan) return 'Updated the report.'
  const ops = plan.operations || []
  const labels = [...new Set(ops.map((op) => OP_LABELS[op.operation_type] || op.operation_type))]
  const what = labels.length ? labels.join(' + ') : (plan.intent_type || 'report').replace(/_/g, ' ')
  return `Analysed: ${what} across ${ops.length} operation${ops.length === 1 ? '' : 's'}`
}

export default function App() {
  const [sessionId, setSessionId] = useState('')
  const [preview, setPreview] = useState(null)
  const [intelligenceBrief, setIntelligenceBrief] = useState(null)
  const [currentView, setCurrentView] = useState('upload')
  // Phase 6 — the computed report preview returned by /analyse (and /refine).
  const [reportPreview, setReportPreview] = useState(null)
  const [downloadToken, setDownloadToken] = useState(null)
  const [version, setVersion] = useState(0)
  // Phase 7 — the iterative refinement loop.
  const [refinementHistory, setRefinementHistory] = useState([])
  const [refinementCount, setRefinementCount] = useState(0)
  const [isRefining, setIsRefining] = useState(false)

  const handleUploadComplete = (nextSessionId, nextPreview, nextIntelligenceBrief) => {
    setSessionId(nextSessionId)
    setPreview(nextPreview)
    setIntelligenceBrief(nextIntelligenceBrief)
    setReportPreview(null)
    setDownloadToken(null)
    setVersion(0)
    setRefinementHistory([])
    setRefinementCount(0)
    setCurrentView('preview')
  }

  // First analysis: lift the report up and seed the conversation history.
  const handleAnalyseResult = (data, instruction) => {
    setReportPreview(data.preview)
    setDownloadToken(data.download_token)
    setVersion(data.version)
    setRefinementHistory([
      { role: 'user', content: instruction },
      { role: 'assistant', content: summariseActionPlan(data.action_plan) },
    ])
    setRefinementCount(0)
    setCurrentView('preview')
  }

  const handleRefine = async (feedback) => {
    const priorHistory = refinementHistory
    setRefinementHistory((prev) => [...prev, { role: 'user', content: feedback }])
    setIsRefining(true)
    try {
      const data = await refineReport({
        session_id: sessionId,
        feedback,
        history: priorHistory,
        current_version: version,
      })
      setReportPreview(data.preview)
      setDownloadToken(data.download_token)
      setVersion(data.version)
      setRefinementHistory((prev) => [...prev, { role: 'assistant', content: summariseActionPlan(data.action_plan) }])
      setRefinementCount((count) => count + 1)
    } catch (err) {
      setRefinementHistory((prev) => [...prev, { role: 'assistant', content: `⚠️ ${err.message || 'Refinement failed.'}` }])
    } finally {
      setIsRefining(false)
    }
  }

  const handleStartFresh = () => {
    setReportPreview(null)
    setDownloadToken(null)
    setVersion(0)
    setRefinementHistory([])
    setRefinementCount(0)
    setCurrentView('instruction')
  }

  const handleDownload = () => downloadFile(downloadToken)

  const showReport = reportPreview && currentView === 'preview'

  return (
    <div className="min-h-screen bg-navy text-text-primary">
      <header className="mx-auto flex max-w-7xl flex-col gap-3 px-6 py-8 lg:flex-row lg:items-end lg:justify-between lg:px-8">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.25em] text-blue-electric">ExcelGPT</p>
          <h1 className="mt-2 text-4xl font-semibold">Turn spreadsheets into executive-ready intelligence.</h1>
          <p className="eg-text-muted mt-2 max-w-2xl">Upload a workbook and inspect a rich data preview with sheet tabs, profile insights, and suggested next actions.</p>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-text-secondary">
          {sessionId ? `Session ${sessionId.slice(0, 8)}…` : 'Phase 3 • Intent Engine'}
        </div>
      </header>

      <main className="mx-auto flex max-w-7xl flex-col gap-8 px-6 pb-12 lg:px-8">
        {currentView === 'upload' ? <UploadZone onUploadComplete={handleUploadComplete} /> : null}
        {currentView !== 'upload' ? (
          <>
            {showReport ? (
              <>
                <PreviewPanel
                  preview={reportPreview}
                  downloadToken={downloadToken}
                  version={version}
                  onDownload={handleDownload}
                />
                <RefinementInput
                  history={refinementHistory}
                  version={version}
                  refinementCount={refinementCount}
                  isRefining={isRefining}
                  onRefine={handleRefine}
                  onStartFresh={handleStartFresh}
                />
              </>
            ) : (
              <>
                <DataPreview preview={preview} intelligenceBrief={intelligenceBrief} />
                <InstructionInput
                  sessionId={sessionId}
                  intelligenceBrief={intelligenceBrief}
                  onAnalyse={handleAnalyseResult}
                />
              </>
            )}
          </>
        ) : null}
      </main>

      <footer className="border-t border-white/10 px-6 py-6 text-center text-sm text-text-secondary lg:px-8">
        <p>© ExcelGPT • Data Intelligence Layer</p>
      </footer>
    </div>
  )
}
