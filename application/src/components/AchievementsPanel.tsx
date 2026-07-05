/**
 * AchievementsPanel — affichage compact des badges débloqués / locked.
 * Utilisable dans Cyber V1 ou Academy V1 avec un filter category.
 *
 * v82bz.
 */
import { useEffect, useMemo, useState } from 'react'
import { useCyberLeaderboardStore } from '../stores/cyberLeaderboardStore'
import { useAcademyLeaderboardStore } from '../stores/academyLeaderboardStore'
import { computeAchievements, countUnlocked, currentStreak, type Achievement, type AchievementCategory } from '../services/achievements'
import { UNLOCK_TIMES_KEY } from '../hooks/useAchievementToasts'
import Sparkline from './Sparkline'

const GOLD = 'oklch(0.74 0.13 60)'
const DIM = 'var(--fg-mute, #777)'
// v82en : choix utilisateur du nombre de milestones affichés
const TOP_MILESTONES_KEY = 'aurora-top-milestones-count-v1'
const VALID_COUNTS = [1, 3, 5] as const
type MilestoneCount = (typeof VALID_COUNTS)[number]
const readTopMilestonesCount = (): MilestoneCount => {
  if (typeof window === 'undefined') return 3
  try {
    const raw = window.localStorage.getItem(TOP_MILESTONES_KEY)
    const n = raw ? parseInt(raw, 10) : 3
    return (VALID_COUNTS as readonly number[]).includes(n) ? (n as MilestoneCount) : 3
  } catch { return 3 }
}
// v82eo : prefs unifiées d'affichage AchievementsPanel
const DISPLAY_PREFS_KEY = 'aurora-achievements-display-prefs-v1'
type DisplayPrefs = {
  showLadders: boolean
  showTrend: boolean
  showWeeklyRibbon: boolean
  showMilestones: boolean
}
const DEFAULT_PREFS: DisplayPrefs = {
  showLadders: true, showTrend: true,
  showWeeklyRibbon: true, showMilestones: true,
}
const readDisplayPrefs = (): DisplayPrefs => {
  if (typeof window === 'undefined') return DEFAULT_PREFS
  try {
    const raw = window.localStorage.getItem(DISPLAY_PREFS_KEY)
    if (!raw) return DEFAULT_PREFS
    const obj = JSON.parse(raw) as Partial<DisplayPrefs>
    return { ...DEFAULT_PREFS, ...obj }
  } catch { return DEFAULT_PREFS }
}
// v82ea : objectif perso hebdomadaire (target + scope)
const WEEKLY_GOAL_KEY = 'aurora-weekly-goal-v1'
type WeeklyGoalScope = 'all' | 'cyber' | 'academy'
type WeeklyGoal = { target: number; scope: WeeklyGoalScope }
const readWeeklyGoal = (): WeeklyGoal | null => {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(WEEKLY_GOAL_KEY)
    if (!raw) return null
    const obj = JSON.parse(raw) as Partial<WeeklyGoal>
    if (typeof obj.target !== 'number' || obj.target < 1) return null
    const scope: WeeklyGoalScope = obj.scope === 'cyber' || obj.scope === 'academy' ? obj.scope : 'all'
    return { target: Math.min(200, Math.max(1, Math.round(obj.target))), scope }
  } catch { return null }
}
// v82eq : presets custom user-définis (au-delà des 3 hardcoded)
const CUSTOM_PRESETS_KEY = 'aurora-achievements-display-custom-presets-v1'
type CustomPresets = Record<string, DisplayPrefs>
const readCustomPresets = (): CustomPresets => {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(CUSTOM_PRESETS_KEY)
    return raw ? (JSON.parse(raw) as CustomPresets) : {}
  } catch { return {} }
}

interface Props {
  filter?: AchievementCategory[]   // undefined = all
  compact?: boolean                // affiche juste les unlocked si true
}

