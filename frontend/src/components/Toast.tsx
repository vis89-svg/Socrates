import { createContext, useCallback, useContext, useState } from 'react'

interface ToastItem {
  id: number
  message: string
  kind: 'error' | 'ok'
}

type ShowToast = (message: string, kind?: 'error' | 'ok') => void

const ToastContext = createContext<ShowToast>(() => {})

export function useToast(): ShowToast {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<ToastItem | null>(null)
  let seq = 0

  const showToast = useCallback<ShowToast>((message, kind = 'error') => {
    const id = ++seq
    setToast({ id, message, kind })
    window.setTimeout(() => {
      setToast((cur) => (cur && cur.id === id ? null : cur))
    }, 4500)
  }, [])

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      {toast && (
        <div key={toast.id} className={`error-toast ${toast.kind === 'ok' ? 'toast-ok' : ''}`}>
          {toast.message}
        </div>
      )}
    </ToastContext.Provider>
  )
}
