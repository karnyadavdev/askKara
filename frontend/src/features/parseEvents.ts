export interface StreamEvent {
  type: 'stage' | 'token' | 'step' | 'sources' | 'done' | 'error' | 'conversation'
  message?: string
  text?: string
  answer?: string
  sources?: unknown
  id?: number
  retryable?: boolean
}

export function parseEvents(buffer: string): { events: StreamEvent[]; rest: string } {
  const lines = buffer.split('\n')
  const rest = lines.pop() ?? ''
  const events: StreamEvent[] = []

  for (const line of lines) {
    if (!line.trim()) continue
    try {
      events.push(JSON.parse(line) as StreamEvent)
    } catch {
    }
  }

  return { events, rest }
}
