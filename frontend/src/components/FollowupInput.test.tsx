import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { FollowupInput } from '../App'

describe('FollowupInput', () => {
  it('keeps the dig deeper placeholder while an answer is running', () => {
    render(<FollowupInput busy onSubmit={() => true} />)

    expect(screen.getByPlaceholderText('Dig deeper...')).toBeInTheDocument()
  })
})
