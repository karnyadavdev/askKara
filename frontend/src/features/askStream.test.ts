import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ask, abortAsk } from './askStream'
import { setToken } from './authSlice'
import { reset, toggleThinking } from './streamSlice'
import { store } from '../app/store'

const encoder = new TextEncoder()

function abortError() {
  const err = new Error('The operation was aborted')
  err.name = 'AbortError'
  return err
}

type Chunk = { value?: Uint8Array; done: boolean }

const chunk = (text: string): Chunk => ({ value: encoder.encode(text), done: false })

function mockStream(chunks: Chunk[]) {
  let index = 0
  let signal: AbortSignal | undefined
  vi.stubGlobal(
    'fetch',
    vi.fn((_input: unknown, init: RequestInit) => {
      signal = init.signal ?? undefined
      return {
        ok: true,
        status: 200,
        body: {
          getReader() {
            return {
              read(): Promise<Chunk> {
                if (index < chunks.length) return Promise.resolve(chunks[index++])
                return new Promise((_resolve, reject) => {
                  if (signal?.aborted) reject(abortError())
                  else signal?.addEventListener('abort', () => reject(abortError()), { once: true })
                })
              },
            }
          },
        },
      } as unknown as Response
    }) as unknown as typeof fetch,
  )
}

type MockedCall = { body: unknown }

type MockedResponse = {
  status?: number
  headers?: Record<string, string>
  chunks: Chunk[]
  failWith?: Error
}

function mockResponses(items: MockedResponse[]) {
  const calls: MockedCall[] = []
  let index = 0
  let signal: AbortSignal | undefined
  vi.stubGlobal(
    'fetch',
    vi.fn((_input: unknown, init: RequestInit) => {
      calls.push({ body: init.body })
      signal = init.signal ?? undefined
      const item = items[Math.min(index, items.length - 1)]
      index += 1
      const status = item.status ?? 200
      const ok = status >= 200 && status < 300
      let chunkIndex = 0
      return {
        ok,
        status,
        headers: { get: (name: string) => item.headers?.[name] ?? null },
        body: ok
          ? {
              getReader() {
                return {
                  read(): Promise<Chunk> {
                    if (chunkIndex < item.chunks.length) return Promise.resolve(item.chunks[chunkIndex++])
                    if (item.failWith) return Promise.reject(item.failWith)
                    return new Promise((_resolve, reject) => {
                      if (signal?.aborted) reject(abortError())
                      else signal?.addEventListener('abort', () => reject(abortError()), { once: true })
                    })
                  },
                }
              },
            }
          : null,
      } as unknown as Response
    }) as unknown as typeof fetch,
  )
  return calls
}

