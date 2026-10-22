import { useState } from 'react'

type Props = {
  message: string
  steps?: string[]
}

export default function StageLine({ message, steps }: Props) {
  const clean = String(message || 'Working').replace(/\.+\s*$/, '')
  const history = steps ?? []
  const [open, setOpen] = useState(false)
  const hasHistory = history.length > 0

  return (
    <div className="answer-block">
      <p className="thinking-line">
        {hasHistory ? (
          <button
            type="button"
            className="step-toggle"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            <span className="step-toggle-mark">{open ? 'v' : '>'}</span>
            <span className="thinking-dots">{clean}</span>
            {open ? null : <span className="step-toggle-count">{history.length} earlier</span>}
          </button>
        ) : (
          <span className="thinking-dots">{clean}</span>
        )}
      </p>
      {open && hasHistory ? (
        <div className="step-history">
          {[...history].reverse().map((text, index) => (
            <p className="step-history-item" key={`${index}-${text.slice(0, 32)}`}>
              {text}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  )
}
