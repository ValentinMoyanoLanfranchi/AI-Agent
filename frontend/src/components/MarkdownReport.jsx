import { Fragment } from 'react'

// Renderiza spans inline: **negrita**, *cursiva*, `código`, [texto](url) y URLs sueltas.
function renderInline(text, keyPrefix = 'i') {
  const nodes = []
  let remaining = text
  let key = 0

  // Patrón combinado: link markdown | negrita | cursiva | código | url suelta
  const pattern = /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(`([^`]+)`)|(https?:\/\/[^\s)]+)/g

  let lastIndex = 0
  let match
  while ((match = pattern.exec(remaining)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(remaining.slice(lastIndex, match.index))
    }
    if (match[1]) {
      // [texto](url)
      nodes.push(
        <a key={`${keyPrefix}-${key++}`} href={match[3]} target="_blank" rel="noopener noreferrer">
          {match[2]}
        </a>
      )
    } else if (match[4]) {
      // **negrita**
      nodes.push(<strong key={`${keyPrefix}-${key++}`}>{match[5]}</strong>)
    } else if (match[6]) {
      // *cursiva*
      nodes.push(<em key={`${keyPrefix}-${key++}`}>{match[7]}</em>)
    } else if (match[8]) {
      // `código`
      nodes.push(<code key={`${keyPrefix}-${key++}`}>{match[9]}</code>)
    } else if (match[10]) {
      // url suelta
      nodes.push(
        <a key={`${keyPrefix}-${key++}`} href={match[10]} target="_blank" rel="noopener noreferrer">
          {match[10]}
        </a>
      )
    }
    lastIndex = pattern.lastIndex
  }
  if (lastIndex < remaining.length) {
    nodes.push(remaining.slice(lastIndex))
  }
  return nodes
}

// Convierte un texto markdown en bloques (headings, listas, hr, párrafos).
function parseBlocks(markdown) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n')
  const blocks = []
  let listBuffer = null
  let paragraphBuffer = []

  const flushParagraph = () => {
    if (paragraphBuffer.length) {
      blocks.push({ type: 'p', text: paragraphBuffer.join(' ') })
      paragraphBuffer = []
    }
  }
  const flushList = () => {
    if (listBuffer) {
      blocks.push(listBuffer)
      listBuffer = null
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/, '')

    if (line.trim() === '') {
      flushParagraph()
      flushList()
      continue
    }

    // Separador horizontal
    if (/^\s*---+\s*$/.test(line)) {
      flushParagraph()
      flushList()
      blocks.push({ type: 'hr' })
      continue
    }

    // Headings #, ##, ###...
    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      flushParagraph()
      flushList()
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] })
      continue
    }

    // Items de lista (con indentación opcional para anidar)
    const bullet = line.match(/^(\s*)[-*+]\s+(.*)$/)
    if (bullet) {
      flushParagraph()
      const indent = bullet[1].length
      if (!listBuffer) listBuffer = { type: 'ul', items: [] }
      listBuffer.items.push({ indent, text: bullet[2] })
      continue
    }

    // Línea normal -> párrafo
    flushList()
    paragraphBuffer.push(line.trim())
  }
  flushParagraph()
  flushList()
  return blocks
}

export default function MarkdownReport({ children, className = 'report-container markdown-report' }) {
  const markdown = typeof children === 'string' ? children : String(children ?? '')
  const blocks = parseBlocks(markdown)

  return (
    <div className={className}>
      {blocks.map((block, idx) => {
        if (block.type === 'hr') return <hr key={idx} />
        if (block.type === 'heading') {
          const Tag = `h${Math.min(block.level + 1, 6)}`
          return <Tag key={idx}>{renderInline(block.text, `h${idx}`)}</Tag>
        }
        if (block.type === 'ul') {
          return (
            <ul key={idx}>
              {block.items.map((item, i) => (
                <li key={i} style={item.indent >= 2 ? { marginLeft: `${item.indent * 8}px` } : undefined}>
                  {renderInline(item.text, `l${idx}-${i}`)}
                </li>
              ))}
            </ul>
          )
        }
        return <p key={idx}>{renderInline(block.text, `p${idx}`)}</p>
      })}
    </div>
  )
}
