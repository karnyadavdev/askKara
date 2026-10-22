import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import StageLine from '../components/StageLine'

describe('StageLine', () => {
  it('shows only the label when there is no history', () => {
    render(<StageLine message="Researching..." steps={[]} />)

    expect(screen.getByText('Researching')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('starts collapsed and reveals the history on click', () => {
    render(<StageLine message="Fetching source page..." steps={['Researching...', 'need the page first']} />)

    const toggle = screen.getByRole('button')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByText('2 earlier')).toBeInTheDocument()
    expect(screen.queryByText('need the page first')).toBeNull()

    fireEvent.click(toggle)

    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('need the page first')).toBeInTheDocument()
    expect(screen.queryByText('2 earlier')).toBeNull()
  })

  it('keeps the newest entry at the top of the opened box', () => {
    const { container } = render(
      <StageLine message="Composing answer..." steps={['Researching...', 'old note', 'new note']} />,
    )

    fireEvent.click(screen.getByRole('button'))

    const items = Array.from(container.querySelectorAll('.step-history-item')).map((el) => el.textContent)
    expect(items).toEqual(['new note', 'old note', 'Researching...'])
  })
})
