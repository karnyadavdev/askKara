import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import SourceChips from '../components/SourceChips'

const sources = [
  { title: 'Wikipedia', url: 'https://en.wikipedia.org/wiki/Web_scraping' },
  { title: 'MDN', url: 'https://developer.mozilla.org/' },
]

describe('SourceChips', () => {
  it('renders numbered links per source', () => {
    render(<SourceChips sources={sources} />)

    expect(screen.getByText('en.wikipedia.org')).toBeInTheDocument()
    expect(screen.getByText('developer.mozilla.org')).toBeInTheDocument()
    expect(screen.getAllByRole('link')).toHaveLength(2)
  })

  it('renders nothing without sources', () => {
    const { container } = render(<SourceChips sources={[]} />)
    expect(container.firstChild).toBeNull()
  })
})
