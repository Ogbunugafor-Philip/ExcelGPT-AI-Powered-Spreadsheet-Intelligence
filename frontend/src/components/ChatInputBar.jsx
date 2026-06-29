import { useRef } from 'react'
import { ArrowUp } from 'lucide-react'

// Fixed bottom composer for the chat. Single-line textarea that grows to 3 lines,
// coral send button, Ctrl/Cmd+Enter to submit.
export default function ChatInputBar({ value, onChange, onSubmit, disabled }) {
  const ref = useRef(null)

  const autoGrow = (el) => {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px` // max ~5 lines
  }

  const submit = () => {
    const trimmed = (value || '').trim()
    if (!trimmed || disabled) return
    onSubmit?.(trimmed)
    if (ref.current) ref.current.style.height = 'auto'
  }

  const handleKeyDown = (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      submit()
    }
  }

  const canSend = Boolean((value || '').trim()) && !disabled

  return (
    <div className="sticky bottom-0 z-10 border-t border-border bg-base px-6 pb-6 pt-4 sm:px-10">
      <div className="mx-auto max-w-[900px]">
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 transition-all duration-200 focus-within:border-coral focus-within:shadow-coral">
          <textarea
            ref={ref}
            value={value}
            rows={1}
            onChange={(event) => {
              onChange?.(event.target.value)
              autoGrow(event.target)
            }}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your data..."
            className="max-h-[120px] min-h-[24px] flex-1 resize-none border-none bg-transparent text-[15px] leading-6 text-text-1 placeholder:text-text-3 focus:outline-none focus:ring-0"
          />
          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            aria-label="Send question"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-coral text-white transition hover:bg-coral-600 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 text-center text-[11px] text-text-3">ExcelGPT · Powered by Cerebras</p>
      </div>
    </div>
  )
}
