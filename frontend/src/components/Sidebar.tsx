import { motion } from 'framer-motion'
import { Plus, Trash2, LogOut } from 'lucide-react'
import OwlMascot from './OwlMascot'
import type { ConversationSummary, User } from '../types'

interface SidebarProps {
  conversations: ConversationSummary[]
  activeId: number | null
  busy: boolean
  onSelect: (id: number) => void
  onNew: () => void
  onDelete: (id: number) => void
  onLogout: () => void
  user: User
}

export default function Sidebar({
  conversations,
  activeId,
  busy,
  onSelect,
  onNew,
  onDelete,
  onLogout,
  user,
}: SidebarProps) {
  return (
    <div className="sidebar">
      <div className="sidebar-brand">
        <div className="mini-owl">
          <OwlMascot size={34} />
        </div>
        <h2>
          Owl<span className="dot">.</span>
        </h2>
      </div>

      <button className="btn new-chat-btn" onClick={onNew} disabled={busy}>
        <Plus size={16} /> New Chat
      </button>

      <div className="conv-list">
        {conversations.length === 0 && (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textAlign: 'center', padding: '1rem 0' }}>
            No conversations yet
          </p>
        )}
        {conversations.map((conv) => (
          <motion.div
            key={conv.id}
            layout
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className={`conv-item ${activeId === conv.id ? 'active' : ''}`}
            onClick={() => onSelect(conv.id)}
          >
            <span className="title">{conv.title || 'New Chat'}</span>
            <span
              className="del"
              title="Delete conversation"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(conv.id)
              }}
            >
              <Trash2 size={13} />
            </span>
          </motion.div>
        ))}
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="avatar">{user.username.charAt(0).toUpperCase()}</div>
          <span className="uname">{user.username}</span>
        </div>
        <button className="icon-btn" title="Logout" onClick={onLogout}>
          <LogOut size={15} />
        </button>
      </div>
    </div>
  )
}
