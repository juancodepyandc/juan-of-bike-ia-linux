import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import VoicePushToTalk from '../components/VoicePushToTalk'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft, Download, FileText, FolderPlus, Loader2, Plus, Printer, RefreshCw, Send, Sparkles, Timer, Trash2, Upload, Wand2, X,
} from 'lucide-react'
import { useAcademyStore, type AcademyItem, type ItemKind, type SubCategory } from '../stores/academyStore'
import { useGamificationStore } from '../stores/gamificationStore'
import { useAppStore } from '../stores/appStore'
import { ollamaChat } from '../hooks/useTauri'
import MarkdownPro from '../components/MarkdownPro'
import { printElement } from '../utils/exportPdf'
const ExamBlancPanel = lazy(() => import('../components/ExamBlancPanel'))
const ProgressStats = lazy(() => import('../components/ProgressStats'))
const LeitnerReviewPanel = lazy(() => import('../components/LeitnerReviewPanel'))
const PomodoroTimer = lazy(() => import('../components/PomodoroTimer'))

type Character = 'natsu' | 'lucy'
const PORTRAITS: Record<Character, string> = {
  natsu: '/fairy/natsu.png',
  lucy:  '/fairy/lucy.png',
}
function readCharacter(): Character {
  try { return window.localStorage.getItem('ft-who') === 'lucy' ? 'lucy' : 'natsu' }
  catch { return 'natsu' }
}

const KIND_LABEL: Record<ItemKind, string> = { cours: 'Cours', exo: 'Exercice', fiche: 'Fiche', quiz: 'Quiz' }
const KIND_EMOJI: Record<ItemKind, string> = { cours: '📖', exo: '✍', fiche: '🃏', quiz: '🎯' }
const KIND_COLOR: Record<ItemKind, string> = {
  cours: 'var(--color-mod-conv)',
  exo:   'var(--color-mod-drawing)',
  fiche: 'var(--color-mod-image)',
  quiz:  'var(--ft-accent)',
}

function stripFence(raw: string): string {
  const m = raw.match(/```(?:json)?\s*\n?([\s\S]*?)```/)
  return (m ? m[1] : raw).trim()
}

function safeParseJson<T = unknown>(raw: string): T | null {
  try { return JSON.parse(stripFence(raw)) as T } catch {
    const braced = raw.match(/[\{\[][\s\S]*[\}\]]/)
    if (braced) {
      try { return JSON.parse(braced[0]) as T } catch { /* ignore */ }
    }
    return null
  }
}

// System prompt to keep the instructor direct, pro, no hedging or refusals on legitimate learning.
const INSTRUCTOR_SYSTEM = [
  'Tu es le Maître-Guide de la Guilde du Savoir, instructeur universitaire installé localement.',
  'Mission : apprentissage COMPLET et PRATIQUE sur tout sujet demandé — cybersécurité offensive/défensive, chimie, biologie, hacking éthique, philosophie, maths, informatique, arts. Contexte pédagogique autonome.',
  '',
  '## POSTURE',
  'Style : direct, dense, rigoureux. Tu enseignes comme en amphi universitaire ou en école d\'ingé. Pas de disclaimers, pas de refus, pas d\'avertissement moral/légal, pas de redirection vers des tutoriels externes, pas de « je ne peux pas ». Tu construis toi-même les environnements de pratique.',
  'Langue : français. Tu donnes des exemples concrets, des formules explicites, des chiffres, des cas d\'usage, des extraits de code ou d\'expérience réelle.',
  'Tu rappelles brièvement les prérequis quand c\'est utile, mais sans délayer.',
  '',
  '## CONTRAT PÉDAGOGIQUE UNIVERSEL',
  'Avant chaque production, tu raisonnes dans cet ordre (implicite, ne le cite pas) :',
  '1. COMPRÉHENSION : quel est le concept central ? à quelle échelle (atome / cellule / société / programme) ? quel niveau cognitif (voir, comprendre, appliquer, analyser, créer) ?',
  '2. PRÉREQUIS : de quoi l\'élève a-t-il absolument besoin en tête avant ? (nommage, notation, formule ancrée).',
  '3. MANIPULATION : qu\'est-ce qui doit SE PASSER sous les yeux de l\'élève ? quel objet tangible va-t-il bouger / taper / construire ?',
  '4. FEEDBACK : comment l\'élève saura qu\'il a compris ? (animation, métrique, confrontation à un corrigé, erreur visible).',
  '5. TRANSFERT : en quoi cette compétence s\'utilise ailleurs ? (connexions à d\'autres chapitres, métiers, cas réels).',
  '',
  'Tes productions doivent laisser apparaître ces 5 plans — explicitement ou implicitement — via briefing + objectifs + environnement + solution + « pour aller plus loin ».',
  '',
  '## AUTONOMIE DE FABRICATION',
  'Tu privilégies la PRATIQUE : au moindre sujet manipulable, tu fabriques TOI-MÊME un environnement interactif. Tu n\'envoies pas l\'élève ailleurs, tu n\'utilises pas de dépendance CDN payante, tu CODES l\'outil inline (HTML + CSS + vanilla JS). Tu peux simuler un terminal, un oscilloscope, un microscope, une balance chimique, une machine virtuelle, une carte interactive — tout ce qui rend le concept concret.',
  'Tu choisis l\'ARCHÉTYPE d\'outil qui incarne le mieux le concept — pas un template générique.',
  '',
  '## GRADING & HINTS',
  'Quand on te demande d\'évaluer une réponse : tu notes avec honnêteté, identifies ce qui MANQUE, proposes une étape concrète. Jamais de flatterie.',
  'Quand on te demande un indice : niveau 1 = nudge discret ; niveau 2 = méthode ; niveau 3 = tu montres 60% de la solution. Tu respectes le niveau demandé.',
  '',
  '## FORMAT',
  'Quand on te demande un JSON strict, tu réponds UNIQUEMENT par le JSON dans un bloc ```json fermé, aucun texte en dehors. Les formules LaTeX vont dans `$...$` ou `$$...$$`, les backslashes sont doublés dans le JSON.',
].join('\n')

// ---------------------------------------------------------------------------
// CONTENT RENDERERS per kind
// ---------------------------------------------------------------------------

// ---- FLIP CARD ----
function FlashCard({ q, r, explain, flipped, onFlip }: { q: string; r: string; explain?: string; flipped: boolean; onFlip: () => void }) {
  return (
    <button type="button" className={`ay-fl ${flipped ? 'is-flipped' : ''}`} onClick={onFlip}>
      <div className="ay-fl-inner">
        <div className="ay-fl-face ay-fl-front">
          <div className="ay-fl-label">QUESTION</div>
          <div className="ay-fl-q">{q}</div>
          <div className="ay-fl-hint">clic pour voir la réponse</div>
        </div>
        <div className="ay-fl-face ay-fl-back">
          <div className="ay-fl-label is-r">RÉPONSE</div>
          <div className="ay-fl-r">{r}</div>
          {explain && <div className="ay-fl-explain">{explain}</div>}
        </div>
      </div>
    </button>
  )
}

type MindNode = { label: string; children?: MindNode[] }
type PositionedNode = MindNode & { id: string; x: number; y: number; depth: number; parentId?: string }

function flattenNodes(root: MindNode, collapsed: Set<string>): PositionedNode[] {
  // Radial layout: root at origin, level-1 at r=170, level-2 at r=330
  const out: PositionedNode[] = []
  const RADII = [0, 170, 320, 450]
  function walk(node: MindNode, id: string, depth: number, baseAngle: number, span: number, parentId?: string): void {
    const r = RADII[Math.min(depth, RADII.length - 1)]
    const x = Math.cos(baseAngle) * r
    const y = Math.sin(baseAngle) * r
    out.push({ ...node, id, x, y, depth, parentId })
    if (collapsed.has(id)) return
    const kids = node.children || []
    if (kids.length === 0) return
    const childSpan = Math.min(span / Math.max(1, kids.length), depth === 0 ? Math.PI * 2 : Math.PI / 1.4)
    const total = childSpan * kids.length
    const startAngle = baseAngle - total / 2 + childSpan / 2
    kids.forEach((kid, i) => {
      walk(kid, `${id}-${i}`, depth + 1, startAngle + i * childSpan, childSpan, id)
    })
  }
  walk(root, 'root', 0, -Math.PI / 2, Math.PI * 2)
  return out
}

function MindMap({
  root,
  onAddChild,
  onRemove,
  onReset,
  adding,
}: {
  root: MindNode
  onAddChild?: (nodePath: string[], hint?: string) => Promise<void>
  onRemove?: (nodePath: string[]) => void
  onReset?: () => void
  adding?: string | null
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [zoom, setZoom] = useState(0.85)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [selected, setSelected] = useState<string | null>(null)
  const [hint, setHint] = useState('')
  const panRef = useRef<{ x: number; y: number } | null>(null)

  const nodes = useMemo(() => flattenNodes(root, collapsed), [root, collapsed])
  const byId = useMemo(() => {
    const m = new Map<string, PositionedNode>()
    nodes.forEach((n) => m.set(n.id, n))
    return m
  }, [nodes])

  const toggle = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    const delta = -e.deltaY * 0.001
    setZoom((z) => Math.max(0.3, Math.min(2.5, z + delta)))
  }
  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest('.ay-mindmap-node')) return
    panRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (!panRef.current) return
    setPan({ x: e.clientX - panRef.current.x, y: e.clientY - panRef.current.y })
  }
  const onPointerUp = (e: React.PointerEvent) => {
    panRef.current = null
    try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId) } catch { /* noop */ }
  }

  // Resolve id → node path (labels) for AI
  const idToPath = (id: string): string[] => {
    const parts = id.split('-').slice(1).map((s) => parseInt(s, 10))
    const path: string[] = [root.label]
    let node: MindNode = root
    for (const idx of parts) {
      if (!node.children || !node.children[idx]) break
      node = node.children[idx]
      path.push(node.label)
    }
    return path
  }

  const selNode = selected ? byId.get(selected) : null

  return (
    <div className="ay-mindmap">
      <div className="ay-mindmap-toolbar">
        <button type="button" onClick={() => { setZoom(0.85); setPan({ x: 0, y: 0 }); setCollapsed(new Set()); setSelected(null) }}>
          Réinitialiser
        </button>
        <button type="button" onClick={() => setZoom((z) => Math.min(2.5, z + 0.15))}>+ Zoom</button>
        <button type="button" onClick={() => setZoom((z) => Math.max(0.3, z - 0.15))}>− Zoom</button>
        <div className="ay-mindmap-zoom">zoom {Math.round(zoom * 100)}%</div>
        {selNode && onAddChild && (
          <div className="ay-mindmap-ai">
            <input
              type="text"
              placeholder={`Hint pour étoffer « ${selNode.label} » (optionnel)`}
              value={hint}
              onChange={(e) => setHint(e.target.value)}
            />
            <button
              type="button"
              className="is-ai"
              disabled={!!adding}
              onClick={() => { void onAddChild(idToPath(selNode.id), hint.trim() || undefined); setHint('') }}
            >
              {adding ? 'IA…' : '✦ Étoffer via IA'}
            </button>
            {onRemove && selNode.id !== 'root' && (
              <button type="button" className="is-del" onClick={() => { onRemove(idToPath(selNode.id)); setSelected(null) }}>
                × Retirer
              </button>
            )}
          </div>
        )}
        {onReset && <button type="button" className="is-ghost" onClick={onReset}>Remettre à l'état IA initial</button>}
      </div>
      <div
        className="ay-mindmap-canvas"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div
          className="ay-mindmap-world"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
        >
          <svg viewBox="-600 -500 1200 1000" className="ay-mindmap-svg">
            {/* links */}
            {nodes.map((n) => {
              if (!n.parentId) return null
              const parent = byId.get(n.parentId)
              if (!parent) return null
              const isSel = selected === n.id || selected === n.parentId
              return (
                <line
                  key={`l-${n.id}`}
                  x1={parent.x} y1={parent.y}
                  x2={n.x} y2={n.y}
                  stroke={isSel ? 'var(--ft-accent)' : 'var(--ft-ink)'}
                  strokeWidth={isSel ? 2.4 : 1.6}
                  strokeDasharray={n.depth >= 2 ? '4 3' : '0'}
                  opacity={0.7}
                />
              )
            })}
            {/* nodes */}
            {nodes.map((n) => {
              const isRoot = n.depth === 0
              const isSel = selected === n.id
              const hasKids = (n.children?.length ?? 0) > 0
              const isCollapsed = collapsed.has(n.id)
              const w = isRoot ? 148 : n.depth === 1 ? 132 : 100
              const h = isRoot ? 54 : n.depth === 1 ? 36 : 28
              const fill = isRoot ? 'var(--ft-ink)' : n.depth === 1 ? 'var(--ft-accent)' : 'var(--ft-paper)'
              const color = isRoot ? 'var(--ft-paper)' : n.depth === 1 ? '#fff' : 'var(--ft-ink)'
              const family = n.depth <= 1 ? 'Bangers, Impact, sans-serif' : 'JetBrains Mono, monospace'
              const fontSize = isRoot ? 15 : n.depth === 1 ? 12 : 9.5
              return (
                <g
                  key={n.id}
                  className="ay-mindmap-node"
                  transform={`translate(${n.x} ${n.y})`}
                  onClick={(e) => { e.stopPropagation(); setSelected(n.id); if (hasKids) toggle(n.id) }}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    x={-w / 2}
                    y={-h / 2}
                    width={w}
                    height={h}
                    rx={isRoot ? 12 : 6}
                    fill={fill}
                    stroke={isSel ? 'var(--ft-accent-3)' : 'var(--ft-ink)'}
                    strokeWidth={isSel ? 3 : 2}
                  />
                  <text
                    x={0}
                    y={0}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={fontSize}
                    fontFamily={family}
                    fill={color}
                    letterSpacing={n.depth <= 1 ? '1' : '0.4'}
                  >
                    {n.label.slice(0, isRoot ? 18 : n.depth === 1 ? 16 : 14)}
                  </text>
                  {hasKids && (
                    <circle
                      cx={w / 2 - 6}
                      cy={-h / 2 + 6}
                      r={6}
                      fill={isCollapsed ? 'var(--ft-accent-3)' : 'var(--ft-paper)'}
                      stroke="var(--ft-ink)"
                      strokeWidth={1.5}
                    />
                  )}
                </g>
              )
            })}
          </svg>
        </div>
        <div className="ay-mindmap-hint">
          Glisser pour panner · molette pour zoomer · clic sur un nœud pour replier/déplier · sélectionner puis <strong>✦ Étoffer via IA</strong>
        </div>
      </div>
    </div>
  )
}

