// Shared React components for the Learning module
import { memo, useState, useEffect, useRef, useMemo, useCallback } from 'react'
import type { ReactNode, RefObject } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, Star, Flame, Trophy, Layers, Sparkles, Target, BookOpen, GraduationCap, Map as MapIcon } from 'lucide-react'
import { useFlashcardsStore } from '../../stores/flashcardsStore'
import { useGamificationStore } from '../../stores/gamificationStore'
import type { LearningSource } from '../../services/learningResearch'
import type { TocEntry, Tab } from './types'
import { slugify } from './utils'

export function LearningMetricCard({
  icon: Icon,
  label,
  value,
  tone = 'default',
}: {
  icon: typeof Star
  label: string
  value: string
  tone?: 'default' | 'accent' | 'warm'
}) {
  const toneClass =
    tone === 'accent'
      ? 'bg-aurora-accent/14 text-aurora-accent'
      : tone === 'warm'
        ? 'bg-aurora-orange/14 text-aurora-orange'
        : 'bg-aurora-surface-2 text-aurora-text-dim'

  return (
    <div className="glass rounded-2xl p-4">
      <div className="flex items-center gap-3">
        <div className={`rounded-xl p-2.5 ${toneClass}`}>
          <Icon size={18} />
        </div>
        <div>
          <p className="text-xl font-semibold text-aurora-text">{value}</p>
          <p className="text-xs text-aurora-text-dim">{label}</p>
        </div>
      </div>
    </div>
  )
}

export function XpPopup({ amount }: { amount: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.92 }}
      animate={{ opacity: 1, y: -28, scale: 1 }}
      exit={{ opacity: 0, y: -52 }}
      className="fixed bottom-20 right-8 z-50 text-2xl font-bold gradient-text"
    >
      +{amount} XP
    </motion.div>
  )
}

export function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g
  let lastIndex = 0
  let count = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index))
    }
    const token = match[0]
    if (token.startsWith('**')) {
      nodes.push(
        <strong key={`${keyPrefix}-b-${count++}`} className="font-semibold text-aurora-text">
          {token.slice(2, -2)}
        </strong>,
      )
    } else if (token.startsWith('`')) {
      nodes.push(
        <code key={`${keyPrefix}-c-${count++}`} className="rounded bg-aurora-surface-2 px-1.5 py-0.5 text-[0.85em] text-aurora-accent">
          {token.slice(1, -1)}
        </code>,
      )
    }
    lastIndex = match.index + token.length
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex))
  }
  return nodes
}

