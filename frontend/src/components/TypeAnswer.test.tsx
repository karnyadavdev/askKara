import { render, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import TypeAnswer from '../components/TypeAnswer'

describe('TypeAnswer', () => {
  it('renders tables and code blocks instead of dropping them', async () => {
    const { container } = render(
      <TypeAnswer text={'Intro paragraph.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n```js\nconst x = 1\n```'} />,
    )

    await waitFor(() => {
      expect(container.querySelector('.answer-table table')).not.toBeNull()
      expect(container.querySelector('.answer-code code')).not.toBeNull()
    })
    expect(container.querySelectorAll('p').length).toBeGreaterThan(0)
  })

  it('keeps plain answers as paragraphs', async () => {
    const { container } = render(<TypeAnswer text="Just a short answer." />)

    await waitFor(() => {
      expect(container.textContent).toContain('Just a short answer.')
    })
  })
})
