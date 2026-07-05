/**
 * AuroraV33DView — Ricochet "CAD blueprint" entry for the 3D module.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-3.jsx
 * (ThreeV3): cyan-on-navy drafting grid, AURORA · DRAFT DEPT. header,
 * 4-view orthographic projection (FRONT / TOP / SIDE / ISO) with
 * dimension lines + measurements, parts table at the bottom (CAPTURE
 * / SILHOUETTE / VOXELS / MESH / UV / TEXTURES) with stage status
 * (DONE / ACTIVE / PENDING).
 *
 * Like V1, the live session delegates to the full ModelView (3617 LOC)
 * so every Manga feature stays alive — Hunyuan3D, DreamGaussian, Blender
 * procedural, Meshroom, mesh post-processing, bones display, rescue,
 * HDRI environment.
 */
import { lazy, Suspense, useState } from 'react'

const ModelView = lazy(() => import('./ModelView'))

const NAVY = '#0c2944'
const CYAN = '#7dc8ff'
const CYAN_LIGHT = '#cce8ff'
const CYAN_LINE = '#4a82b4'
const AMBER = '#ffd166'
const GREEN = '#7df9c4'

const VIEWS: Array<{ label: string; d: number }> = [
  { label: 'FRONT', d: 0 },
  { label: 'TOP', d: 1 },
  { label: 'SIDE', d: 2 },
  { label: 'ISO', d: 3 },
]

const PARTS: Array<[string, number, string, string, string, string]> = [
  ['001', 1, 'CAPTURE — image-source', '—', '—', 'DONE'],
  ['002', 1, 'SILHOUETTE — extraction alpha', '—', '—', 'DONE'],
  ['003', 1, 'VOXELS — résolution 256³', '16M', '—', 'DONE'],
  ['004', 1, 'MESH — marching cubes', '24,614', '12,308', 'ACTIVE'],
  ['005', 1, 'UV — déplié angulaire', '—', '—', 'PENDING'],
  ['006', 1, 'TEXTURES — diffuse/normal/rough', '—', '—', 'PENDING'],
]

