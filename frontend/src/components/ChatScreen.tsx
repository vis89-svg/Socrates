import { useCallback, useEffect, useRef, useState } from 'react'
import Sidebar from './Sidebar'
import ChatHeader from './ChatHeader'
import MessagesView, { type StreamingState, type CitationMap } from './MessagesView'
import Composer from './Composer'
import ShareDialog from './ShareDialog'
import { useToast } from './Toast'
import {
  createConversation,
  deleteConversation,
  exportMessage,
  getConversation,
  getMessages,
  listConversations,
  patchMessage,
  readStream,
  shareConversation,
  streamChat,
} from '../api/chat'
import { downloadBlob, getTableRows } from '../markdown'
import type { ConversationSummary, EvidenceItem, Message, User } from '../types'

interface ChatScreenProps {
  user: User
  theme: 'light' | 'dark'
  toggleTheme: () => void
  onLogout: () => void
}

export default function ChatScreen({ user, theme, toggleTheme, onLogout }: ChatScreenProps) {
  const showToast = useToast()
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [activeTitle, setActiveTitle] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loaded, setLoaded] = useState(false)
  const [streaming, setStreaming] = useState<StreamingState | null>(null)
  const [evidenceMap, setEvidenceMap] = useState<Record<number, EvidenceItem[]>>({})
  const [citationMap, setCitationMap] = useState<CitationMap>({})
  const [editing, setEditing] = useState<{ id: number; content: string } | null>(null)
  const [webSearch, setWebSearch] = useState(
    () => localStorage.getItem('owl-websearch') === '1' || localStorage.getItem('socrates-websearch') === '1',
  )
  const [shareOpen, setShareOpen] = useState(false)
  const [shareUrl, setShareUrl] = useState('')
  const messagesRef = useRef<HTMLDivElement>(null)
  const tempId = useRef(-1)

  const errText = (err: unknown, fallback: string) =>
    err instanceof Error && err.message ? err.message : fallback

  const loadConversation = useCallback(
    async (id: number) => {
      try {
        const conv = await getConversation(id)
        setActiveId(conv.id)
        setActiveTitle(conv.title || 'New Chat')
        setMessages(conv.messages || [])
        setEvidenceMap({})
        setCitationMap({})
        setStreaming(null)
      } catch (err) {
        showToast(`Failed to load conversation: ${errText(err, 'unknown error')}`)
      }
    },
    [showToast],
  )

  const refreshConversations = useCallback(async () => {
    try {
      const list = await listConversations()
      setConversations(list)
    } catch {
      /* silent */
    }
  }, [])

  useEffect(() => {
    ;(async () => {
      try {
        const list = await listConversations()
        setConversations(list)
        if (list.length > 0) {
          await loadConversation(list[0].id)
        }
      } catch {
        showToast('Failed to load conversations')
      } finally {
        setLoaded(true)
      }
    })()
  }, [loadConversation, showToast])

  useEffect(() => {
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, streaming?.content, streaming?.status])

  const handleNewConversation = async () => {
    try {
      const conv = await createConversation()
      await refreshConversations()
      await loadConversation(conv.id)
    } catch (err) {
      showToast(`Failed to create conversation: ${errText(err, 'unknown error')}`)
    }
  }

  const handleSelectConversation = (id: number) => {
    if (streaming) return
    if (id === activeId) return
    setEditing(null)
    loadConversation(id)
  }

  const handleDeleteConversation = async (id: number) => {
    try {
      await deleteConversation(id)
      if (id === activeId) {
        setActiveId(null)
        setActiveTitle('')
        setMessages([])
        setStreaming(null)
        setEditing(null)
      }
      await refreshConversations()
    } catch (err) {
      showToast(`Failed to delete: ${errText(err, 'unknown error')}`)
    }
  }

  const handleEdit = (msg: Message) => {
    if (streaming) return
    setEditing({ id: msg.id, content: msg.content })
  }

  const handleExport = async (msgId: number, format: 'docx' | 'pdf') => {
    if (!activeId || streaming) return
    try {
      const blob = await exportMessage(activeId, msgId, format)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = format === 'docx' ? 'report.docx' : 'report.pdf'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      showToast('Exported successfully', 'ok')
    } catch (err) {
      showToast(`Export failed: ${errText(err, 'unknown error')}`)
    }
  }

  const handleTableAction = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    const wrap = target.closest('.table-wrap') as HTMLElement | null
    if (!wrap) return
    const rows = getTableRows(wrap.dataset.tableId || '')
    if (!rows.length) return
    const btn = target.closest('.table-btn') as HTMLElement | null
    if (!btn) return
    if (btn.classList.contains('table-copy')) {
      const tsv = rows.map((r) => r.join('\t')).join('\n')
      navigator.clipboard
        .writeText(tsv)
        .then(() => {
          btn.textContent = 'Copied!'
          setTimeout(() => {
            btn.textContent = 'Copy'
          }, 1500)
        })
        .catch(() => showToast('Copy failed'))
    } else if (btn.classList.contains('table-csv')) {
      const csv = rows
        .map((r) => r.map((c) => (/[",\n]/.test(c) ? '"' + c.replace(/"/g, '""') + '"' : c)).join(','))
        .join('\r\n')
      downloadBlob(csv, 'table.csv', 'text/csv;charset=utf-8')
    }
  }

  const handleSend = async (text: string, fileIds: number[]) => {
    if (!activeId || streaming) return

    if (editing) {
      const msgId = editing.id
      setEditing(null)
      try {
        await patchMessage(activeId, msgId, text)
        const msgs = await getMessages(activeId)
        setMessages(msgs)
        await runStream(text, fileIds, msgId)
      } catch (err) {
        showToast(`Edit failed: ${errText(err, 'unknown error')}`)
      }
      return
    }

    const temp: Message = {
      id: tempId.current--,
      role: 'user',
      content: text,
      tokens_used: 0,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, temp])
    await runStream(text, fileIds)
  }

  const runStream = async (text: string, fileIds: number[], regenerateId?: number) => {
    if (!activeId) return
    setStreaming({ status: 'Analyzing...', content: '', evidence: [], citations: null, timings: null })
    let response
    try {
      response = await streamChat(activeId, {
        message: text,
        web_search: webSearch,
        file_ids: fileIds.length > 0 ? fileIds : undefined,
        regenerate_message_id: regenerateId,
      })
    } catch (err) {
      setStreaming(null)
      showToast(`Failed to start: ${errText(err, 'unknown error')}`)
      return
    }

    if (!response.ok) {
      let detail = `HTTP ${response.status}`
      try {
        const data = await response.json()
        detail = data.error || data.detail || detail
      } catch {
        /* not json */
      }
      setStreaming(null)
      showToast(`Message failed: ${detail}`)
      return
    }

    let content = ''
    let messageId: number | null = null
    let evidence: EvidenceItem[] = []

    const apply = (patch: Partial<StreamingState>) => {
      setStreaming((s) => (s ? { ...s, ...patch } : s))
    }

    try {
      await readStream(response, (ev) => {
        if (ev.analysis) {
          const caps = ev.analysis.join(', ')
          apply({ status: `Analyzed: ${caps}` })
        } else if (ev.tool_use) {
          apply({ status: ev.tool_use.label })
        } else if (ev.stage) {
          apply({ status: ev.stage })
        } else if (ev.search) {
          evidence = ev.search.evidence || evidence
          const intentTag = ev.search.intent ? ` [${ev.search.intent}]` : ''
          let covTag = ''
          if (ev.search.coverage && ev.search.coverage.required.length > 0) {
            const miss = ev.search.coverage.missing || []
            covTag =
              miss.length > 0
                ? ` · missing: ${miss.join(', ')}`
                : ` · sources ${ev.search.coverage.found.length}/${ev.search.coverage.required.length} ✓`
          }
          const countText = ev.search.count > 0 ? `${ev.search.count} results` : 'no results'
          apply({ status: `Search found ${countText}${intentTag}${covTag}`, evidence })
        } else if (ev.citations) {
          if (ev.citations.length > 0) {
            const map: CitationMap = {}
            for (const c of ev.citations) {
              if (c.index) map[c.index] = { url: c.url, title: c.title }
            }
            setCitationMap(map)
            apply({ citations: ev.citations })
          }
        } else if (ev.summary) {
          const s = ev.summary
          const conf = s.confidence || {}
          let text = `Research summary: ${s.sources} sources searched, ${s.fields_verified} facts verified (${conf.high || 0} high / ${conf.medium || 0} medium confidence)`
          if (s.top_domains && s.top_domains.length) text += ` from ${s.top_domains.join(', ')}`
          setMessages((prev) => [
            ...prev,
            {
              id: tempId.current--,
              role: 'system',
              content: text,
              tokens_used: 0,
              created_at: new Date().toISOString(),
            },
          ])
        } else if (ev.timings) {
          apply({ timings: ev.timings })
        } else if (ev.token) {
          content += ev.token
          apply({ content })
        } else if (ev.done) {
          messageId = ev.done.message_id
        }
      })
    } catch (err) {
      setStreaming(null)
      showToast(`Message failed: ${errText(err, 'network error')}`)
      return
    }

    const finalContent = content || '(no response)'
    const finalId = messageId ?? tempId.current--
    if (evidence.length > 0) {
      setEvidenceMap((prev) => ({ ...prev, [finalId]: evidence }))
    }
    const finalMsg: Message = {
      id: finalId,
      role: 'assistant',
      content: finalContent,
      tokens_used: 0,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, finalMsg])
    setStreaming(null)
    await refreshConversations()
  }

  const handleShare = async () => {
    if (!activeId) return
    try {
      const url = await shareConversation(activeId, true)
      if (url) {
        setShareUrl(url)
        setShareOpen(true)
      }
    } catch (err) {
      showToast(`Failed to share: ${errText(err, 'unknown error')}`)
    }
  }

  const handleStopSharing = async () => {
    if (!activeId) return
    try {
      await shareConversation(activeId, false)
      setShareOpen(false)
      showToast('Sharing stopped', 'ok')
    } catch (err) {
      showToast(`Failed to stop sharing: ${errText(err, 'unknown error')}`)
    }
  }

  const toggleWebSearch = () => {
    setWebSearch((cur) => {
      const next = !cur
      localStorage.setItem('owl-websearch', next ? '1' : '0')
      return next
    })
  }

  const handleSuggestion = (text: string) => {
    if (!activeId || streaming) return
    setMessages((prev) => [
      ...prev,
      {
        id: tempId.current--,
        role: 'user',
        content: text,
        tokens_used: 0,
        created_at: new Date().toISOString(),
      },
    ])
    runStream(text, [])
  }

  return (
    <div className="chat-screen">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        busy={!!streaming}
        onSelect={handleSelectConversation}
        onNew={handleNewConversation}
        onDelete={handleDeleteConversation}
        onLogout={onLogout}
        user={user}
      />
      <div className="chat-main">
        <ChatHeader
          title={activeTitle}
          hasConv={activeId !== null}
          busy={!!streaming}
          theme={theme}
          onShare={handleShare}
          onToggleTheme={toggleTheme}
          user={user}
        />
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {loaded && (
            <MessagesView
              messages={messages}
              streaming={streaming}
              evidenceMap={evidenceMap}
              citationMap={citationMap}
              editingMsgId={editing?.id ?? null}
              onEdit={handleEdit}
              onExport={handleExport}
              onTableAction={handleTableAction}
              onSuggestion={handleSuggestion}
              scrollRef={messagesRef}
            />
          )}
        </div>
        <Composer
          disabled={!activeId}
          streaming={!!streaming}
          webSearch={webSearch}
          onToggleWebSearch={toggleWebSearch}
          editing={editing}
          onCancelEdit={() => setEditing(null)}
          onSend={handleSend}
          conversationId={activeId}
        />
      </div>
      <ShareDialog
        open={shareOpen}
        url={shareUrl}
        onClose={() => setShareOpen(false)}
        onStop={handleStopSharing}
      />
    </div>
  )
}
