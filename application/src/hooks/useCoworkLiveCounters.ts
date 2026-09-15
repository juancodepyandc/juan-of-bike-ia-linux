// ---------------------------------------------------------------------------
// useCoworkLiveCounters — polls the Cowork bridge for two counters that the
// user wants visible at-a-glance on the floating Cowork button:
//   - extensionsCount : number of Aurora-Connect browser extensions currently
//     polling the bridge (one extension == one Chrome window). Each extension
//     can drive multiple tabs, but a count > 0 means "I can act on tabs".
//   - mobileEventsCount : pending mobile events waiting to be consumed by the
//     planner (an iOS Shortcut / Tasker that pinged /mobile/inbound).
//
// Poll cadence : 8s — fast enough to feel live, slow enough to not hammer the
// bridge. Errors are swallowed (counters stay at the last known good value).
// ---------------------------------------------------------------------------

import { useEffect, useState } from 'react'
import { getBridgeUrl } from '../utils/runtime.ts'

export type CoworkLiveCounters = {
  extensionsCount: number
  mobileEventsCount: number
  // Min lastSeenAgoMs across active extensions (best signal for "is the
  // extension currently polling ?"). null when no extensions are tracked.
  // Used by the floating button to colour-code its status pill (green if
  // < 30s — actively polling, amber 30-60s, red if > 60s or null).
  freshestExtensionMs: number | null
  // True the very first time we receive a successful response — let callers
  // hide the badges until we know there's something to show.
  hasData: boolean
}

const INITIAL: CoworkLiveCounters = {
  extensionsCount: 0,
  mobileEventsCount: 0,
  freshestExtensionMs: null,
  hasData: false,
}

const POLL_MS = 8_000

export function useCoworkLiveCounters(active: boolean = true): CoworkLiveCounters {
  const [counters, setCounters] = useState<CoworkLiveCounters>(INITIAL)

  useEffect(() => {
    if (!active) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const tick = async () => {
      try {
        const base = getBridgeUrl()
        const [extResp, mobResp] = await Promise.allSettled([
          fetch(`${base}/api/cowork/extension/list`, { signal: AbortSignal.timeout(4_000) }),
          fetch(`${base}/api/cowork/mobile/events`, { signal: AbortSignal.timeout(4_000) }),
        ])
        let extensionsCount = 0
        let mobileEventsCount = 0
        let freshestExtensionMs: number | null = null
        if (extResp.status === 'fulfilled' && extResp.value.ok) {
          const d = await extResp.value.json() as { ok: boolean; extensions?: Array<{ extId?: string; lastSeenAgoMs?: number }> }
          if (Array.isArray(d.extensions)) {
            extensionsCount = d.extensions.length
            for (const e of d.extensions) {
              if (typeof e.lastSeenAgoMs === 'number') {
                freshestExtensionMs = freshestExtensionMs === null
                  ? e.lastSeenAgoMs
                  : Math.min(freshestExtensionMs, e.lastSeenAgoMs)
              }
            }
          }
        }
        if (mobResp.status === 'fulfilled' && mobResp.value.ok) {
          const d = await mobResp.value.json() as { ok: boolean; events?: unknown[] }
          mobileEventsCount = Array.isArray(d.events) ? d.events.length : 0
        }
        if (!cancelled) setCounters({ extensionsCount, mobileEventsCount, freshestExtensionMs, hasData: true })
      } catch {
        // Swallow — keep last known counters.
      }
      if (!cancelled) timer = setTimeout(tick, POLL_MS)
    }

    void tick()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [active])

  return counters
}
