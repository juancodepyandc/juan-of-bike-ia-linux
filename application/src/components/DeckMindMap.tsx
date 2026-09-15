import { useCallback, useMemo, useRef, useState } from 'react'
import type { MindNode } from '../services/deckMindMap.ts'

type Props = {
  root: MindNode
  /** Called when the user clicks a card-level node, with the cardId payload. */
  onCardSelect?: (cardId: string) => void
  /** Tight UI when embedded inside the FichesPanel sidebar. */
  compact?: boolean
}

type Positioned = MindNode & {
  id: string
  x: number
  y: number
  depth: number
  parentId?: string
}

/**
 * Self-contained, interactive mind map component for flashcard decks.
 * - Radial layout with depth-based radius
 * - Pan + zoom + click-to-collapse + click card to open original flashcard
 * - Pure SVG, zero external dependencies
 *
 * Used by FichesPanel sidebar to give the user "interactivité sur les cartes
 * mentales" as requested.
 */
export default function DeckMindMap({ root, onCardSelect, compact = false }: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [zoom, setZoom] = useState(0.9)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [selected, setSelected] = useState<string | null>(null)
  const panRef = useRef<{ x: number; y: number } | null>(null)

  const positioned = useMemo(() => layout(root, collapsed), [root, collapsed])

  const handleNodeClick = useCallback(
    (node: Positioned) => {
      setSelected(node.id)
      const hasKids = (node.children?.length ?? 0) > 0
      if (hasKids) {
        setCollapsed((prev) => {
          const next = new Set(prev)
          if (next.has(node.id)) next.delete(node.id)
          else next.add(node.id)
          return next
        })
      }
      // Smooth-center on the selected node so the user keeps context after
      // clicking deep in the tree. Only animate when the node is far from
      // the current pan center to avoid jitter on every click.
      const targetPanX = -node.x * zoom
      const targetPanY = -node.y * zoom
      const distance = Math.hypot(targetPanX - pan.x, targetPanY - pan.y)
      if (distance > 80) {
        setPan({ x: targetPanX, y: targetPanY })
      }
      if (node.kind === 'card' && node.cardId && onCardSelect) {
        onCardSelect(node.cardId)
      }
    },
    [onCardSelect, pan.x, pan.y, zoom],
  )

  const onWheel = (event: React.WheelEvent) => {
    event.preventDefault()
    const delta = -event.deltaY * 0.001
    setZoom((z) => Math.max(0.35, Math.min(2.4, z + delta)))
  }
  const onPointerDown = (event: React.PointerEvent) => {
    if ((event.target as HTMLElement).closest('.aurora-mindmap-node')) return
    panRef.current = { x: event.clientX - pan.x, y: event.clientY - pan.y }
    ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  }
  const onPointerMove = (event: React.PointerEvent) => {
    if (!panRef.current) return
    setPan({ x: event.clientX - panRef.current.x, y: event.clientY - panRef.current.y })
  }
  const onPointerUp = (event: React.PointerEvent) => {
    panRef.current = null
    try {
      ;(event.currentTarget as HTMLElement).releasePointerCapture(event.pointerId)
    } catch {
      /* noop */
    }
  }
  const reset = () => {
    setZoom(0.9)
    setPan({ x: 0, y: 0 })
    setCollapsed(new Set())
    setSelected(null)
  }

  const height = compact ? 280 : 460
  const viewBox = compact ? '-460 -260 920 520' : '-560 -380 1120 760'

  return (
    <div className="rounded-2xl border border-aurora-border/50 bg-aurora-surface/40 p-3">
      <div className="flex items-center gap-2 pb-2 text-[10px] uppercase tracking-[0.18em] text-aurora-text-dim">
        <span className="font-semibold text-aurora-text">Carte mentale</span>
        <span>· glisse / zoom / clic = ouvrir</span>
        <span className="ml-auto rounded-full border border-aurora-border/50 bg-aurora-surface-2/60 px-2 py-0.5">
          zoom {Math.round(zoom * 100)}%
        </span>
        <button
          type="button"
          onClick={reset}
          className="rounded-full border border-aurora-border/50 bg-aurora-surface-2/60 px-2 py-0.5 hover:text-aurora-text"
        >
          Reset
        </button>
      </div>
      <div
        className="relative overflow-hidden rounded-xl bg-aurora-surface-2/40"
        style={{ height, touchAction: 'none' }}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <svg
          viewBox={viewBox}
          className="h-full w-full select-none"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center',
            transition: panRef.current ? 'none' : 'transform 320ms cubic-bezier(0.22, 1, 0.36, 1)',
          }}
        >
          {positioned.map((node) => {
            if (!node.parentId) return null
            const parent = positioned.find((n) => n.id === node.parentId)
            if (!parent) return null
            const isSel = selected === node.id || selected === node.parentId
            return (
              <line
                key={`l-${node.id}`}
                x1={parent.x}
                y1={parent.y}
                x2={node.x}
                y2={node.y}
                stroke={isSel ? 'rgb(116, 232, 255)' : 'rgba(255,255,255,0.22)'}
                strokeWidth={isSel ? 2 : 1.2}
                strokeDasharray={node.depth >= 3 ? '4 3' : '0'}
              />
            )
          })}
          {positioned.map((node) => {
            const isRoot = node.depth === 0
            const isTheme = node.kind === 'theme'
            const isCard = node.kind === 'card'
            const isSel = selected === node.id
            const hasKids = (node.children?.length ?? 0) > 0
            const isCollapsed = collapsed.has(node.id)
            const w = isRoot ? 152 : isTheme ? 132 : isCard ? 108 : 80
            const h = isRoot ? 50 : isTheme ? 38 : isCard ? 30 : 24
            const fill = isRoot
              ? 'rgb(116, 232, 255)'
              : isTheme
                ? 'rgba(167, 139, 250, 0.85)'
                : isCard
                  ? 'rgba(15, 23, 42, 0.92)'
                  : 'rgba(15, 23, 42, 0.6)'
            const textColor = isRoot ? '#0a1020' : isTheme ? '#0a1020' : isCard ? '#fff' : '#cbd5e1'
            const fontSize = isRoot ? 13 : isTheme ? 11 : isCard ? 10 : 9
            return (
              <g
                key={node.id}
                className="aurora-mindmap-node"
                transform={`translate(${node.x} ${node.y})`}
                onClick={(event) => {
                  event.stopPropagation()
                  handleNodeClick(node)
                }}
                style={{ cursor: 'pointer' }}
              >
                <rect
                  x={-w / 2}
                  y={-h / 2}
                  width={w}
                  height={h}
                  rx={isRoot ? 14 : 8}
                  fill={fill}
                  stroke={isSel ? 'rgb(116, 232, 255)' : 'rgba(255,255,255,0.18)'}
                  strokeWidth={isSel ? 2.2 : 1.2}
                />
                <text
                  x={0}
                  y={0}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={fontSize}
                  fill={textColor}
                  letterSpacing="0.4"
                >
                  {node.label}
                </text>
                {hasKids && (
                  <circle
                    cx={w / 2 - 6}
                    cy={-h / 2 + 6}
                    r={5}
                    fill={isCollapsed ? 'rgb(245, 158, 11)' : 'rgba(255,255,255,0.95)'}
                    stroke="rgba(15,23,42,0.85)"
                    strokeWidth={1.2}
                  />
                )}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}

/** Radial layout: root at origin, each level radiates further out. */
function layout(root: MindNode, collapsed: Set<string>): Positioned[] {
  const radii = [0, 175, 320, 440, 540]
  const out: Positioned[] = []

  function walk(
    node: MindNode,
    id: string,
    depth: number,
    baseAngle: number,
    span: number,
    parentId?: string,
  ): void {
    const r = radii[Math.min(depth, radii.length - 1)]
    const x = Math.cos(baseAngle) * r
    const y = Math.sin(baseAngle) * r
    out.push({ ...node, id, x, y, depth, parentId })
    if (collapsed.has(id)) return
    const kids = node.children || []
    if (kids.length === 0) return
    const childSpan = Math.min(span / Math.max(1, kids.length), depth === 0 ? Math.PI * 2 : Math.PI / 1.3)
    const total = childSpan * kids.length
    const startAngle = baseAngle - total / 2 + childSpan / 2
    kids.forEach((kid, index) => {
      walk(kid, `${id}-${index}`, depth + 1, startAngle + index * childSpan, childSpan, id)
    })
  }

  walk(root, 'root', 0, -Math.PI / 2, Math.PI * 2)
  return out
}
