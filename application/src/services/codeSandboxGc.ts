import { fsListDir, fsRemoveDirAll } from '../hooks/useTauri.ts'
import type { CodeSandboxStepResult } from './codeSandboxTypes.ts'

export type SandboxGcPlan = {
  remove: string[]
  keep: string[]
}

export type SandboxGcOptions = {
  nowMs?: number
  maxAgeMs?: number
  maxEntries?: number
  activeName?: string | null
}

export type SandboxGcResult = {
  removed: string[]
  kept: string[]
}

const DEFAULT_MAX_AGE_MS = 24 * 60 * 60 * 1000
const DEFAULT_MAX_ENTRIES = 25
const HOST_SENTINEL_PREFIX = 'AURORA_HOST_SENTINEL_'

function timestampFromEntry(entry: string): number | null {
  if (!/^\d{12,}$/.test(entry)) return null
  const value = Number(entry)
  return Number.isSafeInteger(value) ? value : null
}

function isHostSentinelEntry(entry: string): boolean {
  return entry.startsWith(HOST_SENTINEL_PREFIX)
}

export function planSandboxGarbageCollection(
  entries: string[],
  options: SandboxGcOptions = {},
): SandboxGcPlan {
  const nowMs = options.nowMs ?? Date.now()
  const maxAgeMs = options.maxAgeMs ?? DEFAULT_MAX_AGE_MS
  const maxEntries = options.maxEntries ?? DEFAULT_MAX_ENTRIES
  const activeName = options.activeName ?? null

  const timestamped = entries
    .map((entry) => ({ entry, timestamp: timestampFromEntry(entry) }))
    .filter((item): item is { entry: string; timestamp: number } => item.timestamp !== null)
    .sort((a, b) => b.timestamp - a.timestamp)

  const keep = new Set<string>()
  const remove = new Set<string>(entries.filter(isHostSentinelEntry))

  for (let index = 0; index < timestamped.length; index += 1) {
    const { entry, timestamp } = timestamped[index]
    if (entry === activeName) {
      keep.add(entry)
      continue
    }
    if (nowMs - timestamp > maxAgeMs || index >= maxEntries) {
      remove.add(entry)
    } else {
      keep.add(entry)
    }
  }

  for (const entry of entries) {
    if (!remove.has(entry) && !keep.has(entry)) keep.add(entry)
  }

  return {
    remove: [...remove],
    keep: [...keep],
  }
}

export async function collectCodeSandboxGarbage(
  sandboxBasePath: string,
  options: SandboxGcOptions = {},
  fs = {
    listDir: fsListDir,
    removeDirAll: fsRemoveDirAll,
  },
): Promise<SandboxGcResult> {
  const entries = await fs.listDir(sandboxBasePath)
  const plan = planSandboxGarbageCollection(entries, options)

  for (const entry of plan.remove) {
    await fs.removeDirAll(`${sandboxBasePath}/${entry}`)
  }

  return {
    removed: plan.remove,
    kept: plan.keep,
  }
}

export function buildSandboxGcStep(result: SandboxGcResult): CodeSandboxStepResult {
  return {
    label: 'GC sandboxes WS7',
    command: 'internal:sandbox-gc',
    ok: true,
    output: `removed=${result.removed.length}\nkept=${result.kept.length}\n${result.removed.join('\n')}`,
  }
}
