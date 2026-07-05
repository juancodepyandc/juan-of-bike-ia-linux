/**
 * AuroraV1DrawingView — Editorial sumi-e port.
 *
 * Visual chrome from _design/aurora_design_screens_v1/modules.jsx
 * (DrawScreen): paper background, left rail with editorial title +
 * brush selector, right canvas + AI suggestion floater. Real wiring
 * via useDrawingViewLogic — every Manga feature preserved: pointer-
 * pressure brushes, palette + custom picker, brush size slider,
 * symmetry, undo/redo (Ctrl+Z/Y), IDB persistence, FLUX render via
 * Aurora-Connect grounding, drying-line gallery, download PNG.
 */
import { useEffect, useState } from 'react'
import { Brush, Download, Eraser, Eye, Loader2, RotateCcw, Sparkles, StopCircle } from 'lucide-react'
import { useDrawingViewLogic, PALETTE, PORTRAITS } from '../hooks/useDrawingViewLogic'
import { useModuleStreak } from '../hooks/useModuleStreak'
import { useFileDrop } from '../hooks/useFileDrop'
import { getDailyTip } from '../utils/dailyTip'
import { loadBlobUrl } from '../utils/blobStore'
import type { PromptHistoryEntry } from '../utils/promptHistory'
import FavoriteButton from '../components/FavoriteButton'
import VoicePushToTalk from '../components/VoicePushToTalk'

const PAPER = 'oklch(0.99 0.005 85)'

function Eyebrow({ children, dot, style }: { children: React.ReactNode; dot?: string; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
      letterSpacing: '0.14em', textTransform: 'uppercase',
      color: 'var(--fg-mute, #5a4a3a)', display: 'flex', alignItems: 'center', gap: 8,
      ...style,
    }}>
      {dot && <span style={{
        width: 8, height: 8, borderRadius: 99, background: dot,
        boxShadow: `0 0 12px ${dot}`,
      }} />}
      {children}
    </div>
  )
}

function Display({ size = 36, children, style }: {
  size?: number; children: React.ReactNode; style?: React.CSSProperties
}) {
  return (
    <div style={{
      fontFamily: 'var(--font-display, "Cormorant Garamond", serif)', fontSize: size,
      fontStyle: 'italic', fontWeight: 400, lineHeight: 0.95,
      letterSpacing: '-0.02em', color: 'var(--fg, #1a140d)', ...style,
    }}>{children}</div>
  )
}

function Pill({ active, onClick, children, disabled, title }: {
  active?: boolean; onClick?: () => void; children: React.ReactNode; disabled?: boolean; title?: string
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
      style={{
        padding: '6px 10px',
        border: `1px solid ${active ? 'var(--fg, #1a140d)' : 'var(--line, #d4cab8)'}`, borderRadius: 4,
        fontSize: 12, fontFamily: 'var(--font-mono, monospace)',
        background: active ? 'var(--fg, #1a140d)' : 'transparent',
        color: active ? PAPER : 'var(--fg, #1a140d)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        display: 'inline-flex', alignItems: 'center', gap: 4,
      }}>{children}</button>
  )
}