describe('ask stream', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    store.dispatch(reset())
  })

  it('reconnects once on a dropped stream then fails with stream_ended', async () => {
    const calls = mockResponses([
      {
        chunks: [
          chunk('{"type":"conversation","id":7}\n{"type":"stage","message":"Working..."}\n'),
          { done: true },
        ],
      },
      {
        chunks: [
          chunk('{"type":"conversation","id":7}\n{"type":"stage","message":"Working..."}\n'),
          { done: true },
        ],
      },
    ])

    await store.dispatch(ask('what is 2+2?'))

    expect(store.getState().stream.status).toBe('error')
    expect(store.getState().stream.error).toBe('stream_ended')
    expect(calls).toHaveLength(2)
  })

  it('reconnects once after a network error and completes', async () => {
    const calls = mockResponses([
      {
        chunks: [chunk('{"type":"conversation","id":5}\n{"type":"stage","message":"Researching..."}\n')],
        failWith: new TypeError('Failed to fetch'),
      },
      {
        chunks: [
          chunk('{"type":"conversation","id":5}\n{"type":"done","answer":"recovered","sources":[]}\n'),
          { done: true },
        ],
      },
    ])

    await store.dispatch(ask('q'))

    const state = store.getState().stream
    expect(state.status).toBe('done')
    expect(state.answer).toBe('recovered')
    expect(calls).toHaveLength(2)
  })

  it('reconnects once when the stream stalls', async () => {
    vi.useFakeTimers()
    try {
      const calls = mockResponses([
        { chunks: [chunk('{"type":"conversation","id":2}\n')] },
        { chunks: [chunk('{"type":"conversation","id":2}\n')] },
      ])

      const pending = store.dispatch(ask('q'))
      await vi.advanceTimersByTimeAsync(120_000)
      await vi.advanceTimersByTimeAsync(120_000)
      await pending

      expect(store.getState().stream.status).toBe('error')
      expect(store.getState().stream.error).toBe('stream_stalled')
      expect(calls).toHaveLength(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('completes normally when done arrives', async () => {
    mockStream([
      chunk('{"type":"conversation","id":9}\n{"type":"token","text":"hello "}\n{"type":"token","text":"world"}\n'),
      chunk('{"type":"done","answer":"hello world","sources":[]}\n'),
      { done: true },
    ])

    await store.dispatch(ask('q'))

    expect(store.getState().stream.status).toBe('done')
    expect(store.getState().stream.answer).toBe('hello world')
    expect(store.getState().stream.conversationId).toBe(9)
  })

  it('collects step narration into the history instead of wiping the answer', async () => {
    mockStream([
      chunk('{"type":"conversation","id":3}\n{"type":"stage","message":"Researching..."}\n'),
      chunk('{"type":"step","text":"need the page first"}\n{"type":"stage","message":"Fetching source page..."}\n'),
      chunk('{"type":"done","answer":"final","sources":[]}\n'),
      { done: true },
    ])

    await store.dispatch(ask('q'))

    const state = store.getState().stream
    expect(state.status).toBe('done')
    expect(state.answer).toBe('final')
    expect(state.steps).toEqual(['Researching...', 'need the page first'])
    expect(state.streamed).toBe(false)
  })

  it('abortAsk cancels silently without dispatching fail', async () => {
    mockStream([chunk('{"type":"conversation","id":1}\n')])

    const pending = store.dispatch(ask('q'))
    await new Promise((resolve) => setTimeout(resolve, 0))
    abortAsk()
    await pending

    expect(store.getState().stream.status).toBe('running')
    expect(store.getState().stream.error).toBe('')
    store.dispatch(reset())
  })

  it('sends the auth token in the stream request body', async () => {
    const calls = mockResponses([
      { chunks: [chunk('{"type":"done","answer":"ok","sources":[]}\n'), { done: true }] },
    ])
    store.dispatch(setToken('tok-123'))

    await store.dispatch(ask('q'))

    expect(JSON.parse(String(calls[0].body))).toMatchObject({ question: 'q', token: 'tok-123' })
    store.dispatch(setToken(''))
  })

  it('maps an app rate limit to rate_limited with the Retry-After seconds', async () => {
    const calls = mockResponses([{ status: 429, headers: { 'Retry-After': '47' }, chunks: [] }])

    await store.dispatch(ask('q'))

    expect(store.getState().stream.status).toBe('error')
    expect(store.getState().stream.error).toBe('rate_limited:47')
    expect(calls).toHaveLength(1)
  })

  it('retries once on a retryable error and reuses the same conversation', async () => {
    const calls = mockResponses([
      {
        chunks: [
          chunk('{"type":"conversation","id":7}\n{"type":"error","message":"provider_rate_limited","retryable":true}\n'),
          { done: true },
        ],
      },
      {
        chunks: [
          chunk('{"type":"conversation","id":7}\n{"type":"done","answer":"recovered","sources":[]}\n'),
          { done: true },
        ],
      },
    ])

    await store.dispatch(ask('q'))

    const state = store.getState().stream
    expect(state.status).toBe('done')
    expect(state.answer).toBe('recovered')
    expect(state.conversationId).toBe(7)
    expect(calls).toHaveLength(2)
    expect(JSON.parse(String(calls[1].body))).toMatchObject({ question: 'q', conversation_id: 7 })
  })

  it('fails with the provider code when both attempts hit a retryable error', async () => {
    const calls = mockResponses([
      {
        chunks: [
          chunk('{"type":"conversation","id":3}\n{"type":"error","message":"provider_rate_limited","retryable":true}\n'),
          { done: true },
        ],
      },
      {
        chunks: [
          chunk('{"type":"conversation","id":3}\n{"type":"error","message":"provider_rate_limited","retryable":true}\n'),
          { done: true },
        ],
      },
    ])

    await store.dispatch(ask('q'))

    expect(store.getState().stream.status).toBe('error')
    expect(store.getState().stream.error).toBe('provider_rate_limited')
    expect(calls).toHaveLength(2)
  })

  it('does not retry a non-retryable error', async () => {
    const calls = mockResponses([
      { chunks: [chunk('{"type":"error","message":"Internal research error","retryable":false}\n'), { done: true }] },
    ])

    await store.dispatch(ask('q'))

    expect(store.getState().stream.error).toBe('Internal research error')
    expect(calls).toHaveLength(1)
  })

  it('does not retry once answer tokens have streamed', async () => {
    const calls = mockResponses([
      {
        chunks: [
          chunk(
            '{"type":"conversation","id":4}\n{"type":"token","text":"partial "}\n{"type":"error","message":"provider_rate_limited","retryable":true}\n',
          ),
          { done: true },
        ],
      },
      { chunks: [chunk('{"type":"done","answer":"recovered","sources":[]}\n'), { done: true }] },
    ])

    await store.dispatch(ask('q'))

    expect(store.getState().stream.status).toBe('error')
    expect(store.getState().stream.error).toBe('provider_rate_limited')
    expect(store.getState().stream.answer).toBe('partial ')
    expect(calls).toHaveLength(1)
  })

  it('sends the selected thinking level in the request body', async () => {
    const calls = mockResponses([
      { chunks: [chunk('{"type":"done","answer":"ok","sources":[]}\n'), { done: true }] },
    ])
    store.dispatch(toggleThinking())

    await store.dispatch(ask('q'))

    expect(JSON.parse(String(calls[0].body))).toMatchObject({ question: 'q', thinking: 'high' })
    store.dispatch(toggleThinking())
  })
})
