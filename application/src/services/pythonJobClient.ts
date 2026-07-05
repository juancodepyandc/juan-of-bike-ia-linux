/**
 * Thin client for the bridge's async Python job endpoints.
 *
 *   POST /api/python/run-async    → returns { jobId }
 *   GET  /api/python/job/<id>     → returns { status, output, error, exitCode }
 *
 * Why this exists:
 * The default `runPythonScript` hides the jobId inside a single promise. When
 * the tab is killed mid-run (iOS backgrounding, Vite HMR, manual reload…),
 * the promise dies and we lose the ability to reattach to the subprocess
 * that is still happily running on the PC bridge.
 *
 * This module keeps the jobId at the call-site so it can be persisted in the
 * Forge queue store and resumed after a reload.
 */
import { getBridgeUrl, isTauriRuntime } from '../utils/runtime.ts'

export interface PythonJobStatus {
  jobId: string
  status: 'queued' | 'running' | 'done' | 'unknown'
  output: string
  error: string
  exitCode: number
}

function baseUrl(): string {
  return getBridgeUrl() || ''
}

/**
 * Launch a Python script asynchronously and return the jobId immediately.
 * The subprocess keeps running on the bridge regardless of tab lifecycle.
 * On Tauri we fall back to the existing synchronous pathway (the tauri shell
 * owns the subprocess and is not subject to web-tab lifecycles).
 */
/** Translate a raw fetch failure into a human-readable reason. Safari turns
 * every network-layer failure into `TypeError: Load failed`, which is what
 * the user saw in the Forge notification — replace it with something that
 * tells them *why* it failed (bridge off, tunnel broken, CORS…). */
function friendlyFetchError(err: unknown, label: string): Error {
  const msg = err instanceof Error ? err.message : String(err)
  if (/Load failed|Failed to fetch|NetworkError|TypeError: (Network|Load)/i.test(msg)) {
    return new Error(
      `${label} : bridge Python injoignable. ` +
      `Démarre le bridge sur le PC (port 3001) ou vérifie le tunnel Cloudflare.`,
    )
  }
  return new Error(`${label} : ${msg}`)
}

export async function launchPythonJob(
  scriptPath: string,
  args: string[],
): Promise<string> {
  if (isTauriRuntime()) {
    // Tauri keeps state on the native side; synthesize a pseudo-jobId so the
    // caller treats the two modes uniformly. The resume path short-circuits
    // on Tauri because the backend keeps going regardless.
    return `tauri:${scriptPath}:${Date.now().toString(36)}`
  }
  const base = baseUrl()
  let resp: Response
  try {
    resp = await fetch(`${base}/api/python/run-async`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scriptPath, args }),
    })
  } catch (err) {
    throw friendlyFetchError(err, `launchPythonJob(${scriptPath})`)
  }
  if (!resp.ok) {
    const txt = await resp.text().catch(() => '')
    throw new Error(`launchPythonJob HTTP ${resp.status}: ${txt.slice(0, 200)}`)
  }
  const data = await resp.json() as { ok: boolean; jobId?: string; error?: string }
  if (!data.ok || !data.jobId) {
    throw new Error(data.error || 'bridge did not return a jobId')
  }
  return data.jobId
}

/** One-shot status check (no polling) — used to discover if a previously
 * launched job has already finished on the bridge while the tab was dead. */
export async function fetchPythonJob(jobId: string): Promise<PythonJobStatus> {
  if (jobId.startsWith('tauri:')) {
    // No stored state on the Tauri side — treat as "unknown" and re-run.
    return { jobId, status: 'unknown', output: '', error: '', exitCode: -1 }
  }
  const base = baseUrl()
  try {
    const resp = await fetch(`${base}/api/python/job/${jobId}`)
    if (!resp.ok) {
      // 404 = bridge gc'd the job (older than 1h typically), treat as unknown
      return { jobId, status: 'unknown', output: '', error: '', exitCode: -1 }
    }
    const data = await resp.json() as {
      status?: string
      output?: string
      error?: string
      exitCode?: number
    }
    return {
      jobId,
      status: (data.status as PythonJobStatus['status']) ?? 'unknown',
      output: data.output ?? '',
      error: data.error ?? '',
      exitCode: typeof data.exitCode === 'number' ? data.exitCode : -1,
    }
  } catch {
    return { jobId, status: 'unknown', output: '', error: '', exitCode: -1 }
  }
}

/**
 * Poll a running Python job until it finishes. Re-emits PROGRESS:pct:detail
 * lines to the caller via `onProgress` as they become visible through the
 * bridge's `/api/python/progress` event stream.
 */
export async function waitForPythonJob(
  jobId: string,
  opts: {
    onProgress?: (line: string) => void
    /** Poll interval in ms (default 2500) */
    intervalMs?: number
    /** Max total time before giving up (default 2h) */
    maxMs?: number
  } = {},
): Promise<PythonJobStatus> {
  const { onProgress, intervalMs = 2500, maxMs = 2 * 60 * 60 * 1000 } = opts
  const base = baseUrl()
  const start = Date.now()
  let progressCursor = 0

  let consecutiveUnknown = 0
  while (true) {
    if (Date.now() - start > maxMs) {
      throw new Error(`waitForPythonJob: timeout after ${Math.round(maxMs / 1000)}s`)
    }
    await new Promise((r) => setTimeout(r, intervalMs))

    // Drain any fresh PROGRESS lines emitted since last poll.
    if (onProgress) {
      try {
        const r = await fetch(`${base}/api/python/progress?since=${progressCursor}`)
        if (r.ok) {
          const ct = r.headers.get('content-type') || ''
          if (!ct.includes('text/html')) {
            const d = await r.json() as { events?: string[]; cursor?: number }
            for (const ev of d.events || []) onProgress(ev)
            if (typeof d.cursor === 'number') progressCursor = d.cursor
          }
        }
      } catch { /* transient network — ignore */ }
    }

    // Check job status
    const status = await fetchPythonJob(jobId)
    if (status.status === 'done') return status
    if (status.status === 'unknown') {
      // Tolerate a single transient 404 / bridge restart, but bail after a
      // handful of consecutive misses so the user sees a real error instead
      // of watching the overlay spin forever.
      consecutiveUnknown += 1
      if (consecutiveUnknown >= 4) {
        throw new Error(
          `Bridge Python injoignable après ${consecutiveUnknown} tentatives (jobId=${jobId.slice(0, 16)}…). ` +
          `Assure-toi que le bridge tourne sur le PC (port 3001) ou relance la forge.`,
        )
      }
      continue
    }
    consecutiveUnknown = 0
    // status === 'queued' | 'running' → keep polling
  }
}

/** Lightweight availability probe — used by UI overlays to gate a run button
 * behind "bridge is reachable" without having to parse an error. */
export async function isBridgeReachable(timeoutMs = 3000): Promise<boolean> {
  if (isTauriRuntime()) return true
  const base = baseUrl()
  try {
    const resp = await fetch(`${base}/api/ping`, {
      method: 'GET',
      signal: AbortSignal.timeout(timeoutMs),
    })
    return resp.ok
  } catch {
    return false
  }
}
