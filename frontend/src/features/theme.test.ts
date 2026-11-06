import { beforeEach, describe, expect, it, vi } from 'vitest'
import { initTheme } from '../features/theme'

type Listener = (event: { matches: boolean }) => void

function mockScheme(matches: boolean) {
  const listeners: Listener[] = []
  const query = {
    matches,
    addEventListener: (_name: string, listener: Listener) => listeners.push(listener),
  }
  vi.stubGlobal('matchMedia', vi.fn(() => query))
  return {
    change(next: boolean) {
      query.matches = next
      listeners.forEach((listener) => listener({ matches: next }))
    },
  }
}

describe('initTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    vi.unstubAllGlobals()
  })

  it('follows the browser scheme when nothing is stored', () => {
    mockScheme(true)
    initTheme()
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')

    document.documentElement.removeAttribute('data-theme')
    mockScheme(false)
    initTheme()
    expect(document.documentElement.getAttribute('data-theme')).toBeNull()
  })

  it('tracks live browser changes until a manual choice is stored', () => {
    const scheme = mockScheme(true)
    initTheme()

    scheme.change(false)
    expect(document.documentElement.getAttribute('data-theme')).toBeNull()

    scheme.change(true)
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('prefers a stored manual choice over the browser', () => {
    mockScheme(true)
    localStorage.setItem('kara_theme', 'dark')
    initTheme()
    expect(document.documentElement.getAttribute('data-theme')).toBeNull()
  })
})
