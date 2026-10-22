import { useEffect, useRef } from 'react'
import { renderAnswerMarkdown } from './markdown'

type Props = {
  text: string
}

export default function TypeAnswer({ text }: Props) {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = hostRef.current
    if (host) host.innerHTML = ''

    const perChar = Math.max(2, Math.min(12, Math.round(4000 / Math.max(1, text.length))))

    const source = document.createElement('div')
    source.innerHTML = renderAnswerMarkdown(text)
    const paragraphs = Array.from(source.querySelectorAll('p'))

    let paragraphIndex = 0
    let cancelled = false
    let timer: number | undefined

    function nextParagraph() {
      if (cancelled || paragraphIndex >= paragraphs.length) return
      const full = paragraphs[paragraphIndex].innerHTML
      const p = document.createElement('p')
      const cursor = document.createElement('span')
      cursor.className = 'answer-typing-cursor'
      host?.appendChild(p)
      let charIndex = 0

      function nextChar() {
        if (cancelled) return
        if (charIndex >= full.length) {
          p.innerHTML = full
          paragraphIndex++
          timer = window.setTimeout(nextParagraph, 80)
          return
        }
        if (full[charIndex] === '<') {
          charIndex++
          while (charIndex < full.length && full[charIndex] !== '>') charIndex++
          if (charIndex < full.length) charIndex++
        } else {
          charIndex++
        }
        p.innerHTML = full.substring(0, charIndex)
        p.appendChild(cursor)
        timer = window.setTimeout(nextChar, perChar)
      }

      nextChar()
    }

    nextParagraph()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [text])

  return <div className="answer-block" ref={hostRef} />
}
