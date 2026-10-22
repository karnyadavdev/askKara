import { useEffect, useRef, useState } from 'react'
import SourceChips from './SourceChips'
import { renderAnswerMarkdown } from './markdown'
import StageLine from './StageLine'
import TypeAnswer from './TypeAnswer'
import type { Source } from '../features/historyApi'

export interface FeedItem {
  id: string
  question: string
  stage?: string
  answer?: string
  sources?: Source[]
  error?: string
  instant?: boolean
}

type Props = {
  item: FeedItem
  stage?: string
  liveText?: string
  steps?: string[]
}

export default function FeedBlock({ item, stage, liveText, steps }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), 100)
    return () => window.clearTimeout(timer)
  }, [])

  return (
    <div className={`feed-block${visible ? ' visible' : ''}`} id={item.id} ref={ref}>
      <div className="query-huge">{item.question}</div>
      {item.sources && item.sources.length > 0 ? <SourceChips sources={item.sources} /> : null}
      {item.error ? (
        <div className="answer-block">
          <p>{item.error}</p>
        </div>
      ) : item.answer !== undefined ? (
        item.instant ? (
          <div className="answer-block" dangerouslySetInnerHTML={{ __html: renderAnswerMarkdown(item.answer) }} />
        ) : (
          <TypeAnswer text={item.answer} />
        )
      ) : liveText ? (
        <>
          <div className="answer-block live-tokens" dangerouslySetInnerHTML={{ __html: renderAnswerMarkdown(liveText) }} />
          <span className="live-cursor" />
        </>
      ) : (
        <StageLine message={stage || item.stage || 'Researching...'} steps={steps} />
      )}
    </div>
  )
}
