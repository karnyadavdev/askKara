import type { Source } from '../features/historyApi'

type Props = {
  sources: Source[]
}

export default function SourceChips({ sources }: Props) {
  if (!sources.length) return null

  return (
    <div className="sources-strip">
      <div className="strip-label">REF //</div>
      <div className="strip-items">
        {sources.map((source, index) => {
          const safeHref = /^https?:\/\//i.test(source.url) ? source.url : undefined
          let host = 'source'
          try {
            host = new URL(source.url).hostname.replace(/^www\./, '')
          } catch {
            host = source.url
          }
          return (
            <a
              key={`${source.url}-${index}`}
              className="source-item"
              href={safeHref}
              target={safeHref ? '_blank' : undefined}
              rel="noreferrer"
            >
              <span className="source-index">{index + 1}</span>
              <span>{host}</span>
            </a>
          )
        })}
      </div>
    </div>
  )
}