function HistoryThumb({ entry, onClick }: { entry: PromptHistoryEntry; onClick: () => void }) {
  const [url, setUrl] = useState<string | null>(null)
  const renderBlobId = typeof entry.meta?.renderBlobId === 'string' ? entry.meta.renderBlobId : ''

  useEffect(() => {
    if (!renderBlobId) {
      setUrl(null)
      return
    }
    let alive = true
    let objectUrl: string | null = null
    void loadBlobUrl(renderBlobId).then((loaded) => {
      if (!alive) {
        if (loaded) URL.revokeObjectURL(loaded)
        return
      }
      objectUrl = loaded
      setUrl(loaded)
    })
    return () => {
      alive = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [renderBlobId])

  if (!url) return null

  return (
    <button type="button" onClick={onClick} title="Rappeler ce rendu"
      style={{
        width: 38, height: 38, padding: 0,
        border: '1px solid var(--line, #d4cab8)',
        background: 'var(--bg-card, #fef9f0)',
        cursor: 'pointer', overflow: 'hidden', borderRadius: 4,
      }}>
      <img src={url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
    </button>
  )
}

export default function AuroraV1DrawingView() {
  const D = useDrawingViewLogic({ paperColor: '#fafaf5' })
  const drawingStreak = useModuleStreak('drawing')
  // v82iy : 1-5 = pick brush preset (quand pas dans un input).
  // v82iz : B/E/S = brush / eraser / symmetry toggle.
  useEffect(() => {
    const PRESETS = [1, 2, 4, 6, 12]
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return
      const tag = (e.target as HTMLElement | null)?.tagName?.toUpperCase()
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      // 1-5 brush size
      const idx = ['1', '2', '3', '4', '5'].indexOf(e.key)
      if (idx !== -1) {
        e.preventDefault()
        D.setBrushSize(PRESETS[idx])
        return
      }
      // v82iz : letter shortcuts.
      // v82j1 : X swap brush/eraser (Photoshop convention).
      // v82j2 : [ / ] size -1px / +1px (Photoshop convention).
      const k = e.key.toLowerCase()
      if (k === 'b') { e.preventDefault(); D.setBrush('ink') }
      else if (k === 'e') { e.preventDefault(); D.setBrush('eraser') }
      else if (k === 's') { e.preventDefault(); D.setSymmetry(!D.symmetry) }
      else if (k === 'x') {
        e.preventDefault()
        D.setBrush(D.brush === 'ink' ? 'eraser' : 'ink')
      }
      else if (e.key === '[') {
        e.preventDefault()
        D.setBrushSize(Math.max(1, D.brushSize - 1))
      }
      else if (e.key === ']') {
        e.preventDefault()
        D.setBrushSize(Math.min(12, D.brushSize + 1))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [D])
  // v82fo : drop zone Drawing → load image dans le canvas comme base.
  const drop = useFileDrop({
    onFile: (file) => void D.loadImageToCanvas(file),
    accept: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif'],
    acceptMime: ['image/'],
    disabled: D.rendering,
  })

  return (
    // v82o : root carries data-theme="paper" so the v82k Editorial light-mode
    // override kicks in (--bg = --paper, --fg = --ink-1000, --line = warm bone).
    // The previous hardcoded #fafaf5 was a small drift from the design's
    // intended oklch(0.97 0.008 85). Inline-style fallbacks remain for
    // safety if the stylesheet fails to load.
    <div data-theme="paper" {...drop.bind} className="aurora-v1-cols" style={{
      height: '100%', background: 'var(--bg, #fafaf5)', color: 'var(--fg, #1a140d)',
      position: 'relative', display: 'flex',
      fontFamily: 'var(--font-sans, system-ui)',
      outline: drop.isDraggingOver ? '2px dashed oklch(0.74 0.13 60)' : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      transition: 'outline 120ms ease',
    }}>
      {/* v82fo : hint visuel pendant drag-over */}
      {drop.isDraggingOver && (
        <div style={{
          position: 'absolute', top: 14, left: '50%', transform: 'translateX(-50%)',
          zIndex: 100, pointerEvents: 'none',
          padding: '8px 16px', borderRadius: 99,
          background: 'oklch(0.74 0.13 60 / 0.95)',
          color: '#fafaf5',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase',
          boxShadow: '0 6px 24px rgba(0,0,0,0.4)',
        }}>
          ✏ Déposer image · base de tracé
        </div>
      )}
      {/* Left rail (→ pleine largeur empilée au-dessus du canvas sur mobile) */}
      <div className="aurora-v1-side" style={{
        width: 280, padding: '32px 24px',
        borderRight: '1px solid #d4cab8',
        display: 'flex', flexDirection: 'column', gap: 16,
        overflowY: 'auto',
      }}>
        <Eyebrow style={{ color: 'var(--fg-mute, #5a4a3a)' }}>墨 Dessin · Sumi-e</Eyebrow>
        <Display size={56}>Sumi-e<br/><em>local</em></Display>
        <p style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--fg-mute, #5a4a3a)', margin: 0 }}>
          Tablette + ML — Aurora suit la pression et le geste, propose
          des continuations dans le style sumi-e ou sketch2img.
        </p>
        {/* v82ia : streak créativité (parité Cyber/Academy/Image) */}
        {drawingStreak.current > 0 && (
          <div style={{
            fontSize: 10, color: drawingStreak.current >= 7 ? 'oklch(0.62 0.16 60)' : 'var(--fg-mute, #5a4a3a)',
            fontFamily: 'var(--font-mono, monospace)', letterSpacing: '0.05em',
          }}
          title={`Streak créativité Dessin : ${drawingStreak.current} jour(s) consécutif(s)\nRecord : ${drawingStreak.longest} jour(s)`}>
            🔥 {drawingStreak.current}j{drawingStreak.longest > drawingStreak.current ? ` / record ${drawingStreak.longest}j` : drawingStreak.current >= 7 ? ' 🏆' : ''}
          </div>
        )}
        <div style={{ borderTop: '1px solid #d4cab8' }} />

        <Eyebrow style={{ color: 'var(--fg-mute, #5a4a3a)' }}>
          Pinceaux <span style={{
            opacity: 0.55, fontSize: 9, marginLeft: 6,
            fontFamily: 'var(--font-mono, monospace)', letterSpacing: '0.05em',
          }}>· B / E / S</span>
        </Eyebrow>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <Pill active={D.brush === 'ink'} onClick={() => D.setBrush('ink')}>
            <Brush size={11} /> Encre
          </Pill>
          <Pill active={D.brush === 'eraser'} onClick={() => D.setBrush('eraser')}>
            <Eraser size={11} /> Gomme
          </Pill>
          <Pill active={D.symmetry} onClick={() => D.setSymmetry(!D.symmetry)} title="Symétrie verticale">
            ⇄ Symétrie
          </Pill>
        </div>

        <Eyebrow style={{ color: 'var(--fg-mute, #5a4a3a)' }}>Couleurs</Eyebrow>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {PALETTE.map((c) => (
            <button key={c} type="button" onClick={() => { D.setInkColor(c); D.setBrush('ink') }}
              title={c}
              style={{
                width: 26, height: 26, borderRadius: 4,
                background: c,
                border: D.inkColor === c ? '2px solid #1a140d' : '1px solid #d4cab8',
                cursor: 'pointer',
              }} />
          ))}
          <label style={{
            width: 26, height: 26, borderRadius: 4, cursor: 'pointer',
            border: '1px dashed #1a140d',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, color: 'var(--fg, #1a140d)',
          }}>
            +
            <input type="color" value={D.inkColor}
              onChange={(e) => { D.setInkColor(e.target.value); D.setBrush('ink') }}
              style={{ display: 'none' }} />
          </label>
        </div>
        {/* v82ip : pinned colors sticky (Shift+click pour pin/unpin) */}
        {D.pinnedColors.length > 0 && (
          <>
            <Eyebrow style={{ color: 'var(--fg-mute, #5a4a3a)', marginTop: 4 }}>★ Épinglés</Eyebrow>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {D.pinnedColors.map((c) => (
                <button key={`pin-${c}`} type="button"
                  onClick={(e) => {
                    if (e.shiftKey) { D.togglePinColor(c); return }
                    D.setInkColor(c); D.setBrush('ink')
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault()
                    D.togglePinColor(c)
                  }}
                  title={`★ ${c.toUpperCase()}\nShift+clic ou clic-droit = retirer du pin`}
                  style={{
                    width: 20, height: 20, padding: 0,
                    background: c, borderRadius: 3,
                    border: D.inkColor === c
                      ? '2px solid oklch(0.62 0.16 60)'
                      : '2px solid #1a140d',
                    cursor: 'pointer',
                    boxShadow: '0 0 0 1px #fff inset',
                  }} />
              ))}
            </div>
          </>
        )}
        {/* v82il : color history (10 dernières couleurs custom utilisées) */}
        {D.colorHistory.filter((c) => !D.pinnedColors.includes(c)).length > 0 && (
          <>
            <Eyebrow style={{ color: 'var(--fg-mute, #5a4a3a)', marginTop: 4 }}>Récents</Eyebrow>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {D.colorHistory.filter((c) => !D.pinnedColors.includes(c)).map((c) => (
                <button key={c} type="button"
                  onClick={(e) => {
                    if (e.shiftKey) { D.togglePinColor(c); return }
                    D.setInkColor(c); D.setBrush('ink')
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault()
                    D.removeColorFromHistory(c)
                  }}
                  title={`Récent · ${c.toUpperCase()}\nShift+clic = épingler · Clic-droit = supprimer`}
                  style={{
                    width: 18, height: 18, padding: 0,
                    background: c, borderRadius: 3,
                    border: D.inkColor === c ? '2px solid #1a140d' : '1px solid #d4cab8',
                    cursor: 'pointer',
                  }} />
              ))}
            </div>
          </>
        )}

        <Eyebrow style={{ color: 'var(--fg-mute, #5a4a3a)' }}>Rendu IA</Eyebrow>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <Pill active={D.colorMode === 'auto'} onClick={() => D.setColorMode('auto')} title="Couleur decidee par le brief et le croquis">
            Auto
          </Pill>
          <Pill active={D.colorMode === 'color'} onClick={() => D.setColorMode('color')} title="Forcer un rendu couleur">
            Couleur
          </Pill>
          <Pill active={D.colorMode === 'monochrome'} onClick={() => D.setColorMode('monochrome')} title="Forcer noir et blanc">
            N&B
          </Pill>
        </div>

        <Eyebrow style={{ color: 'var(--fg-mute, #5a4a3a)' }}>
          Trait · {D.brushSize.toFixed(1)} <span style={{
            opacity: 0.55, fontSize: 9, marginLeft: 6,
            fontFamily: 'var(--font-mono, monospace)', letterSpacing: '0.05em',
          }}>· 1-5</span>
        </Eyebrow>
        <input type="range" min={1} max={12} step={0.5} value={D.brushSize}
          onChange={(e) => D.setBrushSize(Number(e.target.value))} />
        {/* v82iw : brush size presets quick-pick (5 valeurs courantes) */}
        <div style={{ display: 'flex', gap: 4, marginTop: 2 }}>
          {[1, 2, 4, 6, 12].map((sz) => {
            const active = Math.abs(D.brushSize - sz) < 0.25
            return (
              <button key={sz} type="button"
                onClick={() => D.setBrushSize(sz)}
                title={`Trait ${sz}px`}
                style={{
                  flex: 1, padding: '4px 0',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  background: active ? '#1a140d' : 'transparent',
                  color: active ? '#fafaf5' : '#1a140d',
                  border: `1px solid ${active ? '#1a140d' : '#d4cab8'}`,
                  borderRadius: 3, cursor: 'pointer',
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                }}>
                <span style={{
                  width: Math.min(sz, 10), height: Math.min(sz, 10),
                  borderRadius: '50%',
                  background: active ? '#fafaf5' : '#1a140d',
                  marginRight: 4,
                }} />
                {sz}
              </button>
            )
          })}
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <Pill onClick={D.undo} disabled={D.historyLen === 0} title="Annuler (Ctrl+Z)">
            ↶ Undo{D.historyLen > 0 ? ` (${D.historyLen})` : ''}
          </Pill>
          <Pill onClick={D.redo} disabled={D.futureLen === 0} title="Rétablir (Ctrl+Y)">
            ↷ Redo{D.futureLen > 0 ? ` (${D.futureLen})` : ''}
          </Pill>
          <Pill onClick={D.clearCanvas}>
            <RotateCcw size={11} /> Feuille
          </Pill>
        </div>

        {/* Drying line preview */}
        {D.line.length > 0 && (
          <>
            <div style={{ borderTop: '1px solid #d4cab8' }} />
            <Eyebrow style={{ color: 'var(--fg-mute, #5a4a3a)' }}>Séchage · {D.line.length}</Eyebrow>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {D.line.slice(0, 4).map((sheet) => (
                <button key={sheet.id} type="button" title={sheet.prompt}
                  onClick={() => D.recallSheet(sheet)}
                  style={{ position: 'relative', padding: 0, background: 'transparent', border: 'none', cursor: 'pointer' }}>
                  {sheet.renderUrl && <img src={sheet.renderUrl} alt={sheet.prompt}
                    style={{ width: '100%', aspectRatio: '1/1', objectFit: 'cover', border: '1px solid #d4cab8' }} />}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Canvas + result */}
      <div className="aurora-v1-stage-min" style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div className="aurora-v1-cols aurora-v1-stage-min" style={{
          position: 'relative', flex: 1,
          padding: 40, display: 'grid',
          gridTemplateColumns: D.renderUrl || D.rendering ? '1fr 1fr' : '1fr',
          gap: 24,
        }}>
          {/* Sketch canvas */}
          <div style={{
            position: 'relative',
            background: PAPER, border: '1px solid #d4cab8',
            boxShadow: '0 30px 80px rgba(0,0,0,0.08)',
          }}>
            <canvas
              ref={D.canvasRef}
              {...D.canvasHandlers}
              style={{
                width: '100%', height: '100%', display: 'block',
                cursor: D.brush === 'eraser' ? 'cell' : 'crosshair',
                touchAction: 'none',
              }} />
            <div style={{
              position: 'absolute', top: 8, left: 8,
              fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
              color: 'var(--fg-mute, #5a4a3a)', letterSpacing: '0.2em',
            }}>SUMI-E · 和</div>
          </div>

          {/* Result panel */}
          {(D.renderUrl || D.rendering) && (
            <div style={{
              position: 'relative',
              background: 'var(--bg-card, #fef9f0)', border: '1px solid #d4cab8',
              boxShadow: '0 30px 80px rgba(0,0,0,0.12)',
              padding: 12, display: 'flex', flexDirection: 'column', gap: 8,
            }}>
              <Eyebrow dot="var(--ember-500, #ff6a3d)" style={{ color: 'var(--fg-mute, #5a4a3a)' }}>
                <Eye size={11} style={{ marginRight: 4 }} /> Aurora propose
              </Eyebrow>
              <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
                {D.renderUrl ? (
                  <img src={D.renderUrl} alt="rendu"
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                ) : D.rendering ? (
                  <div style={{
                    height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexDirection: 'column', gap: 12, color: 'var(--fg-mute, #5a4a3a)',
                  }}>
                    <Loader2 size={36} style={{ animation: 'spin 1s linear infinite' }} />
                    <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
                    <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11 }}>{D.progress || 'rendu…'}</span>
                  </div>
                ) : null}
              </div>
              {D.renderUrl && !D.rendering && (
                <button type="button" onClick={D.downloadRender}
                  style={{
                    padding: '6px 12px', fontSize: 12,
                    background: 'var(--fg, #1a140d)', color: PAPER, border: 'none',
                    cursor: 'pointer', fontFamily: 'var(--font-sans, system-ui)',
                    display: 'inline-flex', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
                  }}>
                  <Download size={12} /> PNG
                </button>
              )}
            </div>
          )}
        </div>

        {/* Spell strip */}
        <div style={{
          borderTop: '1px solid #d4cab8', padding: '14px 20px',
          background: 'var(--bg-card, #fef9f0)',
          display: 'flex', gap: 12, alignItems: 'flex-start',
          flexDirection: 'column',
        }}>
          {/* v82ft : daily tip Drawing (visible si pas de rendu encore) */}
          {!D.renderUrl && !D.rendering && (
            <div style={{
              padding: '6px 12px',
              fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
              color: '#5a4a3a',
              background: 'oklch(0.74 0.13 60 / 0.10)',
              border: '1px solid oklch(0.74 0.13 60 / 0.30)',
              borderRadius: 6, alignSelf: 'flex-start',
              maxWidth: '100%',
            }}>
              {getDailyTip('drawing')}
            </div>
          )}
          <div style={{ display: 'flex', gap: 12, width: '100%', alignItems: 'flex-start' }}>
          <VoicePushToTalk
            onTranscript={(text) => D.setPrompt((D.prompt ? D.prompt + ' ' : '') + text)}
            label="Dicter l'intention de dessin"
            disabled={D.rendering}
            variant="ghost"
            size={32}
          />
          <textarea
            value={D.prompt} onChange={(e) => D.setPrompt(e.target.value)}
            onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); void D.invoke() } }}
            disabled={D.rendering}
            placeholder="Donne ton intention. Mon pinceau invoquera l'image depuis ton trait."
            rows={2}
            style={{
              flex: 1, padding: 10, fontSize: 13,
              background: PAPER, color: 'var(--fg, #1a140d)',
              border: '1px solid #d4cab8',
              fontFamily: 'var(--font-sans, system-ui)',
              resize: 'none', outline: 'none',
            }} />
          {D.rendering ? (
            <button type="button" onClick={D.stop}
              style={{
                padding: '10px 16px',
                background: '#b5241e', color: PAPER, border: 'none',
                fontSize: 13, cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 6,
                fontFamily: 'var(--font-sans, system-ui)',
              }}>
              <StopCircle size={14} /> Stop
            </button>
          ) : (
            <button type="button" onClick={() => void D.invoke()} disabled={!D.prompt.trim()}
              style={{
                padding: '10px 16px',
                background: 'var(--ember-500, #ff6a3d)', color: '#0a0a0a',
                border: 'none', fontSize: 13, cursor: !D.prompt.trim() ? 'not-allowed' : 'pointer',
                opacity: !D.prompt.trim() ? 0.5 : 1,
                display: 'inline-flex', alignItems: 'center', gap: 6,
                fontFamily: 'var(--font-sans, system-ui)',
              }}>
              <Sparkles size={14} /> Generer le rendu
            </button>
          )}
          {/* v82ey : preset surprise (random ink + random prompt + invoke) */}
          {!D.rendering && (
            <button type="button"
              onClick={() => {
                D.randomDrawPreset()
                window.setTimeout(() => { void D.invoke() }, 0)
              }}
              title="Pioche couleur d'encre + prompt au hasard PUIS invoque le rendu"
              style={{
                padding: '10px 14px',
                background: 'oklch(0.74 0.13 60 / 0.12)',
                color: 'oklch(0.50 0.13 60)',
                border: '1px solid oklch(0.74 0.13 60 / 0.55)',
                fontSize: 12, cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 6,
                fontFamily: 'var(--font-mono, monospace)', fontWeight: 700,
              }}>
              ⚡ surprise · go
            </button>
          )}
          {/* v82hc : ★ favori dans bibliothèque */}
          <FavoriteButton
            prompt={D.prompt}
            module="drawing"
            tags={['drawing']}
            disabled={D.rendering}
          />
          </div>
          {/* v82gs : prompt history persistant cliquable */}
          {D.history.length > 0 && (
            <div style={{ marginTop: 8, paddingTop: 8,
              borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.08))' }}>
              <div style={{
                fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.22em', textTransform: 'uppercase',
                color: 'var(--fg-mute, #888)', marginBottom: 4,
              }}>↻ Historique ({D.history.length})</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2,
                maxHeight: 120, overflowY: 'auto' }}>
                {D.history.map((h) => {
                  const hasThumb = typeof h.meta?.renderBlobId === 'string'
                  return (
                  <div key={h.prompt} style={{
                    display: 'grid', gridTemplateColumns: hasThumb ? '42px 1fr 22px' : '1fr 22px', gap: 6,
                    alignItems: 'center', padding: '3px 6px', borderRadius: 4,
                    fontSize: 11,
                    background: 'var(--bg-card, rgba(255,255,255,0.03))',
                    border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
                  }}>
                    {hasThumb && <HistoryThumb entry={h} onClick={() => D.recallPrompt(h)} />}
                    <button type="button" onClick={() => D.recallPrompt(h)} title={h.prompt}
                      style={{
                        background: 'transparent', border: 'none', padding: 0,
                        color: 'var(--fg, #f5f5f5)', cursor: 'pointer', textAlign: 'left',
                        fontFamily: 'inherit', fontSize: 'inherit',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>{h.prompt}</button>
                    <button type="button" onClick={() => D.removeHistory(h.prompt)}
                      title="Retirer de l'historique"
                      style={{
                        width: 22, height: 22, background: 'transparent',
                        border: '1px solid var(--line, rgba(255,255,255,0.12))',
                        borderRadius: 3, cursor: 'pointer',
                        color: 'var(--fg-mute, #888)', fontSize: 11, padding: 0,
                      }}>×</button>
                  </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
        {D.error && (
          <div style={{
            padding: '8px 20px', background: '#fee2e2', color: '#991b1b',
            borderTop: '1px solid #fca5a5', fontSize: 12,
          }}>⚠ {D.error}</div>
        )}
      </div>

      {/* Idle portrait when canvas empty AND no render */}
      {!D.renderUrl && !D.rendering && (
        <div style={{
          position: 'absolute', bottom: 80, right: 60, width: 120,
          opacity: 0.5, pointerEvents: 'none',
        }}>
          <img src={PORTRAITS[D.who]} alt={D.who} style={{ width: '100%', filter: 'sepia(0.3)' }} />
        </div>
      )}
    </div>
  )
}
