import { answer, fail, setConversation, start, stage, step, token } from './streamSlice'
import { parseEvents } from './parseEvents'
import type { StreamEvent } from './parseEvents'
import type { Source } from './historyApi'
import type { AppDispatch, RootState } from '../app/store'

const STALL_MS = 120_000
const MAX_PROVIDER_RETRIES = 1
const MAX_RECONNECTS = 1
const MAX_ATTEMPTS = 1 + MAX_PROVIDER_RETRIES + MAX_RECONNECTS

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

class StreamError extends Error {
  retryable: boolean

  constructor(message: string, retryable: boolean) {
    super(message)
    this.retryable = retryable
  }
}

export function ask(question: string, conversationId: number | null = null, maxSources = 8) {
  return async (dispatch: AppDispatch, getState: () => RootState) => {
    abortAsk()

    const authToken = getState().auth.token
    const deep = getState().stream.deep
    let ctrl = new AbortController()
    let targetConversation = conversationId
    let providerRetries = 0
    let reconnects = 0

    try {
      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
        ctrl = new AbortController()
        activeController = ctrl
        dispatch(start(question))
        let sawTerminal = false
        let stalled = false

        let stallTimer = 0
        const onStall = () => {
          stalled = true
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
              if (typeof event.id === 'number') {
                targetConversation = event.id
                dispatch(setConversation(event.id))
              }
            } else if (event.type === 'stage') {
              dispatch(stage(event.message ?? 'Working...'))
            } else if (event.type === 'token') {
              dispatch(token(event.text ?? ''))
            } else if (event.type === 'step') {
              dispatch(step(event.text ?? ''))
            } else if (event.type === 'done') {
              sawTerminal = true
              dispatch(answer({ answer: event.answer ?? '', sources: (event.sources ?? []) as Source[] }))
            } else if (event.type === 'error') {
              sawTerminal = true
              throw new StreamError(event.message ?? 'backend_error', event.retryable === true)
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
              ...(targetConversation ? { conversation_id: targetConversation } : {}),
              ...(authToken ? { token: authToken } : {}),
            }),
            signal: ctrl.signal,
          })

          if (!resp.ok || !resp.body) {
            if (resp.status === 401) throw new StreamError('auth_required', false)
            if (resp.status === 422) throw new StreamError('question_invalid', false)
            if (resp.status === 429) {
              const retryAfter = Number(resp.headers.get('Retry-After'))
              const seconds = Number.isFinite(retryAfter) && retryAfter > 0 ? Math.ceil(retryAfter) : 0
              throw new StreamError(seconds > 0 ? `rate_limited:${seconds}` : 'rate_limited', false)
            }
            throw new StreamError(`backend_status_${resp.status}`, false)
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

          if (!sawTerminal) throw new StreamError('stream_ended', false)
        } catch (err) {
          if (isAbort(err)) {
            if (!stalled) return
            if (reconnects < MAX_RECONNECTS) {
              reconnects += 1
              continue
            }
            dispatch(fail('stream_stalled'))
            return
          }

          const streamErr = err instanceof StreamError ? err : null
          const connectionDeath = streamErr?.message === 'stream_ended' || err instanceof TypeError
          if (connectionDeath) {
            if (reconnects < MAX_RECONNECTS) {
              reconnects += 1
              continue
            }
            dispatch(fail('stream_ended'))
            return
          }

          const streamedSomething = getState().stream.answer !== '' || getState().stream.steps.length > 0
          if (streamErr?.retryable && providerRetries < MAX_PROVIDER_RETRIES && !streamedSomething) {
            providerRetries += 1
            continue
          }
          dispatch(fail(err instanceof Error ? err.message : String(err)))
          return
        } finally {
          clearTimeout(stallTimer)
        }

        return
      }
    } finally {
      if (activeController === ctrl) activeController = null
    }
  }
}
