import { apiFetch, API_BASE, getToken } from './client'
import type {
  Conversation,
  ConversationSummary,
  Message,
  StreamEvent,
} from '../types'

export interface StreamRequest {
  message: string
  web_search: boolean
  file_ids?: number[]
  regenerate_message_id?: number
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const data = await apiFetch<{ results: ConversationSummary[] }>('/chat/conversations/')
  return data.results || (data as unknown as ConversationSummary[])
}

export async function getConversation(id: number): Promise<Conversation> {
  return apiFetch<Conversation>(`/chat/conversations/${id}/`)
}

export async function createConversation(title = 'New Chat'): Promise<Conversation> {
  return apiFetch<Conversation>('/chat/conversations/', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export async function deleteConversation(id: number): Promise<void> {
  await apiFetch(`/chat/conversations/${id}/`, { method: 'DELETE' })
}

export async function getMessages(convId: number): Promise<Message[]> {
  const data = await apiFetch<{ results: Message[] }>(`/chat/conversations/${convId}/messages/`)
  return data.results || (data as unknown as Message[])
}

export async function patchMessage(convId: number, msgId: number, content: string): Promise<Message> {
  return apiFetch<Message>(`/chat/conversations/${convId}/messages/${msgId}/`, {
    method: 'PATCH',
    body: JSON.stringify({ content }),
  })
}

export async function exportMessage(convId: number, msgId: number, format: 'docx' | 'pdf'): Promise<Blob> {
  const response = await fetch(`${API_BASE}/chat/conversations/${convId}/messages/${msgId}/export/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken() || ''}`,
    },
    body: JSON.stringify({ format }),
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return response.blob()
}

export async function shareConversation(convId: number, active: boolean): Promise<string | null> {
  if (active) {
    const data = await apiFetch<{ share_url: string }>(`/chat/conversations/${convId}/share/`, {
      method: 'POST',
    })
    return data.share_url
  }
  await apiFetch(`/chat/conversations/${convId}/share/`, { method: 'DELETE' })
  return null
}

export async function streamChat(convId: number, request: StreamRequest): Promise<Response> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(`${API_BASE}/chat/conversations/${convId}/stream/`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  })
}

export async function readStream(
  response: Response,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  if (!response.body) return
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const event = JSON.parse(line.slice(6).trim()) as StreamEvent
        onEvent(event)
      } catch {
        /* skip malformed */
      }
    }
  }
}
