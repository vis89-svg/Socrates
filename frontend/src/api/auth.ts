import { apiFetch, clearTokens, saveTokens } from './client'
import type { AuthTokens, User } from '../types'

export async function login(username: string, password: string): Promise<AuthTokens> {
  const data = await apiFetch<AuthTokens>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  saveTokens(data.access, data.refresh)
  return data
}

export async function register(username: string, email: string, password: string): Promise<AuthTokens> {
  await apiFetch('/auth/register/', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
  })
  return login(username, password)
}

export async function fetchMe(): Promise<User> {
  return apiFetch<User>('/auth/me/')
}

export function logout(): void {
  clearTokens()
}
