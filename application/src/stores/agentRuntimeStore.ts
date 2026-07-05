import { create } from 'zustand'
import type { AssistantStage, ModuleId } from '../types/app'
import {
  PRODUCTION_AGENT_IDS,
  type AgentRuntimeState,
  type ProductionAgentId,
} from '../services/auroraAgents'
import type { CoworkActionEvent } from '../services/coworkTypes'

export type AgentRuntimeTool =
  | 'runtime'
  | 'chat'
  | 'cowork'
  | 'voice'
  | 'handoff'
  | 'preview'
  | 'module'

export type AgentRuntimeSlice = {
  state: AgentRuntimeState
  startedAt: number | null
  progress: number
  etaMs: number | null
  activeTool: AgentRuntimeTool | string | null
  detail: string
  collaborators: ProductionAgentId[]
  updatedAt: number
}

export type AgentHandoffLogEntry = {
  id: string
  from: ProductionAgentId
  to: ProductionAgentId
  detail: string
  at: number
}

type AgentRuntimeStore = {
  agents: Record<ProductionAgentId, AgentRuntimeSlice>
  voiceActive: boolean
  handoffLog: AgentHandoffLogEntry[]
  setAgentRuntime: (id: ProductionAgentId, patch: Partial<AgentRuntimeSlice>) => void
  setModuleRuntime: (moduleId: ModuleId, patch: Partial<AgentRuntimeSlice>) => void
  setVoiceActive: (active: boolean) => void
  recordHandoff: (from: ProductionAgentId, to: ProductionAgentId, detail: string) => void
  resetAgentRuntime: (id?: ProductionAgentId) => void
}

function clampProgress(progress: number | undefined): number {
  if (!Number.isFinite(progress)) return 0
  return Math.max(0, Math.min(100, Math.round(progress || 0)))
}

function defaultRuntime(_id: ProductionAgentId): AgentRuntimeSlice {
  return {
    state: 'idle',
    startedAt: null,
    progress: 0,
    etaMs: null,
    activeTool: null,
    detail: 'Pret.',
    collaborators: [],
    updatedAt: Date.now(),
  }
}

function createInitialAgents(): Record<ProductionAgentId, AgentRuntimeSlice> {
  return PRODUCTION_AGENT_IDS.reduce((acc, id) => {
    acc[id] = defaultRuntime(id)
    return acc
  }, {} as Record<ProductionAgentId, AgentRuntimeSlice>)
}

export function deriveEtaMs(
  startedAt: number | null | undefined,
  progress: number | null | undefined,
  fallbackMs: number | null = null,
): number | null {
  const normalized = clampProgress(progress ?? undefined)
  if (normalized >= 100) return 0
  if (!startedAt || normalized <= 1) return fallbackMs

  const elapsed = Math.max(0, Date.now() - startedAt)
  if (elapsed <= 0) return fallbackMs

  const remaining = elapsed * ((100 - normalized) / normalized)
  if (!Number.isFinite(remaining)) return fallbackMs
  return Math.max(0, Math.min(remaining, 1000 * 60 * 60 * 24))
}

export function formatEta(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return 'calcul...'
  if (ms <= 0) return '0m'
  const totalMinutes = Math.max(1, Math.ceil(ms / 60000))
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours > 0) return `${hours}h${minutes > 0 ? ` ${minutes}m` : ''}`
  return `${totalMinutes}m`
}

export function runtimePhaseToAgentState(
  phase: 'idle' | 'prepare' | 'generate' | 'cleanup' | 'done' | 'error',
): AgentRuntimeState {
  switch (phase) {
    case 'prepare':
      return 'planning'
    case 'generate':
      return 'working'
    case 'cleanup':
      return 'verifying'
    case 'done':
      return 'done'
    case 'error':
      return 'error'
    default:
      return 'idle'
  }
}

export function assistantStageToAgentState(stage: AssistantStage): AgentRuntimeState {
  switch (stage) {
    case 'understand':
      return 'thinking'
    case 'plan':
      return 'planning'
    case 'draft':
    case 'refine':
      return 'working'
    case 'verify':
      return 'verifying'
    case 'done':
      return 'done'
    case 'blocked':
    case 'error':
      return 'error'
    default:
      return 'idle'
  }
}

export function coworkEventToAgentState(event: CoworkActionEvent): AgentRuntimeState {
  if (event.kind === 'error') return 'error'
  if (event.kind === 'warn') return 'handoff'
  if (event.actionKind === 'finish') return event.kind === 'success' ? 'done' : 'verifying'
  if (event.actionKind === 'reply' || event.actionKind === 'voice_speak') return 'working'
  if (event.kind === 'success') return 'verifying'
  return event.actionKind ? 'working' : 'planning'
}

export const useAgentRuntimeStore = create<AgentRuntimeStore>()((set) => ({
  agents: createInitialAgents(),
  voiceActive: false,
  handoffLog: [],

  setAgentRuntime: (id, patch) =>
    set((state) => {
      const previous = state.agents[id] ?? defaultRuntime(id)
      const nextState = patch.state ?? previous.state
      const startedAt =
        patch.startedAt !== undefined
          ? patch.startedAt
          : previous.startedAt ?? (nextState !== 'idle' && nextState !== 'done' ? Date.now() : null)
      const progress = patch.progress !== undefined ? clampProgress(patch.progress) : previous.progress
      const etaMs = patch.etaMs !== undefined
        ? patch.etaMs
        : deriveEtaMs(startedAt, progress, previous.etaMs)

      return {
        agents: {
          ...state.agents,
          [id]: {
            ...previous,
            ...patch,
            state: nextState,
            startedAt,
            progress,
            etaMs,
            updatedAt: Date.now(),
          },
        },
      }
    }),

  setModuleRuntime: (moduleId, patch) =>
    set((state) => {
      const previous = state.agents[moduleId] ?? defaultRuntime(moduleId)
      const nextState = patch.state ?? previous.state
      const startedAt =
        patch.startedAt !== undefined
          ? patch.startedAt
          : previous.startedAt ?? (nextState !== 'idle' && nextState !== 'done' ? Date.now() : null)
      const progress = patch.progress !== undefined ? clampProgress(patch.progress) : previous.progress
      const etaMs = patch.etaMs !== undefined
        ? patch.etaMs
        : deriveEtaMs(startedAt, progress, previous.etaMs)

      return {
        agents: {
          ...state.agents,
          [moduleId]: {
            ...previous,
            ...patch,
            state: nextState,
            startedAt,
            progress,
            etaMs,
            updatedAt: Date.now(),
          },
        },
      }
    }),

  setVoiceActive: (active) => set({ voiceActive: active }),

  recordHandoff: (from, to, detail) =>
    set((state) => ({
      handoffLog: [
        ...state.handoffLog.slice(-19),
        {
          id: `handoff-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          from,
          to,
          detail,
          at: Date.now(),
        },
      ],
    })),

  resetAgentRuntime: (id) =>
    set((state) => {
      if (!id) {
        return { agents: createInitialAgents(), voiceActive: false, handoffLog: [] }
      }
      return {
        agents: {
          ...state.agents,
          [id]: defaultRuntime(id),
        },
      }
    }),
}))
