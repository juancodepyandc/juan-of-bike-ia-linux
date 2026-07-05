export type ChatMessage = { role: 'system' | 'user' | 'assistant'; content: string; images?: string[] }

export type CoworkSession = {
  id: string
  title: string
  createdAt: string
  lastUsedAt: string | null
  messages: ChatMessage[]
  metadata?: Record<string, unknown>
  tempFiles?: string[]
}

export type CoworkSessionStore = {
  version: number
  sessions: CoworkSession[]
}

export const COWORK_SESSION_STORE_VERSION = 1

let store: CoworkSessionStore = { version: COWORK_SESSION_STORE_VERSION, sessions: [] }

function createSessionId(): string {
  const cryptoRef = globalThis.crypto
  if (cryptoRef?.randomUUID) return `sess_${cryptoRef.randomUUID()}`

  const entropy = `${Date.now()}-${Math.random()}-${store.sessions.length}`
  let hash = 0
  for (let i = 0; i < entropy.length; i += 1) {
    hash = (Math.imul(31, hash) + entropy.charCodeAt(i)) | 0
  }
  return `sess_${Date.now().toString(36)}_${Math.abs(hash).toString(36)}`
}

export function createSessionStore(): CoworkSessionStore {
  store = { version: COWORK_SESSION_STORE_VERSION, sessions: [] }
  return store
}

export function listSessions(): CoworkSession[] {
  return store.sessions.slice()
}

export function getSession(id: string): CoworkSession | undefined {
  return store.sessions.find((s) => s.id === id)
}

export function createSession(opts?: { title?: string; messages?: ChatMessage[]; metadata?: Record<string, unknown> }): CoworkSession {
  const id = createSessionId()
  const now = new Date().toISOString()
  const session: CoworkSession = {
    id,
    title: opts?.title ?? `Session ${store.sessions.length + 1}`,
    createdAt: now,
    lastUsedAt: now,
    messages: opts?.messages ?? [],
    metadata: opts?.metadata,
    tempFiles: [],
  }
  store.sessions.push(session)
  return session
}

export function updateSessionMessages(id: string, messages: ChatMessage[]): CoworkSession | undefined {
  const s = getSession(id)
  if (!s) return undefined
  s.messages = messages
  s.lastUsedAt = new Date().toISOString()
  return s
}

export function pushSessionMessage(id: string, message: ChatMessage): CoworkSession | undefined {
  const s = getSession(id)
  if (!s) return undefined
  s.messages.push(message)
  s.lastUsedAt = new Date().toISOString()
  return s
}

export function attachTempFile(id: string, relativePath: string): CoworkSession | undefined {
  const s = getSession(id)
  if (!s) return undefined
  s.tempFiles = s.tempFiles ?? []
  if (!s.tempFiles.includes(relativePath)) s.tempFiles.push(relativePath)
  s.lastUsedAt = new Date().toISOString()
  return s
}

export function removeSession(id: string): boolean {
  const before = store.sessions.length
  store.sessions = store.sessions.filter((s) => s.id !== id)
  return store.sessions.length < before
}

export function clearAllSessions(): void {
  store.sessions = []
}

export function exportStore(): CoworkSessionStore {
  return JSON.parse(JSON.stringify(store))
}

export function importStore(input: CoworkSessionStore): void {
  if (!input || !Array.isArray(input.sessions)) return
  store = { version: COWORK_SESSION_STORE_VERSION, sessions: input.sessions }
}

async function getBridgeRoot(): Promise<string> {
  try {
    const mod = await import('../utils/runtime')
    return mod.getBridgeUrl()
  } catch {
    return ''
  }
}

export async function remoteListSessions(): Promise<{ ok: boolean; sessions?: CoworkSession[]; warnings?: string[] }>{
  try {
    const root = await getBridgeRoot()
    if (!root) return { ok: false, warnings: ['bridge_unavailable'] }
    const resp = await fetch(`${root}/api/cowork/session/list`)
    const data = await resp.json()
    return data
  } catch (err) {
    return { ok: false, warnings: [String(err instanceof Error ? err.message : err)] }
  }
}

export async function remoteCreateSession(title?: string): Promise<{ ok: boolean; session?: CoworkSession; warnings?: string[] }>{
  try {
    const root = await getBridgeRoot()
    if (!root) return { ok: false, warnings: ['bridge_unavailable'] }
    const resp = await fetch(`${root}/api/cowork/session/create`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title })
    })
    const data = await resp.json()
    return data
  } catch (err) {
    return { ok: false, warnings: [String(err instanceof Error ? err.message : err)] }
  }
}

export async function remoteRemoveSession(id: string): Promise<{ ok: boolean; warnings?: string[] }>{
  try {
    const root = await getBridgeRoot()
    if (!root) return { ok: false, warnings: ['bridge_unavailable'] }
    const resp = await fetch(`${root}/api/cowork/session/remove`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sessionId: id })
    })
    const data = await resp.json()
    return data
  } catch (err) {
    return { ok: false, warnings: [String(err instanceof Error ? err.message : err)] }
  }
}

export async function remoteListFiles(id: string): Promise<{ ok: boolean; files?: string[]; warnings?: string[] }>{
  try {
    const root = await getBridgeRoot()
    if (!root) return { ok: false, warnings: ['bridge_unavailable'] }
    const resp = await fetch(`${root}/api/cowork/session/list_files?sessionId=${encodeURIComponent(id)}`)
    const data = await resp.json()
    return data
  } catch (err) {
    return { ok: false, warnings: [String(err instanceof Error ? err.message : err)] }
  }
}

export async function remoteWriteFile(sessionId: string, filename: string, content: string): Promise<{ ok: boolean; warnings?: string[] }>{
  try {
    const root = await getBridgeRoot()
    if (!root) return { ok: false, warnings: ['bridge_unavailable'] }
    const resp = await fetch(`${root}/api/cowork/session/write`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sessionId, filename, content })
    })
    const data = await resp.json()
    return data
  } catch (err) {
    return { ok: false, warnings: [String(err instanceof Error ? err.message : err)] }
  }
}

export async function remoteReadFile(sessionId: string, filename: string): Promise<{ ok: boolean; content?: string; warnings?: string[] }>{
  try {
    const root = await getBridgeRoot()
    if (!root) return { ok: false, warnings: ['bridge_unavailable'] }
    const resp = await fetch(`${root}/api/cowork/session/read?sessionId=${encodeURIComponent(sessionId)}&filename=${encodeURIComponent(filename)}`)
    const data = await resp.json()
    return data
  } catch (err) {
    return { ok: false, warnings: [String(err instanceof Error ? err.message : err)] }
  }
}
