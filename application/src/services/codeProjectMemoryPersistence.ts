import type { CodeFile } from './codeOrchestrator.ts'
import {
  type CodeProjectMemory,
  type CodeProjectMemoryFile,
  buildCodeProjectMemory,
} from './codeProjectMemory.ts'

export const CODE_PROJECT_MEMORY_SCHEMA_VERSION = 'aurora.code.project-memory/1'

export type CodeProjectMemorySnapshot = {
  schemaVersion: typeof CODE_PROJECT_MEMORY_SCHEMA_VERSION
  fingerprint: string
  createdAt: number
  files: CodeProjectMemoryFile[]
}

export type CodeProjectMemoryStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

function normalizePath(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').toLowerCase()
}

function hashText(input: string) {
  let hash = 2166136261
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

export function fingerprintCodeFiles(files: CodeFile[]) {
  const payload = files
    .map((file) => `${normalizePath(file.name)}\0${file.language}\0${file.content.length}\0${hashText(file.content)}`)
    .sort()
    .join('\n')
  return hashText(payload)
}

export function createCodeProjectMemorySnapshot(files: CodeFile[], now = Date.now()): CodeProjectMemorySnapshot {
  return {
    schemaVersion: CODE_PROJECT_MEMORY_SCHEMA_VERSION,
    fingerprint: fingerprintCodeFiles(files),
    createdAt: now,
    files: buildCodeProjectMemory(files).files,
  }
}

export function restoreCodeProjectMemorySnapshot(snapshot: CodeProjectMemorySnapshot): CodeProjectMemory {
  return {
    files: snapshot.files,
    byPath: new Map(snapshot.files.map((file) => [normalizePath(file.path), file])),
  }
}

export function parseCodeProjectMemorySnapshot(raw: string | null): CodeProjectMemorySnapshot | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<CodeProjectMemorySnapshot>
    if (parsed.schemaVersion !== CODE_PROJECT_MEMORY_SCHEMA_VERSION) return null
    if (typeof parsed.fingerprint !== 'string' || typeof parsed.createdAt !== 'number') return null
    if (!Array.isArray(parsed.files)) return null
    return parsed as CodeProjectMemorySnapshot
  } catch {
    return null
  }
}

function defaultStorage(): CodeProjectMemoryStorage | null {
  try {
    return typeof globalThis.localStorage === 'object' ? globalThis.localStorage : null
  } catch {
    return null
  }
}

function keyForFingerprint(fingerprint: string) {
  return `aurora:code:project-memory:${fingerprint}`
}

export function loadOrBuildCodeProjectMemory(
  files: CodeFile[],
  storage: CodeProjectMemoryStorage | null = defaultStorage(),
): CodeProjectMemory {
  const fingerprint = fingerprintCodeFiles(files)
  const key = keyForFingerprint(fingerprint)
  const cached = parseCodeProjectMemorySnapshot(storage?.getItem(key) ?? null)
  if (cached?.fingerprint === fingerprint) return restoreCodeProjectMemorySnapshot(cached)

  const snapshot = createCodeProjectMemorySnapshot(files)
  try { storage?.setItem(key, JSON.stringify(snapshot)) } catch { /* storage quota or privacy mode */ }
  return restoreCodeProjectMemorySnapshot(snapshot)
}
