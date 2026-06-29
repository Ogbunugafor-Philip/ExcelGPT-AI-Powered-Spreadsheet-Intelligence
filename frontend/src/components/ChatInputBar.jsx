import { useRef } from 'react'
import { Send } from 'lucide-react'

// Fixed bottom composer for the chat. Single-line textarea that grows to 3 lines,
// coral send button, Ctrl/Cmd+Enter to submit.
export default function ChatInputBar({ value, onChange, onSubmit, disabled }) {
  const ref = useRef(null)

  const autoGrow = (el) => {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 96)}px` // ~3 lines max
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
    <div
      className="sticky bottom-0 z-10 border-t border-border px-4 py-3 sm:px-6"
      style={{ background: 'rgba(15,15,15,0.85)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}
    >
      <div className="mx-auto flex max-w-3xl items-end gap-3">
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
          className="max-h-24 flex-1 resize-none rounded-2xl border border-transparent bg-input px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/30"
        />
        <button
          type="button"
          onClick={submit}
          disabled={!canSend}
          aria-label="Send question"
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition ${
            canSend ? 'bg-coral text-white hover:bg-coral-dark hover:shadow-glow-coral' : 'cursor-not-allowed bg-hover text-text-muted'
          }`}
        >
          <Send className="h-5 w-5" />
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-micro text-text-muted">
        ExcelGPT · Powered by Cerebras · Numbers computed by Python
      </p>
    </div>
  )
}
