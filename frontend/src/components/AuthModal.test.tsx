import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AuthModal from '../components/AuthModal'
import { registerErrorMessage } from '../features/authErrors'
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

describe('registerErrorMessage', () => {
  it('uses a string detail from the server', () => {
    expect(registerErrorMessage({ data: { detail: 'Email already registered' } })).toBe('Email already registered')
  })

  it('uses the first validation message', () => {
    expect(registerErrorMessage({ data: { detail: [{ msg: 'String should have at least 8 characters' }] } })).toBe(
      'String should have at least 8 characters',
    )
  })

  it('falls back to the generic message', () => {
    expect(registerErrorMessage(new Error('network'))).toBe('Could not register that email')
  })
})

describe('AuthModal password hint', () => {
  it('shows the password length hint only in register mode', async () => {
    const user = userEvent.setup()
    renderWithStore(<AuthModal onClose={() => {}} onAuth={() => {}} />)

    expect(screen.queryByText('Use at least 8 characters.')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'New user?' }))
    expect(screen.getByText('Use at least 8 characters.')).toBeInTheDocument()
  })
})
