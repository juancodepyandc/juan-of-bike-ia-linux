/**
 * useRealAgents — fetch the user's actual 38-agent system from
 * `/api/agents/list` and cache it at module scope so multiple views
 * (V1 Cowork, V3 Cowork, Settings, etc.) share one roundtrip.
 *
 * Returns { count, leads } where leads is the array of lead-agent
 * names (3d-lead, code-lead, conversation-lead, …) and count is the
 * total agent count including sub-agents and crosscut.
 *
 * Falls back to zero state on tunnel offline / bridge KO so the UI
 * stays mountable. Components should branch on `count > 0` to decide
 * whether to render the dynamic data or a fallback.
 */
import { useEffect, useState } from 'react'
import { getBridgeUrl } from '../utils/runtime.ts'

export type AgentInfo = {
  count: number
  leads: string[]
}

let agentCache: AgentInfo | null = null

export function useRealAgents(): AgentInfo {
  const [info, setInfo] = useState<AgentInfo>(agentCache ?? { count: 0, leads: [] })
  useEffect(() => {
    if (agentCache) return
    let cancelled = false
    void (async () => {
      try {
        const res = await fetch(`${getBridgeUrl()}/api/agents/list`, {
          signal: AbortSignal.timeout(4000),
        })
        if (!res.ok) return
        const data = await res.json() as { agent_count?: number; leads?: Record<string, unknown> }
        const next: AgentInfo = {
          count: data.agent_count ?? 0,
          leads: Object.keys(data.leads ?? {}),
        }
        agentCache = next
        if (!cancelled) setInfo(next)
      } catch { /* offline tunnel — keep zero state */ }
    })()
    return () => { cancelled = true }
  }, [])
  return info
}
