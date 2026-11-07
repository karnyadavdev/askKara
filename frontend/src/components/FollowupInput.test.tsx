import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { FollowupInput } from '../App'

describe('FollowupInput', () => {
  it('keeps the dig deeper placeholder while an answer is running', () => {
    render(<FollowupInput busy onSubmit={() => true} />)

    expect(screen.getByPlaceholderText('Dig deeper...')).toBeInTheDocument()
  })

  it('sends on enter and clears the box', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn(() => true)
    render(<FollowupInput busy={false} onSubmit={onSubmit} />)

    await user.type(screen.getByPlaceholderText('Dig deeper...'), 'why{Enter}')

    expect(onSubmit).toHaveBeenCalledWith('why')
    expect(screen.getByPlaceholderText('Dig deeper...')).toHaveValue('')
  })

  it('keeps shift enter as a newline', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn(() => true)
    render(<FollowupInput busy={false} onSubmit={onSubmit} />)

    await user.type(screen.getByPlaceholderText('Dig deeper...'), 'line1{Shift>}{Enter}{/Shift}')

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByPlaceholderText('Dig deeper...')).toHaveValue('line1\n')
  })
})
