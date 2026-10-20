function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.appendChild(document.createTextNode(text))
  return div.innerHTML
}

function formatInlineMarkdown(text: string): string {
  return escapeHtml(text)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[(\d+)\]/g, '<span class="cite-num">[$1]</span>')
}

export function renderAnswerMarkdown(text: string): string {
  const lines = String(text || '')
    .replace(/\r\n/g, '\n')
    .split('\n')
  const html: string[] = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue

    const heading = trimmed.match(/^#{1,4}\s+(.+)$/)
    if (heading) {
      html.push(`<p><strong>${formatInlineMarkdown(heading[1])}</strong></p>`)
      continue
    }

    const bullet = trimmed.match(/^[-*]\s+(.+)$/)
    if (bullet) {
      html.push(`<p class="answer-bullet">${formatInlineMarkdown(bullet[1])}</p>`)
      continue
    }

    html.push(`<p>${formatInlineMarkdown(trimmed)}</p>`)
  }

  return html.join('') || '<p>No answer returned.</p>'
}
