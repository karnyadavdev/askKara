import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FeedBlock from '../components/FeedBlock'

describe('FeedBlock', () => {
  it('shows the stage line while researching', () => {
    render(<FeedBlock item={{ id: 'a', question: 'What is rate limiting?' }} stage="Searching for sources..." />)
    expect(screen.getByText('What is rate limiting?')).toBeInTheDocument()
    expect(screen.getByText('Searching for sources')).toBeInTheDocument()
  })

  it('shows the error text', () => {
    render(<FeedBlock item={{ id: 'a', question: 'q', error: 'The research service is temporarily rate-limited.' }} />)
    expect(screen.getByText('The research service is temporarily rate-limited.')).toBeInTheDocument()
  })

  it('renders finished answers as markdown instantly', () => {
    render(<FeedBlock item={{ id: 'a', question: 'q', answer: '**bold** claim [1]', instant: true }} />)
    expect(screen.getByText('bold')).toBeInTheDocument()
    expect(screen.getByText('[1]')).toBeInTheDocument()
  })

  it('renders live streamed tokens', () => {
    const { container } = render(<FeedBlock item={{ id: 'a', question: 'q' }} liveText="partial **answer**" />)
    const live = container.querySelector('.live-tokens')
    expect(live).not.toBeNull()
    expect(live?.innerHTML).toContain('<strong>answer</strong>')
    expect(container.querySelector('.live-cursor')).not.toBeNull()
  })

  it('keeps the stage line when the first tokens are whitespace', () => {
    render(<FeedBlock item={{ id: 'a', question: 'q' }} stage="Researching..." liveText={'\n\n'} />)

    expect(screen.getByText('Researching')).toBeInTheDocument()
    expect(screen.queryByText('No answer returned.')).toBeNull()
  })

  it('shows the stage line next to live tokens', () => {
    render(<FeedBlock item={{ id: 'a', question: 'q' }} stage="Fetching source page..." liveText="partial answer" />)

    expect(screen.getByText('Fetching source page')).toBeInTheDocument()
    expect(screen.getByText('partial answer')).toBeInTheDocument()
  })
})
