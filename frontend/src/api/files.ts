import { apiFetch } from './client'
import type { UploadedFile } from '../types'

export interface UploadPayload {
  file: File
  file_type: string
  original_name: string
  conversation: number
}

export async function uploadFile(payload: UploadPayload): Promise<UploadedFile> {
  const fd = new FormData()
  fd.append('file', payload.file)
  fd.append('file_type', payload.file_type)
  fd.append('original_name', payload.original_name)
  fd.append('conversation', String(payload.conversation))
  const data = await apiFetch<UploadedFile>('/files/upload/', {
    method: 'POST',
    body: fd,
  })
  return data
}

export function guessFileType(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  if (['pdf'].includes(ext)) return 'pdf'
  if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'].includes(ext)) return 'image'
  if (['doc', 'docx', 'txt', 'csv', 'md'].includes(ext)) return 'doc'
  if (['mp3', 'wav', 'ogg', 'flac'].includes(ext)) return 'audio'
  return 'other'
}
