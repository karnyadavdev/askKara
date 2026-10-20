import { describe, expect, it } from 'vitest'
import { renderAnswerMarkdown } from '../components/markdown'

describe('renderAnswerMarkdown', () => {
  it('renders headings, bullets, bold and citations', () => {
    const html = renderAnswerMarkdown('# Title\n- one\n- two\n**bold** claim [1]')

    expect(html).toContain('<strong>Title</strong>')
    expect(html).toContain('answer-bullet')
    expect(html).toContain('<strong>bold</strong>')
    expect(html).toContain('cite-num')
  })

  it('escapes html in answers', () => {
    const html = renderAnswerMarkdown('<script>alert(1)</script>')
    expect(html).not.toContain('<script>')
  })

  it('falls back for empty answers', () => {
    expect(renderAnswerMarkdown('')).toContain('No answer returned')
  })
})
