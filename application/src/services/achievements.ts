/**
 * achievements — système de badges unifié Cyber + Academy.
 *
 * Calcul pur depuis les stores existants (cyberLeaderboardStore +
 * academyLeaderboardStore). Pas de persistence séparée — un badge
 * débloqué se déduit toujours des runs persistés. Si l'user clear
 * son leaderboard, les badges disparaissent (cohérent avec source).
 *
 * v82bz.
 */
import type { KataRun } from '../stores/cyberLeaderboardStore.ts'
import type { AcademyRun } from '../stores/academyLeaderboardStore.ts'
import { computeStreak } from '../utils/streak.ts'

export type AchievementCategory = 'cyber' | 'academy' | 'cross'

export type AchievementTier = 'bronze' | 'silver' | 'gold' | 'diamond'

export interface Achievement {
  id: string
  label: string
  description: string
  category: AchievementCategory
  glyph: string  // emoji / character
  unlocked: boolean
  progress?: { current: number; target: number }
  // Tier escalation: auto-calculated from progress ratio (bronze→silver→gold→diamond).
  tier?: AchievementTier
}

interface CheckInput {
  cyberRuns: KataRun[]
  academyRuns: AcademyRun[]
}

interface AchievementDef {
  id: string
  label: string
  description: string
  category: AchievementCategory
  glyph: string
  check: (input: CheckInput) => { unlocked: boolean; progress?: { current: number; target: number } }
}

