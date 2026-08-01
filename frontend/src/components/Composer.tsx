import { useEffect, useRef, useState } from 'react'
import { Globe2, Paperclip, Pencil, Send, X } from 'lucide-react'
import { guessFileType, uploadFile } from '../api/files'
import { useToast } from './Toast'
import type { UploadedFile } from '../types'

interface ComposerProps {
  disabled: boolean
  streaming: boolean
  webSearch: boolean
  onToggleWebSearch: () => void
  editing: { id: number; content: string } | null
  onCancelEdit: () => void
  onSend: (text: string, fileIds: number[]) => void
  conversationId: number | null
}

export default function Composer({
  disabled,
  streaming,
  webSearch,
  onToggleWebSearch,
  editing,
  onCancelEdit,
  onSend,
  conversationId,
}: ComposerProps) {
  const showToast = useToast()
  const [attachments, setAttachments] = useState<UploadedFile[]>([])
  const inputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const submit = () => {
    const input = inputRef.current
    if (!input) return
    const text = input.value.trim()
    if (!text || disabled || streaming) return
    input.value = ''
    const fileIds = attachments.map((f) => f.id)
    setAttachments([])
    onSend(text, fileIds)
  }

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.value = editing.content
      inputRef.current.focus()
    }
  }, [editing])

  const handleFile = async (file: File) => {
    if (!conversationId) {
      showToast('Select a conversation first')
      return
    }
    const fd = new FormData()
    fd.append('file', file)
    fd.append('file_type', guessFileType(file.name))
    fd.append('original_name', file.name)
    fd.append('conversation', String(conversationId))
    try {
      const result = await uploadFile({
        file,
        file_type: guessFileType(file.name),
        original_name: file.name,
        conversation: conversationId,
      })
      setAttachments((prev) => [...prev, result])
    } catch (err) {
      showToast(`File upload failed: ${err instanceof Error ? err.message : 'unknown'}`)
    }
  }

  return (
    <div className="composer-wrap">
      <div className="input-tools">
        <div
          className={`toggle-wrap ${webSearch ? 'active' : ''}`}
          title="Search the web for current information"
          onClick={() => !streaming && onToggleWebSearch()}
          style={streaming ? { pointerEvents: 'none', opacity: 0.5 } : undefined}
        >
          <span className="toggle-track">
            <span className="toggle-knob" />
          </span>
          <Globe2 size={13} />
          <span className="toggle-label">Search Web</span>
        </div>
        <button className="tool-btn" title="Attach file" disabled={disabled || streaming} onClick={() => fileInputRef.current?.click()}>
          <Paperclip size={13} /> Attach file
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,.txt"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) handleFile(file)
            e.target.value = ''
          }}
        />
      </div>
      {attachments.length > 0 && (
        <div className="attachments">
          {attachments.map((f) => (
            <span key={f.id} className="attach-chip">
              {f.name}
              <span
                className="attach-chip-del"
                onClick={() => setAttachments((prev) => prev.filter((x) => x.id !== f.id))}
              >
                <X size={13} />
              </span>
            </span>
          ))}
        </div>
      )}
      <div className="input-row">
        {editing && (
          <>
            <span className="edit-indicator">
              <Pencil size={11} /> Editing message
            </span>
            <button className="cancel-edit" title="Cancel edit" onClick={onCancelEdit}>
              <X size={16} />
            </button>
          </>
        )}
        <input
          ref={inputRef}
          type="text"
          placeholder={disabled ? 'Select a conversation to start...' : streaming ? 'Owl is thinking...' : 'Type a message...'}
          disabled={disabled || streaming}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submit()
          }}
        />
        <button className="btn send-btn" disabled={disabled || streaming} onClick={submit}>
          {streaming ? '...' : editing ? 'Save' : <Send size={15} />}
          {!streaming && !editing && 'Send'}
        </button>
      </div>
    </div>
  )
}
