import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import ThemeToggle from '../components/ThemeToggle'

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('switches to light theme and remembers it', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    await user.click(screen.getByRole('button'))
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(localStorage.getItem('kara_theme')).toBe('light')

    await user.click(screen.getByRole('button'))
    expect(document.documentElement.getAttribute('data-theme')).toBeNull()
    expect(localStorage.getItem('kara_theme')).toBe('dark')
  })
})
