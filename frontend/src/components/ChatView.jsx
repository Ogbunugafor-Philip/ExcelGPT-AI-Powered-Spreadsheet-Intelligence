import { useEffect, useRef } from 'react'
import { Download, FileSpreadsheet } from 'lucide-react'
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
    <div className="flex h-screen overflow-hidden bg-base text-text-1">
      {/* LEFT PANEL — color separation only, no hard border. */}
      <aside className="hidden w-[280px] shrink-0 flex-col bg-sidebar md:flex">
        <div className="px-5 pb-2 pt-5">
          <span className="font-display text-lg font-extrabold">
            <span className="text-text-1">Excel</span>
            <span className="text-coral">GPT</span>
          </span>
        </div>

        {/* File card — no border, no chrome. */}
        <div className="px-4 pt-4">
          <div className="flex items-start gap-3">
            <FileSpreadsheet className="mt-0.5 h-5 w-5 shrink-0 text-coral" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-semibold text-text-1" title={file?.name}>
                {file?.name}
              </p>
              <p className="mt-0.5 text-[11px] text-text-3">
                {(file?.rowCount || 0).toLocaleString()} rows · {file?.sheetCount || 0} sheet
                {file?.sheetCount === 1 ? '' : 's'}
              </p>
              <button
                type="button"
                onClick={handleChangeFile}
                className="mt-1.5 text-[12px] font-medium text-coral transition hover:text-coral-light"
              >
                Change file
              </button>
            </div>
          </div>
        </div>

        {/* Question history */}
        <div className="mt-2 flex-1 overflow-y-auto pb-4">
          {chatHistory.length ? (
            <p className="mb-1 mt-6 px-4 text-[10px] font-semibold uppercase tracking-[0.08em] text-text-3">
              History
            </p>
          ) : null}
          <ul>
            {chatHistory.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => scrollToExchange(item.id)}
                  className="group flex w-full items-center border-l-2 border-l-transparent px-4 py-2 text-left text-[13px] text-text-2 transition hover:border-l-coral hover:bg-card"
                  title={item.question}
                >
                  <span className="truncate">{item.question}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {/* Download All */}
        {canDownloadAll ? (
          <div className="p-4">
            <button
              type="button"
              onClick={() => onDownloadAll?.(answeredTokens)}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-coral text-[13px] font-semibold text-white transition hover:bg-coral-600 hover:shadow-glow-coral"
            >
              <Download className="h-4 w-4" />
              Download All ({answeredTokens.length})
            </button>
          </div>
        ) : null}
      </aside>

      {/* RIGHT PANEL */}
      <main className="flex min-w-0 flex-1 flex-col bg-base">
        {/* Mobile brand + change-file row (left panel is hidden on small screens) */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3 md:hidden">
          <span className="font-display text-base font-extrabold">
            <span className="text-text-1">Excel</span>
            <span className="text-coral">GPT</span>
          </span>
          <button
            type="button"
            onClick={handleChangeFile}
            className="text-[13px] font-medium text-coral"
          >
            Change file
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-8 sm:px-10">
          <div className="mx-auto max-w-[900px]">
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
