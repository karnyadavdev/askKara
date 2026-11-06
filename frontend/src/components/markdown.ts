function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.appendChild(document.createTextNode(text))
  return div.innerHTML
}

function safeUrl(url: string): string {
  const trimmed = url.trim()
  if (/^(https?:\/\/|mailto:)/i.test(trimmed)) return trimmed
  return ''
}

function formatInlineMarkdown(text: string): string {
  const codeSpans: string[] = []
  let out = escapeHtml(text).replace(/`([^`]+)`/g, (_match, code: string) => {
    codeSpans.push(code)
    return `\uE000${codeSpans.length - 1}\uE001`
  })

  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_match, label: string, url: string) => {
    const href = safeUrl(url)
    if (!href) return label
    return `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`
  })
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
  out = out.replace(/\[(\d+)\]/g, '<span class="cite-num">[$1]</span>')
  return out.replace(/\uE000(\d+)\uE001/g, (_match, index: string) => `<code>${codeSpans[Number(index)]}</code>`)
}

function splitTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  return trimmed.split('|').map((cell) => cell.trim())
}

function isTableSeparator(line: string): boolean {
  const cells = splitTableRow(line)
  return cells.length > 0 && cells.every((cell) => /^:?-{2,}:?$/.test(cell))
}

function renderTable(header: string[], rows: string[][]): string {
  const head = header.map((cell) => `<th>${formatInlineMarkdown(cell)}</th>`).join('')
  const body = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${formatInlineMarkdown(cell)}</td>`).join('')}</tr>`)
    .join('')
  return `<div class="answer-table"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`
}

function renderCodeBlock(language: string, code: string[]): string {
  const className = language ? ` class="language-${language.replace(/[^a-zA-Z0-9_+-]/g, '')}"` : ''
  return `<pre class="answer-code"><code${className}>${escapeHtml(code.join('\n'))}</code></pre>`
}

export function renderAnswerMarkdown(text: string): string {
  const lines = String(text || '')
    .replace(/\r\n/g, '\n')
    .split('\n')
  const html: string[] = []

  for (let index = 0; index < lines.length; index += 1) {
    const trimmed = lines[index].trim()
    if (!trimmed) continue

    if (trimmed.startsWith('```')) {
      const language = trimmed.slice(3).trim().split(/\s+/)[0] ?? ''
      const code: string[] = []
      index += 1
      while (index < lines.length && !lines[index].trim().startsWith('```')) {
        code.push(lines[index])
        index += 1
      }
      html.push(renderCodeBlock(language, code))
      continue
    }

    if (trimmed.includes('|') && index + 1 < lines.length && isTableSeparator(lines[index + 1].trim())) {
      const header = splitTableRow(trimmed)
      const rows: string[][] = []
      index += 2
      while (index < lines.length && lines[index].trim() && lines[index].includes('|')) {
        rows.push(splitTableRow(lines[index].trim()))
        index += 1
      }
      index -= 1
      html.push(renderTable(header, rows))
      continue
    }

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
