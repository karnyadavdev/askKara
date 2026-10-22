import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ask, abortAsk } from './askStream'
import { reset } from './streamSlice'
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

describe('ask stream', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    store.dispatch(reset())
  })

  it('fails with stream_ended when the body ends without a terminal event', async () => {
    mockStream([
      chunk('{"type":"conversation","id":7}\n{"type":"stage","message":"Working..."}\n'),
      { done: true },
    ])

    await store.dispatch(ask('what is 2+2?'))

    expect(store.getState().stream.status).toBe('error')
    expect(store.getState().stream.error).toBe('stream_ended')
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
})
