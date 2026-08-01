let tableSeq = 0
const tableStore = new Map<string, string[][]>()

export interface CitationLink {
  url: string
  title: string
}

export function getTableRows(id: string): string[][] {
  return tableStore.get(id) || []
}

function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

export function renderMarkdown(text: string, citations: Record<number, CitationLink> = {}): string {
  let html = escapeHtml(text)
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/((?:^\|.*\|\s*$\n?)+)/gm, (block) => {
    const rows: string[][] = []
    for (const line of block.trim().split('\n')) {
      const cells = line.slice(1, -1).split('|').map((c) => c.trim())
      if (cells.length === 1 && cells[0] === '') continue
      if (cells.every((c) => /^:?-{2,}:?$/.test(c))) continue
      rows.push(cells)
    }
    if (!rows.length) return ''
    const id = 't' + ++tableSeq
    tableStore.set(id, rows)
    const body = rows.map((r) => '<tr><td>' + r.join('</td><td>') + '</td></tr>').join('')
    return (
      `<div class="table-wrap" data-table-id="${id}"><div class="table-tools">` +
      `<button type="button" class="table-btn table-copy" title="Copy as TSV (pastes into Excel)">Copy</button>` +
      `<button type="button" class="table-btn table-csv" title="Download as CSV">CSV</button></div>` +
      `<table>${body}</table></div>`
    )
  })
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\[Confidence: (High|Medium|Low|None)\]/g, '<span class="conf-badge conf-$1">$1</span>')
  html = html.replace(/\[Source\s+(\d+)\]/g, (_, n) => {
    const c = citations[Number(n)]
    if (c && c.url) {
      const domain = c.url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]
      return `<a class="src-ref link" href="${escapeHtml(c.url)}" target="_blank" rel="noopener" title="${escapeHtml(c.title)}">[${escapeHtml(domain)}]</a>`
    }
    return `<sup class="src-ref">[${n}]</sup>`
  })
  html = html.replace(/---/g, '<hr>')
  html = html.replace(/\n\n/g, '</p><p>')
  html = '<p>' + html + '</p>'
  html = html.replace(/<p><\/p>/g, '')
  html = html.replace(/<table><\/table>/g, '')
  return html
}

export function domainOf(url: string): string {
  return url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]
}

export function downloadBlob(content: string, filename: string, mime: string): void {
  const blob = new Blob(['\ufeff' + content], { type: mime || 'text/plain;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    URL.revokeObjectURL(a.href)
    a.remove()
  }, 1000)
}
