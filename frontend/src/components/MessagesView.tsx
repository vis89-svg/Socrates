import { motion } from 'framer-motion'
import { Pencil, Download } from 'lucide-react'
import OwlMascot from './OwlMascot'
import { renderMarkdown, domainOf } from '../markdown'
import type { Citation, EvidenceItem, Message, TimingsEvent } from '../types'

export interface StreamingState {
  status: string
  content: string
  evidence: EvidenceItem[]
  citations: Citation[] | null
  timings: TimingsEvent | null
}

export interface CitationMap {
  [index: number]: { url: string; title: string }
}

interface MessagesViewProps {
  messages: Message[]
  streaming: StreamingState | null
  evidenceMap: Record<number, EvidenceItem[]>
  citationMap: CitationMap
  editingMsgId: number | null
  onEdit: (msg: Message) => void
  onExport: (msgId: number, format: 'docx' | 'pdf') => void
  onTableAction: (e: React.MouseEvent) => void
  onSuggestion: (text: string) => void
  scrollRef: React.RefObject<HTMLDivElement>
}

export default function MessagesView({
  messages,
  streaming,
  evidenceMap,
  citationMap,
  editingMsgId,
  onEdit,
  onExport,
  onTableAction,
  onSuggestion,
  scrollRef,
}: MessagesViewProps) {
  const hasContent = messages.length > 0 || streaming !== null

  if (!hasContent) {
    return (
      <div className="messages" ref={scrollRef} style={{ justifyContent: 'center', alignItems: 'center' }}>
        <EmptyState onSuggestion={onSuggestion} />
      </div>
    )
  }

  return (
    <div className="messages" ref={scrollRef} onClick={onTableAction}>
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          msg={msg}
          evidenceMap={evidenceMap}
          citationMap={citationMap}
          editingMsgId={editingMsgId}
          onEdit={onEdit}
          onExport={onExport}
        />
      ))}
      {streaming && <StreamingBubble streaming={streaming} citationMap={citationMap} />}
      {streaming?.citations && streaming.citations.length > 0 && (
        <CitationsCard citations={streaming.citations} timings={streaming.timings} />
      )}
    </div>
  )
}

function EmptyState({ onSuggestion }: { onSuggestion: (t: string) => void }) {
  const suggestions = [
    'What can you help me with?',
    'Summarize the latest AI research',
    'Explain quantum computing simply',
    'Help me write a report',
  ]
  return (
    <motion.div
      className="empty-state"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.1, type: 'spring', bounce: 0.4 }}
      >
        <OwlMascot mood="greeting" size={150} />
      </motion.div>
      <h2>Hoot! I&apos;m Owl</h2>
      <p>Ask me anything — I research the web, analyze files, and think deeply before answering.</p>
      <div className="suggestion-chips">
        {suggestions.map((s) => (
          <button key={s} className="suggestion-chip" onClick={() => onSuggestion(s)}>
            {s}
          </button>
        ))}
      </div>
    </motion.div>
  )
}

interface BubbleProps {
  msg: Message
  evidenceMap: Record<number, EvidenceItem[]>
  citationMap: CitationMap
  editingMsgId: number | null
  onEdit: (msg: Message) => void
  onExport: (msgId: number, format: 'docx' | 'pdf') => void
}

function MessageBubble({ msg, evidenceMap, citationMap, editingMsgId, onEdit, onExport }: BubbleProps) {
  if (msg.role === 'user') {
    return (
      <motion.div
        className="msg user"
        initial={{ opacity: 0, y: 14, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.28, ease: 'easeOut' }}
      >
        <div className="bubble">{msg.content}</div>
        {msg.id > 0 && (
          <button
            className="edit-btn"
            title="Edit message"
            onClick={() => onEdit(msg)}
            style={{ color: editingMsgId === msg.id ? 'var(--accent)' : undefined }}
          >
            <Pencil size={12} />
          </button>
        )}
      </motion.div>
    )
  }

  if (msg.role === 'system') {
    return (
      <motion.div
        className="msg system"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28 }}
      >
        <div className="bubble">{msg.content}</div>
      </motion.div>
    )
  }

  const evidence = evidenceMap[msg.id] || []
  return (
    <motion.div
      className="msg assistant"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
    >
      <div className="bubble">
        <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content, citationMap) }} />
        {evidence.length > 0 && <EvidencePanel items={evidence} />}
      </div>
      {msg.id > 0 && (
        <div className="msg-tools">
          <button className="tool-btn msg-export" title="Download as Word" onClick={() => onExport(msg.id, 'docx')}>
            <Download size={12} /> Word
          </button>
          <button className="tool-btn msg-export" title="Download as PDF" onClick={() => onExport(msg.id, 'pdf')}>
            <Download size={12} /> PDF
          </button>
        </div>
      )}
    </motion.div>
  )
}

export function EvidencePanel({ items }: { items: EvidenceItem[] }) {
  return (
    <details className="evidence-panel">
      <summary>Evidence — {items.length} sources</summary>
      <div className="evidence-list">
        {items.map((e, i) => {
          const domain = domainOf(e.url)
          const meta = e.published_date ? ` · ${e.published_date}` : ''
          return (
            <div className="evidence-item" key={i}>
              <span className="evidence-num">{i + 1}</span>
              <a className="evidence-title" href={e.url} target="_blank" rel="noopener">
                {e.title}
              </a>
              <span className="evidence-meta">{meta}</span>
              <span className="evidence-domain">{domain}</span>
            </div>
          )
        })}
      </div>
    </details>
  )
}

function StreamingBubble({ streaming, citationMap }: { streaming: StreamingState; citationMap: CitationMap }) {
  const hasText = streaming.content.length > 0
  return (
    <motion.div className="msg assistant" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
      <div className="bubble" style={{ minWidth: 90 }}>
        <div
          className="status-bar"
          style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', marginBottom: hasText ? '0.6rem' : 0 }}
        >
          <OwlMascot mood="thinking" size={26} />
          <span className="status-dot" />
          <span>{streaming.status}</span>
        </div>
        {hasText && <div dangerouslySetInnerHTML={{ __html: renderMarkdown(streaming.content, citationMap) }} />}
      </div>
    </motion.div>
  )
}

function CitationsCard({ citations, timings }: { citations: Citation[]; timings: TimingsEvent | null }) {
  const fmt = (ms: number) => (ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : ms + 'ms')
  const timingsLine = timings
    ? `planner ${fmt(timings.planner_ms)} · search ${fmt(timings.search_ms)} · extract ${fmt(timings.extract_ms)} · generate ${fmt(timings.generation_ms)} · total ${fmt(timings.total_ms)}`
    : null
  return (
    <motion.div
      className="msg system"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="bubble" style={{ fontSize: '0.8rem', textAlign: 'left', maxWidth: 560 }}>
        <div style={{ fontWeight: 700, marginBottom: '0.35rem' }}>Sources:</div>
        {citations.map((c) => (
          <div key={c.index} style={{ margin: '0.15rem 0' }}>
            <a href={c.url} target="_blank" rel="noopener" style={{ color: 'var(--accent)' }}>
              [{c.index}] {c.title}
            </a>
          </div>
        ))}
        {timingsLine && <div style={{ marginTop: '0.4rem', color: 'var(--text-muted)' }}>Timings: {timingsLine}</div>}
      </div>
    </motion.div>
  )
}
