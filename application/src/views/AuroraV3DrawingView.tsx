/**
 * AuroraV3DrawingView — Ricochet "l'atelier" port.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-4.jsx
 * (DrawV3): cream paper background with vignette, hand-drawn "l'atelier"
 * title, paper-edge curl corner, dashed sidebar with hand-drawn pencil
 * SVGs, layer list. Real wiring via useDrawingViewLogic — every Manga
 * feature preserved 1:1: pointer-pressure brushes, palette, brush size,
 * symmetry, undo/redo, IDB persistence, FLUX render via Aurora-Connect,
 * drying-line gallery, download PNG.
 */
import { useDrawingViewLogic, PALETTE } from '../hooks/useDrawingViewLogic'
import { useFileDrop } from '../hooks/useFileDrop'
import { getDailyTip } from '../utils/dailyTip'
import VoicePushToTalk from '../components/VoicePushToTalk'

const PAPER = '#faf2e0'
const INK = '#2a1f15'
const RED = '#a8231d'

function CavBtn({ active, onClick, children, disabled, title, danger }: {
  active?: boolean; onClick?: () => void; children: React.ReactNode
  disabled?: boolean; title?: string; danger?: boolean
}) {
  const bg = danger ? RED : active ? INK : 'transparent'
  const fg = danger || active ? PAPER : INK
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
      style={{
        padding: '6px 12px', fontSize: 14,
        background: bg, color: fg,
        border: `1px solid ${INK}`,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        fontFamily: 'Caveat, Bradley Hand, cursive',
        display: 'inline-flex', alignItems: 'center', gap: 4,
        transform: 'rotate(-0.5deg)',
      }}>{children}</button>
  )
}

