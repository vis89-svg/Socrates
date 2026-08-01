import { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Globe2, FileText, Share2, Sparkles } from 'lucide-react'
import OwlMascot from './OwlMascot'
import { fetchMe, login, register } from '../api/auth'
import { useToast } from './Toast'
import type { User } from '../types'

interface AuthScreenProps {
  onAuthed: (user: User) => void
}

export default function AuthScreen({ onAuthed }: AuthScreenProps) {
  const showToast = useToast()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const heroRef = useRef<HTMLDivElement>(null)

  const usernameRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const emailRef = useRef<HTMLInputElement>(null)

  const handleLook = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = heroRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width - 0.5
    const y = (e.clientY - r.top) / r.height - 0.5
    el.style.setProperty('--owl-look-x', `${x * 10}px`)
    el.style.setProperty('--owl-look-y', `${y * 8}px`)
  }

  const fail = (err: unknown) => {
    const message = err instanceof Error ? err.message : 'Something went wrong'
    setError(message)
    showToast(message)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (busy) return
    setError('')
    const username = usernameRef.current?.value.trim() || ''
    const password = passwordRef.current?.value || ''
    const email = emailRef.current?.value.trim() || ''
    if (mode === 'register') {
      if (!username || !email || !password) {
        setError('All fields are required')
        return
      }
      if (password.length < 8) {
        setError('Password must be at least 8 characters')
        return
      }
    } else if (!username || !password) {
      setError('Username and password are required')
      return
    }
    setBusy(true)
    try {
      if (mode === 'register') {
        await register(username, email, password)
      } else {
        await login(username, password)
      }
      const user = await fetchMe()
      onAuthed(user)
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-hero" ref={heroRef} onMouseMove={handleLook}>
        <div className="auth-hero-inner">
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.92 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          >
            <OwlMascot mood="greeting" size={200} />
          </motion.div>
          <motion.h1
            className="auth-brand"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
          >
            Owl<span className="dot">.</span>
          </motion.h1>
          <motion.p
            className="auth-tagline"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.25 }}
          >
            Wise answers, sharp research, and a little hoot of magic — your curious companion.
          </motion.p>
          <div className="auth-features">
            <motion.div className="auth-feature" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
              <Globe2 size={16} /> Live web research with sources you can trust
            </motion.div>
            <motion.div className="auth-feature" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.43 }}>
              <FileText size={16} /> Analyze documents &amp; files in chat
            </motion.div>
            <motion.div className="auth-feature" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.51 }}>
              <Share2 size={16} /> Export to Word or PDF, share conversations
            </motion.div>
            <motion.div className="auth-feature" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.59 }}>
              <Sparkles size={16} /> Animated, thoughtful AI responses
            </motion.div>
          </div>
        </div>
      </div>

      <div className="auth-panel">
        <motion.div
          className="auth-card"
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: 'easeOut' }}
        >
          <h1>{mode === 'login' ? 'Welcome back' : 'Join the nest'}</h1>
          <p className="sub">
            {mode === 'login' ? 'Sign in to continue your conversations' : 'Create an account to start chatting'}
          </p>
          <div className={`auth-error ${error ? 'show' : ''}`}>{error}</div>
          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="auth-username">Username</label>
              <input id="auth-username" ref={usernameRef} type="text" placeholder="Your username" autoComplete="username" />
            </div>
            {mode === 'register' && (
              <div className="field">
                <label htmlFor="auth-email">Email</label>
                <input id="auth-email" ref={emailRef} type="email" placeholder="you@example.com" autoComplete="email" />
              </div>
            )}
            <div className="field">
              <label htmlFor="auth-password">Password</label>
              <input
                id="auth-password"
                ref={passwordRef}
                type="password"
                placeholder={mode === 'register' ? 'At least 8 characters' : 'Your password'}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>
            <button className="btn auth-submit" type="submit" disabled={busy}>
              {busy ? 'One moment...' : mode === 'login' ? 'Sign In' : 'Register'}
            </button>
          </form>
          <p className="auth-switch">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <a
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setError('')
              }}
            >
              {mode === 'login' ? 'Create one' : 'Sign in'}
            </a>
          </p>
        </motion.div>
      </div>
    </div>
  )
}
