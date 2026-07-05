import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface CalEvent {
  id: string
  title: string
  start: number     // ms since epoch
  end: number
  location?: string
  description?: string
  source: 'ics' | 'manual'
  /** When imported from an ICS feed, raw UID so re-imports update instead of duplicating. */
  uid?: string
}

interface CalState {
  events: CalEvent[]
  feedUrl: string | null
  lastSyncedAt: number | null
  importIcs: (icsText: string, sourceName?: string) => number
  removeEvent: (id: string) => void
  clearAll: () => void
  setFeedUrl: (url: string | null) => void
}

// -------- Minimal ICS parser (no external dep) --------
function parseIcsDate(raw: string): number {
  // Either YYYYMMDDTHHMMSSZ or YYYYMMDD (all-day)
  const m = raw.match(/^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2}))?(Z)?$/)
  if (!m) return Date.now()
  const [, y, mo, d, h = '0', mi = '0', s = '0', z] = m
  const iso = `${y}-${mo}-${d}T${h.padStart(2, '0')}:${mi.padStart(2, '0')}:${s.padStart(2, '0')}${z ? 'Z' : ''}`
  const t = Date.parse(iso)
  return Number.isFinite(t) ? t : Date.now()
}

function unfold(text: string): string[] {
  // ICS folds long lines with CRLF+space; unfold before splitting
  const normalized = text.replace(/\r\n[ \t]/g, '').replace(/\r\n/g, '\n')
  return normalized.split('\n')
}

export function parseIcs(text: string): CalEvent[] {
  const lines = unfold(text)
  const events: CalEvent[] = []
  let inEvent = false
  let buf: Record<string, string> = {}
  for (const line of lines) {
    if (line === 'BEGIN:VEVENT') { inEvent = true; buf = {}; continue }
    if (line === 'END:VEVENT') {
      if (buf.UID || buf.SUMMARY) {
        events.push({
          id: `ics-${buf.UID || Math.random().toString(36).slice(2)}`,
          uid: buf.UID,
          title: buf.SUMMARY || '(sans titre)',
          start: parseIcsDate(buf.DTSTART || ''),
          end: parseIcsDate(buf.DTEND || buf.DTSTART || ''),
          location: buf.LOCATION,
          description: buf.DESCRIPTION,
          source: 'ics',
        })
      }
      inEvent = false; continue
    }
    if (!inEvent) continue
    const idx = line.indexOf(':')
    if (idx === -1) continue
    const keyPart = line.slice(0, idx)
    const value = line.slice(idx + 1)
    const key = keyPart.split(';')[0].toUpperCase()
    buf[key] = value
  }
  return events
}

export const useCalendarStore = create<CalState>()(
  persist(
    (set) => ({
      events: [],
      feedUrl: null,
      lastSyncedAt: null,
      importIcs: (icsText, _sourceName) => {
        const parsed = parseIcs(icsText)
        set((state) => {
          const byUid = new Map<string, CalEvent>()
          for (const ev of state.events) if (ev.uid) byUid.set(ev.uid, ev)
          const kept = state.events.filter((ev) => !ev.uid || !parsed.find((p) => p.uid === ev.uid))
          return { events: [...kept, ...parsed], lastSyncedAt: Date.now() }
        })
        return parsed.length
      },
      removeEvent: (id) => set((state) => ({ events: state.events.filter((e) => e.id !== id) })),
      clearAll: () => set({ events: [], lastSyncedAt: null }),
      setFeedUrl: (url) => set({ feedUrl: url }),
    }),
    { name: 'aurora-calendar-v1' },
  ),
)