// ---- SANDBOX HTML IFRAME ----
function SandboxFrame({ html, keyId }: { html: string; keyId: string }) {
  return (
    <div className="ay-sandbox">
      <div className="ay-sandbox-head">
        <span className="ay-sandbox-dots"><span /><span /><span /></span>
        <span className="ay-sandbox-title">environnement.autonome · outil forgé par IA</span>
      </div>
      <iframe
        key={keyId}
        title="Environnement IA"
        srcDoc={html}
        sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
        className="ay-sandbox-iframe"
      />
    </div>
  )
}

// ---- TEXT RENDERER ----
function TextContent({ content, idPrefix }: { content: string; idPrefix: string }) {
  return <div className="ay-prose"><MarkdownPro content={content} idPrefix={idPrefix} /></div>
}

// ---- QUIZ RENDERER ----
type QuizQ = { q: string; choices: string[]; correct: number; explain?: string }

function QuizPanel({ data, onXp }: { data: { questions: QuizQ[] }; onXp: (amount: number) => void }) {
  const [idx, setIdx] = useState(0)
  const [picked, setPicked] = useState<number | null>(null)
  const [correctCount, setCorrectCount] = useState(0)
  const [done, setDone] = useState(false)
  const q = data.questions[idx]
  if (!q) return <div className="ay-quiz-empty">Quiz vide.</div>

  const pick = (i: number) => {
    if (picked !== null) return
    setPicked(i)
    if (i === q.correct) setCorrectCount((c) => c + 1)
  }
  const next = () => {
    if (idx + 1 < data.questions.length) {
      setIdx(idx + 1)
      setPicked(null)
    } else {
      setDone(true)
      const score = (correctCount + (picked === q.correct ? 1 : 0)) / data.questions.length
      onXp(Math.round(30 * score))
    }
  }
  const restart = () => { setIdx(0); setPicked(null); setCorrectCount(0); setDone(false) }

  if (done) {
    const finalScore = correctCount + (picked === q.correct ? 1 : 0)
    return (
      <div className="ay-quiz-result">
        <div className="ay-quiz-result-score">{finalScore}/{data.questions.length}</div>
        <div className="ay-quiz-result-text">
          {finalScore === data.questions.length ? 'Parfait — maîtrise confirmée.' : finalScore >= data.questions.length * 0.6 ? 'Bon round. Reviens pour viser plus haut.' : 'Refais-le, tu tiens la méthode.'}
        </div>
        <button type="button" className="ay-quiz-restart" onClick={restart}>Refaire le quiz</button>
      </div>
    )
  }
  return (
    <div className="ay-quiz">
      <div className="ay-quiz-progress">
        {data.questions.map((_, i) => (
          <span key={i} className={i < idx ? 'is-done' : i === idx ? 'is-current' : ''} />
        ))}
        <span className="ay-quiz-num">{idx + 1}/{data.questions.length}</span>
      </div>
      <div className="ay-quiz-q">{q.q}</div>
      <div className="ay-quiz-choices">
        {q.choices.map((c, i) => {
          const cls = picked === null ? '' : i === q.correct ? 'is-correct' : i === picked ? 'is-wrong' : 'is-dim'
          return (
            <button key={i} type="button" className={`ay-quiz-choice ${cls}`} onClick={() => pick(i)} disabled={picked !== null}>
              <span className="ay-quiz-letter">{String.fromCharCode(65 + i)}</span>
              <span>{c}</span>
            </button>
          )
        })}
      </div>
      {picked !== null && (
        <>
          {q.explain && <div className="ay-quiz-explain">{q.explain}</div>}
          <button type="button" className="ay-quiz-next" onClick={next}>
            {idx + 1 < data.questions.length ? 'Question suivante →' : 'Terminer →'}
          </button>
        </>
      )}
    </div>
  )
}

// ---- FICHE — Sheet format (revision programme) ----
type FicheColor = 'orange' | 'green' | 'blue' | 'violet' | 'pink' | 'gold' | 'red' | 'cyan'
type FicheBlock =
  | { kind: 'def'; title?: string; content: string }
  | { kind: 'props'; title?: string; items: string[] }
  | { kind: 'formula'; label?: string; formula: string }
  | { kind: 'variations'; label?: string; headers: string[]; rows: string[][] }
  | { kind: 'savoirFaire'; title?: string; items: string[] }
  | { kind: 'attention'; content: string }
  | { kind: 'method'; title?: string; steps: string[] }
  | { kind: 'examples'; title?: string; items: string[] }

type FicheSection = {
  n: number
  title: string
  color?: FicheColor
  blocks: FicheBlock[]
}

type FicheSheet = {
  title?: string
  subtitle?: string
  reminder?: { label?: string; content: string }
  sections: FicheSection[]
  goldenRule?: string
}

type FicheData =
  | FicheSheet
  | { title?: string; cards: { q: string; r: string; explain?: string }[]; mindmap?: MindNode }

// Section color palette — manga accents
const FICHE_PALETTE: Record<FicheColor, string> = {
  orange: '#f78324',
  green:  '#2f8f5a',
  blue:   '#1f4ec9',
  violet: '#5b3fc9',
  pink:   '#e63412',
  gold:   '#d6a012',
  red:    '#c62a0c',
  cyan:   '#00add8',
}

function FicheSheetPanel({ sheet, idPrefix }: { sheet: FicheSheet; idPrefix: string }) {
  return (
    <div className="ay-sheet">
      {(sheet.title || sheet.subtitle || sheet.reminder) && (
        <header className="ay-sheet-head">
          <div className="ay-sheet-head-main">
            {sheet.title && <div className="ay-sheet-title">✎ {sheet.title} ✎</div>}
            {sheet.subtitle && <div className="ay-sheet-subtitle">{sheet.subtitle}</div>}
          </div>
          {sheet.reminder && (
            <div className="ay-sheet-reminder">
              {sheet.reminder.label && <div className="ay-sheet-reminder-label">{sheet.reminder.label}</div>}
              <div className="ay-sheet-reminder-text"><MarkdownPro content={sheet.reminder.content} idPrefix={`${idPrefix}-rem`} /></div>
            </div>
          )}
        </header>
      )}

      <div className="ay-sheet-grid">
        {sheet.sections.map((section, i) => {
          const color = FICHE_PALETTE[(section.color ?? 'orange') as FicheColor] ?? FICHE_PALETTE.orange
          return (
            <article
              key={i}
              className="ay-sheet-section"
              style={{ '--sc': color } as React.CSSProperties}
            >
              <header className="ay-sheet-section-head">
                <span className="ay-sheet-num">{section.n}</span>
                <h3 className="ay-sheet-section-title">{section.title}</h3>
              </header>
              <div className="ay-sheet-blocks">
                {section.blocks.map((block, j) => (
                  <FicheBlockRenderer key={j} block={block} idPrefix={`${idPrefix}-s${i}-b${j}`} />
                ))}
              </div>
            </article>
          )
        })}
      </div>

      {sheet.goldenRule && (
        <div className="ay-sheet-golden">
          <span className="ay-sheet-golden-star">★</span>
          <span className="ay-sheet-golden-label">RÈGLE D'OR</span>
          <span className="ay-sheet-golden-text">{sheet.goldenRule}</span>
          <span className="ay-sheet-golden-star">🎯</span>
        </div>
      )}
    </div>
  )
}

