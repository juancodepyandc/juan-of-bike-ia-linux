/**
 * v82ia : hook réutilisable streak créativité quotidienne par module.
 * Extrait de useImageViewLogic.imageStreak (v82i9) pour usage générique
 * Drawing / Code / Video / 3D / etc.
 *
 * Lit les timestamps des messages assistant dans moduleHistoryStore
 * (legacy histories.{module} + sessions modernes filter module).
 * Compute current + longest via le util computeStreak (v82i7).
 */
import { useMemo } from 'react'
import type { ModuleId } from '../types/app'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore'
import { computeStreak } from '../utils/streak'

export type ModuleStreak = { current: number; longest: number }

export function useModuleStreak(moduleId: ModuleId): ModuleStreak {
  const sessions = useModuleHistoryStore((s) => s.sessions)
  return useMemo(() => {
    const ts: number[] = []
    // Backward compat avec legacy histories.{module}.
    const legacy = useModuleHistoryStore.getState().histories[moduleId] || []
    for (const m of legacy) {
      if (m.role === 'assistant' && m.timestamp) ts.push(m.timestamp)
    }
    for (const s of sessions) {
      if (s.module !== moduleId) continue
      for (const m of s.messages) {
        if (m.role === 'assistant' && m.timestamp) ts.push(m.timestamp)
      }
    }
    return computeStreak(ts)
  }, [sessions, moduleId])
}
