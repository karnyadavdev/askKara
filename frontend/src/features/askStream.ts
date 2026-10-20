import { answer, fail, setConversation, start, stage, streamReset, token } from './streamSlice'
import { parseEvents } from './parseEvents'
import type { StreamEvent } from './parseEvents'
import type { Source } from './historyApi'
import type { AppDispatch, RootState } from '../app/store'

const STALL_MS = 120_000

let activeController: AbortController | null = null

export function abortAsk() {
  if (activeController) {
    activeController.abort()
    activeController = null
  }
}

function isAbort(err: unknown): boolean {
  return err instanceof Error && err.name === 'AbortError'
}

export function ask(question: string, conversationId: number | null = null, maxSources = 8) {
  return async (dispatch: AppDispatch, getState: () => RootState) => {
    abortAsk()
    const ctrl = new AbortController()
    activeController = ctrl

    dispatch(start(question))

    const authToken = getState().auth.token
    const deep = getState().stream.deep
    let sawTerminal = false

    let stallTimer = 0
    const onStall = () => {
      dispatch(fail('stream_stalled'))
      ctrl.abort()
    }
    const bumpStall = () => {
      clearTimeout(stallTimer)
      stallTimer = setTimeout(onStall, STALL_MS)
    }
    bumpStall()

    const handleEvents = (events: StreamEvent[]) => {
      for (const event of events) {
        if (event.type === 'conversation') {
          if (typeof event.id === 'number') dispatch(setConversation(event.id))
        } else if (event.type === 'stage') {
          dispatch(stage(event.message ?? 'Working...'))
        } else if (event.type === 'token') {
          dispatch(token(event.text ?? ''))
        } else if (event.type === 'stream_reset') {
          dispatch(streamReset())
        } else if (event.type === 'done') {
          sawTerminal = true
          dispatch(answer({ answer: event.answer ?? '', sources: (event.sources ?? []) as Source[] }))
        } else if (event.type === 'error') {
          sawTerminal = true
          throw new Error(event.message ?? 'backend_error')
        }
      }
    }

    try {
      const resp = await fetch('/api/ask/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({
          question,
          max_sources: deep ? 50 : maxSources,
          deep,
          ...(conversationId ? { conversation_id: conversationId } : {}),
        }),
        signal: ctrl.signal,
      })

      if (!resp.ok || !resp.body) {
        if (resp.status === 401) throw new Error('auth_required')
        if (resp.status === 422) throw new Error('question_invalid')
        if (resp.status === 429) throw new Error('rate_limited')
        throw new Error(`backend_status_${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        bumpStall()
        buffer += decoder.decode(value, { stream: true })
        const parsed = parseEvents(buffer)
        buffer = parsed.rest
        handleEvents(parsed.events)
      }

      buffer += decoder.decode()
      const final = parseEvents(buffer)
      if (final.rest.trim()) {
        try {
          final.events.push(JSON.parse(final.rest) as StreamEvent)
        } catch {
          // truncated trailing event: dropped, caught by the terminal check below
        }
      }
      handleEvents(final.events)

      if (!sawTerminal) dispatch(fail('stream_ended'))
    } catch (err) {
      if (!isAbort(err)) {
        dispatch(fail(err instanceof Error ? err.message : String(err)))
      }
    } finally {
      clearTimeout(stallTimer)
      if (activeController === ctrl) activeController = null
    }
  }
}
