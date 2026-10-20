type Props = {
  message: string
}

export default function StageLine({ message }: Props) {
  const clean = String(message || 'Working').replace(/\.+\s*$/, '')
  return (
    <div className="answer-block">
      <p className="thinking-line">
        <span className="thinking-dots">{clean}</span>
      </p>
    </div>
  )
}
