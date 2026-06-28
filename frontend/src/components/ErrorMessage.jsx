import { AlertCircle, X } from 'lucide-react'
import { resolveError } from '../utils/errorMessages'

// Friendly, actionable error card. Slides in from the top, red-tinted, with an
// action button and a dismiss control.
export default function ErrorMessage({ errorKey = 'UNKNOWN', customMessage, onAction, onDismiss }) {
  const { title, message, action } = resolveError(errorKey, customMessage)

  return (
    <div
      role="alert"
      className="eg-anim-slide-down relative flex items-start gap-3 rounded-2xl border border-red-alert/40 bg-red-alert/10 p-4 sm:p-5"
    >
      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-alert/15 text-red-alert">
        <AlertCircle className="h-5 w-5" />
      </div>

      <div className="min-w-0 flex-1 pr-6">
        <p className="font-display font-bold text-white">{title}</p>
        {message ? <p className="mt-1 text-small text-text-secondary">{message}</p> : null}
        {action && onAction ? (
          <button
            type="button"
            onClick={onAction}
            className="mt-3 inline-flex items-center rounded-lg border border-red-alert/50 px-3 py-1.5 text-small font-semibold text-red-alert transition hover:bg-red-alert/15"
          >
            {action}
          </button>
        ) : null}
      </div>

      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="absolute right-3 top-3 text-text-muted transition hover:text-text-secondary"
        >
          <X className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  )
}