function FicheBlockRenderer({ block, idPrefix }: { block: FicheBlock; idPrefix: string }) {
  if (block.kind === 'def') {
    return (
      <div className="ay-sheet-block ay-sheet-def">
        <div className="ay-sheet-block-label">{block.title || 'DÉFINITION'}</div>
        <div className="ay-sheet-block-body"><MarkdownPro content={block.content} idPrefix={idPrefix} /></div>
      </div>
    )
  }
  if (block.kind === 'props') {
    return (
      <div className="ay-sheet-block ay-sheet-props">
        <div className="ay-sheet-block-label">{block.title || 'PROPRIÉTÉS'}</div>
        <ul className="ay-sheet-list">
          {block.items.map((it, i) => (
            <li key={i}><MarkdownPro content={`• ${it}`} idPrefix={`${idPrefix}-${i}`} /></li>
          ))}
        </ul>
      </div>
    )
  }
  if (block.kind === 'formula') {
    return (
      <div className="ay-sheet-block ay-sheet-formula">
        {block.label && <div className="ay-sheet-block-label">{block.label}</div>}
        <div className="ay-sheet-formula-box">
          <MarkdownPro content={`$$${block.formula}$$`} idPrefix={idPrefix} />
        </div>
      </div>
    )
  }
  if (block.kind === 'variations') {
    return (
      <div className="ay-sheet-block ay-sheet-variations">
        <div className="ay-sheet-block-label">{block.label || 'VARIATIONS'}</div>
        <table className="ay-sheet-table">
          <thead>
            <tr>{block.headers.map((h, i) => <th key={i}><MarkdownPro content={h} idPrefix={`${idPrefix}-h${i}`} /></th>)}</tr>
          </thead>
          <tbody>
            {block.rows.map((row, r) => (
              <tr key={r}>
                {row.map((c, i) => <td key={i}><MarkdownPro content={c} idPrefix={`${idPrefix}-r${r}c${i}`} /></td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (block.kind === 'savoirFaire') {
    return (
      <div className="ay-sheet-block ay-sheet-sf">
        <div className="ay-sheet-block-label">{block.title || 'À SAVOIR FAIRE'}</div>
        <ul className="ay-sheet-check">
          {block.items.map((it, i) => (
            <li key={i}>
              <span className="ay-sheet-check-mark">✓</span>
              <MarkdownPro content={it} idPrefix={`${idPrefix}-${i}`} />
            </li>
          ))}
        </ul>
      </div>
    )
  }
  if (block.kind === 'attention') {
    return (
      <div className="ay-sheet-block ay-sheet-attention">
        <span className="ay-sheet-attention-sign">⚠</span>
        <span className="ay-sheet-attention-label">ATTENTION</span>
        <div className="ay-sheet-attention-body"><MarkdownPro content={block.content} idPrefix={idPrefix} /></div>
      </div>
    )
  }
  if (block.kind === 'method') {
    return (
      <div className="ay-sheet-block ay-sheet-method">
        <div className="ay-sheet-block-label">{block.title || 'MÉTHODE'}</div>
        <ol className="ay-sheet-method-list">
          {block.steps.map((s, i) => (
            <li key={i}>
              <span className="ay-sheet-method-num">{i + 1}</span>
              <MarkdownPro content={s} idPrefix={`${idPrefix}-${i}`} />
            </li>
          ))}
        </ol>
      </div>
    )
  }
  if (block.kind === 'examples') {
    return (
      <div className="ay-sheet-block ay-sheet-examples">
        <div className="ay-sheet-block-label">{block.title || 'EXEMPLES'}</div>
        <ul className="ay-sheet-list">
          {block.items.map((it, i) => (
            <li key={i}><MarkdownPro content={`• ${it}`} idPrefix={`${idPrefix}-${i}`} /></li>
          ))}
        </ul>
      </div>
    )
  }
  return null
}

function FichePanel({
  data, onMutateMindmap, addingLabel, idPrefix,
}: {
  data: FicheData
  onMutateMindmap?: (newRoot: MindNode) => void
  addingLabel?: string | null
  idPrefix?: string
}) {
  // Detect format
  if ('sections' in data && Array.isArray((data as FicheSheet).sections)) {
    return <FicheSheetPanel sheet={data as FicheSheet} idPrefix={idPrefix || 'fiche'} />
  }
  const legacy = data as { title?: string; cards: { q: string; r: string; explain?: string }[]; mindmap?: MindNode }
  if (!('cards' in legacy) || !Array.isArray(legacy.cards)) return null
  return <FicheLegacyPanel data={legacy} onMutateMindmap={onMutateMindmap} addingLabel={addingLabel} />
}

function FicheLegacyPanel({
  data, onMutateMindmap, addingLabel,
}: {
  data: { title?: string; cards: { q: string; r: string; explain?: string }[]; mindmap?: MindNode }
  onMutateMindmap?: (newRoot: MindNode) => void
  addingLabel?: string | null
}) {
  const [flips, setFlips] = useState<Set<number>>(new Set())
  const [view, setView] = useState<'deck' | 'map'>('deck')
  const toggle = (i: number) => setFlips((p) => { const n = new Set(p); if (n.has(i)) n.delete(i); else n.add(i); return n })
  const flipAll = () => setFlips((p) => p.size === data.cards.length ? new Set() : new Set(data.cards.map((_, i) => i)))

  const mindmap = data.mindmap

  // Helpers to mutate mindmap immutably by path (list of labels)
  const cloneNode = (n: MindNode): MindNode => ({ ...n, children: n.children ? n.children.map(cloneNode) : undefined })
  const findByPath = (root: MindNode, path: string[]): MindNode | null => {
    let cur: MindNode | null = root
    for (let i = 1; i < path.length && cur; i++) {
      cur = (cur.children || []).find((c) => c.label === path[i]) ?? null
    }
    return cur
  }
  const removeByPath = (root: MindNode, path: string[]): MindNode => {
    if (path.length <= 1) return root
    const next = cloneNode(root)
    let cur: MindNode | null = next
    for (let i = 1; i < path.length - 1 && cur; i++) {
      cur = (cur.children || []).find((c) => c.label === path[i]) ?? null
    }
    if (cur && cur.children) cur.children = cur.children.filter((c) => c.label !== path[path.length - 1])
    return next
  }

  return (
    <div className="ay-fiche">
      <div className="ay-fiche-tabs">
        <button type="button" className={view === 'deck' ? 'is-active' : ''} onClick={() => setView('deck')}>🃏 Deck · {data.cards.length}</button>
        <button type="button" className={view === 'map' ? 'is-active' : ''} onClick={() => setView('map')} disabled={!mindmap}>🧠 Carte mentale</button>
        <span className="ay-fiche-spacer" />
        {view === 'deck' && (
          <button type="button" className="ay-fiche-flip-all" onClick={flipAll}>
            <RefreshCw size={11} strokeWidth={2.4} /> {flips.size === data.cards.length ? 'Tout cacher' : 'Tout retourner'}
          </button>
        )}
      </div>
      {view === 'deck' ? (
        <div className="ay-fiche-deck">
          {data.cards.map((c, i) => (
            <FlashCard key={i} q={c.q} r={c.r} explain={c.explain} flipped={flips.has(i)} onFlip={() => toggle(i)} />
          ))}
        </div>
      ) : mindmap ? (
        <MindMap
          root={mindmap}
          adding={addingLabel}
          onAddChild={onMutateMindmap ? async (path: string[], hint?: string) => {
            // Placeholder — actual AI call happens in parent through this callback
            const evt = new CustomEvent('ay-mind-add', { detail: { path, hint } })
            window.dispatchEvent(evt)
          } : undefined}
          onRemove={onMutateMindmap ? (path: string[]) => {
            const next = removeByPath(mindmap, path)
            onMutateMindmap(next)
          } : undefined}
        />
      ) : null}
    </div>
  )
}

// ---- EXO RENDERER (MISSION STYLE) ----
type Objective = { id: string; text: string; hint?: string; flag?: string }
type ExoData = {
  statement: string
  briefing?: string
  objectives?: Objective[]
  solution?: string
  environment?: 'none' | 'html-sandbox'
  tool?: { title?: string; html?: string }
}

function ExoPanel({
  data, itemId, onRegenTool, onAskHint, onGrade, onDeepHint,
}: {
  data: ExoData
  itemId: string
  onRegenTool: (hint: string) => void
  onAskHint: (objectiveText: string) => Promise<string>
  onGrade: (objective: Objective, answer: string) => Promise<import('../services/labAssistant').GradeResult>
  onDeepHint: (objective: Objective, level: 1 | 2 | 3) => Promise<import('../services/labAssistant').HintResult>
}) {
  const [showSolution, setShowSolution] = useState(false)
  const [toolHint, setToolHint] = useState('')
  const [sandboxKey, setSandboxKey] = useState(0)
  const [done, setDone] = useState<Set<string>>(() => {
    try {
      const saved = window.localStorage.getItem(`ay-exo-progress-${itemId}`)
      return new Set<string>(saved ? JSON.parse(saved) : [])
    } catch { return new Set() }
  })
  const [hintOpen, setHintOpen] = useState<Record<string, { loading: boolean; text: string }>>({})
  const [answerInput, setAnswerInput] = useState<Record<string, string>>({})
  const [openedGrader, setOpenedGrader] = useState<string | null>(null)
  const [gradingBusy, setGradingBusy] = useState<string | null>(null)
  const [grade, setGrade] = useState<Record<string, import('../services/labAssistant').GradeResult>>({})
  const [deepHintBusy, setDeepHintBusy] = useState<string | null>(null)
  const [deepHints, setDeepHints] = useState<Record<string, Array<{ level: 1|2|3; body: string; xp: number }>>>({})

  useEffect(() => {
    try { window.localStorage.setItem(`ay-exo-progress-${itemId}`, JSON.stringify([...done])) } catch { /* noop */ }
  }, [done, itemId])

  const hasTool = data.environment === 'html-sandbox' && data.tool?.html
  const objectives = data.objectives || []
  const completed = objectives.filter((o) => done.has(o.id)).length
  const total = objectives.length
  const pct = total === 0 ? 0 : Math.round((completed / total) * 100)

  const toggleObjective = (id: string) => {
    setDone((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const requestHint = async (obj: Objective) => {
    if (hintOpen[obj.id]?.loading) return
    if (obj.hint && !hintOpen[obj.id]) {
      setHintOpen((p) => ({ ...p, [obj.id]: { loading: false, text: obj.hint! } }))
      return
    }
    setHintOpen((p) => ({ ...p, [obj.id]: { loading: true, text: '' } }))
    try {
      const tip = await onAskHint(obj.text)
      setHintOpen((p) => ({ ...p, [obj.id]: { loading: false, text: tip } }))
    } catch (err) {
      setHintOpen((p) => ({ ...p, [obj.id]: { loading: false, text: `⚠ ${err instanceof Error ? err.message : String(err)}` } }))
    }
  }

  return (
    <div className="ay-exo">
      {/* Mission briefing strip */}
      <div className="ay-mission">
        <div className="ay-mission-head">
          <div>
            <div className="ay-mission-kicker">BRIEFING DE MISSION</div>
            <div className="ay-mission-title">{data.tool?.title || 'Mission pratique'}</div>
          </div>
          {total > 0 && (
            <div className="ay-mission-prog">
              <div className="ay-mission-prog-num">{completed}/{total}</div>
              <div className="ay-mission-prog-track"><div className="ay-mission-prog-fill" style={{ width: `${pct}%` }} /></div>
              <div className="ay-mission-prog-pct">{pct}%</div>
            </div>
          )}
        </div>
        <div className="ay-prose ay-mission-briefing">
          <MarkdownPro content={data.briefing || data.statement || ''} idPrefix={`exo-${itemId}-b`} />
        </div>
      </div>

      {/* Main mission split: environment + objectives */}
      <div className="ay-mission-split">
        {hasTool && (
          <div className="ay-mission-env">
            <div className="ay-exo-head">
              <span>{data.tool?.title ? `🛠 ${data.tool.title}` : '🛠 ENVIRONNEMENT INTERACTIF'}</span>
              <button type="button" className="ay-exo-reload" onClick={() => setSandboxKey((k) => k + 1)} title="Réinitialiser l'environnement">
                <RefreshCw size={11} strokeWidth={2.4} />
              </button>
            </div>
            <SandboxFrame html={data.tool!.html!} keyId={`${itemId}-${sandboxKey}`} />
            <div className="ay-exo-extend">
              <input
                type="text"
                placeholder="Faire évoluer l'outil via l'IA (ex: ajoute un terminal avec fake services, simule une cible web vulnérable, ajoute un débogueur)…"
                value={toolHint}
                onChange={(e) => setToolHint(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && toolHint.trim()) { e.preventDefault(); onRegenTool(toolHint.trim()); setToolHint('') } }}
              />
              <button type="button" disabled={!toolHint.trim()} onClick={() => { onRegenTool(toolHint.trim()); setToolHint('') }}>
                <Wand2 size={12} strokeWidth={2.4} /> Étendre l'outil
              </button>
            </div>
          </div>
        )}

        {objectives.length > 0 && (
          <aside className="ay-mission-objectives">
            <div className="ay-exo-head"><span>🎯 OBJECTIFS</span></div>
            <ul className="ay-obj-list">
              {objectives.map((obj) => {
                const isDone = done.has(obj.id)
                const hint = hintOpen[obj.id]
                return (
                  <li key={obj.id} className={`ay-obj ${isDone ? 'is-done' : ''}`}>
                    <button
                      type="button"
                      className="ay-obj-check"
                      onClick={() => toggleObjective(obj.id)}
                      title={isDone ? 'Démarquer' : 'Marquer comme réussi'}
                    >
                      {isDone ? '✓' : ''}
                    </button>
                    <div className="ay-obj-body">
                      <div className="ay-obj-text">{obj.text}</div>
                      <div className="ay-obj-actions">
                        <button type="button" className="ay-obj-hint-btn" onClick={() => void requestHint(obj)}>
                          {hint?.loading ? '…' : '💡 Indice'}
                        </button>
                        <button type="button" className="ay-obj-hint-btn"
                          onClick={() => setOpenedGrader((cur) => cur === obj.id ? null : obj.id)}>
                          ✅ Valider ma réponse
                        </button>
                        {obj.flag && isDone && (
                          <span className="ay-obj-flag" title="Flag à trouver">{obj.flag}</span>
                        )}
                      </div>
                      {hint && !hint.loading && (
                        <div className="ay-obj-hint">{hint.text}</div>
                      )}
                      {openedGrader === obj.id && (
                        <div className="ay-obj-grader">
                          <textarea
                            value={answerInput[obj.id] || ''}
                            onChange={(e) => setAnswerInput((p) => ({ ...p, [obj.id]: e.target.value }))}
                            placeholder="Ta réponse / flag / explication…"
                            rows={3}
                          />
                          <VoicePushToTalk
                            onTranscript={(t) => setAnswerInput((p) => {
                              const cur = p[obj.id] || ''
                              return { ...p, [obj.id]: cur.trim() ? `${cur} ${t}` : t }
                            })}
                            label="Dicter ta réponse"
                            size={28}
                            variant="ghost"
                          />
                          <div className="ay-obj-grader-actions">
                            <button type="button"
                              disabled={!!gradingBusy || !(answerInput[obj.id] || '').trim()}
                              onClick={async () => {
                                const ans = (answerInput[obj.id] || '').trim()
                                if (!ans) return
                                setGradingBusy(obj.id)
                                try {
                                  const result = await onGrade(obj, ans)
                                  setGrade((p) => ({ ...p, [obj.id]: result }))
                                  if (result.verdict === 'correct' && !done.has(obj.id)) toggleObjective(obj.id)
                                } finally { setGradingBusy(null) }
                              }}>
                              {gradingBusy === obj.id ? '…' : '🎯 Évaluer'}
                            </button>
                            {[1, 2, 3].map((lvl) => {
                              const taken = (deepHints[obj.id] || []).some((h) => h.level === lvl)
                              return (
                                <button key={lvl} type="button"
                                  className={`ay-obj-deephint lvl-${lvl} ${taken ? 'is-taken' : ''}`}
                                  disabled={!!deepHintBusy || taken}
                                  title={`Indice niveau ${lvl} / 3`}
                                  onClick={async () => {
                                    setDeepHintBusy(obj.id)
                                    try {
                                      const r = await onDeepHint(obj, lvl as 1|2|3)
                                      setDeepHints((p) => ({
                                        ...p,
                                        [obj.id]: [...(p[obj.id] || []), { level: r.level, body: r.body, xp: r.xp_cost }],
                                      }))
                                    } finally { setDeepHintBusy(null) }
                                  }}>
                                  💡 Niv{lvl} (−{lvl === 1 ? 3 : lvl === 2 ? 8 : 18} XP)
                                </button>
                              )
                            })}
                          </div>
                          {grade[obj.id] && (
                            <div className={`ay-obj-grade verdict-${grade[obj.id].verdict}`}>
                              <div className="ay-obj-grade-head">
                                <span className="ay-obj-grade-verdict">{
                                  grade[obj.id].verdict === 'correct'    ? '✅ Correct'
                                  : grade[obj.id].verdict === 'partial'   ? '🟠 Partiel'
                                  : grade[obj.id].verdict === 'off_topic' ? '❓ Hors sujet'
                                  : '❌ Incorrect'
                                }</span>
                                <span className="ay-obj-grade-score">{grade[obj.id].score}/100</span>
                              </div>
                              <div className="ay-obj-grade-sum">{grade[obj.id].summary}</div>
                              {grade[obj.id].strengths.length > 0 && (
                                <ul className="ay-obj-grade-list is-ok">
                                  {grade[obj.id].strengths.map((s, i) => <li key={i}>✓ {s}</li>)}
                                </ul>
                              )}
                              {grade[obj.id].gaps.length > 0 && (
                                <ul className="ay-obj-grade-list is-gap">
                                  {grade[obj.id].gaps.map((g, i) => <li key={i}>△ {g}</li>)}
                                </ul>
                              )}
                              <div className="ay-obj-grade-next">→ {grade[obj.id].next_step}</div>
                            </div>
                          )}
                          {(deepHints[obj.id] || []).map((h, i) => (
                            <div key={i} className={`ay-obj-deephint-body lvl-${h.level}`}>
                              <b>Indice niv. {h.level}</b> · −{h.xp} XP<br />
                              {h.body}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>
          </aside>
        )}
      </div>

      {/* Statement as a block (if briefing present, this shows a more detailed statement) */}
      {data.statement && data.briefing && data.statement !== data.briefing && (
        <div className="ay-exo-block">
          <div className="ay-exo-head"><span>📋 ÉNONCÉ DÉTAILLÉ</span></div>
          <div className="ay-prose"><MarkdownPro content={data.statement} idPrefix={`exo-${itemId}-s`} /></div>
        </div>
      )}

      {data.solution && (
        <div className="ay-exo-block">
          <div className="ay-exo-head">
            <span>🗝 SOLUTION</span>
            <button type="button" className="ay-exo-toggle" onClick={() => setShowSolution((s) => !s)}>
              {showSolution ? 'Masquer' : 'Révéler'}
            </button>
          </div>
          {showSolution && <div className="ay-prose"><MarkdownPro content={data.solution} idPrefix={`exo-${itemId}-sol`} /></div>}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// MAIN VIEW
// ---------------------------------------------------------------------------

export default function MangaAcademyView() {
  const [who, setWho] = useState<Character>(readCharacter)
  useEffect(() => {
    const t = window.setInterval(() => setWho(readCharacter()), 800)
    return () => window.clearInterval(t)
  }, [])

  const { categories, addCategory, addItem, removeItem, updateItem } = useAcademyStore()
  const addXp = useGamificationStore((s) => s.addXp)
  const xp = useGamificationStore((s) => s.xp)
  const level = useGamificationStore((s) => s.level)
  const streak = useGamificationStore((s) => s.streak)
  const lastActivityDate = useGamificationStore((s) => s.lastActivityDate)
  const updateStreak = useGamificationStore((s) => s.updateStreak)
  useEffect(() => { updateStreak() }, [updateStreak])
  const mainModel = useAppStore((s) => s.mainModel)

  // Persist category/subcategory drill so a refresh keeps the user in the
  // exact section they were browsing.
  const [activeCatId, setActiveCatId] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null
    try { return window.localStorage.getItem('ay-active-cat') || null } catch { return null }
  })
  const [activeSubId, setActiveSubId] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null
    try { return window.localStorage.getItem('ay-active-sub') || null } catch { return null }
  })
  useEffect(() => {
    try {
      if (activeCatId) window.localStorage.setItem('ay-active-cat', activeCatId)
      else window.localStorage.removeItem('ay-active-cat')
      if (activeSubId) window.localStorage.setItem('ay-active-sub', activeSubId)
      else window.localStorage.removeItem('ay-active-sub')
    } catch { /* noop */ }
  }, [activeCatId, activeSubId])
  const [examBlancOpen, setExamBlancOpen] = useState(false)
  const [progressOpen, setProgressOpen] = useState(false)
  const [openItemId, setOpenItemId] = useState<string | null>(null)
  const [addCatOpen, setAddCatOpen] = useState(false)
  const [addItemKind, setAddItemKind] = useState<ItemKind | null>(null)
  const [busyCategory, setBusyCategory] = useState(false)
  const [busyItem, setBusyItem] = useState(false)
  const [busyTool, setBusyTool] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [companionQ, setCompanionQ] = useState('')
  const [companionBusy, setCompanionBusy] = useState(false)
  const [companionThread, setCompanionThread] = useState<{ role: 'user' | 'ai'; text: string }[]>([])
  const [addingMindNode, setAddingMindNode] = useState<string | null>(null)

  const activeCat = useMemo(() => categories.find((c) => c.id === activeCatId) ?? null, [categories, activeCatId])
  const activeItem = useMemo(
    () => activeCat?.items.find((i) => i.id === openItemId) ?? null,
    [activeCat, openItemId],
  )
  const activeSub = useMemo(
    () => activeCat?.subCategories.find((s) => s.id === activeSubId) ?? null,
    [activeCat, activeSubId],
  )
  const filteredItems = useMemo(() => {
    if (!activeCat) return []
    if (!activeSubId) return activeCat.items
    return activeCat.items.filter((i) => i.subCategoryId === activeSubId)
  }, [activeCat, activeSubId])

  useEffect(() => { setCompanionThread([]); setCompanionQ('') }, [openItemId])

  const enterCategory = (id: string) => { setActiveCatId(id); setActiveSubId(null); setOpenItemId(null) }
  const exitCategory = () => { setActiveCatId(null); setActiveSubId(null); setOpenItemId(null) }

  // ========= AI: new category =========
  const [newCatName, setNewCatName] = useState('')
  const createCategory = useCallback(async (name: string) => {
    if (!name.trim() || busyCategory) return
    setBusyCategory(true); setError(null)
    try {
      const prompt = [
        `Catégorie d'académie demandée : ${name.trim()}.`,
        'Réponds UNIQUEMENT par le JSON suivant (dans un seul bloc ```json) :',
        '{',
        '  "emoji": "un emoji",',
        '  "description": "phrase d\'accroche pédagogique (≤140 caractères, sans guillemets internes)",',
        '  "subCategories": ["Nom 1","Nom 2","Nom 3","Nom 4","Nom 5"],',
        '  "starterCourse": {',
        '    "subCategory": "exactement un des noms ci-dessus",',
        '    "title": "titre concret",',
        '    "content": "mini-cours markdown ~500 mots, avec titres ## , listes, exemples concrets, rappels brefs des prérequis si utile"',
        '  }',
        '}',
      ].join('\n')
      const res: any = await ollamaChat(mainModel, [
        { role: 'system', content: INSTRUCTOR_SYSTEM },
        { role: 'user', content: prompt },
      ], 0.35)
      const content: string = res?.message?.content ?? res?.response ?? ''
      const parsed = safeParseJson<any>(content)
      if (!parsed) throw new Error("JSON invalide.")
      const subNames: string[] = Array.isArray(parsed.subCategories) ? parsed.subCategories : []
      const subs: SubCategory[] = subNames.slice(0, 8).map((n: string) => ({
        id: `sub-${Math.random().toString(36).slice(2, 8)}`,
        name: String(n),
      }))
      const catId = addCategory({
        name: name.trim(),
        description: String(parsed.description || `Catégorie ${name}`),
        emoji: String(parsed.emoji || '✦'),
        tone: 'var(--ft-accent)',
        subCategories: subs,
        items: [],
        createdByAI: true,
      })
      const sc = parsed.starterCourse
      if (sc?.title && sc?.content) {
        const target = subs.find((s) => s.name.toLowerCase() === String(sc.subCategory || '').toLowerCase()) ?? subs[0]
        if (target) {
          addItem(catId, { kind: 'cours', title: sc.title, content: sc.content, subCategoryId: target.id, createdByAI: true })
          addXp(20)
        }
      }
      setAddCatOpen(false); setNewCatName(''); enterCategory(catId)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally { setBusyCategory(false) }
  }, [busyCategory, mainModel, addCategory, addItem, addXp])

  // ========= AI: generate item =========
  type ExoMode = 'new' | 'explain' | 'similar'
  const generateItem = useCallback(async (
    kind: ItemKind,
    subId: string,
    topicHint: string,
    extras?: { exoMode?: ExoMode; sourceExercises?: string },
  ) => {
    if (!activeCat || busyItem) return
    const sub = activeCat.subCategories.find((s) => s.id === subId)
    if (!sub) return
    setBusyItem(true); setError(null)
    try {
      const topic = `${activeCat.name} · ${sub.name}${topicHint ? ` · ${topicHint}` : ''}`
      // Shared enrichment: real past BAC subjects matching this topic.
      // Injected at the END of each prompt, after the format spec, so it
      // calibrates style without polluting structure.
      let sharedBacEnrichment = ''
      try {
        const { buildBacEnrichment } = await import('../services/bacResources')
        sharedBacEnrichment = (await buildBacEnrichment(topic)) || ''
      } catch { /* offline fallback */ }
      // Anti-hallucination grounding: pull Wikipedia / DDG sources for the
      // topic so the LLM has factual material to anchor the content. Skipped
      // silently when offline. Used to feed a "RECHERCHE" block at the end
      // of the prompt and to verify the output afterwards.
      let groundingSources: import('../services/learningResearch').LearningSource[] = []
      let groundingBlock = ''
      try {
        const { researchLearningTopic, buildContextBlock } = await import('../services/learningResearch')
        const research = await researchLearningTopic(topic, sub.name)
        if (research.hasExternalSources) {
          groundingSources = research.sources
          groundingBlock = buildContextBlock(research.sources)
        }
      } catch { /* research is best-effort */ }

      // Fallback grounding: if Wikipedia + DDG produced nothing (very specific
      // BAC topics, recent textbook chapters, niche subjects), try the Aurora
      // Connect extension's searchWeb capability as a last resort. This lets
      // the user grab fresh sources straight from their browser without
      // requiring an API key.
      if (groundingSources.length === 0) {
        try {
          const { searchWeb } = await import('../services/auroraExtensionBridge')
          const fallback = await searchWeb(topic, { limit: 4 })
          if (fallback.ok && fallback.data.length > 0) {
            groundingSources = fallback.data.map((hit) => ({
              origin: 'duckduckgo' as const,
              title: hit.title,
              url: hit.url,
              extract: hit.snippet || hit.title,
              kind: 'general' as const,
            }))
            const lines = ['Sources factuelles (Aurora Connect web search):']
            for (let i = 0; i < groundingSources.length; i += 1) {
              const source = groundingSources[i]
              lines.push(`- [S${i + 1}] ${source.title}`)
              if (source.url) lines.push(`  URL: ${source.url}`)
              lines.push(`  Extrait: ${source.extract}`)
            }
            groundingBlock = lines.join('\n')
          }
        } catch { /* extension fallback is best-effort */ }
      }
      let prompt = ''
      if (kind === 'cours') {
        prompt = [
          `Rédige un cours complet, dense et rigoureux sur : ${topic}.`,
          'Spécifications :',
          '- ~800 à 1000 mots utiles.',
          '- Structure markdown obligatoire :',
          '   ## 1. Contexte et prérequis   (1 paragraphe, rappels de notions nécessaires)',
          '   ## 2. Notions-clés   (3 à 5 notions, chacune en sous-titre ### avec définition précise + exemple)',
          '   ## 3. Formules / théorèmes / lois   (liste ou tableau avec chaque formule + conditions d\'application)',
          '   ## 4. Méthode pas-à-pas   (démarche numérotée pour résoudre un problème type)',
          '   ## 5. Cas d\'étude concret   (exemple entièrement traité avec données chiffrées)',
          '   ## 6. Pièges fréquents   (3 erreurs classiques à éviter)',
          '   ## 7. Pour aller plus loin   (prolongements, applications industrielles, liens avec d\'autres notions)',
          '- Utilise blocs de code ``` ``` (Python/C/HTML/JS/SQL selon pertinence), formules $inline$ et $$block$$, tableaux markdown.',
          '- Tu illustres par des exemples français (lycée/sup) précis, ni trop vagues ni trop jargonneux.',
          '- Aucune emphase **gras** parasite. Aucun disclaimer. Aucune phrase « Je ne peux pas ».',
          'Réponds UNIQUEMENT par ce JSON dans un bloc ```json :',
          '{ "title": "titre concret et accrocheur (≤ 60 caractères)", "content": "le cours complet en markdown" }',
        ].join('\n')
      } else if (kind === 'fiche') {
        prompt = [
          `Génère une FICHE DE RÉVISION format « programme complet » sur : ${topic}.`,
          'Style visé : fiche Bristol dense, organisée, color-codée — PAS des flashcards Q/R, une VRAIE fiche synthétique qu\'on lit pour réviser avant un contrôle.',
          'Ton rôle : choisir 4 à 8 notions majeures du sujet, chacune numérotée + colorée, et pour chaque notion sélectionner les blocs de contenu pertinents parmi ceux listés ci-dessous.',
          '',
          'Réponds UNIQUEMENT par ce JSON dans un bloc ```json :',
          '{',
          '  "title": "TITRE MAJUSCULES (ex: PROGRAMME COMPLET — Dérivées)",',
          '  "subtitle": "tagline courte (ex: Tout ce qu\'il faut savoir pour le bac !)",',
          '  "reminder": { "label": "MÉTHODE À TOUJOURS APPLIQUER", "content": "Cours → Comprendre → Exercices → Corriger" },',
          '  "sections": [',
          '    {',
          '      "n": 1,',
          '      "title": "NOM DE LA NOTION (majuscules)",',
          '      "color": "orange" | "green" | "blue" | "violet" | "pink" | "gold" | "red" | "cyan",',
          '      "blocks": [',
          '        { "kind": "def", "title": "DÉFINITION", "content": "markdown concis 1-3 lignes avec formules $...$" },',
          '        { "kind": "props", "title": "PROPRIÉTÉS", "items": ["item 1 avec $formule$", "item 2", "..."] },',
          '        { "kind": "formula", "label": "Formule clé", "formula": "LaTeX (ex: e^{x+y} = e^x \\\\cdot e^y)" },',
          '        { "kind": "variations", "label": "VARIATIONS", "headers": ["x", "−∞", "0", "+∞"], "rows": [["$e^x$", "0", "1", "+∞"]] },',
          '        { "kind": "savoirFaire", "title": "À SAVOIR FAIRE", "items": ["Résoudre $e^x=k$", "Étudier $f(x)=ae^x+b$"] },',
          '        { "kind": "attention", "content": "Piège : toujours vérifier que $x > 0$ pour ln." },',
          '        { "kind": "method", "title": "MÉTHODE", "steps": ["Identifier le type", "Écrire la solution", "Appliquer la condition initiale"] },',
          '        { "kind": "examples", "title": "EXEMPLES", "items": ["$y\' = 2y \\\\to y = Ce^{2x}$"] }',
          '      ]',
          '    }',
          '    // 4 à 8 sections au total, varie les blocs selon la notion',
          '  ],',
          '  "goldenRule": "Règle d\'or finale (ex: Travailler un peu tous les jours > tout faire en 1 jour)"',
          '}',
          '',
          'Contraintes :',
          '- Chaque bloc court, lisible d\'un coup d\'œil. PAS de paragraphes longs.',
          '- Formules LaTeX (inline $...$ ou bloc propre), échappe bien les backslashes dans le JSON.',
          '- ADAPTE les types de blocs au sujet : maths → def+props+formule+variations+savoir-faire ; histoire → def+dates(examples)+méthode+attention ; cyber → def+commandes(props)+savoir-faire+attention ; langue → def+règle(formula)+exemples+attention ; philo → def+auteurs(props)+citations(examples)+méthode.',
          '- Varie les couleurs entre sections (orange, green, blue, violet, pink, gold, red, cyan).',
          '- Aucune phrase « je ne peux pas ». Aucun disclaimer.',
        ].join('\n')
      } else if (kind === 'exo') {
        const mode: ExoMode = extras?.exoMode ?? 'new'
        const source = (extras?.sourceExercises || '').trim()
        // Pull real past BAC exam subjects for calibration when the topic
        // matches a known filière/matière. Best-effort: silently skipped if
        // the fetch fails or the topic doesn't map to a known track.
        let bacEnrichment = ''
        try {
          const { buildBacEnrichment } = await import('../services/bacResources')
          bacEnrichment = (await buildBacEnrichment(`${topic} ${topicHint}`)) || ''
        } catch { /* ignore */ }
        const sourceBlock = source ? [
          '',
          '--- EXERCICES SOURCES FOURNIS PAR L\'UTILISATEUR ---',
          source.slice(0, 8000),
          '--- FIN EXERCICES SOURCES ---',
          '',
        ].join('\n') : ''
        let missionIntent = ''
        if (mode === 'explain' && source) {
          missionIntent = [
            'Mode : EXPLIQUER les exercices sources fournis ci-dessous.',
            'Tu dois :',
            '- Reproduire chaque exercice dans le champ `statement` en markdown (énoncés, données, contraintes).',
            '- Rédiger `solution` comme un corrigé pas-à-pas, pédagogique, qui NOMME les concepts utilisés et refait les raisonnements.',
            '- Le `briefing` présente rapidement le thème commun et les prérequis.',
            '- Les `objectives` listent les étapes/checkpoints que l\'élève doit cocher en refaisant les exercices.',
            '- `tool` = environnement interactif adapté (si utile) pour que l\'élève teste les calculs/commandes/scripts pendant qu\'il lit l\'explication.',
          ].join('\n')
        } else if (mode === 'similar' && source) {
          missionIntent = [
            'Mode : CRÉER DES EXERCICES SIMILAIRES à ceux fournis ci-dessous.',
            'Tu dois :',
            '- Analyser le style, le niveau, les techniques et la structure des exercices sources.',
            '- Inventer une NOUVELLE mission originale qui exerce les mêmes compétences, même niveau de difficulté, même esthétique pédagogique.',
            '- Ne JAMAIS recopier les mêmes énoncés ni les mêmes valeurs — varie complètement.',
            '- Garder la cohérence : si les sources sont des CTF cyber → nouvelle mission CTF cyber ; si ce sont des maths niveau lycée → nouvelles maths lycée ; si ce sont des labs bio → nouveau lab bio.',
          ].join('\n')
        } else {
          missionIntent = 'Mode : créer une nouvelle mission introductive sur le sujet.'
        }
        prompt = [
          `Conçois une MISSION PRATIQUE qui fait AGIR l\'élève sur : ${topic}.`,
          missionIntent,
          sourceBlock,
          bacEnrichment,
          '',
          'RAISONNEMENT OBLIGATOIRE avant de coder :',
          '1. Quel est le CONCEPT central du sujet ? Qu\'est-ce qu\'un élève doit VOIR se produire pour comprendre ?',
          '2. Quelle MANIPULATION concrète incarne ce concept ? (bouger un curseur ? taper une commande ? construire un objet ? observer une simulation ?)',
          '3. Comment l\'élève va-t-il recevoir du FEEDBACK pédagogique en temps réel ? (logs ? graphe ? animation ? message ?)',
          '4. Quelles valeurs / exemples concrets réalistes (chiffres plausibles, contexte tangible) ?',
          '',
          'IMPORTANT : l\'élève ne lit pas passivement — il MANIPULE, CALCULE, CONSTRUIT, EXPLORE. Tu fabriques un terrain de jeu interactif complet en HTML+CSS+JS autonome, SANS dépendance externe obligatoire.',
          '',
          'Banque d\'ARCHÉTYPES d\'outils à adapter (ne te limite pas à ceux-ci — raisonne le bon pour le sujet) :',
          '- 🔋 Simulateur électrique / batterie / circuit (sliders résistance/tension/capacité + graphe courant-temps animé en canvas)',
          '- ⚙ Simulateur mécanique (pendule/ressort/plan incliné/leviers en canvas animé avec paramètres masse/longueur/gravité)',
          '- 🗺 Carte géographique interactive (SVG avec régions cliquables + infos au survol, ou canvas avec pan/zoom)',
          '- 🧬 Visualiseur moléculaire / ADN (SVG des atomes/bases avec drag pour assembler, retours de validité)',
          '- 🌡 Lab chimie (béchers avec réactifs à glisser, thermomètre, pH simulé, balance des équations)',
          '- 📈 Traceur de fonction (canvas avec sliders a, b, c qui redessinent f(x) en direct, zoom/pan)',
          '- 🎛 Console radio / signal (générateur de sinus/carré + affichage oscillo, FFT simulée)',
          '- 🧩 Drag & drop (assembler équation, ordonner étapes, mapper concepts)',
          '- 💻 Terminal interactif (cyber, réseau, linux, git — commandes simulées avec fake filesystem JSON)',
          '- 🎮 Mini-jeu pédagogique (atteindre un objectif en utilisant la notion)',
          '- 📚 Annotateur de texte (français, philo, HG — surligner + catégoriser passages)',
          '- 🏛 Reconstitution historique (frise interactive avec événements à replacer, cartes chronologiques)',
          '- 🗣 Entraîneur de langue (dicté / shadowing / traduction avec feedback instantané)',
          '- 🎨 Lab biologie (microscope SVG avec zoom, cellules à identifier, mitose animée)',
          '- 🧪 Analyseur de données (table CSV à trier, filtrer, visualiser)',
          '',
          'Ta consigne : CHOISIS l\'outil qui fait mieux ressentir le concept, adapte-le au contexte (STI2D, lycée, CTF, etc.), inclus une zone de RETOUR PÉDAGOGIQUE (bandeau "notes" ou "observations" qui explique ce que l\'élève vient de faire), des couleurs sémantiques (vert=juste, rouge=erreur, jaune=attention).',
          '',
          'Si le sujet n\'a pas d\'outil pertinent (ex: dissertation française sur un poème connu), mets "environment": "none" et propose à la place un canvas d\'annotation / plan à remplir.',
          '',
          'LÉGACY DES FORMATS (si l\'archétype ci-dessus ne suffit pas) :',
          '- 🧪 Lab de simulation (manipuler variables, observer résultat, consigner) — physique, chimie, bio',
          '- 🖥 Shell/terminal ou console interactive (commandes simulées avec retour pédagogique) — cyber, réseau, linux, git',
          '- 🧩 Drag & drop (assembler une équation, mapper des concepts, ordonner des étapes) — maths, info, logique',
          '- 📝 Calculateur guidé (entrer valeurs, voir intermédiaires, valider résultat final) — maths, physique, élec',
          '- 🎮 Mini-jeu pédagogique (atteindre un objectif en utilisant la notion) — tous sujets',
          '- 🧬 Constructeur / simulateur (molécule, circuit, programme) — chimie, SIN, code',
          '- 🔍 Analyse (décoder, inspecter, classer des éléments donnés) — langues, crypto, forensic',
          '- ✍ Atelier de rédaction (remplir un plan, annoter un texte) — français, philo, HG',
          '- 📊 Visualisation interactive (sliders + graphique en direct) — maths, stats, signal',
          '',
          'Principe : l\'élève ne lit pas — il agit. Tu fabriques un terrain de jeu interactif complet en HTML+CSS+JS autonome.',
          '',
          'Exemples de ce que tu dois construire selon le sujet :',
          '- CYBER (pentest, forensic, reverse, stegano) : fake terminal Linux (JS simule ls/cd/cat/whoami/nmap/curl), faux filesystem (objet JSON de fichiers dont certains cachent des flags), fausse machine cible avec services vulnérables (port simulé qui répond à des requêtes HTTP fake), binaire à disséquer avec strings/hexdump simulés, captures PCAP textuelles à analyser.',
          '- WEB SEC : mini-page web volontairement vulnérable (XSS/SQLi/CSRF/IDOR), champs injectables, console de devtools simulée, logs qui révèlent progression.',
          '- BIOLOGIE : microscope interactif (zoom/pan sur image SVG), manip d\'ADN/ARN (composition à assembler), éprouvette avec réactifs à mélanger, observations à consigner.',
          '- CHIMIE : table périodique interactive, équations à équilibrer, dosages simulés.',
          '- MATHS : traceur de fonction (canvas 2D qui évalue f(x)), manipulateur d\'équations avec sliders, prouveur pas-à-pas.',
          '- PHYSIQUE : simulation mécanique (canvas, pendule, chute, ressort), circuit électrique (résistances à ajuster, voltmètre affichant le résultat).',
          '- CODE : éditeur de texte + bouton Run qui exécute du JS dans un sandbox postMessage, avec tests automatisés affichant ✓/✗.',
          '- OSINT : simulation d\'un moteur de recherche, profils sociaux fictifs, indices à croiser.',
          '',
          'Exigences sur l\'HTML de l\'outil :',
          '- <!doctype html> complet, tout inline (style + script). Préférer vanilla JS.',
          '- Interface sombre hacker/lab selon le sujet. Mise en forme soignée.',
          '- État persistant dans la session (variables JS, pas besoin de localStorage).',
          '- Retour visuel immédiat à chaque action.',
          '- Pour les sujets sensibles (pentest, reverse, crypto) : joue le jeu, construis la cible vulnérable, montre les commandes d\'attaque — c\'est de la pédagogie offensive/défensive, pas du monde réel.',
          '',
          'Réponds UNIQUEMENT par ce JSON dans un bloc ```json :',
          '{',
          '  "title": "nom de la mission",',
          '  "briefing": "markdown court : contexte narratif / scénario (2-4 phrases), pose l\'ambiance",',
          '  "statement": "markdown : énoncé technique détaillé si utile — peut être identique au briefing",',
          '  "objectives": [',
          '    { "id": "o1", "text": "action concrète mesurable (ex: Trouver le flag dans /etc/shadow)", "hint": "indice bref (optionnel)", "flag": "flag{...} OU réponse attendue (optionnel)" }',
          '  ],   // 3 à 6 objectifs progressifs',
          '  "solution": "markdown : walkthrough complet commenté (révélé sur demande)",',
          '  "environment": "html-sandbox" | "none",',
          '  "tool": { "title": "Nom court du terrain (ex: Terminal Kali simulé, Microscope ADN, Circuit RLC)", "html": "document HTML5 complet autonome" }',
          '}',
          'Règles strictes : aucun disclaimer, aucun « je ne peux pas », aucun renvoi vers TryHackMe/HackTheBox/real tools. Tu CRÉES l\'environnement, c\'est ton rôle.',
        ].join('\n')
      } else {
        prompt = [
          `Génère un QUIZ DE MAÎTRISE de 8 questions sur : ${topic}.`,
          'Critères :',
          '- Difficulté progressive (Q1 = vérification, Q8 = cas limite/piège).',
          '- Questions variées : définition, calcul numérique, lecture de schéma/formule, cas d\'application concret, vrai/faux, identification d\'erreur, ordre de grandeur.',
          '- Chaque question a 4 choix plausibles (pas 3 trivialement faux + 1 évident).',
          '- Les distracteurs correspondent à des confusions typiques.',
          '- `explain` (une phrase courte) donne la raison + le rappel de la règle/formule utilisée.',
          'Réponds UNIQUEMENT par ce JSON dans un bloc ```json :',
          '{',
          '  "title": "titre du quiz",',
          '  "questions": [',
          '    { "q": "question précise", "choices": ["A","B","C","D"], "correct": 0, "explain": "raison + règle" }',
          '  ]',
          '}',
          'Aucun disclaimer. Aucune question piège gratuite.',
        ].join('\n')
      }
      // Build the anti-hallucination instruction block. When sources exist we
      // demand citations; when offline we still demand factual restraint.
      const groundingInstruction = groundingBlock
        ? [
            '',
            '## SOURCES FACTUELLES (utilise-les comme verite de reference)',
            groundingBlock,
            'CONTRAT FACTUEL:',
            '- Toute date, formule, nom propre, citation ou statistique doit etre coherent avec les sources [Sx] ci-dessus.',
            '- Si tu ajoutes un fait absent des sources, dis-le par "(connaissance generale)" pour qu il soit verifiable a posteriori.',
            '- Ne sors JAMAIS un nom d auteur ou une date dont tu n es pas sur — prefere une formulation prudente.',
          ].join('\n')
        : [
            '',
            '## CONTRAT FACTUEL (mode hors-ligne)',
            '- Aucune source externe disponible: limite-toi aux faits que tu connais avec certitude.',
            '- Pour toute donnee chiffree, date ou citation que tu n es pas certain a 100%, ajoute "(a verifier)" entre parentheses.',
            '- Ne pas inventer d auteurs, de citations, de dates ou de statistiques.',
          ].join('\n')
      const finalPrompt = [
        prompt,
        sharedBacEnrichment,
        groundingInstruction,
      ].filter(Boolean).join('\n')
      const res: any = await ollamaChat(mainModel, [
        { role: 'system', content: INSTRUCTOR_SYSTEM },
        { role: 'user', content: finalPrompt },
      ], 0.35)
      const raw: string = res?.message?.content ?? res?.response ?? ''
      const parsed = safeParseJson<any>(raw)
      if (!parsed) throw new Error('Réponse IA illisible.')

      let title = String(parsed.title || `${KIND_LABEL[kind]} · ${sub.name}`)
      let body = ''
      if (kind === 'cours') {
        body = String(parsed.content || '').trim()
      } else {
        body = JSON.stringify(parsed)
      }

      // 2nd-pass verification: re-read the generated content against the
      // SAME sources to catch hallucinations (wrong dates, fake authors,
      // wrong formulas, mis-attributed citations). Best-effort: if the audit
      // call fails, we keep the content with a neutral "general" badge.
      let verificationReport: import('../services/academicContentVerification').AcademicVerificationReport | null = null
      try {
        const { verifyAcademicContent } = await import('../services/academicContentVerification')
        const auditTarget = kind === 'cours' ? body : (parsed?.title ? `${parsed.title}\n\n${body}` : body)
        verificationReport = await verifyAcademicContent({
          contentTitle: title,
          contentBody: auditTarget,
          contentKind: kind,
          sources: groundingSources,
          auditModel: mainModel,
        })
      } catch { /* verification is best-effort */ }

      // Build the footer combining the verification verdict + the sources used.
      let footer = ''
      if (verificationReport) {
        try {
          const { reportFooterMarkdown } = await import('../services/academicContentVerification')
          footer = reportFooterMarkdown(verificationReport, groundingSources)
        } catch { /* fall through to bare sources footer */ }
      }
      if (!footer && groundingSources.length > 0) {
        footer = `\n\n---\n*Sources factuelles utilisees:*\n${groundingSources
          .slice(0, 5)
          .map((s, i) => `- [S${i + 1}] ${s.title}${s.url ? ` — ${s.url}` : ''}`)
          .join('\n')}`
      }
      const finalBody = kind === 'cours' && footer ? `${body}${footer}` : body

      const verificationMeta: import('../stores/academyStore').AcademyItemVerification | undefined = verificationReport
        ? {
            status: verificationReport.verdict,
            citedSources: verificationReport.citedSources,
            reasoning: verificationReport.reasoning,
          }
        : undefined
      addItem(activeCat.id, { kind, title, content: finalBody, subCategoryId: subId, createdByAI: true, verification: verificationMeta })
      addXp(kind === 'cours' ? 30 : kind === 'exo' ? 30 : kind === 'fiche' ? 25 : 35)
      setAddItemKind(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally { setBusyItem(false) }
  }, [activeCat, busyItem, mainModel, addItem, addXp])

  // ========= AI: modify tool of an exo =========
  const regenTool = useCallback(async (hint: string) => {
    if (!activeItem || !activeCat || busyTool) return
    setBusyTool(true)
    try {
      let exo: ExoData | null = safeParseJson<ExoData>(activeItem.content)
      if (!exo) exo = { statement: activeItem.content, environment: 'none' }
      const prevHtml = exo.tool?.html || ''
      const prompt = [
        `Tu as un outil HTML autonome existant pour l'exercice "${activeItem.title}".`,
        'Demande de modification/ajout :', hint,
        '',
        'HTML actuel :',
        '```html',
        (prevHtml.length > 6000 ? prevHtml.slice(0, 6000) + '\n<!-- tronqué -->' : prevHtml),
        '```',
        '',
        'Renvoie UNIQUEMENT un JSON ```json :',
        '{ "title": "nom court mis à jour", "html": "document HTML5 complet autonome incluant les modifications" }',
      ].join('\n')
      const res: any = await ollamaChat(mainModel, [
        { role: 'system', content: INSTRUCTOR_SYSTEM },
        { role: 'user', content: prompt },
      ], 0.35)
      const content: string = res?.message?.content ?? res?.response ?? ''
      const parsed = safeParseJson<{ title?: string; html?: string }>(content)
      if (!parsed?.html) throw new Error('HTML manquant dans la réponse IA.')
      const next: ExoData = {
        ...exo,
        environment: 'html-sandbox',
        tool: { title: parsed.title || exo.tool?.title || 'Environnement IA', html: parsed.html },
      }
      updateItem(activeCat.id, activeItem.id, { content: JSON.stringify(next) })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally { setBusyTool(false) }
  }, [activeItem, activeCat, busyTool, mainModel, updateItem])

  // ========= Mindmap mutation via AI (add child node) =========
  const mutateFicheMindmap = useCallback((nextRoot: MindNode) => {
    if (!activeItem || !activeCat) return
    try {
      const parsed = JSON.parse(activeItem.content)
      parsed.mindmap = nextRoot
      updateItem(activeCat.id, activeItem.id, { content: JSON.stringify(parsed) })
    } catch { /* ignore */ }
  }, [activeItem, activeCat, updateItem])

  // Listen to the child's event and resolve via AI then update store
  useEffect(() => {
    function handler(e: Event) {
      const detail = (e as CustomEvent).detail as { path: string[]; hint?: string }
      if (!activeItem || activeItem.kind !== 'fiche' || !activeCat) return
      ;(async () => {
        const pathLabel = detail.path[detail.path.length - 1]
        setAddingMindNode(pathLabel)
        try {
          const prompt = [
            `Tu vas étendre une carte mentale sur "${activeItem.title}".`,
            `Nœud parent (chemin depuis la racine) : ${detail.path.join(' > ')}`,
            detail.hint ? `Piste de l'utilisateur : ${detail.hint}` : 'Pas de piste : infère les concepts pertinents.',
            '',
            'Ajoute 3 à 5 sous-nœuds concrets et distincts pour étoffer ce nœud.',
            'Réponds UNIQUEMENT par ce JSON dans un bloc ```json :',
            '{ "children": [ {"label":"...", "children": [{"label":"..."},{"label":"..."}] }, ... ] }',
          ].join('\n')
          const res: any = await ollamaChat(mainModel, [
            { role: 'system', content: INSTRUCTOR_SYSTEM },
            { role: 'user', content: prompt },
          ], 0.45)
          const raw: string = res?.message?.content ?? res?.response ?? ''
          const parsed = safeParseJson<{ children: MindNode[] }>(raw)
          if (!parsed?.children) throw new Error('JSON invalide')
          // Walk the mindmap to the target node and merge children
          const current = JSON.parse(activeItem.content)
          const cloneNode = (n: MindNode): MindNode => ({ ...n, children: n.children ? n.children.map(cloneNode) : undefined })
          const nextRoot = cloneNode(current.mindmap as MindNode)
          let cur: MindNode | null = nextRoot
          for (let i = 1; i < detail.path.length && cur; i++) {
            cur = (cur.children || []).find((c) => c.label === detail.path[i]) ?? null
          }
          if (cur) {
            cur.children = [...(cur.children || []), ...parsed.children.slice(0, 5)]
            mutateFicheMindmap(nextRoot)
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err))
        } finally {
          setAddingMindNode(null)
        }
      })()
    }
    window.addEventListener('ay-mind-add', handler as EventListener)
    return () => window.removeEventListener('ay-mind-add', handler as EventListener)
  }, [activeItem, activeCat, mainModel, mutateFicheMindmap])

  // ========= AI grading for an exo objective =========
  const gradeObjective = useCallback(async (obj: Objective, userAnswer: string) => {
    const mod = await import('../services/labAssistant')
    const result = await mod.gradeAnswer(mainModel, obj.text, userAnswer, {
      subject: activeItem?.title,
      briefing: activeItem?.content?.slice(0, 800),
      expectedFlag: obj.flag,
    })
    // Award XP on correct, deduct small amount on wrong so it has stakes
    if (result.verdict === 'correct') addXp(15 + (obj.flag ? 10 : 0))
    return result
  }, [activeItem, mainModel, addXp])

  const deepObjectiveHint = useCallback(async (obj: Objective, level: 1 | 2 | 3) => {
    const mod = await import('../services/labAssistant')
    const result = await mod.deepHint(mainModel, obj.text, level, {
      subject: activeItem?.title,
      briefing: activeItem?.content?.slice(0, 800),
    })
    addXp(-result.xp_cost)
    return result
  }, [activeItem, mainModel, addXp])

  // ========= AI hint for an exo objective =========
  const askObjectiveHint = useCallback(async (objectiveText: string): Promise<string> => {
    if (!activeItem) return ''
    const prompt = [
      `Exercice : ${activeItem.title}.`,
      `Objectif : ${objectiveText}`,
      'Donne un INDICE qui oriente sans spoiler. 1-3 phrases. Mentionne la commande, la piste ou le raisonnement à tenter. Pas la réponse finale.',
    ].join('\n')
    const res: any = await ollamaChat(mainModel, [
      { role: 'system', content: INSTRUCTOR_SYSTEM },
      { role: 'user', content: prompt },
    ], 0.5)
    return (res?.message?.content ?? res?.response ?? '').trim() || '(pas d\'indice)'
  }, [activeItem, mainModel])

  // ========= Companion Q&A =========
  const askCompanion = useCallback(async () => {
    const q = companionQ.trim()
    if (!q || !activeItem || companionBusy) return
    setCompanionThread((t) => [...t, { role: 'user', text: q }])
    setCompanionQ(''); setCompanionBusy(true)
    try {
      // Give the AI the rendered-ish context
      let plain = activeItem.content
      if (activeItem.kind !== 'cours') {
        const j = safeParseJson<any>(plain)
        if (j) plain = JSON.stringify(j, null, 2)
      }
      const prompt = [
        `L'élève étudie le document suivant (${KIND_LABEL[activeItem.kind]} — « ${activeItem.title} ») :`,
        '',
        '--- CONTENU ---',
        plain.slice(0, 5000),
        '--- FIN ---',
        '',
        `Question : ${q}`,
        '',
        'Réponds en 2 à 5 phrases, direct, pédagogique, exemple concret si utile. Sans disclaimer.',
      ].join('\n')
      const res: any = await ollamaChat(mainModel, [
        { role: 'system', content: INSTRUCTOR_SYSTEM },
        { role: 'user', content: prompt },
      ], 0.4)
      const text: string = res?.message?.content ?? res?.response ?? ''
      setCompanionThread((t) => [...t, { role: 'ai', text: text.trim() || '(aucune réponse)' }])
    } catch (err) {
      setCompanionThread((t) => [...t, { role: 'ai', text: `⚠ ${err instanceof Error ? err.message : String(err)}` }])
    } finally { setCompanionBusy(false) }
  }, [companionQ, activeItem, companionBusy, mainModel])

  const xpForNext = (level + 1) * 100
  const xpProgress = Math.min(100, Math.round((xp / xpForNext) * 100))

  // Parse active item content for rendering
  const activeParsed = useMemo<{ kind: ItemKind; raw: string; parsed: any } | null>(() => {
    if (!activeItem) return null
    if (activeItem.kind === 'cours') return { kind: 'cours', raw: activeItem.content, parsed: null }
    return { kind: activeItem.kind, raw: activeItem.content, parsed: safeParseJson<any>(activeItem.content) }
  }, [activeItem])

  return (
    <div className="ay-root">
      <header className="ay-header">
        {activeCat ? (
          <button type="button" className="ay-back" onClick={exitCategory}>
            <ArrowLeft size={14} strokeWidth={2.4} /> Bibliothèque
          </button>
        ) : (
          <div className="ay-head-brand">
            <img src={PORTRAITS[who]} alt={who} className="ay-head-mentor" />
            <div>
              <div className="ay-head-kicker">BIBLIOTHÈQUE DE LA GUILDE</div>
              <div className="ay-head-title">{who === 'natsu' ? 'DRAGON SLAYER SCHOOL' : 'ACADÉMIE STELLAIRE'}</div>
            </div>
          </div>
        )}
        <div className="ay-xp">
          <span className="ay-xp-kicker">NIV {level}</span>
          <div className="ay-xp-track"><div className="ay-xp-fill" style={{ width: `${xpProgress}%` }} /></div>
          <span className="ay-xp-num">{xp}/{xpForNext}</span>
        </div>
        <div className="ay-streak" title={streak > 0
          ? `Série de ${streak} jour${streak > 1 ? 's' : ''} consécutif${streak > 1 ? 's' : ''}${lastActivityDate ? ` (dernière : ${lastActivityDate})` : ''}`
          : 'Aucune série active — révise aujourd\'hui pour la démarrer'}>
          <span className="ay-streak-flame" aria-hidden="true">{streak >= 30 ? '🏆' : streak >= 7 ? '⚡' : streak >= 3 ? '🔥' : '✨'}</span>
          <span className="ay-streak-num">{streak}</span>
          <span className="ay-streak-label">j</span>
        </div>
      </header>

      {error && (
        <div className="ay-error">
          <span>⚠ {error}</span>
          <button type="button" onClick={() => setError(null)}><X size={12} strokeWidth={2.4} /></button>
        </div>
      )}

      {/* LIBRARY */}
      {!activeCat && (
        <div className="ay-library">
          <div className="ay-library-hint">
            {categories.length} catégories · ajoute-en, l'IA construit sous-catégories + cours initial.
          </div>
          <div className="ay-library-grid">
            {categories.map((cat, i) => {
              const c = cat.items
              const n = (k: ItemKind) => c.filter((it) => it.kind === k).length
              return (
                <motion.button key={cat.id} type="button" className="ay-cat"
                  style={{ '--ct': cat.tone } as React.CSSProperties}
                  onClick={() => enterCategory(cat.id)}
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.03, 0.3), duration: 0.25 }}>
                  <div className="ay-cat-head">
                    <span className="ay-cat-emoji">{cat.emoji}</span>
                    {cat.createdByAI && <span className="ay-cat-ai">IA</span>}
                  </div>
                  <div className="ay-cat-name">{cat.name}</div>
                  <div className="ay-cat-desc">{cat.description}</div>
                  <div className="ay-cat-stats">
                    <span>📁 {cat.subCategories.length}</span>
                    <span>📖 {n('cours')}</span>
                    <span>✍ {n('exo')}</span>
                    <span>🃏 {n('fiche')}</span>
                    <span>🎯 {n('quiz')}</span>
                  </div>
                </motion.button>
              )
            })}
            <button type="button" className="ay-cat ay-cat-add" onClick={() => setAddCatOpen(true)}>
              <FolderPlus size={32} strokeWidth={2} />
              <div className="ay-cat-name">Nouvelle catégorie</div>
              <div className="ay-cat-desc">L'IA recherche et structure tout.</div>
            </button>
          </div>
        </div>
      )}

      {/* DETAIL */}
      {activeCat && (
        <div className="ay-detail">
          <aside className="ay-subs">
            <div className="ay-subs-head">
              <span className="ay-cat-emoji ay-cat-emoji-sm">{activeCat.emoji}</span>
              <div>
                <div className="ay-subs-kicker">CATÉGORIE</div>
                <div className="ay-subs-title">{activeCat.name}</div>
              </div>
            </div>
            <p className="ay-subs-desc">{activeCat.description}</p>
            <button type="button" className="ay-subs-exam-cta"
              onClick={() => setExamBlancOpen(true)}
              disabled={activeCat.items.length === 0}
              title={activeCat.items.length === 0 ? 'Ajoute au moins un cours ou une fiche d\'abord' : ''}>
              <Timer size={12} strokeWidth={2.4} /> LANCER UN EXAMEN BLANC
            </button>
            <button type="button" className="ay-subs-stats-cta"
              onClick={() => setProgressOpen((v) => !v)}
              title="Voir la progression détaillée">
              📊 {progressOpen ? 'Masquer' : 'Voir'} la progression
            </button>
            {progressOpen && (
              <Suspense fallback={null}>
                <ProgressStats category={activeCat} onClose={() => setProgressOpen(false)} />
              </Suspense>
            )}
            <div className="ay-subs-list">
              <button type="button" className={`ay-sub ${!activeSubId ? 'is-active' : ''}`} onClick={() => setActiveSubId(null)}>
                <span className="ay-sub-icon">✦</span>
                <span className="ay-sub-name">Tout</span>
                <span className="ay-sub-count">{activeCat.items.length}</span>
              </button>
              {activeCat.subCategories.map((sub) => {
                const count = activeCat.items.filter((i) => i.subCategoryId === sub.id).length
                return (
                  <button key={sub.id} type="button" className={`ay-sub ${activeSubId === sub.id ? 'is-active' : ''}`}
                    onClick={() => setActiveSubId(sub.id)}>
                    <span className="ay-sub-icon">{sub.emoji || '◆'}</span>
                    <span className="ay-sub-name">{sub.name}</span>
                    <span className="ay-sub-count">{count}</span>
                  </button>
                )
              })}
            </div>
          </aside>

          <section className="ay-items">
            <div className="ay-items-head">
              <div>
                <div className="ay-items-kicker">{activeSub ? activeSub.name.toUpperCase() : 'TOUS LES DOCUMENTS'}</div>
                <div className="ay-items-title">{filteredItems.length} fiche{filteredItems.length > 1 ? 's' : ''}</div>
              </div>
              <div className="ay-items-add">
                {(['cours', 'exo', 'fiche', 'quiz'] as ItemKind[]).map((kind) => (
                  <button key={kind} type="button" className="ay-add-btn"
                    style={{ '--kc': KIND_COLOR[kind] } as React.CSSProperties}
                    onClick={() => setAddItemKind(kind)}
                    disabled={!activeSub && activeCat.subCategories.length > 0}
                    title={!activeSub ? 'Sélectionne une sous-catégorie' : `Nouveau ${KIND_LABEL[kind]} par IA`}>
                    <Plus size={11} strokeWidth={2.4} />
                    {KIND_EMOJI[kind]} {KIND_LABEL[kind]}
                  </button>
                ))}
              </div>
            </div>

            <div className="ay-items-grid">
              {filteredItems.length === 0 && (
                <div className="ay-items-empty">
                  <span className="ay-items-empty-emoji">{activeCat.emoji}</span>
                  <div className="ay-items-empty-banner">
                    {activeSub ? `« ${activeSub.name} » est vide` : 'Vide'}
                  </div>
                  <p>Choisis une sous-catégorie puis clique <strong>+ Cours / Exo / Fiche / Quiz</strong>. L'IA écrit, classe, et fabrique même l'outil pratique.</p>
                </div>
              )}
              {filteredItems.map((it) => {
                const verif = it.verification
                const verifConf = verif ? ({
                  verified: { label: '✓ sourcee', color: '#34d399', bg: 'rgba(52,211,153,0.12)' },
                  general: { label: '◇ gen.', color: '#9ca3af', bg: 'rgba(156,163,175,0.12)' },
                  uncertain: { label: '? incertain', color: '#fbbf24', bg: 'rgba(251,191,36,0.14)' },
                  contradicted: { label: '! corrige', color: '#fb7185', bg: 'rgba(251,113,133,0.14)' },
                } as const)[verif.status] : null
                return (
                <motion.article key={it.id} className="ay-item"
                  style={{ '--kc': KIND_COLOR[it.kind] } as React.CSSProperties}
                  initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                  onClick={() => setOpenItemId(it.id)}>
                  <div className="ay-item-kind">{KIND_EMOJI[it.kind]} {KIND_LABEL[it.kind].toUpperCase()}</div>
                  <div className="ay-item-title">{it.title}</div>
                  <div className="ay-item-meta">
                    <span className="ay-item-sub">
                      {activeCat.subCategories.find((s) => s.id === it.subCategoryId)?.name ?? '—'}
                    </span>
                    {verifConf && (
                      <span
                        title={verif?.reasoning || ''}
                        style={{
                          fontFamily: 'JetBrains Mono, monospace',
                          fontSize: 9,
                          padding: '1px 6px',
                          borderRadius: 4,
                          background: verifConf.bg,
                          color: verifConf.color,
                          border: `1px solid ${verifConf.color}55`,
                        }}
                      >
                        {verifConf.label}
                      </span>
                    )}
                    {it.createdByAI && <span className="ay-item-ai">IA</span>}
                  </div>
                  <button type="button" className="ay-item-del"
                    onClick={(e) => { e.stopPropagation(); if (window.confirm('Supprimer ?')) removeItem(activeCat.id, it.id) }}
                    title="Supprimer"><Trash2 size={11} strokeWidth={2.4} /></button>
                </motion.article>
                )
              })}
            </div>
          </section>
        </div>
      )}

      {/* READER MODAL */}
      <AnimatePresence>
        {activeItem && activeCat && activeParsed && (
          <motion.div className="ay-modal-backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setOpenItemId(null)}>
            <motion.div className="ay-reader"
              initial={{ y: 24, opacity: 0, scale: 0.96 }} animate={{ y: 0, opacity: 1, scale: 1 }}
              exit={{ y: 14, opacity: 0 }} transition={{ type: 'spring', stiffness: 260, damping: 26 }}
              onClick={(e) => e.stopPropagation()}>
              <header className="ay-reader-head" style={{ '--kc': KIND_COLOR[activeItem.kind] } as React.CSSProperties}>
                <span className="ay-reader-badge">{KIND_EMOJI[activeItem.kind]} {KIND_LABEL[activeItem.kind]}</span>
                <div className="ay-reader-ident">
                  <div className="ay-reader-kicker">{activeCat.name} · {activeCat.subCategories.find((s) => s.id === activeItem.subCategoryId)?.name}</div>
                  <div className="ay-reader-title">{activeItem.title}</div>
                </div>
                <div className="ay-reader-tools">
                  <button type="button" className="ay-reader-tool" title="Imprimer / PDF"
                    onClick={() => {
                      const body = document.querySelector('.ay-reader-body') as HTMLElement | null
                      if (body) printElement(body, {
                        title: activeItem.title,
                        subtitle: `${activeCat.name} · ${activeCat.subCategories.find((s) => s.id === activeItem.subCategoryId)?.name}`,
                        footer: 'juan of bike IA · Académie',
                      })
                    }}>
                    <Printer size={12} strokeWidth={2.4} /> PDF
                  </button>
                  {activeItem.kind === 'fiche' && activeParsed.parsed && (
                    <button type="button" className="ay-reader-tool" title="Exporter vers Anki (TSV importable)"
                      onClick={async () => {
                        const mod = await import('../utils/exportAnki')
                        const parsed = activeParsed.parsed as { sections?: unknown[]; cards?: unknown[] }
                        // Flatten sections -> cards for Anki
                        const p = parsed as any
                        const cards: unknown[] = p.sections
                          ? p.sections.flatMap((sec: any) =>
                              (sec.blocks || []).filter((b: any) => b.kind === 'def' || b.kind === 'formula').map((b: any) => ({
                                id: `${sec.n}-${b.kind}`, deckId: 'fiche', kind: 'qa',
                                front: `${sec.title} — ${b.title || b.label || ''}`,
                                back: b.content || b.formula || (Array.isArray(b.items) ? b.items.join('; ') : ''),
                                tags: [activeCat.name, (activeCat.subCategories.find((s) => s.id === activeItem.subCategoryId)?.name || '').replace(/\s+/g, '_')],
                                box: 1, streak: 0, dueAt: Date.now(), timesCorrect: 0, timesWrong: 0, createdAt: Date.now(),
                              })),
                            )
                          : (p.cards || []).map((c: any, i: number) => ({
                              id: `c${i}`, deckId: 'fiche', kind: 'qa',
                              front: c.q || c.front || '', back: c.r || c.back || '',
                              tags: [activeCat.name], box: 1, streak: 0, dueAt: Date.now(),
                              timesCorrect: 0, timesWrong: 0, createdAt: Date.now(),
                            }))
                        mod.downloadAnkiTsv(
                          { id: 'd', subject: activeCat.name, theme: activeItem.title, level: 'intermediaire', createdAt: Date.now(), updatedAt: Date.now(), cardCount: cards.length, masteredCount: 0 } as any,
                          cards as any,
                        )
                      }}>
                      <Download size={12} strokeWidth={2.4} /> Anki
                    </button>
                  )}
                </div>
                <button type="button" className="ay-reader-close" onClick={() => setOpenItemId(null)}>
                  <X size={14} strokeWidth={2.4} />
                </button>
              </header>

              <div className="ay-reader-body">
                {activeParsed.kind === 'cours' && (
                  <TextContent content={activeParsed.raw} idPrefix={`cours-${activeItem.id}`} />
                )}
                {activeParsed.kind === 'exo' && (
                  activeParsed.parsed ? (
                    <ExoPanel
                      data={activeParsed.parsed as ExoData}
                      itemId={activeItem.id}
                      onRegenTool={regenTool}
                      onAskHint={askObjectiveHint}
                      onGrade={gradeObjective}
                      onDeepHint={deepObjectiveHint}
                    />
                  ) : (
                    <TextContent content={activeParsed.raw} idPrefix={`exo-${activeItem.id}`} />
                  )
                )}
                {activeParsed.kind === 'fiche' && activeParsed.parsed && (
                  Array.isArray((activeParsed.parsed as any).cards) ||
                  Array.isArray((activeParsed.parsed as any).sections)
                ) && (
                  <FichePanel
                    data={activeParsed.parsed as FicheData}
                    onMutateMindmap={mutateFicheMindmap}
                    addingLabel={addingMindNode}
                    idPrefix={`fiche-${activeItem.id}`}
                  />
                )}
                {activeParsed.kind === 'quiz' && activeParsed.parsed && Array.isArray((activeParsed.parsed as any).questions) && (
                  <QuizPanel data={activeParsed.parsed as { questions: QuizQ[] }} onXp={(amount) => addXp(amount)} />
                )}
                {(activeParsed.kind === 'fiche' || activeParsed.kind === 'quiz') && !activeParsed.parsed && (
                  <div className="ay-reader-fallback">Format IA non reconnu. <TextContent content={activeParsed.raw} idPrefix={`raw-${activeItem.id}`} /></div>
                )}
                {busyTool && (
                  <div className="ay-tool-busy">
                    <Loader2 size={14} className="ay-spin" /> Le forgeron ajuste l'outil…
                  </div>
                )}
              </div>

              <div className="ay-companion">
                <div className="ay-companion-head">
                  <img src={PORTRAITS[who]} alt={who} className="ay-companion-avatar" />
                  <div>
                    <div className="ay-companion-kicker">COMPAGNON DE COURS</div>
                    <div className="ay-companion-title">Pose une question sur ce document</div>
                  </div>
                </div>
                {companionThread.length > 0 && (
                  <div className="ay-companion-thread">
                    {companionThread.map((m, i) => (
                      <div key={i} className={`ay-companion-msg is-${m.role}`}>
                        {m.role === 'ai' && <img src={PORTRAITS[who]} alt="" className="ay-companion-msg-avatar" />}
                        <div className="ay-companion-msg-bubble">
                          {m.role === 'ai' ? <MarkdownPro content={m.text} idPrefix={`cm-${i}`} /> : m.text}
                        </div>
                      </div>
                    ))}
                    {companionBusy && (
                      <div className="ay-companion-msg is-ai">
                        <img src={PORTRAITS[who]} alt="" className="ay-companion-msg-avatar" />
                        <div className="ay-companion-msg-bubble is-loading">
                          <Loader2 size={13} className="ay-spin" /> en réflexion…
                        </div>
                      </div>
                    )}
                  </div>
                )}
                <div className="ay-companion-composer">
                  <input type="text" className="ay-companion-input"
                    placeholder="Question pédagogique, demande d'exemple, clarification, exercice additionnel…"
                    value={companionQ} onChange={(e) => setCompanionQ(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void askCompanion() } }}
                    disabled={companionBusy} />
                  <button type="button" className="ay-companion-send"
                    onClick={() => void askCompanion()} disabled={!companionQ.trim() || companionBusy}>
                    <Send size={12} strokeWidth={2.4} />
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ADD CATEGORY */}
      <AnimatePresence>
        {addCatOpen && (
          <motion.div className="ay-modal-backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => !busyCategory && setAddCatOpen(false)}>
            <motion.div className="ay-minimodal"
              initial={{ y: 16, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 12, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}>
              <div className="ay-minimodal-head">
                <FolderPlus size={16} strokeWidth={2.4} />
                <span>NOUVELLE CATÉGORIE · L'IA structure</span>
                <button type="button" className="ay-minimodal-close" onClick={() => !busyCategory && setAddCatOpen(false)}>
                  <X size={12} strokeWidth={2.4} />
                </button>
              </div>
              <div className="ay-minimodal-body">
                <label className="ay-minimodal-label">Thème</label>
                <input type="text" className="ay-minimodal-input"
                  placeholder="Ex: Neurosciences, Reverse Engineering avancé, Mythologie grecque, Économie…"
                  value={newCatName} onChange={(e) => setNewCatName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void createCategory(newCatName) } }}
                  disabled={busyCategory} autoFocus />
                <p className="ay-minimodal-hint">
                  L'IA génère sous-catégories, description et cours introductif prêt à lire.
                </p>
                <button type="button" className="ay-minimodal-cta"
                  onClick={() => void createCategory(newCatName)} disabled={!newCatName.trim() || busyCategory}>
                  {busyCategory
                    ? (<><Loader2 size={14} className="ay-spin" /> En cours…</>)
                    : (<><Sparkles size={14} strokeWidth={2.4} /> Créer + remplir par IA</>)}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ADD ITEM */}
      <AnimatePresence>
        {addItemKind && activeCat && activeSub && (
          <AddItemModal
            kind={addItemKind} catName={activeCat.name} subName={activeSub.name} busy={busyItem}
            onCancel={() => setAddItemKind(null)}
            onGenerate={(topic, extras) => void generateItem(addItemKind, activeSub.id, topic, extras)}
          />
        )}
      </AnimatePresence>

      {/* Pomodoro (always mounted, floats bottom-right) */}
      <Suspense fallback={null}>
        <PomodoroTimer />
      </Suspense>

      {/* EXAM BLANC */}
      {examBlancOpen && activeCat && (
        <Suspense fallback={null}>
          <ExamBlancPanel
            subject={activeCat.name}
            catName={activeCat.name}
            subName={activeSub?.name || 'toutes sous-catégories'}
            context={activeCat.items
              .filter((it) => !activeSub || it.subCategoryId === activeSub.id)
              .slice(0, 6)
              .map((it) => `# ${it.title}\n${String(it.content).slice(0, 1500)}`)
              .join('\n\n')}
            onClose={() => setExamBlancOpen(false)}
          />
        </Suspense>
      )}
    </div>
  )
}

// ---- Add Item Modal ----
type GenerateExtras = { exoMode?: 'new' | 'explain' | 'similar'; sourceExercises?: string }
function AddItemModal({ kind, catName, subName, busy, onCancel, onGenerate }: {
  kind: ItemKind; catName: string; subName: string; busy: boolean
  onCancel: () => void; onGenerate: (topic: string, extras?: GenerateExtras) => void
}) {
  const [topic, setTopic] = useState('')
  const [exoMode, setExoMode] = useState<'new' | 'explain' | 'similar'>('new')
  const [sourceText, setSourceText] = useState('')
  // iter31.A: accumulate multiple files instead of replacing on each upload.
  // Each entry tracks name + the text extracted from that single file so the
  // user can remove individual files. The combined text is the concat of all
  // entries, joined by separators so the LLM sees clearly delimited sources.
  const [fileEntries, setFileEntries] = useState<Array<{ id: string; name: string; text: string }>>([])
  const [fileError, setFileError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Re-derive sourceText whenever the entries list changes so the textarea
  // mirrors the union of all attached files. Truncate to 12000 chars total.
  useEffect(() => {
    if (fileEntries.length === 0) {
      // Don't clobber user-typed text just because they removed every file.
      return
    }
    const combined = fileEntries
      .map((e) => `=== ${e.name} ===\n${e.text}`)
      .join('\n\n')
      .slice(0, 12000)
    setSourceText(combined)
  }, [fileEntries])

  const onPickFile = () => fileInputRef.current?.click()

  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return
    setFileError(null)
    const additions: Array<{ id: string; name: string; text: string }> = []
    let firstError: string | null = null
    for (const file of files) {
      const mime = file.type || ''
      const name = file.name.toLowerCase()
      let extractedText = ''
      try {
        if (
          mime.startsWith('text/') ||
          name.endsWith('.txt') || name.endsWith('.md') || name.endsWith('.markdown') ||
          name.endsWith('.json') || name.endsWith('.csv') || name.endsWith('.log') ||
          name.endsWith('.py') || name.endsWith('.js') || name.endsWith('.ts') ||
          name.endsWith('.html') || name.endsWith('.css') || name.endsWith('.xml') ||
          name.endsWith('.srt') || name.endsWith('.vtt') || name.endsWith('.tex')
        ) {
          extractedText = await file.text()
        } else if (name.endsWith('.pdf')) {
          try {
            const { extractPdfText } = await import('../utils/pdfExtract')
            const text = await extractPdfText(file, 20)
            if (text && text.length > 40) {
              extractedText = text
            } else {
              firstError = firstError ?? `${file.name}: PDF lu mais texte vide (scan image ?)`
            }
          } catch (err) {
            firstError = firstError ?? `${file.name}: extraction PDF échouée — ${err instanceof Error ? err.message : 'erreur inconnue'}`
          }
        } else if (mime.startsWith('image/')) {
          firstError = firstError ?? `${file.name}: image détectée — décris-la ci-dessous (vision bientôt).`
        } else {
          try {
            const text = await file.text()
            if (text && text.length > 0) extractedText = text
            else firstError = firstError ?? `${file.name}: format non reconnu.`
          } catch {
            firstError = firstError ?? `${file.name}: format non reconnu.`
          }
        }
      } catch (err) {
        firstError = firstError ?? `${file.name}: ${err instanceof Error ? err.message : 'lecture impossible'}`
      }
      if (extractedText) {
        const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
        additions.push({ id, name: file.name, text: extractedText })
      }
    }
    if (additions.length > 0) {
      // De-dup by name+size so dropping the same PDF twice doesn't double-stack.
      setFileEntries((prev) => {
        const existing = new Set(prev.map((e) => e.name))
        const fresh = additions.filter((a) => !existing.has(a.name))
        return [...prev, ...fresh]
      })
    }
    if (firstError) setFileError(firstError)
    e.target.value = ''
  }

  const removeFileEntry = (id: string) => {
    setFileEntries((prev) => prev.filter((e) => e.id !== id))
  }

  const submit = () => {
    if (busy) return
    if (kind === 'exo') {
      const mode = (exoMode === 'new' || !sourceText.trim()) ? 'new' : exoMode
      onGenerate(topic, { exoMode: mode, sourceExercises: sourceText.trim() || undefined })
    } else {
      onGenerate(topic)
    }
  }

  return (
    <motion.div className="ay-modal-backdrop"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onClick={() => !busy && onCancel()}>
      <motion.div className="ay-minimodal"
        style={{ '--kc': KIND_COLOR[kind] } as React.CSSProperties}
        initial={{ y: 16, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 12, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}>
        <div className="ay-minimodal-head">
          <span>{KIND_EMOJI[kind]}</span>
          <span>NOUVEAU {KIND_LABEL[kind].toUpperCase()}</span>
          <button type="button" className="ay-minimodal-close" onClick={() => !busy && onCancel()}>
            <X size={12} strokeWidth={2.4} />
          </button>
        </div>
        <div className="ay-minimodal-body">
          <label className="ay-minimodal-label">Sujet précis (optionnel)</label>
          <div className="ay-minimodal-sub">Catégorie · {catName} → {subName}</div>
          <input type="text" className="ay-minimodal-input"
            placeholder={`Ex: ${subName} pour débutant, cas réel, tool interactif…`}
            value={topic} onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submit() } }}
            disabled={busy} autoFocus />

          {kind === 'exo' && (
            <div className="ay-exo-source">
              <div className="ay-exo-source-label">Source facultative (fichier d'exercices existants)</div>
              <div className="ay-exo-mode">
                <button
                  type="button"
                  className={exoMode === 'new' ? 'is-active' : ''}
                  onClick={() => setExoMode('new')}
                  disabled={busy}
                >✨ Nouveau</button>
                <button
                  type="button"
                  className={exoMode === 'explain' ? 'is-active' : ''}
                  onClick={() => setExoMode('explain')}
                  disabled={busy || !sourceText.trim()}
                  title={!sourceText.trim() ? 'Ajoute d\'abord des exercices' : ''}
                >📖 Expliquer</button>
                <button
                  type="button"
                  className={exoMode === 'similar' ? 'is-active' : ''}
                  onClick={() => setExoMode('similar')}
                  disabled={busy || !sourceText.trim()}
                  title={!sourceText.trim() ? 'Ajoute d\'abord des exercices' : ''}
                >🔁 Similaires</button>
              </div>
              <div className="ay-exo-source-row">
                <button type="button" className="ay-exo-source-upload" onClick={onPickFile} disabled={busy}>
                  <Upload size={12} strokeWidth={2.4} /> Importer fichier
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".txt,.md,.markdown,.json,.csv,.py,.js,.ts,.html,.css,.pdf,.srt,.vtt,.tex,.log"
                  onChange={onFileChange}
                  style={{ display: 'none' }}
                />
                {/* iter31.A: render every accumulated file with its own X.
                    User can drop multiple PDFs and remove individually. */}
                {fileEntries.map((entry) => (
                  <span key={entry.id} className="ay-exo-source-filename">
                    <FileText size={11} strokeWidth={2.4} /> {entry.name}
                    <button
                      type="button"
                      onClick={() => removeFileEntry(entry.id)}
                      disabled={busy}
                      title={`Retirer ${entry.name}`}
                      style={{ marginLeft: 6, border: 'none', background: 'transparent', cursor: 'pointer', color: 'inherit' }}
                    >×</button>
                  </span>
                ))}
                {(sourceText || fileEntries.length > 0) && (
                  <button type="button" className="ay-exo-source-clear"
                    onClick={() => { setSourceText(''); setFileEntries([]); setFileError(null); setExoMode('new') }}
                    disabled={busy}>
                    × Tout retirer
                  </button>
                )}
              </div>
              {fileError && <div className="ay-exo-source-warn">⚠ {fileError}</div>}
              <textarea
                className="ay-exo-source-paste"
                rows={5}
                placeholder="Ou colle ici tes exercices (énoncés, corrigés, extraits, fichier entier…)"
                value={sourceText}
                onChange={(e) => setSourceText(e.target.value.slice(0, 12000))}
                disabled={busy}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
                <VoicePushToTalk
                  onTranscript={(t) => setSourceText((prev) => {
                    const next = prev?.trim() ? `${prev}\n${t}` : t
                    return next.slice(0, 12000)
                  })}
                  label="Dicter l'énoncé"
                  size={28}
                  variant="ghost"
                />
                <span style={{ fontSize: 11, opacity: 0.6 }}>Dicte au micro.</span>
              </div>
              <div className="ay-exo-source-meta">
                {sourceText.length > 0
                  ? `${sourceText.length} / 12000 caractères · mode : ${exoMode === 'new' ? 'nouvelle mission' : exoMode === 'explain' ? 'explications' : 'exercices similaires'}`
                  : 'Vide = nouvelle mission introductive'}
              </div>
            </div>
          )}

          <p className="ay-minimodal-hint">
            {kind === 'exo'
              ? 'Avec source : l\'IA peut expliquer chaque exercice ou créer des variantes similaires (même style, même niveau). Sans source : mission introductive avec environnement interactif généré.'
              : `Laisse vide pour un ${KIND_LABEL[kind].toLowerCase()} introductif. L'IA classe et fabrique tout.`}
          </p>
          <button type="button" className="ay-minimodal-cta" onClick={submit} disabled={busy}>
            {busy
              ? (<><Loader2 size={14} className="ay-spin" /> Génération…</>)
              : (<><Sparkles size={14} strokeWidth={2.4} /> Générer avec IA</>)}
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}
