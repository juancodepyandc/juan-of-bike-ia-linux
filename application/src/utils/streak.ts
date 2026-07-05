/**
 * v82i7 : compute streak (current + longest) à partir d'une liste de
 * timestamps. Factorise la logique dupliquée entre Cyber (v82i3+i4)
 * et Academy (v82i6).
 *
 * - Group runs par date YYYY-MM-DD locale (un même jour avec plusieurs
 *   runs = 1 jour streak, pas N).
 * - currentStreak : depuis aujourd'hui en remontant tant que la date
 *   est présente.
 * - longestStreak : tri lexicographique des dates + diff iter run-length.
 *   Failsafe max(best, run, current) pour gérer le cas où le run final
 *   inclut le current streak.
 */

export type StreakResult = { current: number; longest: number }

function dateKey(ts: number): string {
  const d = new Date(ts || 0)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * Compute streak from a list of timestamps (ms epoch).
 * @param timestamps liste de millisecondes epoch (peut contenir doublons).
 */
export function computeStreak(timestamps: Array<number | undefined | null>): StreakResult {
  if (!timestamps || timestamps.length === 0) return { current: 0, longest: 0 }
  const days = new Set<string>()
  for (const ts of timestamps) {
    if (typeof ts === 'number' && !Number.isNaN(ts) && ts > 0) {
      days.add(dateKey(ts))
    }
  }
  if (days.size === 0) return { current: 0, longest: 0 }

  // current : depuis aujourd'hui en remontant.
  let cur = 0
  const probe = new Date()
  probe.setHours(0, 0, 0, 0)
  while (true) {
    const key = dateKey(probe.getTime())
    if (days.has(key)) { cur++; probe.setDate(probe.getDate() - 1) } else break
  }

  // longest : tri lexicographique + diff iter run-length.
  const sorted = Array.from(days).sort()
  let best = 0, run = 0
  let prev: Date | null = null
  for (const k of sorted) {
    const [y, m, d] = k.split('-').map(Number)
    const cd = new Date(y, m - 1, d)
    if (prev) {
      const diff = Math.round((cd.getTime() - prev.getTime()) / (24 * 3600 * 1000))
      if (diff === 1) run++
      else { best = Math.max(best, run); run = 1 }
    } else { run = 1 }
    prev = cd
  }
  best = Math.max(best, run, cur)
  return { current: cur, longest: best }
}
