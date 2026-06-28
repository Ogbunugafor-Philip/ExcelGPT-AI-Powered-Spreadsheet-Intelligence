import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react'
import { Github, Loader2 } from 'lucide-react'
import './index.css'
import UploadZone from './components/UploadZone'
import DataPreview from './components/DataPreview'
import InstructionInput from './components/InstructionInput'
import ProgressIndicator from './components/ProgressIndicator'
import { downloadFile, refineReport } from './services/api'

// Lazy-load the heavier post-analysis surfaces so the initial bundle stays lean.
const PreviewPanel = lazy(() => import('./components/PreviewPanel'))
const RefinementInput = lazy(() => import('./components/RefinementInput'))
const DownloadModal = lazy(() => import('./components/DownloadModal'))

const REPO_URL = 'https://github.com/Ogbunugafor-Philip/ExcelGPT-AI-Powered-Spreadsheet-Intelligence'

// Turn an action plan into a short assistant-style summary for the chat history.
const OP_LABELS = {
  rank: 'ranking', group_sum: 'totals', group_avg: 'averages', filter: 'filtering',
  growth_rate: 'growth rates', variance: 'variance vs target', correlation: 'correlation',
  outlier: 'outlier detection', distribution: 'distribution', forecast: 'forecast',
  cluster: 'clustering', score: 'scoring', chart: 'charts',
}

const summariseActionPlan = (plan) => {
  if (!plan) return 'Updated the report.'
  const ops = plan.operations || []
  const labels = [...new Set(ops.map((op) => OP_LABELS[op.operation_type] || op.operation_type))]
  const what = labels.length ? labels.join(' + ') : (plan.intent_type || 'report').replace(/_/g, ' ')
  return `Analysed: ${what} across ${ops.length} operation${ops.length === 1 ? '' : 's'}`
}

const Spinner = () => (
  <div className="flex items-center justify-center py-16 text-text-secondary">
    <Loader2 className="h-6 w-6 animate-spin text-blue-electric" />
  </div>
)