const DEFS: AchievementDef[] = [
  // ─── Cyber ───────────────────────────────────────────────────────
  {
    id: 'cy-first-kata', label: 'Premier sang',
    description: 'Termine ton premier kata avec au moins 1 objectif validé.',
    category: 'cyber', glyph: '🥋',
    check: ({ cyberRuns }) => ({ unlocked: cyberRuns.some((r) => r.objectivesDone > 0) }),
  },
  {
    id: 'cy-five-disciplines', label: '5 disciplines',
    description: 'Pratique 5 disciplines Cyber différentes.',
    category: 'cyber', glyph: '🎯',
    check: ({ cyberRuns }) => {
      const ids = new Set(cyberRuns.map((r) => r.kataId.split('-')[0]))
      return { unlocked: ids.size >= 5, progress: { current: ids.size, target: 5 } }
    },
  },
  {
    id: 'cy-no-hint-run', label: 'Pure sans aide',
    description: 'Termine une épreuve avec 0 indices et tous les objectifs validés.',
    category: 'cyber', glyph: '💎',
    check: ({ cyberRuns }) => ({
      unlocked: cyberRuns.some((r) => r.mode === 'epreuve'
        && r.hintsTaken === 0 && r.objectivesDone === r.totalObjectives && r.totalObjectives > 0),
    }),
  },
  {
    id: 'cy-no-hint-streak', label: 'Sans-faille',
    description: '5 épreuves Cyber no-hint full success cumulés.',
    category: 'cyber', glyph: '🥷',
    check: ({ cyberRuns }) => {
      const n = cyberRuns.filter((r) =>
        r.mode === 'epreuve'
        && r.hintsTaken === 0
        && r.objectivesDone === r.totalObjectives
        && r.totalObjectives > 0,
      ).length
      return { unlocked: n >= 5, progress: { current: n, target: 5 } }
    },
  },
  {
    id: 'cy-score-1000', label: 'Mille points',
    description: 'Atteins un score d\'épreuve ≥ 1000 sur un kata.',
    category: 'cyber', glyph: '💯',
    check: ({ cyberRuns }) => {
      const max = cyberRuns.reduce((m, r) => Math.max(m, r.score ?? 0), 0)
      return { unlocked: max >= 1000, progress: { current: max, target: 1000 } }
    },
  },
  {
    id: 'cy-custom-forge', label: 'Forgeron',
    description: 'Lance au moins un kata custom forgé à partir d\'un brief libre.',
    category: 'cyber', glyph: '⚒',
    check: ({ cyberRuns }) => ({ unlocked: cyberRuns.some((r) => r.kataId.startsWith('custom-')) }),
  },
  {
    id: 'cy-ten-runs', label: 'Endurance',
    description: 'Cumule 10 runs Cyber tous katas confondus.',
    category: 'cyber', glyph: '🏃',
    check: ({ cyberRuns }) => ({
      unlocked: cyberRuns.length >= 10,
      progress: { current: cyberRuns.length, target: 10 },
    }),
  },
  {
    id: 'cy-daily-streak', label: 'Régulier',
    description: 'Réussis 5 challenges du jour différents (full success).',
    category: 'cyber', glyph: '📅',
    check: ({ cyberRuns }) => {
      // Compte les jours uniques avec un full-success sur n'importe
      // quel kata (proxy raisonnable du daily challenge).
      const days = new Set<string>()
      for (const r of cyberRuns) {
        if (r.mode !== 'epreuve' || r.objectivesDone !== r.totalObjectives || r.totalObjectives === 0) continue
        const d = new Date(r.startedAt)
        days.add(`${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`)
      }
      return { unlocked: days.size >= 5, progress: { current: days.size, target: 5 } }
    },
  },
  {
    id: 'cr-week-streak', label: 'Hebdo',
    description: 'Pratique 7 jours consécutifs (Cyber ou Academy, peu importe).',
    category: 'cross', glyph: '🔥',
    check: ({ cyberRuns, academyRuns }) => {
      const allDays = new Set<string>()
      for (const r of cyberRuns) {
        const d = new Date(r.startedAt)
        allDays.add(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
      }
      for (const r of academyRuns) {
        const d = new Date(r.startedAt)
        allDays.add(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
      }
      // Calcule la plus longue streak consécutive
      const sorted = Array.from(allDays).sort()
      let best = 0, cur = 0, prev = ''
      for (const day of sorted) {
        if (!prev) { cur = 1 }
        else {
          const prevD = new Date(prev + 'T00:00:00')
          const curD = new Date(day + 'T00:00:00')
          const diff = Math.round((curD.getTime() - prevD.getTime()) / 86_400_000)
          cur = diff === 1 ? cur + 1 : 1
        }
        prev = day
        if (cur > best) best = cur
      }
      return { unlocked: best >= 7, progress: { current: best, target: 7 } }
    },
  },
  {
    id: 'cr-marathon', label: 'Marathon',
    description: 'Cumule 10h de pratique (Cyber + Academy) sur les 7 derniers jours.',
    category: 'cross', glyph: '🏃',
    check: ({ cyberRuns, academyRuns }) => {
      const cutoff = Date.now() - 7 * 86_400_000
      const cyberMs = cyberRuns
        .filter((r) => r.startedAt >= cutoff)
        .reduce((a, r) => a + r.durationMs, 0)
      const academyMs = academyRuns
        .filter((r) => r.startedAt >= cutoff)
        .reduce((a, r) => a + r.durationMs, 0)
      const totalH = (cyberMs + academyMs) / 3_600_000
      return {
        unlocked: totalH >= 10,
        progress: { current: Math.round(totalH * 10) / 10, target: 10 },
      }
    },
  },
  {
    id: 'ac-visual-learner', label: 'Apprenant visuel',
    description: '5 sessions Academy avec images attachées (vision multimodale qwen3-vl).',
    category: 'academy', glyph: '🖼',
    check: ({ academyRuns }) => {
      const n = academyRuns.filter((r) => r.usedVision === true).length
      return { unlocked: n >= 5, progress: { current: n, target: 5 } }
    },
  },
  {
    id: 'ac-text-purist', label: 'Lettré',
    description: '10 sessions Academy text-only (sans image, vision pas utilisée).',
    category: 'academy', glyph: '📝',
    check: ({ academyRuns }) => {
      // Compte les runs où usedVision est explicitement false OU undefined
      // (les runs anciens avant v82de comptent comme text-only).
      const n = academyRuns.filter((r) => !r.usedVision).length
      return { unlocked: n >= 10, progress: { current: n, target: 10 } }
    },
  },
  {
    id: 'ac-studious-week', label: 'Studieux',
    description: '5 sessions Academy sans timeout dans une même matière en 7 jours.',
    category: 'academy', glyph: '📖',
    check: ({ academyRuns }) => {
      const cutoff = Date.now() - 7 * 86_400_000
      const recent = academyRuns.filter((r) => r.startedAt >= cutoff && !r.timeoutHit)
      const counts: Record<string, number> = {}
      for (const r of recent) {
        counts[r.subject] = (counts[r.subject] || 0) + 1
      }
      const max = Math.max(0, ...Object.values(counts))
      return { unlocked: max >= 5, progress: { current: max, target: 5 } }
    },
  },
  {
    id: 'cr-month-active', label: 'Mensuel actif',
    description: '20 sessions (Academy + Cyber) sur les 30 derniers jours.',
    category: 'cross', glyph: '🗓',
    check: ({ cyberRuns, academyRuns }) => {
      const cutoff = Date.now() - 30 * 86_400_000
      const n = cyberRuns.filter((r) => r.startedAt >= cutoff).length
        + academyRuns.filter((r) => r.startedAt >= cutoff).length
      return { unlocked: n >= 20, progress: { current: n, target: 20 } }
    },
  },
  {
    id: 'ac-library', label: 'Bibliothèque',
    description: '50 sessions Academy cumulées all-time.',
    category: 'academy', glyph: '🏛',
    check: ({ academyRuns }) => ({
      unlocked: academyRuns.length >= 50,
      progress: { current: academyRuns.length, target: 50 },
    }),
  },
  {
    id: 'cy-veteran', label: 'Vétéran',
    description: '50 katas Cyber lancés all-time.',
    category: 'cyber', glyph: '⚔️',
    check: ({ cyberRuns }) => ({
      unlocked: cyberRuns.length >= 50,
      progress: { current: cyberRuns.length, target: 50 },
    }),
  },
  {
    id: 'ac-expert', label: 'Expert',
    description: 'Atteins un score Academy ≥ 2000 (plafond élite).',
    category: 'academy', glyph: '🎓',
    check: ({ academyRuns }) => {
      const max = academyRuns.reduce((m, r) => Math.max(m, r.score), 0)
      return { unlocked: max >= 2000, progress: { current: max, target: 2000 } }
    },
  },
  {
    id: 'cr-morning-bird', label: 'Matinée studieuse',
    description: 'Termine une session avant 9h du matin.',
    category: 'cross', glyph: '🌅',
    check: ({ cyberRuns, academyRuns }) => {
      const hit = [...cyberRuns, ...academyRuns].some((r) => {
        const d = new Date(r.startedAt)
        return d.getHours() < 9
      })
      return { unlocked: hit }
    },
  },
  {
    id: 'cr-night-owl', label: 'Nuit studieuse',
    description: 'Termine une session après 22h.',
    category: 'cross', glyph: '🌙',
    check: ({ cyberRuns, academyRuns }) => {
      const hit = [...cyberRuns, ...academyRuns].some((r) => {
        const d = new Date(r.startedAt)
        return d.getHours() >= 22
      })
      return { unlocked: hit }
    },
  },
  {
    id: 'cr-double-day', label: 'Jour double',
    description: 'Sessions matin (avant 12h) ET soir (après 18h) le même jour.',
    category: 'cross', glyph: '☀️🌙',
    check: ({ cyberRuns, academyRuns }) => {
      const all = [...cyberRuns, ...academyRuns]
      const days: Record<string, { am: boolean; pm: boolean }> = {}
      for (const r of all) {
        const d = new Date(r.startedAt)
        const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
        if (!days[key]) days[key] = { am: false, pm: false }
        const h = d.getHours()
        if (h < 12) days[key].am = true
        if (h >= 18) days[key].pm = true
      }
      const hit = Object.values(days).some((v) => v.am && v.pm)
      return { unlocked: hit }
    },
  },
  {
    id: 'cr-variety-day', label: 'Jour varié',
    description: 'Cyber ET Academy le même jour.',
    category: 'cross', glyph: '🎭',
    check: ({ cyberRuns, academyRuns }) => {
      const cyberDays = new Set(cyberRuns.map((r) => {
        const d = new Date(r.startedAt)
        return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
      }))
      const academyDays = new Set(academyRuns.map((r) => {
        const d = new Date(r.startedAt)
        return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
      }))
      const hit = Array.from(cyberDays).some((d) => academyDays.has(d))
      return { unlocked: hit }
    },
  },
  {
    id: 'ac-speed-runner', label: 'Speed-runner',
    description: 'Session Academy ≤ 5 min avec score ≥ 500.',
    category: 'academy', glyph: '⚡',
    check: ({ academyRuns }) => ({
      unlocked: academyRuns.some((r) =>
        r.durationMs > 0 && r.durationMs <= 300_000 && r.score >= 500),
    }),
  },
  {
    id: 'cy-speed-runner', label: 'Cyber speed-runner',
    description: 'Épreuve Cyber ≤ 5 min avec full success.',
    category: 'cyber', glyph: '🏎',
    check: ({ cyberRuns }) => ({
      unlocked: cyberRuns.some((r) =>
        r.mode === 'epreuve'
        && r.durationMs > 0 && r.durationMs <= 300_000
        && r.objectivesDone === r.totalObjectives && r.totalObjectives > 0),
    }),
  },
  {
    id: 'cy-clutch-finish', label: 'Sprint final',
    description: 'Termine une épreuve full success dans les 10% derniers du temps imparti.',
    category: 'cyber', glyph: '🎬',
    check: ({ cyberRuns }) => ({
      unlocked: cyberRuns.some((r) => {
        if (r.mode !== 'epreuve' || !r.durationLimitSec || r.totalObjectives === 0) return false
        if (r.objectivesDone !== r.totalObjectives) return false
        const usedRatio = r.durationMs / (r.durationLimitSec * 1000)
        return usedRatio >= 0.9 && usedRatio <= 1.0
      }),
    }),
  },
  // ─── Cyber rank tiers (v82ef, mirror bestRank from useCyberViewLogic) ──
  {
    id: 'cy-rank-recrue', label: 'Rang Recrue',
    description: 'Premier run Cyber enregistré.',
    category: 'cyber', glyph: '🎯',
    check: ({ cyberRuns }) => ({
      unlocked: cyberRuns.length >= 1,
      progress: { current: cyberRuns.length, target: 1 },
    }),
  },
  {
    id: 'cy-rank-bronze', label: 'Rang Bronze',
    description: 'Total XP Cyber all-time ≥ 250.',
    category: 'cyber', glyph: '🥉',
    check: ({ cyberRuns }) => {
      const totalXP = cyberRuns.reduce((a, r) => a + (r.xpEarned || 0), 0)
      return { unlocked: totalXP >= 250, progress: { current: totalXP, target: 250 } }
    },
  },
  {
    id: 'cy-rank-argent', label: 'Rang Argent',
    description: 'Total XP ≥ 750 + 3 katas uniques résolus.',
    category: 'cyber', glyph: '🥈',
    check: ({ cyberRuns }) => {
      let totalXP = 0
      const solved = new Set<string>()
      for (const r of cyberRuns) {
        totalXP += r.xpEarned || 0
        if ((r.xpEarned || 0) > 0 || (r.score || 0) > 0) solved.add(r.kataId)
      }
      return {
        unlocked: totalXP >= 750 && solved.size >= 3,
        progress: { current: totalXP, target: 750 },
      }
    },
  },
  {
    id: 'cy-rank-or', label: 'Rang Or',
    description: 'Total XP ≥ 1500 + 5 katas uniques résolus.',
    category: 'cyber', glyph: '🥇',
    check: ({ cyberRuns }) => {
      let totalXP = 0
      const solved = new Set<string>()
      for (const r of cyberRuns) {
        totalXP += r.xpEarned || 0
        if ((r.xpEarned || 0) > 0 || (r.score || 0) > 0) solved.add(r.kataId)
      }
      return {
        unlocked: totalXP >= 1500 && solved.size >= 5,
        progress: { current: totalXP, target: 1500 },
      }
    },
  },
  {
    id: 'cy-rank-diamant', label: 'Rang Diamant',
    description: 'Total XP ≥ 3000 + 7 katas uniques résolus.',
    category: 'cyber', glyph: '💎',
    check: ({ cyberRuns }) => {
      let totalXP = 0
      const solved = new Set<string>()
      for (const r of cyberRuns) {
        totalXP += r.xpEarned || 0
        if ((r.xpEarned || 0) > 0 || (r.score || 0) > 0) solved.add(r.kataId)
      }
      return {
        unlocked: totalXP >= 3000 && solved.size >= 7,
        progress: { current: totalXP, target: 3000 },
      }
    },
  },
  {
    id: 'cy-rank-legendaire', label: 'Rang Légendaire',
    description: 'Total XP ≥ 5000 + 10 katas uniques résolus.',
    category: 'cyber', glyph: '👑',
    check: ({ cyberRuns }) => {
      let totalXP = 0
      const solved = new Set<string>()
      for (const r of cyberRuns) {
        totalXP += r.xpEarned || 0
        if ((r.xpEarned || 0) > 0 || (r.score || 0) > 0) solved.add(r.kataId)
      }
      return {
        unlocked: totalXP >= 5000 && solved.size >= 10,
        progress: { current: totalXP, target: 5000 },
      }
    },
  },
  {
    id: 'ac-jack-of-all', label: 'Touche-à-tout',
    description: '7 modes Academy différents utilisés au moins une fois.',
    category: 'academy', glyph: '🎨',
    check: ({ academyRuns }) => {
      const modes = new Set(academyRuns.map((r) => r.mode))
      return { unlocked: modes.size >= 7, progress: { current: modes.size, target: 7 } }
    },
  },
  {
    id: 'cy-all-katas', label: 'Guide complet',
    description: 'Joue les 8 katas pré-définis Cyber (sans compter les custom).',
    category: 'cyber', glyph: '🌐',
    check: ({ cyberRuns }) => {
      const ids = new Set(cyberRuns
        .filter((r) => !r.kataId.startsWith('custom-'))
        .map((r) => r.kataId))
      return { unlocked: ids.size >= 8, progress: { current: ids.size, target: 8 } }
    },
  },
  {
    id: 'ac-perfect-flashcard', label: 'Maître flashcards',
    description: '3 decks flashcards 100% confiance dans la même semaine.',
    category: 'academy', glyph: '🃏',
    check: ({ academyRuns }) => {
      const cutoff = Date.now() - 7 * 86_400_000
      const n = academyRuns.filter((r) =>
        r.startedAt >= cutoff && (r.flashcardsConfidence ?? 0) >= 100
      ).length
      return { unlocked: n >= 3, progress: { current: n, target: 3 } }
    },
  },
  {
    id: 'ac-mentor', label: 'Mentor',
    description: '3 sessions "Corriger ma réponse" dans la même semaine.',
    category: 'academy', glyph: '🧑‍🏫',
    check: ({ academyRuns }) => {
      const cutoff = Date.now() - 7 * 86_400_000
      const n = academyRuns.filter((r) =>
        r.startedAt >= cutoff && r.mode.includes('Corriger')
      ).length
      return { unlocked: n >= 3, progress: { current: n, target: 3 } }
    },
  },
  {
    id: 'ac-mathematician', label: 'Mathématicien',
    description: '5 sessions Maths sans timeout cumulées.',
    category: 'academy', glyph: '📐',
    check: ({ academyRuns }) => {
      const n = academyRuns.filter((r) =>
        r.subject === 'Mathématiques' && !r.timeoutHit
      ).length
      return { unlocked: n >= 5, progress: { current: n, target: 5 } }
    },
  },
  {
    id: 'ac-scientist', label: 'Scientifique',
    description: '5 sessions sciences (Physique / Chimie / SVT) sans timeout.',
    category: 'academy', glyph: '🔬',
    check: ({ academyRuns }) => {
      const sciSubjects = new Set(['Physique', 'Chimie', 'SVT'])
      const n = academyRuns.filter((r) =>
        sciSubjects.has(r.subject) && !r.timeoutHit
      ).length
      return { unlocked: n >= 5, progress: { current: n, target: 5 } }
    },
  },
  {
    id: 'ac-humanist', label: 'Humaniste',
    description: '5 sessions humanités (Lettres / Histoire-Géo / Philo) sans timeout.',
    category: 'academy', glyph: '📜',
    check: ({ academyRuns }) => {
      const humSubjects = new Set(['Français / Lettres', 'Histoire-Géo', 'Philosophie'])
      const n = academyRuns.filter((r) =>
        humSubjects.has(r.subject) && !r.timeoutHit
      ).length
      return { unlocked: n >= 5, progress: { current: n, target: 5 } }
    },
  },
  {
    id: 'ac-polyglot', label: 'Polyglotte',
    description: '5 sessions Langues sans timeout cumulées.',
    category: 'academy', glyph: '🗣',
    check: ({ academyRuns }) => {
      const n = academyRuns.filter((r) =>
        r.subject === 'Langues' && !r.timeoutHit
      ).length
      return { unlocked: n >= 5, progress: { current: n, target: 5 } }
    },
  },
  {
    id: 'ac-economist', label: 'Économiste',
    description: '5 sessions Économie sans timeout cumulées.',
    category: 'academy', glyph: '💹',
    check: ({ academyRuns }) => {
      const n = academyRuns.filter((r) =>
        r.subject === 'Économie' && !r.timeoutHit
      ).length
      return { unlocked: n >= 5, progress: { current: n, target: 5 } }
    },
  },
  {
    id: 'ac-coder', label: 'Informaticien',
    description: '5 sessions Informatique / NSI sans timeout cumulées.',
    category: 'academy', glyph: '💻',
    check: ({ academyRuns }) => {
      const n = academyRuns.filter((r) =>
        r.subject.toLowerCase().includes('informatique') && !r.timeoutHit
      ).length
      return { unlocked: n >= 5, progress: { current: n, target: 5 } }
    },
  },
  {
    id: 'ac-everything-everywhere', label: 'Tout savant',
    description: 'Au moins 1 session sans timeout dans 7 matières différentes.',
    category: 'academy', glyph: '🌍',
    check: ({ academyRuns }) => {
      const subjects = new Set(
        academyRuns.filter((r) => !r.timeoutHit).map((r) => r.subject)
      )
      return { unlocked: subjects.size >= 7, progress: { current: subjects.size, target: 7 } }
    },
  },
  {
    id: 'ac-bac-s', label: 'Bac scientifique',
    description: '2 sessions sans timeout dans Physique + Chimie + Maths + SVT.',
    category: 'academy', glyph: '🎓',
    check: ({ academyRuns }) => {
      const need = ['Physique', 'Chimie', 'Mathématiques', 'SVT']
      const counts: Record<string, number> = {}
      for (const r of academyRuns) {
        if (r.timeoutHit) continue
        counts[r.subject] = (counts[r.subject] || 0) + 1
      }
      const done = need.filter((s) => (counts[s] || 0) >= 2).length
      return { unlocked: done >= need.length, progress: { current: done, target: need.length } }
    },
  },
  {
    id: 'ac-bac-l', label: 'Bac littéraire',
    description: '2 sessions sans timeout dans Français + Histoire-Géo + Philo + Langues.',
    category: 'academy', glyph: '📚',
    check: ({ academyRuns }) => {
      const need = ['Français / Lettres', 'Histoire-Géo', 'Philosophie', 'Langues']
      const counts: Record<string, number> = {}
      for (const r of academyRuns) {
        if (r.timeoutHit) continue
        counts[r.subject] = (counts[r.subject] || 0) + 1
      }
      const done = need.filter((s) => (counts[s] || 0) >= 2).length
      return { unlocked: done >= need.length, progress: { current: done, target: need.length } }
    },
  },
  {
    id: 'ac-bac-es', label: 'Bac sciences éco',
    description: '2 sessions sans timeout dans Maths + Histoire-Géo + Économie + Langues.',
    category: 'academy', glyph: '📊',
    check: ({ academyRuns }) => {
      const need = ['Mathématiques', 'Histoire-Géo', 'Économie', 'Langues']
      const counts: Record<string, number> = {}
      for (const r of academyRuns) {
        if (r.timeoutHit) continue
        counts[r.subject] = (counts[r.subject] || 0) + 1
      }
      const done = need.filter((s) => (counts[s] || 0) >= 2).length
      return { unlocked: done >= need.length, progress: { current: done, target: need.length } }
    },
  },
  {
    id: 'ac-mention-ab', label: 'Mention AB',
    description: 'Bac complet (n\'importe quelle série) + score moyen all-time ≥ 1000.',
    category: 'academy', glyph: '🥉',
    check: ({ academyRuns }) => {
      const checkBac = (need: string[]) => {
        const counts: Record<string, number> = {}
        for (const r of academyRuns) {
          if (r.timeoutHit) continue
          counts[r.subject] = (counts[r.subject] || 0) + 1
        }
        return need.every((s) => (counts[s] || 0) >= 2)
      }
      const bacS = checkBac(['Physique', 'Chimie', 'Mathématiques', 'SVT'])
      const bacL = checkBac(['Français / Lettres', 'Histoire-Géo', 'Philosophie', 'Langues'])
      const bacES = checkBac(['Mathématiques', 'Histoire-Géo', 'Économie', 'Langues'])
      const hasBac = bacS || bacL || bacES
      const scored = academyRuns.filter((r) => r.score > 0)
      const avg = scored.length === 0 ? 0
        : scored.reduce((a, r) => a + r.score, 0) / scored.length
      return {
        unlocked: hasBac && avg >= 1000,
        progress: { current: Math.round(avg), target: 1000 },
      }
    },
  },
  {
    id: 'ac-mention-b', label: 'Mention B',
    description: 'Bac complet + score moyen all-time ≥ 1300.',
    category: 'academy', glyph: '🥈',
    check: ({ academyRuns }) => {
      const checkBac = (need: string[]) => {
        const counts: Record<string, number> = {}
        for (const r of academyRuns) {
          if (r.timeoutHit) continue
          counts[r.subject] = (counts[r.subject] || 0) + 1
        }
        return need.every((s) => (counts[s] || 0) >= 2)
      }
      const hasBac =
        checkBac(['Physique', 'Chimie', 'Mathématiques', 'SVT'])
        || checkBac(['Français / Lettres', 'Histoire-Géo', 'Philosophie', 'Langues'])
        || checkBac(['Mathématiques', 'Histoire-Géo', 'Économie', 'Langues'])
      const scored = academyRuns.filter((r) => r.score > 0)
      const avg = scored.length === 0 ? 0
        : scored.reduce((a, r) => a + r.score, 0) / scored.length
      return {
        unlocked: hasBac && avg >= 1300,
        progress: { current: Math.round(avg), target: 1300 },
      }
    },
  },
  {
    id: 'ac-mention-tb', label: 'Mention TB',
    description: 'Bac complet + score moyen all-time ≥ 1500 (très bien).',
    category: 'academy', glyph: '🥇',
    check: ({ academyRuns }) => {
      const checkBac = (need: string[]) => {
        const counts: Record<string, number> = {}
        for (const r of academyRuns) {
          if (r.timeoutHit) continue
          counts[r.subject] = (counts[r.subject] || 0) + 1
        }
        return need.every((s) => (counts[s] || 0) >= 2)
      }
      const hasBac =
        checkBac(['Physique', 'Chimie', 'Mathématiques', 'SVT'])
        || checkBac(['Français / Lettres', 'Histoire-Géo', 'Philosophie', 'Langues'])
        || checkBac(['Mathématiques', 'Histoire-Géo', 'Économie', 'Langues'])
      const scored = academyRuns.filter((r) => r.score > 0)
      const avg = scored.length === 0 ? 0
        : scored.reduce((a, r) => a + r.score, 0) / scored.length
      return {
        unlocked: hasBac && avg >= 1500,
        progress: { current: Math.round(avg), target: 1500 },
      }
    },
  },
  {
    id: 'ac-mention-europeen', label: 'Mention Européenne',
    description: 'Bac + ≥ 5 runs Langues + score moyen Langues ≥ 1500.',
    category: 'academy', glyph: '🌍',
    check: ({ academyRuns }) => {
      const checkBac = (need: string[]) => {
        const counts: Record<string, number> = {}
        for (const r of academyRuns) {
          if (r.timeoutHit) continue
          counts[r.subject] = (counts[r.subject] || 0) + 1
        }
        return need.every((s) => (counts[s] || 0) >= 2)
      }
      const hasBac =
        checkBac(['Physique', 'Chimie', 'Mathématiques', 'SVT'])
        || checkBac(['Français / Lettres', 'Histoire-Géo', 'Philosophie', 'Langues'])
        || checkBac(['Mathématiques', 'Histoire-Géo', 'Économie', 'Langues'])
      const langRuns = academyRuns.filter((r) => r.subject === 'Langues' && r.score > 0)
      const avgLang = langRuns.length === 0 ? 0
        : langRuns.reduce((a, r) => a + r.score, 0) / langRuns.length
      const enoughRuns = langRuns.length >= 5
      return {
        unlocked: hasBac && enoughRuns && avgLang >= 1500,
        progress: { current: Math.round(avgLang), target: 1500 },
      }
    },
  },
  {
    id: 'ac-mention-felicitations', label: 'Félicitations du Jury',
    description: 'Bac complet + score moyen all-time ≥ 1700 (excellence).',
    category: 'academy', glyph: '👑',
    check: ({ academyRuns }) => {
      const checkBac = (need: string[]) => {
        const counts: Record<string, number> = {}
        for (const r of academyRuns) {
          if (r.timeoutHit) continue
          counts[r.subject] = (counts[r.subject] || 0) + 1
        }
        return need.every((s) => (counts[s] || 0) >= 2)
      }
      const hasBac =
        checkBac(['Physique', 'Chimie', 'Mathématiques', 'SVT'])
        || checkBac(['Français / Lettres', 'Histoire-Géo', 'Philosophie', 'Langues'])
        || checkBac(['Mathématiques', 'Histoire-Géo', 'Économie', 'Langues'])
      const scored = academyRuns.filter((r) => r.score > 0)
      const avg = scored.length === 0 ? 0
        : scored.reduce((a, r) => a + r.score, 0) / scored.length
      return {
        unlocked: hasBac && avg >= 1700,
        progress: { current: Math.round(avg), target: 1700 },
      }
    },
  },
  {
    // Engaged: personal weekly goal met (≥1 time). Tracked via localStorage or live check.
    id: 'cr-engage', label: 'Engagé',
    description: 'Atteins ton objectif perso hebdomadaire (banner Achievements).',
    category: 'cross', glyph: '🎯',
    check: ({ cyberRuns, academyRuns }) => {
      // Live check : lit weeklyGoal config + count runs cette semaine
      // par scope. Évite le besoin de tracker des unlocks séparés.
      if (typeof window === 'undefined') return { unlocked: false }
      let goal: { target: number; scope: 'all' | 'cyber' | 'academy' } | null = null
      try {
        const raw = window.localStorage.getItem('aurora-weekly-goal-v1')
        if (raw) goal = JSON.parse(raw)
      } catch { /* ignore */ }
      if (!goal || goal.target < 1) return { unlocked: false }
      const now = new Date()
      const day = now.getDay() === 0 ? 6 : now.getDay() - 1
      const monday = new Date(now)
      monday.setHours(0, 0, 0, 0)
      monday.setDate(monday.getDate() - day)
      const t0 = monday.getTime()
      const cyberWk = cyberRuns.filter((r) => r.startedAt >= t0).length
      const academyWk = academyRuns.filter((r) => r.startedAt >= t0).length
      const progress = goal.scope === 'cyber' ? cyberWk
        : goal.scope === 'academy' ? academyWk
        : cyberWk + academyWk
      return {
        unlocked: progress >= goal.target,
        progress: { current: progress, target: goal.target },
      }
    },
  },
  {
    id: 'cr-month-streak', label: 'Mensuel',
    description: 'Pratique 30 jours consécutifs.',
    category: 'cross', glyph: '🌟',
    check: ({ cyberRuns, academyRuns }) => {
      const allDays = new Set<string>()
      for (const r of [...cyberRuns, ...academyRuns]) {
        const d = new Date(r.startedAt)
        allDays.add(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
      }
      const sorted = Array.from(allDays).sort()
      let best = 0, cur = 0, prev = ''
      for (const day of sorted) {
        if (!prev) { cur = 1 }
        else {
          const prevD = new Date(prev + 'T00:00:00')
          const curD = new Date(day + 'T00:00:00')
          const diff = Math.round((curD.getTime() - prevD.getTime()) / 86_400_000)
          cur = diff === 1 ? cur + 1 : 1
        }
        prev = day
        if (cur > best) best = cur
      }
      return { unlocked: best >= 30, progress: { current: best, target: 30 } }
    },
  },

  // ─── Academy ─────────────────────────────────────────────────────
  {
    id: 'ac-first-session', label: 'Première session',
    description: 'Termine une session Academy en mode épreuve.',
    category: 'academy', glyph: '📚',
    check: ({ academyRuns }) => ({ unlocked: academyRuns.length >= 1 }),
  },
  {
    id: 'ac-three-subjects', label: 'Polymathe',
    description: 'Joue dans 3 matières différentes.',
    category: 'academy', glyph: '🧠',
    check: ({ academyRuns }) => {
      const ids = new Set(academyRuns.map((r) => r.subject))
      return { unlocked: ids.size >= 3, progress: { current: ids.size, target: 3 } }
    },
  },
  {
    id: 'ac-score-1000', label: 'Mention',
    description: 'Atteins un score Academy ≥ 1000 sur une session.',
    category: 'academy', glyph: '🏅',
    check: ({ academyRuns }) => {
      const max = academyRuns.reduce((m, r) => Math.max(m, r.score), 0)
      return { unlocked: max >= 1000, progress: { current: max, target: 1000 } }
    },
  },
  {
    id: 'ac-no-timeout-streak', label: 'Concentration',
    description: 'Termine 3 sessions sans timeout.',
    category: 'academy', glyph: '🎯',
    check: ({ academyRuns }) => {
      const ok = academyRuns.filter((r) => !r.timeoutHit).length
      return { unlocked: ok >= 3, progress: { current: ok, target: 3 } }
    },
  },
  {
    id: 'ac-flashcards-100', label: 'Mémoire d\'éléphant',
    description: 'Atteins 100% confiance sur un deck flashcards.',
    category: 'academy', glyph: '🐘',
    check: ({ academyRuns }) => ({
      unlocked: academyRuns.some((r) => (r.flashcardsConfidence ?? 0) >= 100),
    }),
  },
  {
    id: 'ac-subject-master', label: 'Maître d\'une matière',
    description: 'Cumule 3 sessions complètes (sans timeout) dans une même matière.',
    category: 'academy', glyph: '🎓',
    check: ({ academyRuns }) => {
      const counts: Record<string, number> = {}
      for (const r of academyRuns) {
        if (r.timeoutHit) continue
        counts[r.subject] = (counts[r.subject] || 0) + 1
      }
      const max = Math.max(0, ...Object.values(counts))
      return { unlocked: max >= 3, progress: { current: max, target: 3 } }
    },
  },
  {
    id: 'ac-mega-score', label: 'Excellence',
    description: 'Atteins un score Academy ≥ 1500 sur une session.',
    category: 'academy', glyph: '💎',
    check: ({ academyRuns }) => {
      const max = academyRuns.reduce((m, r) => Math.max(m, r.score), 0)
      return { unlocked: max >= 1500, progress: { current: max, target: 1500 } }
    },
  },
  {
    id: 'ac-triple-thousand', label: 'Triple mille',
    description: '3 sessions Academy consécutives (par date) avec score ≥ 1000.',
    category: 'academy', glyph: '💯',
    check: ({ academyRuns }) => {
      // Sort par startedAt asc, scan séquentiel pour la plus longue
      // séquence consécutive de scores ≥ 1000.
      const sorted = academyRuns.slice().sort((a, b) => a.startedAt - b.startedAt)
      let best = 0, cur = 0
      for (const r of sorted) {
        if (r.score >= 1000) { cur++; if (cur > best) best = cur }
        else cur = 0
      }
      return { unlocked: best >= 3, progress: { current: best, target: 3 } }
    },
  },

  // ─── Cross-module ────────────────────────────────────────────────
  {
    id: 'cr-double-master', label: 'Double maître',
    description: 'Débloque au moins 1 achievement dans Cyber ET dans Academy.',
    category: 'cross', glyph: '🌟',
    check: ({ cyberRuns, academyRuns }) => ({
      unlocked: cyberRuns.length > 0 && academyRuns.length > 0,
    }),
  },
  // Streak achievements: computed from longest consecutive streak across Cyber + Academy.
  {
    id: 'cr-streak-7d', label: 'Streak · semaine',
    description: '7 jours consécutifs avec au moins 1 run Cyber ou Academy.',
    category: 'cross', glyph: '🔥',
    check: ({ cyberRuns, academyRuns }) => {
      const ts = [
        ...cyberRuns.map((r) => r.endedAt || r.startedAt),
        ...academyRuns.map((r) => r.endedAt || r.startedAt),
      ]
      const r = computeStreak(ts)
      return {
        unlocked: r.longest >= 7,
        progress: { current: Math.min(r.longest, 7), target: 7 },
      }
    },
  },
  {
    id: 'cr-streak-30d', label: 'Streak · mois',
    description: '30 jours consécutifs avec au moins 1 run Cyber ou Academy.',
    category: 'cross', glyph: '🔥🔥',
    check: ({ cyberRuns, academyRuns }) => {
      const ts = [
        ...cyberRuns.map((r) => r.endedAt || r.startedAt),
        ...academyRuns.map((r) => r.endedAt || r.startedAt),
      ]
      const r = computeStreak(ts)
      return {
        unlocked: r.longest >= 30,
        progress: { current: Math.min(r.longest, 30), target: 30 },
      }
    },
  },
]

function computeTier(progress?: { current: number; target: number }): AchievementTier | undefined {
  if (!progress || progress.target <= 0) return undefined
  const ratio = progress.current / progress.target
  if (ratio >= 5) return 'diamond'
  if (ratio >= 3) return 'gold'
  if (ratio >= 2) return 'silver'
  if (ratio >= 1) return 'bronze'
  return undefined
}

export function computeAchievements(cyberRuns: KataRun[], academyRuns: AcademyRun[]): Achievement[] {
  return DEFS.map((d) => {
    const r = d.check({ cyberRuns, academyRuns })
    return {
      id: d.id,
      label: d.label,
      description: d.description,
      category: d.category,
      glyph: d.glyph,
      unlocked: r.unlocked,
      progress: r.progress,
      tier: r.unlocked ? computeTier(r.progress) : undefined,
    }
  })
}

export function countUnlocked(achievements: Achievement[]): { unlocked: number; total: number } {
  return {
    unlocked: achievements.filter((a) => a.unlocked).length,
    total: achievements.length,
  }
}

/**
 * Current daily streak: counts today or yesterday. Resets if neither have activity.
 */
export function currentStreak(cyberRuns: KataRun[], academyRuns: AcademyRun[]): number {
  const days = new Set<string>()
  for (const r of [...cyberRuns, ...academyRuns]) {
    const d = new Date(r.startedAt)
    days.add(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
  }
  if (days.size === 0) return 0
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1)
  // Le streak ne compte que si l'user a pratiqué aujourd'hui OU hier
  // (sinon le streak est cassé).
  let cursor = days.has(fmt(today)) ? today : days.has(fmt(yesterday)) ? yesterday : null
  if (!cursor) return 0
  let count = 0
  while (days.has(fmt(cursor))) {
    count++
    cursor.setDate(cursor.getDate() - 1)
  }
  return count
}
