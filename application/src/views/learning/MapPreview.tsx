/**
 * iter35.C — Croquis schématique style BAC géographie.
 *
 * Rend un SVG simplifié à partir du JSON `cartes[]` produit par le LLM dans
 * le payload parcours-bac. Pas une vraie carte du monde — un croquis stylisé
 * type "exam BAC HG" avec une grille de positions relatives N/S/E/O/centre +
 * 4 diagonales, des symboles par type (point, flèche, zone, hachure) et une
 * légende lisible.
 *
 * Usage : <MapPreview carte={parcoursPayload.cartes[0]} />
 */
import React from 'react'
import type { AcademyParcoursCarte } from '../../hooks/useAcademyViewLogic'

interface Props {
  carte: AcademyParcoursCarte
}

const POSITION_MAP: Record<string, { x: number; y: number }> = {
  northwest: { x: 0.18, y: 0.18 },
  north:     { x: 0.50, y: 0.16 },
  northeast: { x: 0.82, y: 0.18 },
  west:      { x: 0.16, y: 0.50 },
  center:    { x: 0.50, y: 0.50 },
  east:      { x: 0.84, y: 0.50 },
  southwest: { x: 0.18, y: 0.82 },
  south:     { x: 0.50, y: 0.84 },
  southeast: { x: 0.82, y: 0.82 },
}

function getPos(position: string, idx: number): { x: number; y: number } {
  const base = POSITION_MAP[position?.toLowerCase()] || POSITION_MAP.center
  // Léger jitter déterministe pour éviter les superpositions exactes
  // quand plusieurs éléments partagent la même position.
  const jx = ((idx * 7919) % 100 - 50) / 1500
  const jy = ((idx * 6131) % 100 - 50) / 1500
  return { x: Math.max(0.05, Math.min(0.95, base.x + jx)), y: Math.max(0.08, Math.min(0.92, base.y + jy)) }
}

