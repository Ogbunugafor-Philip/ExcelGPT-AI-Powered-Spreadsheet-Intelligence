import { useState } from 'react'
import './index.css'
import UploadZone from './components/UploadZone'
import DataPreview from './components/DataPreview'
import InstructionInput from './components/InstructionInput'

export default function App() {
  const [sessionId, setSessionId] = useState('')
  const [preview, setPreview] = useState(null)
  const [intelligenceBrief, setIntelligenceBrief] = useState(null)
  const [currentView, setCurrentView] = useState('upload')

  const handleUploadComplete = (nextSessionId, nextPreview, nextIntelligenceBrief) => {
    setSessionId(nextSessionId)
    setPreview(nextPreview)
    setIntelligenceBrief(nextIntelligenceBrief)
    setCurrentView('preview')
  }

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
        {currentView === 'preview' ? (
          <>
            <DataPreview preview={preview} intelligenceBrief={intelligenceBrief} />
            <InstructionInput sessionId={sessionId} intelligenceBrief={intelligenceBrief} />
          </>
        ) : null}
      </main>

      <footer className="border-t border-white/10 px-6 py-6 text-center text-sm text-text-secondary lg:px-8">
        <p>© ExcelGPT • Data Intelligence Layer</p>
      </footer>
    </div>
  )
}
