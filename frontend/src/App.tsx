import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ToastProvider } from './components/Toast'
import AuthScreen from './components/AuthScreen'
import ChatScreen from './components/ChatScreen'
import { clearTokens } from './api/client'
import { fetchMe } from './api/auth'
import type { User } from './types'

export default function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [status, setStatus] = useState<'loading' | 'auth' | 'app'>('loading')
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    const saved = localStorage.getItem('owl-theme') || localStorage.getItem('socrates-theme') || 'light'
    setTheme(saved === 'dark' ? 'dark' : 'light')
    document.documentElement.setAttribute('data-theme', saved === 'dark' ? 'dark' : 'light')

    const token = localStorage.getItem('owl-token') || localStorage.getItem('socrates-token')
    if (token) {
      fetchMe()
        .then((u) => {
          setUser(u)
          setStatus('app')
        })
        .catch(() => {
          clearTokens()
          setStatus('auth')
        })
    } else {
      setStatus('auth')
    }
  }, [])

  useEffect(() => {
    const handler = () => {
      setUser(null)
      setStatus('auth')
    }
    window.addEventListener('owl-session-expired', handler)
    return () => window.removeEventListener('owl-session-expired', handler)
  }, [])

  const toggleTheme = () => {
    setTheme((cur) => {
      const next = cur === 'dark' ? 'light' : 'dark'
      document.documentElement.setAttribute('data-theme', next)
      localStorage.setItem('owl-theme', next)
      return next
    })
  }

  const handleLogout = () => {
    clearTokens()
    setUser(null)
    setStatus('auth')
  }

  const handleAuthed = (u: User) => {
    setUser(u)
    setStatus('app')
  }

  return (
    <ToastProvider>
      <AnimatePresence mode="wait">
        {status === 'auth' && (
          <motion.div
            key="auth"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, scale: 1.02 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            style={{ height: '100%' }}
          >
            <AuthScreen onAuthed={handleAuthed} />
          </motion.div>
        )}
        {status === 'app' && user && (
          <motion.div
            key="app"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            style={{ height: '100%' }}
          >
            <ChatScreen user={user} theme={theme} toggleTheme={toggleTheme} onLogout={handleLogout} />
          </motion.div>
        )}
      </AnimatePresence>
    </ToastProvider>
  )
}