export default function MapPreview({ carte }: Props) {
  const W = 720
  const H = 380
  const elements = carte.elements || []
  const legende = carte.legende || []

  // Indexe les couleurs par catégorie (pour réutiliser dans les éléments)
  const colorByCategorie = new Map<string, string>()
  for (const l of legende) {
    if (l.libelle) colorByCategorie.set(l.libelle.toLowerCase(), l.couleur || '#e63946')
  }

  return (
    <div style={{
      borderRadius: 12,
      background: 'linear-gradient(180deg, oklch(0.18 0.03 230 / 0.4), oklch(0.14 0.02 230 / 0.55))',
      border: '1px solid rgba(255,255,255,0.12)',
      padding: 16,
      display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <div style={{
        fontSize: 13, fontWeight: 700, color: '#fff',
        fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
        letterSpacing: '-0.01em',
      }}>
        🗺 {carte.titre}
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', borderRadius: 8 }}>
        {/* Fond océan stylisé */}
        <defs>
          <pattern id="oceanGrid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
          </pattern>
          <pattern id="hatchPattern" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="currentColor" strokeWidth="1.5" />
          </pattern>
        </defs>
        <rect x="0" y="0" width={W} height={H} fill="oklch(0.22 0.04 240)" />
        <rect x="0" y="0" width={W} height={H} fill="url(#oceanGrid)" />

        {/* "Continents" stylisés — masses simples NW + NE + S */}
        <g opacity="0.45">
          <ellipse cx={W * 0.22} cy={H * 0.30} rx={W * 0.20} ry={H * 0.22} fill="oklch(0.36 0.05 70)" />
          <ellipse cx={W * 0.78} cy={H * 0.32} rx={W * 0.22} ry={H * 0.26} fill="oklch(0.36 0.05 70)" />
          <ellipse cx={W * 0.50} cy={H * 0.78} rx={W * 0.30} ry={H * 0.18} fill="oklch(0.34 0.04 90)" />
        </g>

        {/* Éléments */}
        {elements.map((el, i) => {
          const pos = getPos(el.position, i)
          const color = el.categorie ? (colorByCategorie.get(el.categorie.toLowerCase()) || '#e63946') : '#e63946'
          const cx = pos.x * W
          const cy = pos.y * H
          const t = (el.type || 'point').toLowerCase()
          if (t === 'fleche' || t === 'flèche' || t === 'arrow') {
            // Flèche depuis centre vers position
            const sx = W * 0.5
            const sy = H * 0.5
            return (
              <g key={i}>
                <defs>
                  <marker id={`arr-${i}`} markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
                    <path d="M 0 0 L 10 5 L 0 10 Z" fill={color} />
                  </marker>
                </defs>
                <line x1={sx} y1={sy} x2={cx} y2={cy} stroke={color} strokeWidth="2.4"
                      markerEnd={`url(#arr-${i})`} opacity="0.85" />
                <text x={cx} y={cy - 12} fill="#fff" fontSize="11" fontWeight="600"
                      textAnchor="middle" style={{ paintOrder: 'stroke', stroke: '#000', strokeWidth: 3 }}>
                  {el.libelle}
                </text>
              </g>
            )
          }
          if (t === 'zone' || t === 'aire') {
            return (
              <g key={i}>
                <ellipse cx={cx} cy={cy} rx={48} ry={28} fill={color} fillOpacity="0.28"
                         stroke={color} strokeWidth="1.5" />
                <text x={cx} y={cy + 4} fill="#fff" fontSize="11" fontWeight="600"
                      textAnchor="middle" style={{ paintOrder: 'stroke', stroke: '#000', strokeWidth: 3 }}>
                  {el.libelle}
                </text>
              </g>
            )
          }
          if (t === 'hachure' || t === 'hatch') {
            return (
              <g key={i} style={{ color }}>
                <ellipse cx={cx} cy={cy} rx={48} ry={28} fill="url(#hatchPattern)" stroke={color} strokeWidth="1.2" />
                <text x={cx} y={cy + 4} fill="#fff" fontSize="11" fontWeight="600"
                      textAnchor="middle" style={{ paintOrder: 'stroke', stroke: '#000', strokeWidth: 3 }}>
                  {el.libelle}
                </text>
              </g>
            )
          }
          // Default : point
          return (
            <g key={i}>
              <circle cx={cx} cy={cy} r="7" fill={color} stroke="#fff" strokeWidth="1.5" />
              <text x={cx + 12} y={cy + 4} fill="#fff" fontSize="11" fontWeight="600"
                    style={{ paintOrder: 'stroke', stroke: '#000', strokeWidth: 3 }}>
                {el.libelle}
              </text>
            </g>
          )
        })}
      </svg>

      {/* Légende */}
      {legende.length > 0 && (
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: 12, padding: '10px 12px',
          borderRadius: 8, background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
        }}>
          {legende.map((l, i) => {
            const sym = (l.symbole || 'point').toLowerCase()
            return (
              <div key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'rgba(255,255,255,0.85)' }}>
                {sym === 'fleche' || sym === 'flèche' ? (
                  <svg width="22" height="14" viewBox="0 0 22 14"><line x1="2" y1="7" x2="18" y2="7" stroke={l.couleur || '#e63946'} strokeWidth="2.4" /><polygon points="18,3 22,7 18,11" fill={l.couleur || '#e63946'} /></svg>
                ) : sym === 'zone' || sym === 'aire' ? (
                  <span style={{ width: 16, height: 12, background: l.couleur || '#e63946', opacity: 0.4, border: `1px solid ${l.couleur || '#e63946'}`, borderRadius: 2 }} />
                ) : sym === 'hachure' || sym === 'hatch' ? (
                  <span style={{
                    width: 16, height: 12, borderRadius: 2,
                    background: `repeating-linear-gradient(45deg, ${l.couleur || '#e63946'} 0 2px, transparent 2px 5px)`,
                  }} />
                ) : (
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: l.couleur || '#e63946', border: '1px solid rgba(255,255,255,0.6)' }} />
                )}
                <span>{l.libelle}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
