import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AuthModal from '../components/AuthModal'
import { renderWithStore } from '../test/renderWithStore'

describe('AuthModal', () => {
  it('switches between login and register', async () => {
    const user = userEvent.setup()
    renderWithStore(<AuthModal onClose={() => {}} onAuth={() => {}} />)

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'New user?' }))
    expect(screen.getByRole('heading', { name: 'Create account' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Register' })).toBeInTheDocument()
  })

  it('closes on overlay click', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const { container } = renderWithStore(<AuthModal onClose={onClose} onAuth={() => {}} />)

    await user.click(container.firstChild as Element)
    expect(onClose).toHaveBeenCalled()
  })
})
