export interface User {
  id: number
  username: string
  email: string
  avatar: string
  bio: string
  settings: Record<string, unknown>
  created_at: string
}

export interface ConversationSummary {
  id: number
  title: string
  last_message: string | null
  message_count: number
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  tokens_used: number
  created_at: string
}

export interface Conversation {
  id: number
  title: string
  messages: Message[]
  message_count: number
  created_at: string
  updated_at: string
}

export interface EvidenceItem {
  title: string
  url: string
  published_date?: string
}

export interface Citation {
  index: number
  url: string
  title: string
}

export interface CoverageInfo {
  required: string[]
  found: string[]
  missing: string[]
}

export interface SearchEvent {
  count: number
  intent?: string
  coverage?: CoverageInfo
  evidence?: EvidenceItem[]
}

export interface SummaryEvent {
  sources: number
  fields_verified: number
  confidence: Record<string, number>
  top_domains: string[]
}

export interface TimingsEvent {
  planner_ms: number
  search_ms: number
  extract_ms: number
  generation_ms: number
  total_ms: number
}

export interface DoneEvent {
  message_id: number
}

export interface ToolUseEvent {
  tool: string
  label: string
  args: Record<string, string>
}

export interface StreamEvent {
  analysis?: string[]
  search?: SearchEvent
  citations?: Citation[]
  summary?: SummaryEvent
  timings?: TimingsEvent
  token?: string
  done?: DoneEvent
  tool_use?: ToolUseEvent
  stage?: string
}

export interface UploadedFile {
  id: number
  name: string
  file_type: string
  size: number
}

export interface AuthTokens {
  access: string
  refresh: string
}