export default function AchievementsPanel({ filter, compact = false }: Props) {
  const cyberRuns = useCyberLeaderboardStore((s) => s.runs)
  const academyRuns = useAcademyLeaderboardStore((s) => s.runs)
  // v82en : nombre de milestones à afficher (cyclique 1 → 3 → 5)
  const [milestonesCount, setMilestonesCount] = useState<MilestoneCount>(readTopMilestonesCount)
  useEffect(() => {
    if (typeof window === 'undefined') return
    try { window.localStorage.setItem(TOP_MILESTONES_KEY, String(milestonesCount)) } catch { /* ignore */ }
  }, [milestonesCount])
  const cycleMilestonesCount = () => {
    setMilestonesCount((c) => {
      const idx = VALID_COUNTS.indexOf(c)
      return VALID_COUNTS[(idx + 1) % VALID_COUNTS.length]
    })
  }
  // v82eo : prefs affichage des sections (ladders, trend, ribbon, milestones)
  const [prefs, setPrefs] = useState<DisplayPrefs>(readDisplayPrefs)
  useEffect(() => {
    if (typeof window === 'undefined') return
    try { window.localStorage.setItem(DISPLAY_PREFS_KEY, JSON.stringify(prefs)) } catch { /* ignore */ }
  }, [prefs])
  const togglePref = (k: keyof DisplayPrefs) =>
    setPrefs((p) => ({ ...p, [k]: !p[k] }))
  // v82ea : weekly goal state + persist
  const [weeklyGoal, setWeeklyGoal] = useState<WeeklyGoal | null>(readWeeklyGoal)
  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      if (weeklyGoal === null) window.localStorage.removeItem(WEEKLY_GOAL_KEY)
      else window.localStorage.setItem(WEEKLY_GOAL_KEY, JSON.stringify(weeklyGoal))
    } catch { /* ignore */ }
  }, [weeklyGoal])
  const setGoalTarget = () => {
    const cur = weeklyGoal?.target ?? 5
    const raw = window.prompt('Objectif perso hebdomadaire (nombre de runs) :', String(cur))
    if (raw === null) return
    const n = parseInt(raw, 10)
    if (!isFinite(n) || n < 1) { setWeeklyGoal(null); return }
    setWeeklyGoal({
      target: Math.min(200, Math.max(1, n)),
      scope: weeklyGoal?.scope ?? 'all',
    })
  }
  const cycleGoalScope = () => {
    if (!weeklyGoal) return
    const order: WeeklyGoalScope[] = ['all', 'cyber', 'academy']
    const idx = order.indexOf(weeklyGoal.scope)
    setWeeklyGoal({ ...weeklyGoal, scope: order[(idx + 1) % order.length] })
  }

  // v82eq : custom presets state + persist
  const [customPresets, setCustomPresets] = useState<CustomPresets>(readCustomPresets)
  useEffect(() => {
    if (typeof window === 'undefined') return
    try { window.localStorage.setItem(CUSTOM_PRESETS_KEY, JSON.stringify(customPresets)) } catch { /* ignore */ }
  }, [customPresets])
  const saveCurrentAsPreset = () => {
    const name = window.prompt('Nom du preset à sauver (max 24 char) :')
    if (!name) return
    const trimmed = name.trim().slice(0, 24)
    if (!trimmed) return
    setCustomPresets((p) => ({ ...p, [trimmed]: { ...prefs } }))
  }
  const deleteCustomPreset = (name: string) => {
    setCustomPresets((p) => {
      const { [name]: _drop, ...rest } = p
      void _drop
      return rest
    })
  }
  // v82er : rename d'un preset custom via prompt natif.
  // Skip si même nom ou collision avec un preset existant.
  const renameCustomPreset = (oldName: string) => {
    const next = window.prompt(`Renommer le preset « ${oldName} » :`, oldName)
    if (next === null) return
    const trimmed = next.trim().slice(0, 24)
    if (!trimmed || trimmed === oldName) return
    setCustomPresets((p) => {
      if (Object.prototype.hasOwnProperty.call(p, trimmed)) {
        // Collision : avorte sans changer (l'utilisateur peut delete d'abord)
        return p
      }
      const { [oldName]: moved, ...rest } = p
      return { ...rest, [trimmed]: moved }
    })
  }
  const achievements = useMemo<Achievement[]>(
    () => computeAchievements(cyberRuns, academyRuns),
    [cyberRuns, academyRuns],
  )
  const filtered = filter
    ? achievements.filter((a) => filter.includes(a.category))
    : achievements
  const stats = countUnlocked(filtered)

  // v82ct : stats hebdomadaires + totales selon filter category.
  // Lundi 00:00 du lundi de cette semaine ISO.
  const weeklyStats = useMemo(() => {
    const now = new Date()
    const day = now.getDay() === 0 ? 6 : now.getDay() - 1 // lundi=0
    const monday = new Date(now)
    monday.setHours(0, 0, 0, 0)
    monday.setDate(monday.getDate() - day)
    const t0 = monday.getTime()
    const wantsCyber = !filter || filter.includes('cyber') || filter.includes('cross')
    const wantsAcademy = !filter || filter.includes('academy') || filter.includes('cross')
    const cyberWk = wantsCyber ? cyberRuns.filter((r) => r.startedAt >= t0) : []
    const academyWk = wantsAcademy ? academyRuns.filter((r) => r.startedAt >= t0) : []
    const cyberAll = wantsCyber ? cyberRuns : []
    const academyAll = wantsAcademy ? academyRuns : []
    const sumMs = (rs: { durationMs: number }[]) => rs.reduce((a, r) => a + r.durationMs, 0)
    const avgScore = (rs: { score?: number }[]) => {
      const ss = rs.map((r) => r.score ?? 0).filter((s) => s > 0)
      return ss.length === 0 ? 0 : Math.round(ss.reduce((a, b) => a + b, 0) / ss.length)
    }
    // v82dj : achievements débloqués cette semaine (depuis lundi)
    let badgesWeek = 0
    if (typeof window !== 'undefined') {
      try {
        const raw = window.localStorage.getItem(UNLOCK_TIMES_KEY)
        if (raw) {
          const map = JSON.parse(raw) as Record<string, number>
          // Filtre selon les achievements visibles (catégorie filter)
          const visibleIds = new Set(filtered.map((a) => a.id))
          for (const [id, ts] of Object.entries(map)) {
            if (visibleIds.has(id) && ts >= t0) badgesWeek++
          }
        }
      } catch { /* ignore */ }
    }
    // v82dk : sparkline des derniers scores (max 30 runs visibles)
    const allMixed = [...cyberAll, ...academyAll]
      .filter((r) => (r.score ?? 0) > 0)
      .sort((a, b) => a.startedAt - b.startedAt)
      .slice(-30)
    const sparkValues = allMixed.map((r) => r.score ?? 0)
    return {
      weekCount: cyberWk.length + academyWk.length,
      weekMin: Math.round((sumMs(cyberWk) + sumMs(academyWk)) / 60000),
      weekAvg: avgScore([...cyberWk, ...academyWk]),
      totalCount: cyberAll.length + academyAll.length,
      totalBest: Math.max(0, ...cyberAll.map((r) => r.score ?? 0), ...academyAll.map((r) => r.score)),
      badgesWeek,
      sparkValues,
    }
  }, [cyberRuns, academyRuns, filter, filtered])

  // v82ei : nombre d'achievements débloqués par semaine sur les
  // 8 dernières semaines ISO. Bar chart trend pour visualiser la
  // courbe d'engagement long-terme.
  const unlocksTrend = useMemo(() => {
    if (typeof window === 'undefined') return { weeks: [], max: 0 }
    const now = new Date()
    const day = now.getDay() === 0 ? 6 : now.getDay() - 1
    const monday = new Date(now)
    monday.setHours(0, 0, 0, 0)
    monday.setDate(monday.getDate() - day)
    const weekStarts: number[] = []
    for (let i = 7; i >= 0; i--) {
      const ws = new Date(monday)
      ws.setDate(ws.getDate() - i * 7)
      weekStarts.push(ws.getTime())
    }
    let map: Record<string, number> = {}
    try {
      const raw = window.localStorage.getItem(UNLOCK_TIMES_KEY)
      if (raw) map = JSON.parse(raw) as Record<string, number>
    } catch { /* ignore */ }
    const visibleIds = new Set(filtered.map((a) => a.id))
    const counts = weekStarts.map((ws, i) => {
      const we = i < weekStarts.length - 1 ? weekStarts[i + 1] : Number.POSITIVE_INFINITY
      let n = 0
      for (const [id, ts] of Object.entries(map)) {
        if (visibleIds.has(id) && ts >= ws && ts < we) n++
      }
      return { ws, count: n }
    })
    const max = Math.max(0, ...counts.map((c) => c.count))
    return { weeks: counts, max }
  }, [filtered])

  // v82el : top 3 next milestones — locked achievements avec ratio
  // progress.current / target le plus élevé. Mini-grid au lieu d'un
  // seul palier pour donner 3 objectifs à viser en parallèle.
  const topMilestones = useMemo(() => {
    const cands: { ach: Achievement; ratio: number }[] = []
    for (const a of filtered) {
      if (a.unlocked || !a.progress || a.progress.target <= 0) continue
      const ratio = a.progress.current / a.progress.target
      if (ratio <= 0 || ratio >= 1) continue
      cands.push({ ach: a, ratio })
    }
    cands.sort((a, b) => b.ratio - a.ratio)
    return cands.slice(0, milestonesCount)
  }, [filtered, milestonesCount])

  // v82eh : achievements unlocked cette semaine, triés par ts asc.
  // Liste affichée comme timeline ribbon au-dessus du grid principal.
  const weeklyUnlocks = useMemo(() => {
    if (typeof window === 'undefined') return [] as { ach: Achievement; ts: number }[]
    const now = new Date()
    const day = now.getDay() === 0 ? 6 : now.getDay() - 1
    const monday = new Date(now)
    monday.setHours(0, 0, 0, 0)
    monday.setDate(monday.getDate() - day)
    const t0 = monday.getTime()
    try {
      const raw = window.localStorage.getItem(UNLOCK_TIMES_KEY)
      if (!raw) return []
      const map = JSON.parse(raw) as Record<string, number>
      const visibleIds = new Set(filtered.map((a) => a.id))
      const idIndex = new Map(achievements.map((a) => [a.id, a]))
      const out: { ach: Achievement; ts: number }[] = []
      for (const [id, ts] of Object.entries(map)) {
        if (!visibleIds.has(id) || ts < t0) continue
        const ach = idIndex.get(id)
        if (ach && ach.unlocked) out.push({ ach, ts })
      }
      out.sort((a, b) => a.ts - b.ts)
      return out
    } catch {
      return []
    }
  }, [achievements, filtered])

  return (
    <div style={{
      padding: 10,
      background: 'oklch(0.74 0.13 60 / 0.06)',
      border: '1px solid oklch(0.74 0.13 60 / 0.3)',
      borderRadius: 8,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8,
        fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
        letterSpacing: '0.14em', textTransform: 'uppercase',
        color: GOLD,
      }}>
        <span>🏆 Trophées</span>
        <span style={{ flex: 1 }} />
        {/* v82da : current streak prominently displayed quand > 0 */}
        {currentStreak(cyberRuns, academyRuns) > 0 && (
          <span style={{
            color: 'oklch(0.72 0.14 25)', // ember red
            fontWeight: 700,
            background: 'oklch(0.72 0.14 25 / 0.15)',
            padding: '1px 6px', borderRadius: 99,
          }}>🔥 streak {currentStreak(cyberRuns, academyRuns)} jour(s)</span>
        )}
        <span>{stats.unlocked}/{stats.total}</span>
      </div>

      {/* v82eo : toggles row pour show/hide ladders / trend / ribbon /
          milestones. Persisté via DISPLAY_PREFS_KEY.
          v82ep : 3 preset buttons "tout / compact / minimal" pour
          basculer plusieurs toggles d'un coup. */}
      <div style={{
        marginBottom: 6, padding: '2px 0',
        display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center',
        fontFamily: 'var(--font-mono, monospace)', fontSize: 8,
      }}>
        <span style={{ color: DIM, letterSpacing: '0.14em', textTransform: 'uppercase', marginRight: 4 }}>
          afficher
        </span>
        {([
          {
            id: 'all',
            label: 'tout',
            prefs: { showLadders: true, showTrend: true, showWeeklyRibbon: true, showMilestones: true } as DisplayPrefs,
          },
          {
            id: 'compact',
            label: 'compact',
            prefs: { showLadders: true, showTrend: false, showWeeklyRibbon: false, showMilestones: true } as DisplayPrefs,
          },
          {
            id: 'minimal',
            label: 'minimal',
            prefs: { showLadders: false, showTrend: false, showWeeklyRibbon: false, showMilestones: false } as DisplayPrefs,
          },
        ]).map((preset) => {
          const active = (Object.keys(preset.prefs) as (keyof DisplayPrefs)[])
            .every((k) => prefs[k] === preset.prefs[k])
          return (
            <button key={preset.id} type="button"
              onClick={() => setPrefs(preset.prefs)}
              title={`Preset ${preset.label} — ${Object.entries(preset.prefs).filter(([, v]) => v).map(([k]) => k.replace('show', '').toLowerCase()).join(' + ') || 'aucun'}`}
              style={{
                padding: '1px 6px', borderRadius: 3,
                fontFamily: 'var(--font-mono, monospace)', fontSize: 8,
                cursor: 'pointer', letterSpacing: '0.1em',
                background: active ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                border: `1px ${active ? 'solid' : 'dashed'} ${active ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line-soft, rgba(255,255,255,0.10))'}`,
                color: active ? GOLD : DIM,
                fontWeight: active ? 700 : 400,
                textTransform: 'uppercase',
              }}>
              {preset.label}
            </button>
          )
        })}
        {/* v82eq : presets custom (saved by user) */}
        {Object.entries(customPresets).map(([name, presetPrefs]) => {
          const active = (Object.keys(presetPrefs) as (keyof DisplayPrefs)[])
            .every((k) => prefs[k] === presetPrefs[k])
          return (
            <span key={name} style={{ display: 'inline-flex', alignItems: 'center' }}>
              <button type="button"
                onClick={() => setPrefs(presetPrefs)}
                title={`Preset perso « ${name} » — clic pour appliquer`}
                style={{
                  padding: '1px 4px 1px 6px', borderRadius: '3px 0 0 3px',
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 8,
                  cursor: 'pointer', letterSpacing: '0.1em',
                  background: active ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                  border: `1px ${active ? 'solid' : 'dashed'} ${active ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line-soft, rgba(255,255,255,0.10))'}`,
                  borderRight: 'none',
                  color: active ? GOLD : DIM,
                  fontWeight: active ? 700 : 400,
                  textTransform: 'uppercase',
                  maxWidth: 80, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                ★ {name}
              </button>
              {/* v82er : bouton rename ✎ au milieu */}
              <button type="button"
                onClick={() => renameCustomPreset(name)}
                title={`Renommer le preset perso « ${name} »`}
                style={{
                  padding: '1px 3px', fontSize: 8,
                  background: 'transparent', color: 'var(--fg-mute, #777)',
                  border: `1px ${active ? 'solid' : 'dashed'} ${active ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line-soft, rgba(255,255,255,0.10))'}`,
                  borderLeft: 'none', borderRight: 'none',
                  cursor: 'pointer', fontFamily: 'inherit',
                }}>✎</button>
              <button type="button"
                onClick={() => deleteCustomPreset(name)}
                title={`Supprimer le preset perso « ${name} »`}
                style={{
                  padding: '1px 4px', borderRadius: '0 3px 3px 0',
                  fontSize: 8,
                  background: 'transparent', color: 'oklch(0.55 0.18 25)',
                  border: `1px ${active ? 'solid' : 'dashed'} ${active ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line-soft, rgba(255,255,255,0.10))'}`,
                  borderLeft: 'none', cursor: 'pointer',
                  fontFamily: 'inherit',
                }}>×</button>
            </span>
          )
        })}
        {/* v82eq : sauver les prefs courantes comme preset */}
        <button type="button"
          onClick={saveCurrentAsPreset}
          title="Sauver les prefs courantes comme nouveau preset perso"
          style={{
            padding: '1px 6px', borderRadius: 3,
            fontFamily: 'var(--font-mono, monospace)', fontSize: 8,
            cursor: 'pointer', letterSpacing: '0.1em',
            background: 'transparent',
            border: '1px dotted oklch(0.74 0.13 60 / 0.45)',
            color: 'oklch(0.74 0.13 60)',
            fontWeight: 400, textTransform: 'uppercase',
          }}>
          + sauver
        </button>
        <span style={{ color: DIM, marginLeft: 4 }}>·</span>
        {([
          { k: 'showLadders' as const, label: 'ladders' },
          { k: 'showTrend' as const, label: 'trend' },
          { k: 'showWeeklyRibbon' as const, label: 'semaine' },
          { k: 'showMilestones' as const, label: 'milestones' },
        ]).map(({ k, label }) => (
          <button key={k} type="button"
            onClick={() => togglePref(k)}
            title={`${prefs[k] ? 'Masquer' : 'Afficher'} ${label}`}
            style={{
              padding: '1px 6px', borderRadius: 99,
              fontFamily: 'var(--font-mono, monospace)', fontSize: 8,
              cursor: 'pointer', letterSpacing: '0.05em',
              background: prefs[k] ? 'oklch(0.74 0.13 60 / 0.15)' : 'transparent',
              border: `1px solid ${prefs[k] ? 'oklch(0.74 0.13 60 / 0.45)' : 'var(--line-soft, rgba(255,255,255,0.10))'}`,
              color: prefs[k] ? GOLD : DIM,
              fontWeight: prefs[k] ? 700 : 400,
            }}>
            {prefs[k] ? '◉' : '○'} {label}
          </button>
        ))}
      </div>

      {/* v82ct : ligne stats hebdomadaires + totales (compact) */}
      {/* v82ea : weekly personal goal banner */}
      {(() => {
        const now = new Date()
        const day = now.getDay() === 0 ? 6 : now.getDay() - 1
        const monday = new Date(now)
        monday.setHours(0, 0, 0, 0)
        monday.setDate(monday.getDate() - day)
        const t0 = monday.getTime()
        const cyberWk = (!filter || filter.includes('cyber') || filter.includes('cross')) ? cyberRuns.filter((r) => r.startedAt >= t0) : []
        const academyWk = (!filter || filter.includes('academy') || filter.includes('cross')) ? academyRuns.filter((r) => r.startedAt >= t0) : []
        const goalProgress = !weeklyGoal ? 0
          : weeklyGoal.scope === 'cyber' ? cyberWk.length
          : weeklyGoal.scope === 'academy' ? academyWk.length
          : cyberWk.length + academyWk.length
        const goalDone = !!weeklyGoal && goalProgress >= weeklyGoal.target
        return (
          <div style={{
            marginBottom: 6, padding: '6px 10px', borderRadius: 6,
            background: weeklyGoal && goalDone
              ? 'oklch(0.74 0.13 60 / 0.15)'
              : 'oklch(0.72 0.14 25 / 0.04)',
            border: `1px ${weeklyGoal ? 'solid' : 'dashed'} ${weeklyGoal && goalDone ? 'oklch(0.74 0.13 60 / 0.55)' : 'oklch(0.72 0.14 25 / 0.20)'}`,
            fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
            display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
          }}>
            <span style={{
              color: weeklyGoal && goalDone ? GOLD : 'oklch(0.72 0.14 25)',
              letterSpacing: '0.14em', textTransform: 'uppercase',
            }}>
              {weeklyGoal && goalDone ? '🎯✓ Objectif atteint' : '🎯 Objectif perso'}
            </span>
            {weeklyGoal ? (
              <>
                <button type="button" onClick={cycleGoalScope}
                  title="Cycler scope : tous / cyber / academy"
                  style={{
                    padding: '1px 6px', borderRadius: 99, fontSize: 9,
                    background: 'transparent', color: DIM,
                    border: '1px dashed var(--line, rgba(255,255,255,0.18))',
                    fontFamily: 'inherit', cursor: 'pointer', letterSpacing: '0.1em',
                  }}>
                  {weeklyGoal.scope}
                </button>
                <div style={{
                  flex: 1, height: 4, borderRadius: 99, minWidth: 100,
                  background: 'var(--ink-800, rgba(255,255,255,0.08))',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${Math.min(100, (goalProgress / weeklyGoal.target) * 100)}%`,
                    background: goalDone ? GOLD : 'oklch(0.72 0.14 25)',
                    transition: 'width 200ms ease',
                  }} />
                </div>
                <button type="button" onClick={setGoalTarget}
                  title="Modifier l'objectif (vide pour supprimer)"
                  style={{
                    padding: '1px 6px', borderRadius: 3, fontSize: 9,
                    background: 'transparent',
                    color: weeklyGoal && goalDone ? GOLD : 'var(--fg, #f5f5f5)',
                    border: '1px solid var(--line, rgba(255,255,255,0.18))',
                    fontFamily: 'inherit', cursor: 'pointer',
                    fontVariantNumeric: 'tabular-nums', fontWeight: 700,
                  }}>
                  {goalProgress} / {weeklyGoal.target}
                </button>
              </>
            ) : (
              <button type="button" onClick={setGoalTarget}
                title="Définir un objectif perso de runs cette semaine"
                style={{
                  padding: '2px 8px', borderRadius: 3, fontSize: 9,
                  background: 'transparent', color: 'oklch(0.72 0.14 25)',
                  border: '1px dashed oklch(0.72 0.14 25 / 0.45)',
                  fontFamily: 'inherit', cursor: 'pointer',
                  letterSpacing: '0.1em',
                }}>
                + définir un objectif
              </button>
            )}
          </div>
        )
      })()}
      {weeklyStats.totalCount > 0 && (
        <div style={{
          marginBottom: 8, padding: '4px 8px',
          background: 'rgba(255,255,255,0.02)',
          border: '1px dashed var(--line-soft, rgba(255,255,255,0.06))',
          borderRadius: 4,
          fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
          color: DIM,
          display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
        }}>
          <span>cette semaine : <b style={{ color: GOLD }}>{weeklyStats.weekCount}</b> session(s)</span>
          {weeklyStats.weekMin > 0 && <span>· {weeklyStats.weekMin} min cumulées</span>}
          {weeklyStats.weekAvg > 0 && <span>· moy {weeklyStats.weekAvg}pts</span>}
          {weeklyStats.badgesWeek > 0 && (
            <span style={{ color: GOLD }}>· 🏆 +{weeklyStats.badgesWeek} badge(s)</span>
          )}
          <span style={{ flex: 1 }} />
          {weeklyStats.sparkValues.length >= 2 && (
            <span title={`Évolution score · ${weeklyStats.sparkValues.length} dernier(s) run(s) avec score`}
              style={{ display: 'inline-flex', alignItems: 'center' }}>
              <Sparkline values={weeklyStats.sparkValues} width={80} height={20} color={GOLD} />
            </span>
          )}
          <span>total : {weeklyStats.totalCount} run(s)</span>
          {weeklyStats.totalBest > 0 && <span>· best <b style={{ color: GOLD }}>{weeklyStats.totalBest}</b></span>}
        </div>
      )}
      {prefs.showLadders && (
      <>
      {/* v82eg : ladder dédiée Rangs Cyber + Mentions Bac. Affiche
          la progression palier-par-palier en ligne, plus lisible que
          la grille générique. Montrée si filter contient cyber/academy. */}
      {(() => {
        const wantsCyber = !filter || filter.includes('cyber')
        const wantsAcademy = !filter || filter.includes('academy')
        const cyberRanks = wantsCyber
          ? ['cy-rank-recrue', 'cy-rank-bronze', 'cy-rank-argent', 'cy-rank-or', 'cy-rank-diamant', 'cy-rank-legendaire']
              .map((id) => achievements.find((a) => a.id === id))
              .filter((x): x is NonNullable<typeof x> => !!x)
          : []
        const academyMentions = wantsAcademy
          ? ['ac-mention-ab', 'ac-mention-b', 'ac-mention-tb', 'ac-mention-europeen', 'ac-mention-felicitations']
              .map((id) => achievements.find((a) => a.id === id))
              .filter((x): x is NonNullable<typeof x> => !!x)
          : []
        const renderLadder = (title: string, items: typeof cyberRanks, accent: string) => {
          if (items.length === 0) return null
          return (
            <div style={{
              padding: 6, marginBottom: 6, borderRadius: 6,
              background: `${accent} / 0.04`,
              border: `1px solid ${accent.replace(')', ' / 0.18)')}`,
              fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
            }}>
              <div style={{
                marginBottom: 4, color: accent, letterSpacing: '0.14em',
                textTransform: 'uppercase',
              }}>
                {title}
              </div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {items.map((a, i) => {
                  const next = items[i + 1]
                  const showProgress = a.unlocked && next && !next.unlocked
                  return (
                    <div key={a.id}
                      title={`${a.description}${a.progress ? ` · ${a.progress.current} / ${a.progress.target}` : ''}`}
                      style={{
                        flex: '1 1 60px', minWidth: 60,
                        display: 'flex', flexDirection: 'column',
                        alignItems: 'center', gap: 2,
                        padding: '4px 2px', borderRadius: 3,
                        background: a.unlocked
                          ? `${accent.replace(')', ' / 0.10)')}`
                          : 'transparent',
                        border: `1px ${a.unlocked ? 'solid' : 'dashed'} ${accent.replace(')', a.unlocked ? ' / 0.45)' : ' / 0.15)')}`,
                        opacity: a.unlocked ? 1 : 0.45,
                        cursor: 'help', position: 'relative',
                      }}>
                      <span style={{
                        fontSize: 14,
                        filter: a.unlocked ? 'none' : 'grayscale(1)',
                      }}>{a.glyph}</span>
                      <span style={{
                        fontWeight: a.unlocked ? 700 : 400,
                        color: a.unlocked ? accent : DIM,
                        whiteSpace: 'nowrap', overflow: 'hidden',
                        textOverflow: 'ellipsis', width: '100%',
                        textAlign: 'center', fontSize: 8,
                      }}>{a.label.replace('Rang ', '').replace('Mention ', '')}</span>
                      {showProgress && next.progress && (
                        <div style={{
                          marginTop: 1, height: 2, width: '100%',
                          borderRadius: 99,
                          background: 'var(--ink-800, rgba(255,255,255,0.08))',
                          overflow: 'hidden',
                        }}>
                          <div style={{
                            height: '100%',
                            width: `${(next.progress.current / Math.max(1, next.progress.target)) * 100}%`,
                            background: accent,
                          }} />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        }
        return (
          <>
            {renderLadder('Rangs Cyber', cyberRanks, 'oklch(0.74 0.13 60)')}
            {renderLadder('Mentions Bac', academyMentions, 'oklch(0.74 0.13 60)')}
          </>
        )
      })()}
      </>
      )}
      {/* v82ei : trend bar chart standalone si max > 0 même si la
          semaine courante est vide (montre l'historique 8 semaines). */}
      {prefs.showTrend && unlocksTrend.max > 0 && weeklyUnlocks.length === 0 && (
        <div style={{
          padding: '4px 8px', marginBottom: 6, borderRadius: 6,
          background: 'oklch(0.72 0.14 25 / 0.04)',
          border: '1px solid oklch(0.72 0.14 25 / 0.18)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
          display: 'flex', alignItems: 'center', gap: 8,
          color: 'oklch(0.72 0.14 25)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
        }}>
          <span>📊 Trend</span>
          {(() => {
            const bestIdx = unlocksTrend.weeks.findIndex((w) => w.count === unlocksTrend.max)
            return (
              <svg width={72} height={22} style={{ overflow: 'visible' }}>
                <title>{`Unlocks par semaine · ${unlocksTrend.weeks.map((w) => w.count).join(', ')} (best : ${unlocksTrend.max})`}</title>
                {unlocksTrend.weeks.map((w, i) => {
                  const bx = i * 9
                  const bh = unlocksTrend.max > 0 ? (w.count / unlocksTrend.max) * 14 : 0
                  const isBest = i === bestIdx && w.count > 0
                  return (
                    <rect key={i}
                      x={bx} y={20 - bh} width={6} height={bh || 0.5}
                      rx={1}
                      fill={isBest ? 'oklch(0.74 0.13 60)' : 'oklch(0.72 0.14 25 / 0.55)'} />
                  )
                })}
                {bestIdx >= 0 && unlocksTrend.max >= 2 && (
                  <text
                    x={bestIdx * 9 + 3} y={4}
                    textAnchor="middle"
                    fontFamily="ui-monospace, monospace"
                    fontSize={7}
                    fontWeight={700}
                    fill="oklch(0.74 0.13 60)">
                    {unlocksTrend.max}★
                  </text>
                )}
              </svg>
            )
          })()}
          <span style={{
            letterSpacing: 0, textTransform: 'none',
            color: 'var(--fg-dim, #aaa)', fontWeight: 400,
          }}>
            8 dernières semaines · 0 cette semaine
          </span>
        </div>
      )}
      {/* v82eh : timeline ribbon — achievements débloqués cette semaine
          (depuis lundi 00:00). Order chronologique. Affiché seulement
          si au moins 1 unlock cette semaine. */}
      {prefs.showWeeklyRibbon && weeklyUnlocks.length > 0 && (
        <div style={{
          padding: 6, marginBottom: 6, borderRadius: 6,
          background: 'oklch(0.72 0.14 25 / 0.05)',
          border: '1px solid oklch(0.72 0.14 25 / 0.22)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
        }}>
          <div style={{
            marginBottom: 4, color: 'oklch(0.72 0.14 25)',
            letterSpacing: '0.14em', textTransform: 'uppercase',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span>✨ Cette semaine</span>
            <span style={{ flex: 1 }} />
            {/* v82ei : barchart trend unlocks 8 dernières semaines */}
            {/* v82ej : best week annotation (gold pill au-dessus du max) */}
            {unlocksTrend.max > 0 && (() => {
              const bestIdx = unlocksTrend.weeks.findIndex((w) => w.count === unlocksTrend.max)
              return (
                <svg width={72} height={22} style={{ overflow: 'visible' }}>
                  <title>{`Trend unlocks · ${unlocksTrend.weeks.map((w) => w.count).join(', ')} (8 dernières semaines, best : ${unlocksTrend.max})`}</title>
                  {unlocksTrend.weeks.map((w, i) => {
                    const bx = i * 9
                    const bh = unlocksTrend.max > 0 ? (w.count / unlocksTrend.max) * 14 : 0
                    const isCurrent = i === unlocksTrend.weeks.length - 1
                    const isBest = i === bestIdx && w.count > 0
                    return (
                      <rect key={i}
                        x={bx} y={20 - bh} width={6} height={bh || 0.5}
                        rx={1}
                        fill={isCurrent ? 'oklch(0.72 0.14 25)' : isBest ? 'oklch(0.74 0.13 60)' : 'oklch(0.72 0.14 25 / 0.45)'} />
                    )
                  })}
                  {bestIdx >= 0 && unlocksTrend.max >= 2 && (
                    <text
                      x={bestIdx * 9 + 3}
                      y={20 - (unlocksTrend.max / unlocksTrend.max) * 14 - 2}
                      textAnchor="middle"
                      fontFamily="ui-monospace, monospace"
                      fontSize={7}
                      fontWeight={700}
                      fill="oklch(0.74 0.13 60)">
                      {unlocksTrend.max}★
                    </text>
                  )}
                </svg>
              )
            })()}
            <span style={{
              letterSpacing: 0, textTransform: 'none',
              color: 'var(--fg-dim, #aaa)', fontWeight: 400,
            }}>
              {weeklyUnlocks.length} unlock(s)
            </span>
          </div>
          <div style={{
            display: 'flex', gap: 6, flexWrap: 'wrap',
            alignItems: 'center',
          }}>
            {weeklyUnlocks.map((w, i) => {
              const d = new Date(w.ts)
              const dayLabel = d.toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit' })
              return (
                <div key={w.ach.id}
                  title={`${w.ach.label} — ${w.ach.description}\nDébloqué ${d.toLocaleString('fr-FR')}`}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    padding: '3px 6px', borderRadius: 99,
                    background: 'oklch(0.72 0.14 25 / 0.10)',
                    border: '1px solid oklch(0.72 0.14 25 / 0.40)',
                    color: 'oklch(0.72 0.14 25)', fontWeight: 700,
                    fontSize: 9, cursor: 'help',
                    animation: i === weeklyUnlocks.length - 1
                      ? 'pulse 2s ease-in-out infinite' : undefined,
                  }}>
                  <span style={{ fontSize: 12 }}>{w.ach.glyph}</span>
                  <span style={{ maxWidth: 90, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {w.ach.label}
                  </span>
                  <span style={{ color: 'var(--fg-mute, #777)', fontWeight: 400 }}>
                    {dayLabel}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
        gap: 4,
      }}>
        {filtered
          .filter((a) => !compact || a.unlocked)
          .map((a) => {
            // v82dg : tier color override
            const tierColor =
              a.tier === 'diamond' ? 'oklch(0.85 0.15 200)'
              : a.tier === 'gold' ? GOLD
              : a.tier === 'silver' ? 'oklch(0.85 0.02 250)'
              : a.tier === 'bronze' ? 'oklch(0.65 0.12 50)'
              : null
            const borderColor = tierColor || (a.unlocked ? GOLD : 'var(--line, rgba(255,255,255,0.1))')
            return (
            <div key={a.id} title={`${a.description}${a.tier ? ` · tier ${a.tier.toUpperCase()}` : ''}`} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 6px', borderRadius: 4,
              background: a.unlocked ? 'var(--bg-card, rgba(255,255,255,0.05))' : 'transparent',
              border: `1px ${a.unlocked ? 'solid' : 'dashed'} ${borderColor}`,
              opacity: a.unlocked ? 1 : 0.5,
              fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
              cursor: 'help',
              boxShadow: a.tier === 'diamond' ? `0 0 6px ${tierColor}` : 'none',
            }}>
              <span style={{ fontSize: 14, filter: a.unlocked ? 'none' : 'grayscale(1)' }}>{a.glyph}</span>
              {a.tier && a.tier !== 'bronze' && (
                <span style={{
                  fontSize: 7, color: tierColor || GOLD, fontWeight: 700,
                  letterSpacing: '0.1em', lineHeight: 1,
                }}>{a.tier === 'diamond' ? '◆' : a.tier === 'gold' ? '★' : '✦'}</span>
              )}
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{
                  fontWeight: a.unlocked ? 700 : 400,
                  color: a.unlocked ? 'var(--fg, #f5f5f5)' : DIM,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>{a.label}</div>
                {a.progress && !a.unlocked && (
                  <div style={{
                    marginTop: 2, height: 2, borderRadius: 99,
                    background: 'var(--ink-800, rgba(255,255,255,0.08))',
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%',
                      width: `${(a.progress.current / Math.max(1, a.progress.target)) * 100}%`,
                      background: GOLD,
                    }} />
                  </div>
                )}
              </div>
            </div>
            )
          })}
      </div>
      {/* v82el : footer "top 3 next milestones" — 3 paliers locked
          les plus avancés affichés en mini-grid. Donne 3 objectifs
          parallèles à viser. */}
      {prefs.showMilestones && topMilestones.length > 0 && (
        <div style={{
          marginTop: 8, padding: '6px 8px', borderRadius: 6,
          background: 'oklch(0.74 0.13 60 / 0.05)',
          border: '1px dashed oklch(0.74 0.13 60 / 0.30)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
        }}>
          <div style={{
            marginBottom: 4, color: GOLD,
            letterSpacing: '0.14em', textTransform: 'uppercase',
            display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
          }}>
            <span>◎ Next</span>
            <span style={{ flex: 1 }} />
            {/* v82em : sigma de la distance totale restante pour
                clear les top 3 milestones d'un coup. Plus concret
                que les 3 ratios pris séparément. */}
            {(() => {
              const sumRemaining = topMilestones.reduce(
                (a, m) => a + Math.max(0, m.ach.progress!.target - m.ach.progress!.current),
                0,
              )
              const avgRatio = topMilestones.reduce((a, m) => a + m.ratio, 0) / topMilestones.length
              return (
                <span style={{
                  letterSpacing: 0, textTransform: 'none',
                  color: 'var(--fg-dim, #aaa)', fontWeight: 400,
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                }}
                  title={`Distance totale restante : ${sumRemaining} pts cumulés sur les ${topMilestones.length} paliers · moyenne ${Math.round(avgRatio * 100)}%`}>
                  <span>Σ restant :</span>
                  <b style={{ color: GOLD, fontVariantNumeric: 'tabular-nums' }}>
                    {sumRemaining}
                  </b>
                  <span style={{ color: DIM }}>· avg {Math.round(avgRatio * 100)}%</span>
                </span>
              )
            })()}
            <span style={{
              letterSpacing: 0, textTransform: 'none',
              color: 'var(--fg-dim, #aaa)', fontWeight: 400,
            }}>
              top {topMilestones.length} palier(s) à viser
            </span>
            {/* v82en : cycle button pour 1 / 3 / 5 milestones */}
            <button type="button"
              onClick={cycleMilestonesCount}
              title={`Afficher ${milestonesCount} milestone(s) — cliquer pour cycler 1 / 3 / 5`}
              style={{
                padding: '1px 6px', fontSize: 9,
                fontFamily: 'var(--font-mono, monospace)',
                background: 'oklch(0.74 0.13 60 / 0.10)',
                color: GOLD,
                border: '1px solid oklch(0.74 0.13 60 / 0.30)',
                borderRadius: 3, cursor: 'pointer',
                letterSpacing: '0.1em',
              }}>
              ⇆ {milestonesCount}
            </button>
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: topMilestones.length === 1
              ? '1fr'
              : topMilestones.length === 2
                ? 'repeat(2, 1fr)'
                : topMilestones.length === 3
                  ? 'repeat(3, 1fr)'
                  : topMilestones.length === 4
                    ? 'repeat(4, 1fr)'
                    : 'repeat(auto-fill, minmax(110px, 1fr))',
            gap: 6,
          }}>
            {topMilestones.map(({ ach, ratio }) => (
              <div key={ach.id}
                title={ach.description}
                style={{
                  padding: '4px 6px', borderRadius: 4,
                  background: 'oklch(0.74 0.13 60 / 0.08)',
                  border: '1px solid oklch(0.74 0.13 60 / 0.25)',
                  display: 'flex', flexDirection: 'column', gap: 3,
                  cursor: 'help',
                }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  fontSize: 9,
                }}>
                  <span style={{ fontSize: 12 }}>{ach.glyph}</span>
                  <span style={{
                    fontWeight: 700, color: 'var(--fg, #f5f5f5)',
                    whiteSpace: 'nowrap', overflow: 'hidden',
                    textOverflow: 'ellipsis', flex: 1,
                  }}>
                    {ach.label}
                  </span>
                  <span style={{
                    color: GOLD, fontWeight: 700,
                    fontVariantNumeric: 'tabular-nums',
                    fontSize: 8,
                  }}>
                    {Math.round(ratio * 100)}%
                  </span>
                </div>
                <div style={{
                  height: 3, borderRadius: 99,
                  background: 'var(--ink-800, rgba(255,255,255,0.08))',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${ratio * 100}%`,
                    background: GOLD,
                  }} />
                </div>
                <div style={{
                  fontSize: 8, color: DIM,
                  fontVariantNumeric: 'tabular-nums',
                  textAlign: 'right',
                }}>
                  {ach.progress!.current} / {ach.progress!.target}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
