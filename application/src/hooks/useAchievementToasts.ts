/**
 * useAchievementToasts — surveille les runs Cyber + Academy et fire
 * un toast success quand un nouvel achievement se débloque.
 *
 * Persiste l'ensemble des achievements déjà-unlocked dans localStorage
 * (key 'aurora-achievements-seen-v1') pour ne pas re-toast au reload.
 *
 * v82dd.
 */
import { useEffect, useRef } from 'react'
import { useCyberLeaderboardStore } from '../stores/cyberLeaderboardStore'
import { useAcademyLeaderboardStore } from '../stores/academyLeaderboardStore'
import { useNotificationStore } from '../stores/notificationStore'
import { computeAchievements } from '../services/achievements'

const SEEN_KEY = 'aurora-achievements-seen-v1'
const TIERS_KEY = 'aurora-achievements-tiers-v1'
// v82dj : timestamps de first-unlock par achievement id, pour pouvoir
// compter les achievements débloqués cette semaine dans le panel
// stats. Format : Record<id, ms_epoch>.
export const UNLOCK_TIMES_KEY = 'aurora-achievements-unlock-times-v1'

// v82dh : ordre des tiers pour comparer "supérieur à"
const TIER_RANK: Record<string, number> = {
  bronze: 1, silver: 2, gold: 3, diamond: 4,
}

function readSeen(): Set<string> {
  if (typeof window === 'undefined') return new Set()
  try {
    const raw = window.localStorage.getItem(SEEN_KEY)
    if (!raw) return new Set()
    const arr = JSON.parse(raw) as string[]
    return new Set(arr)
  } catch { return new Set() }
}

function writeSeen(set: Set<string>) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(SEEN_KEY, JSON.stringify(Array.from(set)))
  } catch { /* quota */ }
}

function readTiers(): Map<string, string> {
  if (typeof window === 'undefined') return new Map()
  try {
    const raw = window.localStorage.getItem(TIERS_KEY)
    if (!raw) return new Map()
    const obj = JSON.parse(raw) as Record<string, string>
    return new Map(Object.entries(obj))
  } catch { return new Map() }
}

function writeTiers(map: Map<string, string>) {
  if (typeof window === 'undefined') return
  try {
    const obj: Record<string, string> = {}
    for (const [k, v] of map) obj[k] = v
    window.localStorage.setItem(TIERS_KEY, JSON.stringify(obj))
  } catch { /* quota */ }
}

export function useAchievementToasts() {
  const cyberRuns = useCyberLeaderboardStore((s) => s.runs)
  const academyRuns = useAcademyLeaderboardStore((s) => s.runs)
  const push = useNotificationStore((s) => s.push)
  const seenRef = useRef<Set<string>>(readSeen())
  const tiersRef = useRef<Map<string, string>>(readTiers())

  useEffect(() => {
    const achievements = computeAchievements(cyberRuns, academyRuns)
    const unlocked = achievements.filter((a) => a.unlocked)
    let dirty = false
    let tiersDirty = false
    for (const a of unlocked) {
      // 1. First-time unlock
      if (!seenRef.current.has(a.id)) {
        seenRef.current.add(a.id)
        dirty = true
        // v82dj : timestamp first-unlock pour weekly stats
        try {
          const raw = window.localStorage.getItem(UNLOCK_TIMES_KEY)
          const map = raw ? (JSON.parse(raw) as Record<string, number>) : {}
          if (!map[a.id]) {
            map[a.id] = Date.now()
            window.localStorage.setItem(UNLOCK_TIMES_KEY, JSON.stringify(map))
          }
        } catch { /* ignore */ }
        push({
          level: 'success',
          message: `${a.glyph} ${a.label} débloqué !`,
          detail: a.description,
          duration: 5000,
        })
        if (a.tier) {
          tiersRef.current.set(a.id, a.tier)
          tiersDirty = true
        }
        continue
      }
      // 2. v82dh : tier upgrade depuis le précédent
      if (a.tier) {
        const prev = tiersRef.current.get(a.id)
        const prevRank = prev ? TIER_RANK[prev] || 0 : 0
        const curRank = TIER_RANK[a.tier] || 0
        if (curRank > prevRank) {
          tiersRef.current.set(a.id, a.tier)
          tiersDirty = true
          const tierLabel = a.tier === 'diamond' ? '◆ DIAMOND'
            : a.tier === 'gold' ? '★ GOLD'
            : a.tier === 'silver' ? '✦ SILVER'
            : 'BRONZE'
          push({
            level: 'success',
            message: `${a.glyph} ${a.label} → ${tierLabel}`,
            detail: `Tier supérieur débloqué (${prev || 'aucun'} → ${a.tier}).`,
            duration: 6000,
          })
        }
      }
    }
    if (dirty) writeSeen(seenRef.current)
    if (tiersDirty) writeTiers(tiersRef.current)
  }, [cyberRuns, academyRuns, push])
}
