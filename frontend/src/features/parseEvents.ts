export interface StreamEvent {
  type: 'stage' | 'token' | 'step' | 'sources' | 'done' | 'error' | 'conversation'
  message?: string
  text?: string
  answer?: string
  sources?: unknown
  id?: number
}

// NDJSON lines can split across network chunks, so a chunk only yields the
// complete lines it carries and the remainder waits for the next chunk.
export function parseEvents(buffer: string): { events: StreamEvent[]; rest: string } {
  const lines = buffer.split('\n')
  const rest = lines.pop() ?? ''
  const events: StreamEvent[] = []

  for (const line of lines) {
    if (!line.trim()) continue
    try {
      events.push(JSON.parse(line) as StreamEvent)
    } catch {
      // a malformed line should never kill the stream
    }
  }

  return { events, rest }
}