export function MarkdownLite({ content }: { content: string }) {
  if (!content.trim()) return null
  const blocks: ReactNode[] = []
  const lines = content.split('\n')
  const seen = new Map<string, number>()
  let listBuffer: string[] = []
  let listType: 'ul' | 'ol' | null = null
  let paragraphBuffer: string[] = []
  let key = 0

  const flushList = () => {
    if (listBuffer.length === 0) return
    const items = listBuffer.map((item, idx) => (
      <li key={`li-${key}-${idx}`} className="leading-relaxed">
        {renderInline(item, `li-${key}-${idx}`)}
      </li>
    ))
    if (listType === 'ol') {
      blocks.push(
        <ol key={`ol-${key++}`} className="my-3 list-decimal space-y-1 pl-6 text-sm text-aurora-text">
          {items}
        </ol>,
      )
    } else {
      blocks.push(
        <ul key={`ul-${key++}`} className="my-3 list-disc space-y-1 pl-6 text-sm text-aurora-text">
          {items}
        </ul>,
      )
    }
    listBuffer = []
    listType = null
  }

  const flushParagraph = () => {
    if (paragraphBuffer.length === 0) return
    const text = paragraphBuffer.join(' ').trim()
    paragraphBuffer = []
    if (!text) return
    blocks.push(
      <p key={`p-${key++}`} className="my-3 text-sm leading-relaxed text-aurora-text">
        {renderInline(text, `p-${key}`)}
      </p>,
    )
  }

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/, '')
    if (!line.trim()) {
      flushList()
      flushParagraph()
      continue
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line.trim())
    if (heading) {
      flushList()
      flushParagraph()
      const level = heading[1].length
      const label = heading[2].trim().replace(/[*_`]/g, '')
      const base = slugify(label) || 'section'
      const occurrence = seen.get(base) ?? 0
      seen.set(base, occurrence + 1)
      const id = occurrence === 0 ? base : `${base}-${occurrence}`
      if (level === 1) {
        blocks.push(
          <h1 key={`h1-${key++}`} id={id} className="mt-6 mb-3 text-2xl font-semibold gradient-text">
            {label}
          </h1>,
        )
      } else if (level === 2) {
        blocks.push(
          <h2 key={`h2-${key++}`} id={id} className="mt-6 mb-2 text-lg font-semibold text-aurora-text">
            {label}
          </h2>,
        )
      } else {
        blocks.push(
          <h3 key={`h3-${key++}`} id={id} className="mt-4 mb-1.5 text-base font-medium text-aurora-accent">
            {label}
          </h3>,
        )
      }
      continue
    }

    const bullet = /^[-*]\s+(.+)$/.exec(line.trim())
    if (bullet) {
      flushParagraph()
      if (listType !== 'ul') {
        flushList()
        listType = 'ul'
      }
      listBuffer.push(bullet[1])
      continue
    }

    const ordered = /^(\d+)[.)]\s+(.+)$/.exec(line.trim())
    if (ordered) {
      flushParagraph()
      if (listType !== 'ol') {
        flushList()
        listType = 'ol'
      }
      listBuffer.push(ordered[2])
      continue
    }

    if (/^>\s+/.test(line.trim())) {
      flushList()
      flushParagraph()
      blocks.push(
        <blockquote
          key={`q-${key++}`}
          className="my-3 rounded-xl border-l-2 border-aurora-accent bg-aurora-accent/5 px-4 py-2 text-sm italic text-aurora-text-dim"
        >
          {renderInline(line.trim().replace(/^>\s+/, ''), `q-${key}`)}
        </blockquote>,
      )
      continue
    }

    paragraphBuffer.push(line.trim())
  }

  flushList()
  flushParagraph()

  return <div className="space-y-1">{blocks}</div>
}

export function ReadingProgress({ targetRef }: { targetRef: RefObject<HTMLElement | null> }) {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const element = targetRef.current
    if (!element) return
    const update = () => {
      const scrollTop = element.scrollTop
      const max = element.scrollHeight - element.clientHeight
      setProgress(max <= 0 ? 0 : Math.min(100, Math.max(0, (scrollTop / max) * 100)))
    }
    update()
    element.addEventListener('scroll', update, { passive: true })
    return () => element.removeEventListener('scroll', update)
  }, [targetRef])

  return (
    <div className="h-0.5 w-full overflow-hidden rounded-full bg-aurora-surface-2">
      <div
        className="h-full gradient-accent transition-[width] duration-150"
        style={{ width: `${progress}%` }}
      />
    </div>
  )
}

export function DashboardCharts({
  quizHistory,
  leitnerBoxes,
}: {
  quizHistory: Array<{ date: string; score: number; total: number; topic: string }>
  leitnerBoxes: [number, number, number, number, number]
}) {
  // Lazy-load recharts to avoid bloating the initial bundle on other tabs.
  const Charts = useMemo(() => {
    return {
      load: () => import('recharts'),
    }
  }, [])

  const [modules, setModules] = useState<null | {
    LineChart: typeof import('recharts').LineChart
    Line: typeof import('recharts').Line
    XAxis: typeof import('recharts').XAxis
    YAxis: typeof import('recharts').YAxis
    CartesianGrid: typeof import('recharts').CartesianGrid
    Tooltip: typeof import('recharts').Tooltip
    ResponsiveContainer: typeof import('recharts').ResponsiveContainer
    BarChart: typeof import('recharts').BarChart
    Bar: typeof import('recharts').Bar
    Cell: typeof import('recharts').Cell
  }>(null)

  useEffect(() => {
    let cancelled = false
    Charts.load().then((mod) => {
      if (cancelled) return
      setModules({
        LineChart: mod.LineChart,
        Line: mod.Line,
        XAxis: mod.XAxis,
        YAxis: mod.YAxis,
        CartesianGrid: mod.CartesianGrid,
        Tooltip: mod.Tooltip,
        ResponsiveContainer: mod.ResponsiveContainer,
        BarChart: mod.BarChart,
        Bar: mod.Bar,
        Cell: mod.Cell,
      })
    }).catch(() => setModules(null))
    return () => { cancelled = true }
  }, [Charts])

  if (!modules) return null

  const {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    BarChart,
    Bar,
    Cell,
  } = modules

  const quizSeries = quizHistory.slice(-14).map((entry, index) => ({
    name: `Q${quizHistory.length - Math.min(quizHistory.length, 14) + index + 1}`,
    pct: entry.total === 0 ? 0 : Math.round((entry.score / entry.total) * 100),
    topic: entry.topic.slice(0, 28),
  }))

  const leitnerData = leitnerBoxes.map((count, index) => ({
    name: `B${index + 1}`,
    count,
  }))

  const leitnerColors = ['#f87171', '#fb923c', '#fbbf24', '#4dd5a4', '#37c7bf']

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="glass rounded-2xl p-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-aurora-text-dim">Scores quiz (14 derniers)</p>
        {quizSeries.length === 0 ? (
          <p className="mt-6 text-xs text-aurora-text-dim">Aucun quiz encore passe — lance-en un pour voir la progression.</p>
        ) : (
          <div className="mt-3 h-48">
            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
              <LineChart data={quizSeries}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: '#f1f5f9' }}
                  formatter={((value: unknown, _key: unknown, entry: unknown) => {
                    const payload = (entry as { payload?: { topic?: string } } | undefined)?.payload
                    return [`${value}%`, payload?.topic ?? 'Score']
                  }) as unknown as (value: unknown, name: unknown) => [string, string]}
                />
                <Line type="monotone" dataKey="pct" stroke="#f97f3d" strokeWidth={2.5} dot={{ r: 3, fill: '#f97f3d' }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="glass rounded-2xl p-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-aurora-text-dim">Distribution Leitner</p>
        {leitnerBoxes.every((count) => count === 0) ? (
          <p className="mt-6 text-xs text-aurora-text-dim">Aucune fiche en etude — cree un deck pour alimenter les boites.</p>
        ) : (
          <div className="mt-3 h-48">
            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
              <BarChart data={leitnerData}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, fontSize: 12 }}
                  labelStyle={{ color: '#f1f5f9' }}
                  formatter={((value: unknown) => [`${value} fiche(s)`, 'Boite']) as unknown as (value: unknown, name: unknown) => [string, string]}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {leitnerData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={leitnerColors[index] ?? '#37c7bf'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}

export function SourcesPanel({ sources, open, onToggle }: { sources: LearningSource[]; open: boolean; onToggle: () => void }) {
  if (sources.length === 0) return null
  return (
    <div className="rounded-2xl border border-aurora-accent/25 bg-aurora-accent/5 p-4">
      <button onClick={onToggle} className="flex w-full items-center gap-2 text-xs font-semibold text-aurora-accent">
        <Sparkles size={13} />
        <span>Sources verifiees ({sources.length})</span>
        <ChevronDown size={12} className={`ml-auto transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-3 space-y-2 overflow-hidden"
          >
            {sources.map((source, index) => (
              <li key={`${source.origin}-${index}`} className="rounded-xl border border-aurora-border/40 bg-aurora-surface-2 px-3 py-2 text-[11px]">
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-aurora-accent/10 px-2 py-0.5 text-[10px] font-medium text-aurora-accent">S{index + 1}</span>
                  <span className="text-aurora-text">{source.title}</span>
                </div>
                {source.url && (
                  <a href={source.url} target="_blank" rel="noreferrer" className="mt-1 block truncate text-aurora-text-dim hover:text-aurora-accent">
                    {source.url}
                  </a>
                )}
                <p className="mt-1 text-aurora-text-dim line-clamp-3">{source.extract}</p>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  )
}

