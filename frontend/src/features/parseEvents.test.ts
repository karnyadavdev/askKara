import { describe, expect, it } from 'vitest'
import { parseEvents } from '../features/parseEvents'

describe('parseEvents', () => {
  it('parses complete lines and keeps the remainder', () => {
    const buffer = `${JSON.stringify({ type: 'stage', message: 'Searching' })}\n${JSON.stringify({ type: 'sources', sources: [] })}\n{"type":"do`
    const { events, rest } = parseEvents(buffer)

    expect(events).toEqual([
      { type: 'stage', message: 'Searching' },
      { type: 'sources', sources: [] },
    ])
    expect(rest).toBe('{"type":"do')
  })

  it('skips blank lines and malformed json', () => {
    const buffer = `\n${JSON.stringify({ type: 'done', answer: 'ok' })}\nnot-json\n`
    const { events } = parseEvents(buffer)

    expect(events).toEqual([{ type: 'done', answer: 'ok' }])
  })

  it('returns nothing for an empty buffer', () => {
    expect(parseEvents('')).toEqual({ events: [], rest: '' })
  })
})