export default function App() {
  const [sessionId, setSessionId] = useState('')
  const [preview, setPreview] = useState(null)
  const [intelligenceBrief, setIntelligenceBrief] = useState(null)
  const [currentView, setCurrentView] = useState('upload')
  const [reportPreview, setReportPreview] = useState(null)
  const [downloadToken, setDownloadToken] = useState(null)
  const [version, setVersion] = useState(0)
  const [refinementHistory, setRefinementHistory] = useState([])
  const [refinementCount, setRefinementCount] = useState(0)
  const [isRefining, setIsRefining] = useState(false)
  // Phase 8 — progress + download modal + header shadow.
  const [analysing, setAnalysing] = useState(false)
  const [progressStep, setProgressStep] = useState(1)
  const [downloadModalOpen, setDownloadModalOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const stepTimers = useRef([])

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Drive the simulated step sequence while a single /analyse request is in flight.
  useEffect(() => {
    stepTimers.current.forEach(clearTimeout)
    stepTimers.current = []
    if (analysing) {
      stepTimers.current.push(setTimeout(() => setProgressStep(2), 1400))
      stepTimers.current.push(setTimeout(() => setProgressStep(3), 2800))
    }
    return () => stepTimers.current.forEach(clearTimeout)
  }, [analysing])

  const dataStats = useMemo(() => ({
    rowCount: preview?.sheets?.reduce((sum, s) => sum + (s?.row_count || 0), 0) || 0,
    sheetCount: preview?.sheets?.length || 0,
  }), [preview])

  const reportSheetCount = useMemo(() => {
    if (!reportPreview) return 0
    let n = 1 // Executive Summary is always written
    if (reportPreview.sheets?.some((s) => s.sheet_name === 'data' && s.columns?.length)) n += 1
    if (((reportPreview.metrics?.length || 0) + (reportPreview.rankings?.length || 0) + (reportPreview.growth_table?.length || 0)) > 0) n += 1
    if (reportPreview.charts?.length) n += 1
    if (reportPreview.forecast && (reportPreview.forecast.historical?.length || reportPreview.forecast.projected?.length)) n += 1
    return n
  }, [reportPreview])

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

  const handleAnalyzeStart = () => {
    setProgressStep(1)
    setAnalysing(true)
  }

  // Called when /analyse returns a real (non-clarification) result.
  const handleAnalyseResult = (data, instruction) => {
    setProgressStep(4)
    setTimeout(() => {
      setReportPreview(data.preview)
      setDownloadToken(data.download_token)
      setVersion(data.version)
      setRefinementHistory([
        { role: 'user', content: instruction },
        { role: 'assistant', content: summariseActionPlan(data.action_plan) },
      ])
      setRefinementCount(0)
      setCurrentView('preview')
      setAnalysing(false)
    }, 700)
  }

  // Called in InstructionInput's finally; stop progress if no report was produced.
  const handleAnalyzeEnd = (success) => {
    if (!success) setAnalysing(false)
  }

  const handleRefine = async (feedback) => {
    const priorHistory = refinementHistory
    setRefinementHistory((prev) => [...prev, { role: 'user', content: feedback }])
    setIsRefining(true)
    try {
      const data = await refineReport({ session_id: sessionId, feedback, history: priorHistory, current_version: version })
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

  const handleConfirmedDownload = () => downloadFile(downloadToken)

  const showReport = reportPreview && currentView === 'preview'

  return (
    <div className="min-h-screen bg-navy text-text-primary">
      {/* Fixed header */}
      <header
        className={`fixed inset-x-0 top-0 z-40 h-16 border-b border-border-subtle transition-shadow ${scrolled ? 'shadow-card' : ''}`}
        style={{ background: 'rgba(10,15,30,0.8)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' }}
      >
        <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between px-6 lg:px-12">
          <div className="flex items-baseline gap-3">
            <span className="font-display text-xl font-extrabold">
              <span className="text-white">Excel</span>
              <span className="gradient-text">GPT</span>
            </span>
            <span className="hidden text-small text-text-muted sm:inline">AI-Powered Spreadsheet Intelligence</span>
          </div>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-border-subtle px-3 py-1.5 text-small text-text-secondary transition hover:border-white/20 hover:text-text-primary"
          >
            <Github className="h-4 w-4" />
            <span className="hidden sm:inline">Star on GitHub</span>
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-[1280px] px-6 pb-16 pt-16 lg:px-12">
        {currentView === 'upload' ? (
          <section className="flex flex-col items-center py-12 text-center sm:py-16">
            <h1 className="font-display text-[32px] font-extrabold leading-tight sm:text-[48px]">
              <span className="gradient-text">Transform any spreadsheet into insights</span>
            </h1>
            <p className="mt-4 max-w-2xl text-body text-text-secondary">
              Upload your Excel file, describe what you need, and receive a professionally formatted report in seconds.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              {['🇳🇬 Built for Nigeria', '⚡ Powered by Cerebras', '📊 World-class Excel output'].map((pill) => (
                <span key={pill} className="glass rounded-full px-4 py-2 text-small text-text-secondary">{pill}</span>
              ))}
            </div>
            <div className="mt-10 w-full">
              <UploadZone onUploadComplete={handleUploadComplete} />
            </div>
          </section>
        ) : null}

        {currentView !== 'upload' ? (
          <div className="flex flex-col gap-8 py-8">
            {showReport ? (
              <Suspense fallback={<Spinner />}>
                <PreviewPanel
                  preview={reportPreview}
                  downloadToken={downloadToken}
                  version={version}
                  onDownload={() => setDownloadModalOpen(true)}
                />
                <RefinementInput
                  history={refinementHistory}
                  version={version}
                  refinementCount={refinementCount}
                  isRefining={isRefining}
                  onRefine={handleRefine}
                  onStartFresh={handleStartFresh}
                />
              </Suspense>
            ) : (
              <>
                {analysing ? (
                  <ProgressIndicator currentStep={progressStep} rowCount={dataStats.rowCount} sheetCount={dataStats.sheetCount} />
                ) : null}
                <div className={analysing ? 'hidden' : 'flex flex-col gap-8'}>
                  <DataPreview preview={preview} intelligenceBrief={intelligenceBrief} />
                  <InstructionInput
                    sessionId={sessionId}
                    intelligenceBrief={intelligenceBrief}
                    onAnalyzeStart={handleAnalyzeStart}
                    onAnalyse={handleAnalyseResult}
                    onAnalyzeEnd={handleAnalyzeEnd}
                  />
                </div>
              </>
            )}
          </div>
        ) : null}
      </main>

      <footer className="border-t border-border-subtle px-6 py-6 text-center text-small text-text-secondary lg:px-12">
        <p>© ExcelGPT • AI-Powered Spreadsheet Intelligence</p>
      </footer>

      {downloadModalOpen ? (
        <Suspense fallback={null}>
          <DownloadModal
            open={downloadModalOpen}
            onClose={() => setDownloadModalOpen(false)}
            onDownload={handleConfirmedDownload}
            sheetCount={reportSheetCount}
            version={version}
          />
        </Suspense>
      ) : null}
    </div>
  )
}
