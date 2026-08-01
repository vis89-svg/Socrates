import { Moon, Share2, Sun } from 'lucide-react'
import OwlMascot from './OwlMascot'
import type { User } from '../types'

interface ChatHeaderProps {
  title: string
  hasConv: boolean
  busy: boolean
  theme: 'light' | 'dark'
  onShare: () => void
  onToggleTheme: () => void
  user: User
}

export default function ChatHeader({
  title,
  hasConv,
  busy,
  theme,
  onShare,
  onToggleTheme,
  user,
}: ChatHeaderProps) {
  return (
    <div className="chat-header">
      <div className="chat-header-left">
        <div className="mini-owl" title="Owl">
          <OwlMascot size={36} mood={busy ? 'thinking' : 'idle'} />
        </div>
        <span className="chat-header-title">{title || 'Select a conversation'}</span>
      </div>
      <div className="chat-header-right">
        <button className="icon-btn" title="Share conversation" disabled={!hasConv || busy} onClick={onShare}>
          <Share2 size={15} />
        </button>
        <button className="icon-btn" title="Toggle dark mode" onClick={onToggleTheme}>
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{user.username}</span>
      </div>
    </div>
  )
}
