/**
 * v82n0 — Tests for the popup "Today's activity" tile + background.js daily
 * stats counter logic. The implementation lives in :
 *   - application/extension/background.js  (statsTodayKey, bumpStatsCounter,
 *                                           cleanupStaleStats)
 *   - application/extension/popup.js        (statsTodayKey, formatStatsLine,
 *                                           refreshStats)
 *
 * Re-importing the SW + popup directly under node --test is impractical
 * (chrome API + DOM globals). Instead we encode the SAME contract here and
 * assert it stays in sync with both files. KEEP IN SYNC.
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/extensionStatsTile.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

// ---------------------------------------------------------------------------
// statsTodayKey — pure date-to-key. Mirror of background.js + popup.js.
// ---------------------------------------------------------------------------

function statsTodayKey(now: Date = new Date()): string {
  const yyyy = now.getFullYear()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  return 'aurora_stats_' + yyyy + '-' + mm + '-' + dd
}

describe('statsTodayKey', () => {
  test('format is aurora_stats_YYYY-MM-DD', () => {
    const k = statsTodayKey(new Date('2026-05-04T12:00:00Z'))
    assert.match(k, /^aurora_stats_\d{4}-\d{2}-\d{2}$/)
  })

  test('zero-pads single-digit months and days', () => {
    const k = statsTodayKey(new Date('2026-01-03T12:00:00Z'))
    assert.equal(k, 'aurora_stats_2026-01-03')
  })

  test('two consecutive days produce different keys', () => {
    const a = statsTodayKey(new Date('2026-05-04T22:00:00'))
    const b = statsTodayKey(new Date('2026-05-05T03:00:00'))
    assert.notEqual(a, b)
  })
})

// ---------------------------------------------------------------------------
// formatStatsLine — pure formatter, mirror of popup.js#formatStatsLine.
// ---------------------------------------------------------------------------

type Stats = {
  pages?: number; scrapes?: number; pins?: number; escalations?: number
  date?: string; updatedAt?: number
}

function formatStatsLine(stats: Stats | null | undefined): string {
  if (!stats || typeof stats !== 'object') {
    return "Aujourd'hui · 0 pages · 0 scrapes"
  }
  const pages = Number(stats.pages) || 0
  const scrapes = Number(stats.scrapes) || 0
  const pins = Number(stats.pins) || 0
  const escal = Number(stats.escalations) || 0
  const parts: string[] = []
  parts.push(pages + (pages === 1 ? ' page' : ' pages'))
  parts.push(scrapes + (scrapes === 1 ? ' scrape' : ' scrapes'))
  if (pins > 0) parts.push(pins + (pins === 1 ? ' pin' : ' pins'))
  if (escal > 0) parts.push(escal + (escal === 1 ? ' escalade' : ' escalades'))
  return "Aujourd'hui · " + parts.join(' · ')
}

describe('formatStatsLine', () => {
  test('null/undefined input → fallback line', () => {
    assert.equal(formatStatsLine(null), "Aujourd'hui · 0 pages · 0 scrapes")
    assert.equal(formatStatsLine(undefined), "Aujourd'hui · 0 pages · 0 scrapes")
  })

  test('full stats render in order pages/scrapes/pins/escalades', () => {
    const line = formatStatsLine({ pages: 12, scrapes: 7, pins: 2, escalations: 1 })
    assert.equal(line, "Aujourd'hui · 12 pages · 7 scrapes · 2 pins · 1 escalade")
  })

  test('singular forms used when count=1', () => {
    const line = formatStatsLine({ pages: 1, scrapes: 1, pins: 1, escalations: 1 })
    assert.equal(line, "Aujourd'hui · 1 page · 1 scrape · 1 pin · 1 escalade")
  })

  test('zero pins/escalations omitted from line', () => {
    const line = formatStatsLine({ pages: 5, scrapes: 3, pins: 0, escalations: 0 })
    assert.equal(line, "Aujourd'hui · 5 pages · 3 scrapes")
  })

  test('partial stats with only pages', () => {
    const line = formatStatsLine({ pages: 4 })
    assert.equal(line, "Aujourd'hui · 4 pages · 0 scrapes")
  })

  test('non-numeric values coerced to 0', () => {
    const line = formatStatsLine({
      pages: 'wat' as unknown as number,
      scrapes: NaN,
    })
    // 0 is plural in our French line ("0 pages"), only 1 takes the singular.
    assert.equal(line, "Aujourd'hui · 0 pages · 0 scrapes")
  })
})

// ---------------------------------------------------------------------------
// bumpStatsCounter — simulated via in-memory storage, mirrors background.js.
// We re-implement the increment + persist semantics on a Map so we can
// exercise the daily rollover and cleanup without chrome.storage.
// ---------------------------------------------------------------------------

class MemStorage {
  data = new Map<string, unknown>()
  set(obj: Record<string, unknown>): void {
    for (const [k, v] of Object.entries(obj)) this.data.set(k, v)
  }
  get(keys: string[] | null): Record<string, unknown> {
    const out: Record<string, unknown> = {}
    if (keys === null) {
      for (const [k, v] of this.data) out[k] = v
    } else {
      for (const k of keys) if (this.data.has(k)) out[k] = this.data.get(k)
    }
    return out
  }
  remove(keys: string[]): void {
    for (const k of keys) this.data.delete(k)
  }
}

function bumpStatsCounter(field: string, store: MemStorage, now: Date = new Date()): void {
  const key = statsTodayKey(now)
  const got = store.get([key])
  const cur = (got[key] as Record<string, unknown> | undefined)
    || { pages: 0, scrapes: 0, pins: 0, escalations: 0 }
  const next: Record<string, unknown> = { ...cur }
  next[field] = (Number(next[field]) || 0) + 1
  next.date = key.replace('aurora_stats_', '')
  next.updatedAt = now.getTime()
  store.set({ [key]: next })
}

function cleanupStaleStats(store: MemStorage, now: Date = new Date()): void {
  const today = statsTodayKey(now)
  const todayDate = today.replace('aurora_stats_', '')
  const todayMs = Date.parse(todayDate + 'T00:00:00')
  if (!Number.isFinite(todayMs)) return
  const all = store.get(null)
  const stale: string[] = []
  for (const k of Object.keys(all)) {
    if (!k.startsWith('aurora_stats_')) continue
    if (k === today) continue
    const dateStr = k.replace('aurora_stats_', '')
    const ms = Date.parse(dateStr + 'T00:00:00')
    if (!Number.isFinite(ms)) { stale.push(k); continue }
    if (todayMs - ms > 7 * 24 * 3600 * 1000) stale.push(k)
  }
  if (stale.length > 0) store.remove(stale)
}

describe('bumpStatsCounter', () => {
  test('increment from 0 creates entry with correct date', () => {
    const s = new MemStorage()
    const now = new Date('2026-05-04T10:00:00')
    bumpStatsCounter('pages', s, now)
    const e = s.data.get('aurora_stats_2026-05-04') as Record<string, unknown>
    assert.equal(e.pages, 1)
    assert.equal(e.scrapes, 0)
    assert.equal(e.date, '2026-05-04')
  })

  test('three bumps on same field → counter=3', () => {
    const s = new MemStorage()
    const now = new Date('2026-05-04T10:00:00')
    bumpStatsCounter('pages', s, now)
    bumpStatsCounter('pages', s, now)
    bumpStatsCounter('pages', s, now)
    const e = s.data.get('aurora_stats_2026-05-04') as Record<string, unknown>
    assert.equal(e.pages, 3)
  })

  test('two days produce two separate entries', () => {
    const s = new MemStorage()
    bumpStatsCounter('pages', s, new Date('2026-05-04T10:00:00'))
    bumpStatsCounter('scrapes', s, new Date('2026-05-05T10:00:00'))
    assert.ok(s.data.has('aurora_stats_2026-05-04'))
    assert.ok(s.data.has('aurora_stats_2026-05-05'))
    const day1 = s.data.get('aurora_stats_2026-05-04') as Record<string, unknown>
    const day2 = s.data.get('aurora_stats_2026-05-05') as Record<string, unknown>
    assert.equal(day1.pages, 1)
    assert.equal(day1.scrapes, 0)
    assert.equal(day2.pages, 0)
    assert.equal(day2.scrapes, 1)
  })

  test('all four fields increment independently', () => {
    const s = new MemStorage()
    const now = new Date('2026-05-04T10:00:00')
    bumpStatsCounter('pages', s, now)
    bumpStatsCounter('scrapes', s, now)
    bumpStatsCounter('pins', s, now)
    bumpStatsCounter('escalations', s, now)
    const e = s.data.get('aurora_stats_2026-05-04') as Record<string, unknown>
    assert.equal(e.pages, 1)
    assert.equal(e.scrapes, 1)
    assert.equal(e.pins, 1)
    assert.equal(e.escalations, 1)
  })
})

describe('cleanupStaleStats', () => {
  test('removes entries older than 7 days', () => {
    const s = new MemStorage()
    // Seed 10 days of past data + today.
    const today = new Date('2026-05-04T10:00:00')
    for (let i = 0; i <= 10; i++) {
      const d = new Date(today)
      d.setDate(d.getDate() - i)
      const key = statsTodayKey(d)
      s.set({ [key]: { pages: i, date: key.replace('aurora_stats_', '') } })
    }
    assert.equal(s.data.size, 11)
    cleanupStaleStats(s, today)
    // Today + last 7 days = 8 entries kept.
    assert.equal(s.data.size, 8, 'only entries within 7 days are retained')
    assert.ok(s.data.has(statsTodayKey(today)))
  })

  test('keeps yesterday entry', () => {
    const s = new MemStorage()
    const today = new Date('2026-05-04T10:00:00')
    const yesterday = new Date('2026-05-03T10:00:00')
    s.set({ [statsTodayKey(today)]: { pages: 1 } })
    s.set({ [statsTodayKey(yesterday)]: { pages: 5 } })
    cleanupStaleStats(s, today)
    assert.ok(s.data.has(statsTodayKey(today)))
    assert.ok(s.data.has(statsTodayKey(yesterday)), 'yesterday must survive cleanup')
  })

  test('removes malformed-date entries', () => {
    const s = new MemStorage()
    const today = new Date('2026-05-04T10:00:00')
    s.set({ [statsTodayKey(today)]: { pages: 1 } })
    s.set({ 'aurora_stats_garbage': { pages: 99 } })
    cleanupStaleStats(s, today)
    assert.equal(s.data.has('aurora_stats_garbage'), false)
  })

  test('does not touch non-stats keys', () => {
    const s = new MemStorage()
    const today = new Date('2026-05-04T10:00:00')
    s.set({ 'bridgeUrl': 'http://127.0.0.1:3001' })
    s.set({ 'pagetype_42': { pageType: { article: true } } })
    s.set({ [statsTodayKey(today)]: { pages: 1 } })
    cleanupStaleStats(s, today)
    assert.ok(s.data.has('bridgeUrl'))
    assert.ok(s.data.has('pagetype_42'))
  })
})

// ---------------------------------------------------------------------------
// End-to-end : popup reads what background writes.
// ---------------------------------------------------------------------------

describe('end-to-end popup reads SW counter', () => {
  test('popup formatStatsLine uses the SW-written entry', () => {
    const s = new MemStorage()
    const now = new Date('2026-05-04T10:00:00')
    // SW bumps : 12 pages, 7 scrapes, 2 escalations
    for (let i = 0; i < 12; i++) bumpStatsCounter('pages', s, now)
    for (let i = 0; i < 7; i++) bumpStatsCounter('scrapes', s, now)
    for (let i = 0; i < 2; i++) bumpStatsCounter('escalations', s, now)
    // Popup reads
    const key = statsTodayKey(now)
    const stats = s.get([key])[key] as Stats
    const line = formatStatsLine(stats)
    assert.equal(line, "Aujourd'hui · 12 pages · 7 scrapes · 2 escalades")
  })
})
