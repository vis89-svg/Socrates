const DEV_API = 'http://localhost:8000/api'

export const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ||
  (import.meta.env.DEV ? DEV_API : '/api')

const TOKEN_KEY = 'owl-token'
const REFRESH_KEY = 'owl-refresh'
const LEGACY_TOKEN_KEY = 'socrates-token'
const LEGACY_REFRESH_KEY = 'socrates-refresh'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY) || localStorage.getItem(LEGACY_REFRESH_KEY)
}

export function saveTokens(access: string, refresh?: string): void {
  localStorage.setItem(TOKEN_KEY, access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function fireSessionExpired(): void {
  window.dispatchEvent(new CustomEvent('owl-session-expired'))
}

export async function tryRefreshToken(): Promise<string | null> {
  const refresh = getRefreshToken()
  if (!refresh) return null
  try {
    const rr = await fetch(`${API_BASE}/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })
    if (!rr.ok) return null
    const data = (await rr.json()) as { access: string }
    saveTokens(data.access, refresh)
    return data.access
  } catch {
    return null
  }
}

export async function apiFetch<T = unknown>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers || {})
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response = await fetch(`${API_BASE}${url}`, { ...options, headers })

  if (response.status === 401 && !url.startsWith('/auth/')) {
    const refreshed = await tryRefreshToken()
    if (refreshed) {
      headers.set('Authorization', `Bearer ${refreshed}`)
      response = await fetch(`${API_BASE}${url}`, { ...options, headers })
    }
    if (response.status === 401) {
      clearTokens()
      fireSessionExpired()
      throw new ApiError(401, 'Session expired. Please log in again.')
    }
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const data = await response.json()
      if (data.detail) detail = data.detail
      else if (data.error) detail = data.error
      else if (data.message) detail = data.message
      else {
        const vals = Object.values(data)
        if (vals.length) {
          const flat = vals.flat(Infinity).join(', ')
          if (flat) detail = flat
        }
      }
    } catch {
      /* not json */
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  const text = await response.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}
