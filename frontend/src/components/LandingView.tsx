import { useEffect, useRef, useState } from 'react'

type Props = {
  onAsk: (question: string) => boolean
}

export default function LandingView({ onAsk }: Props) {
  const [text, setText] = useState('')
  const [caret, setCaret] = useState(0)
  const [barReady, setBarReady] = useState(false)
  const areaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (window.matchMedia('(pointer: fine)').matches) areaRef.current?.focus()
  }, [])

  useEffect(() => {
    const id = setTimeout(() => setBarReady(true), 2400)
    return () => clearTimeout(id)
  }, [])

  function syncCaret(target: HTMLTextAreaElement) {
    setCaret(target.selectionStart ?? target.value.length)
  }

  function doSubmit() {
    const trimmed = text.trim()
    if (trimmed && onAsk(trimmed)) {
      setText('')
      setCaret(0)
    }
  }

  function submit(event: React.FormEvent) {
    event.preventDefault()
    doSubmit()
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      doSubmit()
    }
  }

  return (
    <section className="section-landing active">
      <div className="hero-wrapper">
        <h1 className="hero-prompt">
          <span>What do you</span>
          <br />
          <span className="italic">want to know?</span>
        </h1>

        <form className="input-massive-wrapper" onSubmit={submit}>
          <textarea
            ref={areaRef}
            rows={1}
            className="input-editor"
            autoComplete="off"
            spellCheck={false}
            placeholder="PRESS ENTER TO ASK"
            value={text}
            onChange={(event) => {
              setText(event.target.value)
              syncCaret(event.currentTarget)
            }}
            onSelect={(event) => syncCaret(event.currentTarget)}
            onClick={(event) => syncCaret(event.currentTarget)}
            onKeyUp={(event) => syncCaret(event.currentTarget)}
            onKeyDown={onKeyDown}
          />
          <div className="input-mirror" aria-hidden="true">
            <span className="mirror-text">{text}</span>
          </div>
          <div className={`input-caret-layer${barReady ? ' bar-ready' : ''}`} aria-hidden="true">
            <span className="mirror-text">{text.slice(0, caret)}</span>
            <span className="cursor-blink" />
          </div>
        </form>
        <div className="input-hint-block">
          <span className="input-hint">PRESS ENTER TO ASK</span>
        </div>
      </div>
    </section>
  )
}