export default function AuroraV3DrawingView() {
  const D = useDrawingViewLogic({ paperColor: '#fffdf5' })
  // v82eb : drag-drop parity V3 — image → load canvas comme base de tracé
  const drop = useFileDrop({
    onFile: (f) => void D.loadImageToCanvas(f),
    accept: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif'],
    acceptMime: ['image/'],
    disabled: D.rendering,
  })

  return (
    <div {...drop.bind} style={{
      width: '100%', height: '100%',
      background: PAPER,
      outline: drop.isDraggingOver ? `2px dashed ${INK}` : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      backgroundImage: `radial-gradient(ellipse at 30% 20%, rgba(180,140,90,0.12), transparent 40%),
                        radial-gradient(ellipse at 70% 80%, rgba(180,140,90,0.08), transparent 40%)`,
      padding: 32,
      fontFamily: 'Caveat, Bradley Hand, cursive', color: INK,
      position: 'relative',
      display: 'grid', gridTemplateColumns: '1fr 280px', gridTemplateRows: '1fr auto',
      gap: 24,
    }}>
      {/* Paper edge curl */}
      <div style={{
        position: 'absolute', top: 0, right: 0, width: 80, height: 80,
        background: 'linear-gradient(225deg, transparent 50%, rgba(0,0,0,0.08) 50%)',
      }} />

      {/* Main canvas area */}
      <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <h1 style={{ fontSize: 56, margin: 0, transform: 'rotate(-1deg)', color: INK }}>l'atelier</h1>
        <div style={{
          fontFamily: 'Georgia, serif', fontStyle: 'italic',
          fontSize: 14, marginTop: -4, color: '#5a4a3a', marginBottom: 12,
        }}>
          ↳ feuille du jeudi · {D.brush === 'ink' ? 'encre de Chine' : 'gomme'} · {D.brushSize.toFixed(1)}
          {D.symmetry && ' · symétrie'}
        </div>

        <div style={{
          flex: 1, position: 'relative', minHeight: 360,
          border: '1px solid rgba(42,31,21,0.2)',
          background: 'rgba(255,253,245,0.6)',
        }}>
          <canvas
            ref={D.canvasRef}
            {...D.canvasHandlers}
            style={{
              width: '100%', height: '100%', display: 'block',
              cursor: D.brush === 'eraser' ? 'cell' : 'crosshair',
              touchAction: 'none',
            }} />
          {D.rendering && (
            <div style={{
              position: 'absolute', top: 12, right: 12,
              background: INK, color: PAPER, padding: '4px 10px',
              fontSize: 13, fontFamily: 'Caveat, cursive',
              transform: 'rotate(-2deg)',
            }}>
              ✏ rendu… {D.progress}
            </div>
          )}
        </div>

        {/* Aurora suggestion */}
        <div style={{
          marginTop: 16, display: 'flex', gap: 14, alignItems: 'center',
          fontSize: 22, transform: 'rotate(-0.5deg)', flexWrap: 'wrap',
        }}>
          <span>aurora suggère :</span>
          {D.renderUrl ? (
            <>
              <span style={{ borderBottom: `2px solid ${RED}`, paddingBottom: 2, color: RED }}>
                regarde le rendu →
              </span>
              <button type="button" onClick={D.downloadRender}
                style={{
                  background: 'transparent', border: 'none',
                  fontFamily: 'Caveat, cursive', fontSize: 18, cursor: 'pointer',
                  color: INK, textDecoration: 'underline',
                }}>
                ⬇ télécharger PNG
              </button>
            </>
          ) : D.rendering ? (
            <span style={{ borderBottom: `2px solid ${RED}`, color: RED }}>
              le pinceau travaille…
            </span>
          ) : (
            <div>
              <span style={{ fontSize: 14, color: '#5a4a3a' }}>
                écris une intention en bas, lance le pinceau
              </span>
              {/* v82fw : daily tip Drawing stencil */}
              <div style={{
                marginTop: 12, padding: '6px 12px',
                fontSize: 11, fontFamily: 'Courier New, monospace',
                color: INK,
                background: 'rgba(255,255,255,0.4)',
                border: `1px solid ${INK}`,
                lineHeight: 1.5, display: 'inline-block',
              }}>
                {getDailyTip('drawing')}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Sidebar tools */}
      <aside style={{
        borderLeft: '1px dashed rgba(42,31,21,0.3)', paddingLeft: 18,
        display: 'flex', flexDirection: 'column', gap: 14, fontSize: 18,
        overflowY: 'auto', minHeight: 0,
      }}>
        <div style={{ fontSize: 26, transform: 'rotate(-1deg)' }}>boîte à outils</div>

        {/* Pencil/ink */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, transform: 'rotate(1deg)' }}>
          <button type="button" onClick={() => D.setBrush('ink')}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
              opacity: D.brush === 'ink' ? 1 : 0.5,
            }}>
            <svg width="120" height="20" viewBox="0 0 120 20">
              <path d="M 0 10 L 10 4 L 95 4 L 95 16 L 10 16 Z" fill="#e8a040" stroke={INK}/>
              <path d="M 0 10 L 10 4 L 10 16 Z" fill={INK}/>
              <path d="M 95 4 L 110 4 L 115 10 L 110 16 L 95 16 Z" fill="#d8b890" stroke={INK}/>
            </svg>
          </button>
          <span style={{ textDecoration: D.brush === 'ink' ? 'underline' : 'none' }}>
            encre {D.brush === 'ink' && '★'}
          </span>
        </div>

        {/* Eraser */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, transform: 'rotate(-2deg)' }}>
          <button type="button" onClick={() => D.setBrush('eraser')}
            style={{
              background: 'transparent', border: 'none', cursor: 'pointer', padding: 0,
              opacity: D.brush === 'eraser' ? 1 : 0.5,
            }}>
            <svg width="120" height="20" viewBox="0 0 120 20">
              <path d="M 0 10 L 10 4 L 95 4 L 95 16 L 10 16 Z" fill="#3a5a4a" stroke={INK}/>
              <path d="M 0 10 L 10 4 L 10 16 Z" fill={INK}/>
            </svg>
          </button>
          <span style={{ textDecoration: D.brush === 'eraser' ? 'underline' : 'none' }}>
            gomme {D.brush === 'eraser' && '★'}
          </span>
        </div>

        {/* Brush size slider */}
        <div style={{ transform: 'rotate(0.5deg)' }}>
          <div style={{ fontSize: 14 }}>épaisseur · {D.brushSize.toFixed(1)}</div>
          <input type="range" min={1} max={12} step={0.5} value={D.brushSize}
            onChange={(e) => D.setBrushSize(Number(e.target.value))}
            style={{ width: '100%' }} />
        </div>

        {/* Palette */}
        <div>
          <div style={{ fontSize: 14, marginBottom: 4 }}>palette</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {PALETTE.map((c) => (
              <button key={c} type="button"
                onClick={() => { D.setInkColor(c); D.setBrush('ink') }}
                title={c}
                style={{
                  width: 22, height: 22, background: c,
                  border: D.inkColor === c ? `2px solid ${INK}` : `1px solid ${INK}`,
                  cursor: 'pointer', borderRadius: '50%',
                  transform: D.inkColor === c ? 'scale(1.15)' : 'none',
                }} />
            ))}
            <label style={{
              width: 22, height: 22, borderRadius: '50%',
              border: `1px dashed ${INK}`, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
            }}>
              +
              <input type="color" value={D.inkColor}
                onChange={(e) => { D.setInkColor(e.target.value); D.setBrush('ink') }}
                style={{ display: 'none' }} />
            </label>
          </div>
        </div>

        <div>
          <div style={{ fontSize: 14, marginBottom: 4 }}>rendu IA</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            <CavBtn active={D.colorMode === 'auto'} onClick={() => D.setColorMode('auto')}>auto</CavBtn>
            <CavBtn active={D.colorMode === 'color'} onClick={() => D.setColorMode('color')}>couleur</CavBtn>
            <CavBtn active={D.colorMode === 'monochrome'} onClick={() => D.setColorMode('monochrome')}>N&B</CavBtn>
          </div>
        </div>

        {/* Symmetry + history controls */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          <CavBtn active={D.symmetry} onClick={() => D.setSymmetry(!D.symmetry)}>⇄ sym</CavBtn>
          <CavBtn onClick={D.undo} disabled={D.historyLen === 0} title="Ctrl+Z">↶ undo</CavBtn>
          <CavBtn onClick={D.redo} disabled={D.futureLen === 0} title="Ctrl+Y">↷ redo</CavBtn>
          <CavBtn onClick={D.clearCanvas}>✕ feuille</CavBtn>
        </div>

        <div style={{
          borderTop: '1px dashed rgba(42,31,21,0.3)',
          paddingTop: 12, marginTop: 4,
          fontFamily: 'Georgia, serif', fontStyle: 'italic',
          fontSize: 13, color: '#5a4a3a',
        }}>
          séchage :
          {D.line.length === 0 ? (
            <ol style={{ margin: '6px 0 0', paddingLeft: 20, fontSize: 14, color: INK }}>
              <li style={{ opacity: 0.5 }}>vide</li>
            </ol>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 8 }}>
              {D.line.slice(0, 4).map((sheet) => (
                sheet.renderUrl && (
                  <button key={sheet.id} type="button" title={sheet.prompt}
                    onClick={() => D.recallSheet(sheet)}
                    style={{
                      background: PAPER, padding: 4,
                      transform: `rotate(${(Math.random() * 4 - 2).toFixed(1)}deg)`,
                      boxShadow: '0 4px 8px rgba(0,0,0,0.15)',
                      border: 'none',
                      cursor: 'pointer',
                    }}>
                    <img src={sheet.renderUrl} alt={sheet.prompt}
                      style={{ width: '100%', display: 'block', filter: 'sepia(0.15)' }} />
                  </button>
                )
              ))}
            </div>
          )}
        </div>

        <div style={{
          marginTop: 'auto', textAlign: 'center', fontSize: 14,
          fontFamily: 'Georgia, serif', fontStyle: 'italic', color: '#5a4a3a',
        }}>
          {new Date().toTimeString().slice(0, 5)} ·{' '}
          {['lundi','mardi','mercredi','jeudi','vendredi','samedi','dimanche'][new Date().getDay() === 0 ? 6 : new Date().getDay() - 1]}
        </div>
      </aside>

      {/* Render preview floating mid-bottom */}
      {(D.renderUrl || D.rendering) && (
        <div style={{
          gridColumn: '1', position: 'relative',
          padding: '8px 12px',
          background: PAPER, border: `1px solid ${INK}`,
          transform: 'rotate(-0.5deg)',
          boxShadow: '0 8px 22px rgba(0,0,0,0.3)',
          maxHeight: 200, overflow: 'hidden',
        }}>
          <div style={{ fontSize: 14, marginBottom: 4 }}>aurora · proposition</div>
          {D.renderUrl ? (
            <img src={D.renderUrl} alt="rendu"
              style={{ maxWidth: 200, maxHeight: 140, filter: 'sepia(0.1)' }} />
          ) : (
            <div style={{
              width: 200, height: 140, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              fontSize: 14, color: '#5a4a3a',
            }}>
              ✏ {D.progress || 'rendu…'}
            </div>
          )}
        </div>
      )}

      {/* Compose strip */}
      <div style={{
        gridColumn: '1 / -1',
        background: INK, color: PAPER, padding: '14px 20px',
        display: 'flex', gap: 16, alignItems: 'flex-start',
        transform: 'rotate(-0.3deg)', boxShadow: '0 6px 18px rgba(0,0,0,0.3)',
      }}>
        <span style={{
          fontFamily: 'Permanent Marker, Marker Felt, cursive', fontSize: 16,
          flexShrink: 0, paddingTop: 4,
        }}>
          ✏ intention :
        </span>
        <textarea
          value={D.prompt} onChange={(e) => D.setPrompt(e.target.value)}
          onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); void D.invoke() } }}
          disabled={D.rendering}
          rows={2}
          placeholder="« décris ce que tu invoques… »"
          style={{
            flex: 1, padding: '4px 0',
            background: 'transparent', color: PAPER,
            border: 'none', borderBottom: `1px dashed ${PAPER}`,
            outline: 'none', fontStyle: 'italic',
            fontSize: 14, fontFamily: 'Georgia, serif',
            resize: 'none',
          }} />
        <VoicePushToTalk
          onTranscript={(text) => D.setPrompt((D.prompt ? D.prompt + ' ' : '') + text)}
          label="Dicter l'intention de dessin"
          disabled={D.rendering}
          variant="ghost"
          size={32}
        />
        {D.rendering ? (
          <button type="button" onClick={D.stop}
            style={{
              background: RED, color: PAPER, border: 'none', padding: '8px 18px',
              fontFamily: 'Permanent Marker, Marker Felt, cursive', fontSize: 14,
              cursor: 'pointer',
            }}>◼ STOP</button>
        ) : (
          <>
            <button type="button" onClick={() => void D.invoke()} disabled={!D.prompt.trim()}
              style={{
                background: PAPER, color: INK, border: 'none', padding: '8px 18px',
                fontFamily: 'Permanent Marker, Marker Felt, cursive', fontSize: 14,
                cursor: !D.prompt.trim() ? 'not-allowed' : 'pointer',
                opacity: !D.prompt.trim() ? 0.5 : 1,
              }}>
              GENERER LE RENDU
            </button>
            {/* v82fh : preset surprise (random ink + prompt + auto-invoke) */}
            <button type="button"
              onClick={() => {
                D.randomDrawPreset()
                window.setTimeout(() => { void D.invoke() }, 0)
              }}
              title="Encre + prompt aléatoires PUIS invoque le rendu"
              style={{
                background: 'transparent', color: INK,
                border: `1px solid ${INK}`,
                padding: '8px 14px', marginLeft: 8,
                fontFamily: 'Permanent Marker, Marker Felt, cursive',
                fontSize: 13, cursor: 'pointer',
              }}>⚡ SURPRISE</button>
          </>
        )}
      </div>

      {D.error && (
        <div style={{
          gridColumn: '1 / -1', padding: '8px 16px',
          background: RED, color: PAPER, fontSize: 14,
          fontFamily: 'Caveat, cursive', transform: 'rotate(-0.5deg)',
        }}>
          ⚠ {D.error}
        </div>
      )}
    </div>
  )
}