export default function AuroraV33DView() {
  // v82an : skip preview, boot direct sur ModelView.
  const [live, setLive] = useState(true)
  void setLive

  if (live) {
    return (
      <Suspense fallback={
        <div style={{
          width: '100%', height: '100%',
          background: NAVY, color: CYAN_LIGHT,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'Courier New, monospace',
          letterSpacing: '0.3em', fontSize: 14,
        }}>VOLUMEN · INITIALIZING WORKBENCH…</div>
      }>
        <ModelView />
      </Suspense>
    )
  }

  return (
    <div style={{
      width: '100%', height: '100%',
      background: NAVY,
      backgroundImage: `linear-gradient(rgba(120,200,255,0.07) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(120,200,255,0.07) 1px, transparent 1px),
                        linear-gradient(rgba(120,200,255,0.04) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(120,200,255,0.04) 1px, transparent 1px)`,
      backgroundSize: '80px 80px, 80px 80px, 16px 16px, 16px 16px',
      color: CYAN_LIGHT, fontFamily: 'Courier New, Courier, monospace',
      padding: 24, position: 'relative',
      display: 'flex', flexDirection: 'column', overflow: 'auto',
    }}>
      {/* Header */}
      <header style={{
        display: 'flex', justifyContent: 'space-between',
        borderBottom: `1px solid ${CYAN_LINE}`, paddingBottom: 8,
      }}>
        <div>
          <div style={{ fontSize: 11, letterSpacing: '0.3em' }}>AURORA · DRAFT DEPT.</div>
          <div style={{ fontSize: 22, marginTop: 4, letterSpacing: '0.05em' }}>
            VOLUMEN — Hunyuan3D
          </div>
        </div>
        <div style={{ fontSize: 11, textAlign: 'right' }}>
          <div>SHEET 06 / 10</div>
          <div>SCALE 1:1 · METRIC</div>
          <div>REV. C · {new Date().toLocaleDateString('en-US', { month: '2-digit', year: '2-digit' }).replace(/\//g, ' / ')}</div>
        </div>
      </header>

      {/* 4-view grid */}
      <div style={{
        flex: 1, display: 'grid',
        gridTemplateColumns: '1fr 1fr', gridTemplateRows: '1fr 1fr',
        gap: 12, padding: '20px 0', minHeight: 0,
      }}>
        {VIEWS.map((v) => (
          <div key={v.label} style={{
            border: `1px solid ${CYAN_LINE}`, position: 'relative', padding: 14,
            cursor: 'pointer',
          }}
            onClick={() => setLive(true)}>
            <div style={{
              position: 'absolute', top: 6, left: 8, fontSize: 9,
              letterSpacing: '0.2em', background: NAVY, padding: '0 4px',
            }}>{v.label}</div>
            <svg viewBox="0 0 200 120" width="100%" height="100%">
              {v.d === 3 ? (
                <g>
                  <path d="M 60 70 L 100 50 L 140 70 L 140 100 L 100 120 L 60 100 Z" fill="none" stroke={CYAN} strokeWidth="1" />
                  <path d="M 60 70 L 100 50 L 100 80 L 60 100 Z" fill="rgba(125,200,255,0.08)" stroke={CYAN} strokeWidth="1" />
                  <path d="M 100 50 L 140 70 L 140 100 L 100 80 Z" fill="rgba(125,200,255,0.04)" stroke={CYAN} strokeWidth="1" />
                  <path d="M 60 70 L 100 80 L 140 70" fill="none" stroke={CYAN} strokeWidth="0.5" strokeDasharray="2 2" />
                </g>
              ) : (
                <g>
                  <rect x={50 + v.d * 4} y={30} width={100 - v.d * 4} height={70}
                    fill="none" stroke={CYAN} strokeWidth="1" />
                  <path d={`M ${50 + v.d * 4} 65 L ${150 - v.d * 4} 65`}
                    stroke={CYAN} strokeWidth="0.5" strokeDasharray="3 3" />
                  <circle cx="100" cy="65" r={12 - v.d * 2} fill="none" stroke={CYAN} strokeWidth="1" />
                </g>
              )}
              <g stroke={CYAN} strokeWidth="0.4" fill="none">
                <line x1="50" y1="20" x2="150" y2="20" />
                <line x1="50" y1="16" x2="50" y2="24" />
                <line x1="150" y1="16" x2="150" y2="24" />
              </g>
              <text x="100" y="14" fontSize="6" fill={CYAN_LIGHT} textAnchor="middle">142.0</text>
              <g stroke={CYAN} strokeWidth="0.4" fill="none">
                <line x1="170" y1="30" x2="170" y2="100" />
                <line x1="166" y1="30" x2="174" y2="30" />
                <line x1="166" y1="100" x2="174" y2="100" />
              </g>
              <text x="178" y="68" fontSize="6" fill={CYAN_LIGHT}>88.5</text>
            </svg>
          </div>
        ))}
      </div>

      {/* Parts table */}
      <div style={{ border: `1px solid ${CYAN_LINE}`, fontSize: 11, marginBottom: 16 }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '60px 60px 1fr 80px 80px 80px',
          borderBottom: `1px solid ${CYAN_LINE}`, padding: '6px 10px',
          letterSpacing: '0.2em', fontSize: 9, color: CYAN,
        }}>
          <span>ITEM</span><span>QTY</span><span>DESCRIPTION</span><span>VERTS</span><span>FACES</span><span>STAGE</span>
        </div>
        {PARTS.map((row) => (
          <div key={row[0]} style={{
            display: 'grid', gridTemplateColumns: '60px 60px 1fr 80px 80px 80px',
            padding: '6px 10px',
            borderBottom: '1px dashed #2a4a6a',
          }}>
            {row.map((c, i) => (
              <span key={i} style={{
                color: i === 5 && c === 'ACTIVE' ? AMBER
                  : i === 5 && c === 'DONE' ? GREEN
                  : i === 5 && c === 'PENDING' ? '#5a7a9a'
                  : CYAN_LIGHT,
              }}>{c}</span>
            ))}
          </div>
        ))}
      </div>

      {/* Enter workbench */}
      <button type="button" onClick={() => setLive(true)}
        style={{
          padding: '12px 24px', background: 'transparent',
          color: CYAN, border: `1px solid ${CYAN}`,
          fontSize: 12, letterSpacing: '0.3em', cursor: 'pointer',
          fontFamily: 'inherit', alignSelf: 'flex-start',
        }}>
        [ ENTER WORKBENCH · FORGE NEW SHEET ]
      </button>
    </div>
  )
}
