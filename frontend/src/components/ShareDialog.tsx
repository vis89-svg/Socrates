import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Copy, X } from 'lucide-react'
import { useToast } from './Toast'

interface ShareDialogProps {
  open: boolean
  url: string
  onClose: () => void
  onStop: () => void
}

export default function ShareDialog({ open, url, onClose, onStop }: ShareDialogProps) {
  const showToast = useToast()
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      showToast('Link copied to clipboard', 'ok')
      setTimeout(() => setCopied(false), 1600)
    } catch {
      showToast('Copy failed')
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="share-dialog-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={(e) => {
            if (e.target === e.currentTarget) onClose()
          }}
        >
          <motion.div
            className="share-dialog-card"
            initial={{ opacity: 0, scale: 0.9, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 10 }}
            transition={{ type: 'spring', bounce: 0.35, duration: 0.4 }}
          >
            <h2>Share conversation</h2>
            <p className="hint">Anyone with this link can view this conversation.</p>
            <div className="share-row">
              <input type="text" readOnly value={url} onFocus={(e) => e.target.select()} />
              <button className="btn-secondary btn" onClick={copy} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <div className="share-actions">
              <button className="btn btn-danger" onClick={onStop}>
                Stop sharing
              </button>
              <button className="btn btn-secondary" onClick={onClose} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                <X size={14} /> Close
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
