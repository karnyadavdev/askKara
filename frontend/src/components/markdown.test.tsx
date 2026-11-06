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

describe('renderAnswerMarkdown tables, links and code', () => {
  it('renders a gfm table with header and body cells', () => {
    const html = renderAnswerMarkdown('| Name | Posts |\n| --- | ---: |\n| Elon | 111.6K |\n| Flying Beast | 3M |')

    expect(html).toContain('<div class="answer-table"><table>')
    expect(html).toContain('<th>Name</th>')
    expect(html).toContain('<td>Elon</td>')
    expect(html).toContain('<td>3M</td>')
  })

  it('renders citations inside table cells', () => {
    const html = renderAnswerMarkdown('| Claim | Source |\n| --- | --- |\n| grew fast [1] | wiki [2] |')

    expect(html).toContain('cite-num')
    expect(html).toContain('[1]')
  })

  it('renders safe links and drops unsafe schemes', () => {
    const html = renderAnswerMarkdown('[docs](https://example.com) and [bad](javascript:alert(1))')

    expect(html).toContain('<a href="https://example.com" target="_blank" rel="noopener noreferrer">docs</a>')
    expect(html).not.toContain('javascript:')
    expect(html).toContain('bad')
  })

  it('renders fenced code blocks escaped with a language class', () => {
    const html = renderAnswerMarkdown('```python\nprint("<hi>")\n```')

    expect(html).toContain('<pre class="answer-code"><code class="language-python">')
    expect(html).toContain('print("&lt;hi&gt;")')
    expect(html).not.toContain('<hi>')
  })

  it('renders inline code before bold and links', () => {
    const html = renderAnswerMarkdown('use `**not bold**` and **bold**')

    expect(html).toContain('<code>**not bold**</code>')
    expect(html).toContain('<strong>bold</strong>')
  })
})

describe('bare url linking', () => {
  it('links a bare https url', () => {
    const html = renderAnswerMarkdown('source: https://example.com/page')

    expect(html).toContain('<a href="https://example.com/page" target="_blank" rel="noopener noreferrer">https://example.com/page</a>')
  })

  it('keeps trailing punctuation outside the link', () => {
    const html = renderAnswerMarkdown('see https://example.com/page.')

    expect(html).toContain('>https://example.com/page</a>.')
  })

  it('does not wrap a url that is already a markdown link', () => {
    const html = renderAnswerMarkdown('[docs](https://example.com)')

    expect(html.match(/<a /g)).toHaveLength(1)
    expect(html).not.toContain('<a href="https://example.com" target="_blank" rel="noopener noreferrer">https://example.com</a>')
  })
})
