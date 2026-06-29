import { useEffect, useRef } from 'react'
import { Download, FileSpreadsheet, RefreshCw } from 'lucide-react'
import ChatExchange from './ChatExchange'
import ThinkingIndicator from './ThinkingIndicator'
import ChatInputBar from './ChatInputBar'

export default function ChatView({
  file,
  chatHistory,
  isThinking,
  inputValue,
  onInputChange,
  onSubmit,
  onChangeFile,
  onDownloadOne,
  onDownloadAll,
}) {
  const scrollRef = useRef(null)
  const bottomRef = useRef(null)

  // Auto-scroll to the newest exchange / thinking indicator.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chatHistory.length, isThinking])

  const answeredTokens = chatHistory.filter((c) => c.downloadToken).map((c) => c.downloadToken)
  const canDownloadAll = answeredTokens.length >= 2

  const handleChangeFile = () => {
    if (window.confirm('This will clear your chat history. Continue?')) onChangeFile?.()
  }

  const scrollToExchange = (id) => {
    document.getElementById(`exchange-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="flex h-screen overflow-hidden bg-base text-text-primary">
      {/* LEFT PANEL */}
      <aside className="hidden w-[300px] shrink-0 flex-col border-r border-border bg-card md:flex">
        <div className="border-b border-border px-5 py-4">
          <span className="font-display text-lg font-extrabold">
            <span className="text-text-primary">Excel</span>
            <span className="text-coral">GPT</span>
          </span>
        </div>

        {/* File info */}
        <div className="border-b border-border px-5 py-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-coral/15 text-coral">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="truncate font-semibold text-text-primary" title={file?.name}>{file?.name}</p>
              <p className="mt-0.5 text-micro text-text-muted">
                {(file?.rowCount || 0).toLocaleString()} rows · {file?.sheetCount || 0} sheet
                {file?.sheetCount === 1 ? '' : 's'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleChangeFile}
            className="mt-3 inline-flex items-center gap-1.5 text-small font-semibold text-coral transition hover:text-coral-light"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Change File
          </button>
        </div>

        {/* Question history */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {chatHistory.length ? (
            <p className="mb-3 text-micro uppercase tracking-wider text-text-muted">Your questions</p>
          ) : null}
          <ul className="space-y-2">
            {chatHistory.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => scrollToExchange(item.id)}
                  className="w-full truncate rounded-lg border-l-2 border-l-coral bg-base px-3 py-2 text-left text-small text-text-primary transition hover:bg-hover"
                  title={item.question}
                >
                  {item.question}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Download All */}
        {canDownloadAll ? (
          <div className="border-t border-border p-4">
            <button
              type="button"
              onClick={() => onDownloadAll?.(answeredTokens)}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-coral px-4 py-2.5 text-small font-semibold text-white transition hover:bg-coral-dark hover:shadow-glow-coral"
            >
              <Download className="h-4 w-4" />
              Download All ({answeredTokens.length} insights)
            </button>
          </div>
        ) : null}
      </aside>

      {/* RIGHT PANEL */}
      <main className="flex min-w-0 flex-1 flex-col">
        {/* Mobile brand + change-file row (left panel is hidden on small screens) */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3 md:hidden">
          <span className="font-display text-base font-extrabold">
            <span className="text-text-primary">Excel</span>
            <span className="text-coral">GPT</span>
          </span>
          <button type="button" onClick={handleChangeFile} className="inline-flex items-center gap-1.5 text-small font-semibold text-coral">
            <RefreshCw className="h-3.5 w-3.5" /> Change
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
          <div className="mx-auto max-w-3xl space-y-8">
            {chatHistory.map((item) => (
              <ChatExchange key={item.id} item={item} onDownload={onDownloadOne} />
            ))}
            {isThinking ? <ThinkingIndicator /> : null}
            <div ref={bottomRef} />
          </div>
        </div>

        <ChatInputBar value={inputValue} onChange={onInputChange} onSubmit={onSubmit} disabled={isThinking} />
      </main>
    </div>
  )
}
