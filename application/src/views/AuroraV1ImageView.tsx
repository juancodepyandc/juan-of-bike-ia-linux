/**
 * AuroraV1ImageView — Editorial Computing port for the Image module.
 *
 * Visual chrome from _design/aurora_design_screens_v1/modules.jsx
 * (ImageScreen): style wheel left, canvas grid centre, prompt + settings
 * panel right. Real wiring through useImageViewLogic so every Manga
 * feature is preserved 1:1: prompt + neg prompt, style picker, seed,
 * batch (×1..×4), aspect ratio, IP-Adapter reference + denoise slider,
 * Aurora-Connect grounding fallback, gallery + IDB persistence,
 * pending prompt resume banner, inpaint modal, upscale 2×/4×, download.
 */
import { lazy, Suspense, useState, useEffect } from 'react'
import { Brush, Download, Loader2, Maximize, Sparkles, StopCircle, X } from 'lucide-react'
import AuroraSphereV1 from '../components/AuroraSphereV1.tsx'
import { useImageViewLogic, DIMENSIONS, type DimensionId } from '../hooks/useImageViewLogic.ts'
import { useFileDrop } from '../hooks/useFileDrop.ts'
import { getDailyTip } from '../utils/dailyTip.ts'
import FavoriteButton from '../components/FavoriteButton.tsx'
import VoicePushToTalk from '../components/VoicePushToTalk.tsx'
import SessionSwitcher from '../components/SessionSwitcher.tsx'

const InpaintingPanel = lazy(() => import('../components/InpaintingPanel'))

const PINK = 'oklch(0.70 0.14 320)'

function Eyebrow({ children, dot, style }: { children: React.ReactNode; dot?: string; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono, ui-monospace, monospace)', fontSize: 11,
      letterSpacing: '0.14em', textTransform: 'uppercase',
      color: 'var(--fg-mute, #888)', display: 'flex', alignItems: 'center', gap: 8,
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

function Tag({ children, accent }: { children: React.ReactNode; accent?: string }) {
  return (
    <span style={{
      fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
      letterSpacing: '0.08em', textTransform: 'uppercase',
      color: accent ?? 'var(--fg-dim, #aaa)',
      padding: '3px 9px',
      border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
      borderRadius: 999,
      background: 'var(--bg-card, rgba(255,255,255,0.03))',
    }}>{children}</span>
  )
}

function Panel({ children, raised, padded = true, style }: {
  children: React.ReactNode; raised?: boolean; padded?: boolean; style?: React.CSSProperties
}) {
  return (
    <div style={{
      background: raised ? 'var(--bg-raised, rgba(255,255,255,0.04))' : 'var(--bg-card, rgba(255,255,255,0.02))',
      border: '1px solid var(--line, rgba(255,255,255,0.12))',
      borderRadius: 'var(--r-md, 12px)',
      padding: padded ? 16 : 0,
      ...style,
    }}>{children}</div>
  )
}

function Btn({ size = 'md', variant = 'ghost', children, onClick, disabled, style, title }: {
  size?: 'sm' | 'md'; variant?: 'primary' | 'ghost' | 'danger'
  children: React.ReactNode; onClick?: () => void; disabled?: boolean
  style?: React.CSSProperties; title?: string
}) {
  const fg = variant === 'primary' ? 'var(--ink-1000, #0a0a0a)'
    : variant === 'danger' ? '#ff6a3d' : 'var(--fg, #f5f5f5)'
  const bg = variant === 'primary' ? PINK : 'var(--bg-card, rgba(255,255,255,0.04))'
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
      style={{
        fontFamily: 'var(--font-sans, system-ui)',
        fontSize: size === 'sm' ? 12 : 13,
        padding: size === 'sm' ? '6px 12px' : '9px 16px',
        background: bg, color: fg,
        border: '1px solid var(--line, rgba(255,255,255,0.12))',
        borderRadius: 'var(--r-md, 10px)', cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        display: 'inline-flex', alignItems: 'center', gap: 6, justifyContent: 'center',
        ...style,
      }}>{children}</button>
  )
}

function compactMessage(text: string, max = 130) {
  const clean = text.replace(/\[image:[^\]]+\]/gi, '[image]').replace(/\[id:[^\]]+\]/gi, '').replace(/\s+/g, ' ').trim()
  return clean.length > max ? `${clean.slice(0, max - 1)}...` : clean
}

export default function AuroraV1ImageView() {
  const I = useImageViewLogic()
  // v82hw : right-click context menu sur les thumbs gallery.
  const [thumbMenu, setThumbMenu] = useState<{ id: string; x: number; y: number } | null>(null)
  useEffect(() => {
    if (!thumbMenu) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null
      if (t && t.closest('[data-thumb-menu]')) return
      setThumbMenu(null)
    }
    window.addEventListener('mousedown', onDoc)
    return () => window.removeEventListener('mousedown', onDoc)
  }, [thumbMenu])
  const dim = DIMENSIONS[I.dimensions]
  // v82fn : drop zone Image view → upload référence IP-Adapter direct.
  const drop = useFileDrop({
    onFile: (file) => void I.uploadReferenceFile(file),
    accept: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif'],
    acceptMime: ['image/'],
    disabled: I.generating || I.refUploading,
  })

  return (
    <div {...drop.bind} style={{
      position: 'relative', height: '100%', padding: '32px 40px',
      display: 'flex', flexDirection: 'column', gap: 18,
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)', overflow: 'hidden',
      outline: drop.isDraggingOver ? '2px dashed oklch(0.74 0.13 60)' : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      transition: 'outline 120ms ease',
    }}>
      {/* v82fn : hint visuel pendant drag-over */}
      {drop.isDraggingOver && (
        <div style={{
          position: 'absolute', top: 14, left: '50%', transform: 'translateX(-50%)',
          zIndex: 100, pointerEvents: 'none',
          padding: '8px 16px', borderRadius: 99,
          background: 'oklch(0.74 0.13 60 / 0.95)',
          color: 'var(--bg, #0c0a09)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase',
          boxShadow: '0 6px 24px rgba(0,0,0,0.4)',
        }}>
          🖼 Déposer image · référence d'édition
        </div>
      )}
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, flexWrap: 'wrap' }}>
        <Eyebrow dot={PINK}>Image · FLUX dev</Eyebrow>
        <span style={{ flex: 1 }} />
        <Tag accent={PINK}>FLUX.2 (GGUF)</Tag>
        <Tag>{dim.w}×{dim.h} · 28 steps</Tag>
        <Tag>seed {I.seed || 'random'}</Tag>
        {I.generating && <Tag accent="#ff6a3d">live</Tag>}
        {/* v82i9 : streak créativité quotidienne */}
        {I.imageStreak.current > 0 && (
          <Tag accent={I.imageStreak.current >= 7 ? 'oklch(0.78 0.16 80)' : undefined}>
            <span title={`Streak créativité : ${I.imageStreak.current} jour${I.imageStreak.current > 1 ? 's' : ''} consécutif${I.imageStreak.current > 1 ? 's' : ''}\nRecord all-time : ${I.imageStreak.longest} jour${I.imageStreak.longest > 1 ? 's' : ''}${I.imageStreak.current === I.imageStreak.longest ? ' · 🏆 actuel = record' : ''}`}>
              🔥 {I.imageStreak.current}j{I.imageStreak.longest > I.imageStreak.current ? ` / ${I.imageStreak.longest}j` : I.imageStreak.current >= 7 ? ' 🏆' : ''}
            </span>
          </Tag>
        )}
      </div>

      {I.resumeBanner && (
        <div style={{
          padding: '0.6rem 0.9rem', borderRadius: 12,
          border: '1px solid rgba(251, 191, 36, 0.4)',
          background: 'rgba(251, 191, 36, 0.1)', color: '#fef3c7', fontSize: 12,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 2 }}>⏳ Reprise d'une image en cours</div>
          <div style={{ opacity: 0.85, lineHeight: 1.4 }}>
            Le PC finit une image démarrée il y a {I.resumeBanner.minutes} min
            {I.resumeBanner.text ? ` (« ${I.resumeBanner.text.slice(0, 60)}${I.resumeBanner.text.length > 60 ? '…' : ''} »)` : ''}.
          </div>
        </div>
      )}

      {/* Three-column grid (→ 1 colonne empilée sur mobile via .aurora-v1-cols) */}
      <div className="aurora-v1-cols" style={{
        display: 'grid', gridTemplateColumns: '1fr 1.6fr 320px', gap: 20,
        flex: 1, minHeight: 0,
      }}>
        {/* Style wheel */}
        <Panel padded={false} style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))' }}>
            <Eyebrow>Style wheel</Eyebrow>
          </div>
          <div style={{ position: 'relative', height: 'calc(100% - 50px)' }}>
            <div style={{
              position: 'absolute', top: '50%', left: '50%',
              transform: 'translate(-50%,-50%)',
              width: 140, height: 140,
              filter: `drop-shadow(0 0 60px ${PINK}55)`,
              pointerEvents: 'none',
            }}>
              <AuroraSphereV1
                tint={PINK}
                state={I.generating ? 'streaming' : 'idle'}
                radius={0.42}
                glow={1.2}
              />
              <div style={{
                position: 'absolute', inset: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-mono, monospace)', textAlign: 'center',
              }}>
                <div>
                  <div style={{ fontSize: 9, letterSpacing: '0.2em', color: 'rgba(255,255,255,0.85)' }}>STYLE</div>
                  <div style={{
                    fontSize: 12, fontWeight: 700, color: '#fff',
                    textTransform: 'uppercase', textShadow: '0 1px 6px rgba(0,0,0,0.6)',
                  }}>
                    {I.styles.find((s) => s.id === I.style)?.label.split(/\s|\//)[0] ?? I.style}
                  </div>
                </div>
              </div>
            </div>
            {I.styles.map((s, i) => {
              const angle = (i / I.styles.length) * 360
              const rad = angle * Math.PI / 180
              const radius = 130
              const x = Math.cos(rad - Math.PI / 2) * radius
              const y = Math.sin(rad - Math.PI / 2) * radius
              const isActive = s.id === I.style
              return (
                <button key={s.id} type="button" onClick={() => I.setStyle(s.id)}
                  title={s.label}
                  style={{
                    position: 'absolute', left: '50%', top: '50%',
                    transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
                    background: 'transparent', border: 'none', cursor: 'pointer',
                    padding: 4, whiteSpace: 'nowrap',
                    fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
                    fontStyle: 'italic',
                    fontSize: isActive ? 18 : 12,
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? PINK : 'var(--fg-dim, #aaa)',
                    letterSpacing: '-0.01em',
                    textShadow: isActive ? `0 0 12px ${PINK}66` : undefined,
                    transition: 'all 200ms ease',
                  }}>
                  {s.label}
                </button>
              )
            })}
          </div>
        </Panel>

        {/* Canvas */}
        <Panel padded={false} style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{
            padding: '14px 18px', borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <Eyebrow>Canvas · {dim.w}×{dim.h}</Eyebrow>
            <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 10, color: 'var(--fg-dim, #aaa)' }}>
              {I.progress || (I.generating ? 'rendu…' : `${I.images.length} pièce${I.images.length > 1 ? 's' : ''}`)}
            </span>
          </div>
          <div style={{
            flex: 1, padding: 18, overflowY: 'auto',
            display: 'grid',
            gridTemplateColumns: I.current ? '1fr' : 'repeat(2, 1fr)',
            gridTemplateRows: I.current ? '1fr auto' : undefined,
            gap: 12,
          }}>
            {I.current ? (
              <>
                <div style={{ position: 'relative', borderRadius: 8, overflow: 'hidden', minHeight: 0 }}>
                  <img src={I.current.url} alt={I.current.prompt}
                    style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }} />
                  {/* v82i1 + v82i2 : badges metadata bottom-left (seed + style + ts) */}
                  <div style={{
                    position: 'absolute', bottom: 8, left: 8,
                    display: 'flex', gap: 4, flexWrap: 'wrap',
                  }}>
                    {I.current.seed !== null && I.current.seed !== undefined && (
                      <span style={{
                        padding: '3px 8px',
                        background: 'rgba(0,0,0,0.65)',
                        color: 'oklch(0.78 0.16 80)',
                        border: '1px solid oklch(0.78 0.16 80 / 0.35)',
                        borderRadius: 4,
                        fontFamily: 'var(--font-mono, monospace)',
                        fontSize: 10, fontVariantNumeric: 'tabular-nums',
                        letterSpacing: '0.05em',
                        backdropFilter: 'blur(2px)',
                        cursor: 'pointer',
                      }}
                      title="Clic = copie le seed au presse-papier"
                      onClick={async () => {
                        try { await navigator.clipboard.writeText(String(I.current?.seed)) } catch { /* noop */ }
                      }}>
                        seed: {I.current.seed}
                      </span>
                    )}
                    {/* v82i2 : badge style courant */}
                    {I.current.style && (
                      <span style={{
                        padding: '3px 8px',
                        background: 'rgba(0,0,0,0.65)',
                        color: 'oklch(0.74 0.13 60)',
                        border: '1px solid oklch(0.74 0.13 60 / 0.35)',
                        borderRadius: 4,
                        fontFamily: 'var(--font-mono, monospace)',
                        fontSize: 10, letterSpacing: '0.05em',
                        backdropFilter: 'blur(2px)',
                      }}
                      title={`Style FLUX : ${I.current.style}`}>
                        {I.current.style}
                      </span>
                    )}
                    {/* v82i2 : badge timestamp HH:mm */}
                    {I.current.timestamp && (
                      <span style={{
                        padding: '3px 8px',
                        background: 'rgba(0,0,0,0.65)',
                        color: 'rgba(255,255,255,0.7)',
                        border: '1px solid rgba(255,255,255,0.18)',
                        borderRadius: 4,
                        fontFamily: 'var(--font-mono, monospace)',
                        fontSize: 10, fontVariantNumeric: 'tabular-nums',
                        letterSpacing: '0.05em',
                        backdropFilter: 'blur(2px)',
                      }}
                      title={new Date(I.current.timestamp).toLocaleString('fr-FR')}>
                        {new Date(I.current.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    )}
                  </div>
                  {!I.generating && (
                    <div style={{
                      position: 'absolute', top: 8, right: 8,
                      display: 'flex', gap: 6, flexWrap: 'wrap',
                    }}>
                      <Btn size="sm" onClick={I.downloadCurrent} title="Télécharger PNG">
                        <Download size={12} /> PNG
                      </Btn>
                      <Btn size="sm" onClick={() => I.setInpaintOpen(true)} title="Retouche LaMa">
                        <Brush size={12} /> Retouche
                      </Btn>
                      <Btn size="sm" disabled={I.upscaling}
                        onClick={() => void I.upscaleCurrent(2)} title="Upscale 2×">
                        {I.upscaling ? <Loader2 size={12} /> : <Maximize size={12} />} 2×
                      </Btn>
                      <Btn size="sm" disabled={I.upscaling}
                        onClick={() => void I.upscaleCurrent(4)} title="Upscale 4×">
                        4×
                      </Btn>
                    </div>
                  )}
                </div>
                {I.images.length > 1 && (
                  <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
                    {I.images.map((img) => (
                      <button key={img.id} type="button"
                        onClick={() => I.setCurrent(img)}
                        onContextMenu={(e) => {
                          e.preventDefault()
                          setThumbMenu({ id: img.id, x: e.clientX, y: e.clientY })
                        }}
                        title={`${img.prompt}${img.seed != null ? `\nseed: ${img.seed}` : ''}\nClic-droit = menu`}
                        style={{
                          position: 'relative',
                          flexShrink: 0, width: 60, height: 60, padding: 2,
                          background: img.id === I.current?.id ? PINK : 'var(--bg-card, rgba(255,255,255,0.04))',
                          border: '1px solid var(--line, rgba(255,255,255,0.12))',
                          borderRadius: 6, cursor: 'pointer',
                        }}>
                        <img src={img.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 4 }} />
                        {/* v82i4 : mini badge style (top-left) + index numérique */}
                        <span style={{
                          position: 'absolute', top: 3, left: 3,
                          padding: '0 3px', fontSize: 8,
                          background: 'rgba(0,0,0,0.7)',
                          color: 'oklch(0.74 0.13 60)',
                          fontFamily: 'var(--font-mono, monospace)',
                          letterSpacing: '0.04em',
                          borderRadius: 2,
                          backdropFilter: 'blur(2px)',
                        }}>
                          {img.style.slice(0, 3)}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                {/* v82hw : context menu thumb */}
                {thumbMenu && (() => {
                  const img = I.images.find((m) => m.id === thumbMenu.id)
                  if (!img) return null
                  const close = () => setThumbMenu(null)
                  return (
                    <div data-thumb-menu style={{
                      position: 'fixed', top: thumbMenu.y, left: thumbMenu.x, zIndex: 90,
                      background: 'var(--bg-raised, oklch(0.13 0.013 250))',
                      border: '1px solid var(--line, rgba(255,255,255,0.18))',
                      borderRadius: 6, padding: 4,
                      boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                      display: 'flex', flexDirection: 'column', gap: 2,
                      minWidth: 180, fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                    }}>
                      <button type="button" onClick={() => { I.setPrompt(img.prompt); close() }}
                        style={thumbMenuBtn}>
                        Reprendre le prompt
                      </button>
                      <button type="button" onClick={() => { I.setCurrent(img); close() }}
                        style={thumbMenuBtn}>
                        ⌖ Voir en grand
                      </button>
                      <button type="button" onClick={async () => {
                        try {
                          await navigator.clipboard.writeText(img.prompt)
                        } catch { /* noop */ }
                        close()
                      }} style={thumbMenuBtn}>
                        ⎘ Copier le prompt
                      </button>
                      <button type="button" onClick={async () => {
                        const { downloadImageUniversal } = await import('../utils/imageDownload')
                        await downloadImageUniversal(img, { filename: `aurora-image-${img.id}.png` })
                        close()
                      }} style={thumbMenuBtn}>
                        💾 Télécharger PNG
                      </button>
                      {/* v82hx : utilise cette image comme référence IP-Adapter
                          pour la prochaine génération */}
                      <button type="button" onClick={async () => {
                        try {
                          const res = await fetch(img.url)
                          const blob = await res.blob()
                          const file = new File([blob], `aurora-ref-${img.id}.png`,
                            { type: blob.type || 'image/png' })
                          await I.uploadReferenceFile(file)
                        } catch (err) {
                          window.alert('Échec upload référence : ' + (err as Error).message)
                        }
                        close()
                      }} style={thumbMenuBtn}>
                        🎯 Comme référence d'édition
                      </button>
                      {/* v82hz : variation seed +1 sur la même base */}
                      {img.seed !== null && img.seed !== undefined && (
                        <>
                          <button type="button" onClick={() => {
                            I.setPrompt(img.prompt)
                            I.setStyle(img.style)
                            I.setSeed(String(img.seed))
                            close()
                          }} style={thumbMenuBtn}
                            title={`Reproduit exactement avec seed ${img.seed} (résultat identique sur même modèle)`}>
                            ⟲ Re-générer (seed exact {img.seed})
                          </button>
                          <button type="button" onClick={() => {
                            I.setPrompt(img.prompt)
                            I.setStyle(img.style)
                            I.setSeed(String((img.seed ?? 0) + 1))
                            close()
                          }} style={thumbMenuBtn}
                            title={`Génère avec prompt+style identiques mais seed ${(img.seed ?? 0) + 1} (variation proche)`}>
                            🎲 Variation seed +1 ({img.seed})
                          </button>
                        </>
                      )}
                    </div>
                  )
                })()}
              </>
            ) : I.generating ? (
              <div style={{
                gridColumn: 'span 2',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'var(--fg-dim, #aaa)', flexDirection: 'column', gap: 12, padding: 40,
              }}>
                <Loader2 size={32} style={{ animation: 'spin 1s linear infinite' }} />
                <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
                <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 12 }}>{I.progress || 'rendu…'}</span>
              </div>
            ) : (
              <div style={{
                gridColumn: 'span 2', textAlign: 'center', padding: 60,
                color: 'var(--fg-mute, #777)', fontStyle: 'italic',
                fontFamily: 'var(--font-display, serif)', fontSize: 24,
              }}>
                Décris ta scène, choisis un style, invoque.
                {/* v82ft : daily tip rotatif Image */}
                <div style={{
                  marginTop: 16, padding: '6px 12px',
                  fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                  color: 'var(--fg-dim, #aaa)', fontStyle: 'normal',
                  background: 'oklch(0.74 0.13 60 / 0.06)',
                  border: '1px solid oklch(0.74 0.13 60 / 0.22)',
                  borderRadius: 8, display: 'inline-block',
                  maxWidth: 480, lineHeight: 1.55,
                }}>
                  {getDailyTip('image')}
                </div>
              </div>
            )}
          </div>
        </Panel>

        {/* Prompt + settings */}
        <Panel raised>
          <div style={{ marginBottom: 12 }}>
            <SessionSwitcher module="image" onSessionChange={I.onImageSessionChange} />
            {I.recentImageMessages.length > 0 && (
              <div style={{
                marginTop: 8,
                padding: '7px 8px',
                border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
                borderRadius: 8,
                background: 'var(--bg-card, rgba(255,255,255,0.035))',
                fontFamily: 'var(--font-mono, monospace)',
                fontSize: 10,
                color: 'var(--fg-dim, #aaa)',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  letterSpacing: '0.14em',
                  textTransform: 'uppercase',
                  color: 'var(--fg-mute, #888)',
                }}>
                  <span>continuite</span>
                  <span>{I.activeImageSession.messages.length} msg</span>
                </div>
                {I.recentImageMessages.slice(-4).map((message) => (
                  <div key={`${message.timestamp}-${message.role}`} style={{
                    display: 'grid',
                    gridTemplateColumns: '62px 1fr',
                    gap: 6,
                    alignItems: 'baseline',
                  }}>
                    <span style={{ color: message.role === 'user' ? PINK : 'oklch(0.75 0.12 150)' }}>
                      {message.role === 'user' ? 'toi' : 'image'}
                    </span>
                    <span style={{
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      color: 'var(--fg, #f5f5f5)',
                    }}>{compactMessage(message.content)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <Eyebrow>Prompt</Eyebrow>
            <VoicePushToTalk
              onTranscript={(text) => I.setPrompt((I.prompt ? I.prompt + ' ' : '') + text)}
              label="Dicter le prompt image"
              disabled={I.generating}
              variant="ghost"
              size={28}
            />
          </div>
          <textarea
            value={I.prompt} onChange={(e) => I.setPrompt(e.target.value)}
            onKeyDown={(e) => { if (!I.generating && (e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); void I.queuePrompt() } }}
            disabled={I.generating}
            placeholder={I.who === 'natsu'
              ? "Ex: vélo gravel orange, atelier, étincelles, ciel orageux…"
              : "Ex: portrait stellaire, nuit étoilée, porte dorée…"}
            rows={3}
            style={{
              width: '100%', resize: 'vertical', padding: 10,
              background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              borderRadius: 8, fontSize: 13, lineHeight: 1.5,
              fontFamily: 'var(--font-sans, system-ui)',
            }} />
          {/* v82bk + v82bm : live-preview du parser. Affiche les
              mots-clés détectés + edit-intent + denoise effective. */}
          {(I.previewIntent.removals.length > 0
            || I.previewIntent.isEditIntent
            || I.effectiveDenoise !== null
            || I.styleOverrideReason) && (
            <div style={{
              marginTop: 6, padding: '6px 10px',
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
              borderRadius: 6, fontSize: 11,
              fontFamily: 'var(--font-mono, monospace)',
              color: 'var(--fg-dim, #aaa)',
              display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap',
            }}>
              {I.previewIntent.removals.length > 0 && (
                <>
                  <span style={{ color: 'var(--fg-mute, #777)' }}>− retirer :</span>
                  {I.previewIntent.removals.map((r, i) => (
                    <span key={i} style={{
                      padding: '1px 6px', borderRadius: 99,
                      background: 'oklch(0.55 0.18 25 / 0.15)',
                      color: 'oklch(0.72 0.14 25)',
                    }}>{r}</span>
                  ))}
                </>
              )}
              {I.previewIntent.isEditIntent && (
                <span style={{
                  padding: '1px 6px', borderRadius: 99,
                  background: `${PINK}22`, color: PINK,
                }}>{I.previewIntent.editContract.label}</span>
              )}
              {I.previewIntent.isEditIntent && (
                <span style={{
                  padding: '1px 6px', borderRadius: 99,
                  background: I.editEngine === 'kontext'
                    ? 'oklch(0.6 0.15 150 / 0.18)'
                    : 'oklch(0.6 0.12 80 / 0.18)',
                  color: I.editEngine === 'kontext'
                    ? 'oklch(0.75 0.14 150)'
                    : 'oklch(0.78 0.12 80)',
                }}>{I.editEngine === 'kontext' ? 'Kontext · édition réelle' : 'img2img · approximatif'}</span>
              )}
              {I.effectiveDenoise !== null && I.editEngine !== 'kontext' && (
                <span style={{
                  padding: '1px 6px', borderRadius: 99,
                  background: 'var(--bg-input, rgba(255,255,255,0.06))',
                  color: 'var(--fg-dim, #aaa)',
                  marginLeft: 'auto',
                }}>denoise {I.effectiveDenoise.toFixed(2)}</span>
              )}
              {I.styleOverrideReason && (
                <span title={I.styleOverrideReason} style={{
                  padding: '1px 6px', borderRadius: 99,
                  background: 'oklch(0.64 0.12 210 / 0.18)',
                  color: 'oklch(0.80 0.11 210)',
                }}>style photo preserve</span>
              )}
            </div>
          )}
          <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={() => I.setShowNeg(!I.showNeg)}
              style={{
                fontSize: 10, padding: '3px 8px',
                background: I.showNeg ? PINK : 'transparent', color: I.showNeg ? '#000' : 'var(--fg-dim, #aaa)',
                border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 6, cursor: 'pointer',
              }}>{I.showNeg ? '− neg' : '+ neg'}{I.negPrompt.trim() ? ' •' : ''}</button>
          </div>
          {I.showNeg && (
            <textarea
              value={I.negPrompt} onChange={(e) => I.setNegPrompt(e.target.value)}
              disabled={I.generating}
              placeholder="Ex: blurry, low quality, watermark, extra fingers, text"
              rows={2}
              style={{
                width: '100%', marginTop: 6, padding: 8, fontSize: 12,
                background: 'var(--bg, #0c0a09)', color: 'var(--fg-dim, #aaa)',
                border: '1px dashed var(--line, rgba(255,255,255,0.12))',
                borderRadius: 6, resize: 'vertical',
                fontFamily: 'var(--font-mono, monospace)',
              }} />
          )}

          {I.error && (
            <div style={{
              marginTop: 8, padding: 8, fontSize: 11,
              background: 'rgba(255,106,61,0.1)', color: '#ff6a3d',
              border: '1px solid rgba(255,106,61,0.3)', borderRadius: 6,
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <X size={12} /> {I.error}
            </div>
          )}
          {/* v86 : conseil non bloquant (ex : personnage nommé inconnu du modèle
              → joins une référence). Distinct de l'erreur, fermable. */}
          {I.notice && (
            <div style={{
              marginTop: 8, padding: 8, fontSize: 11, lineHeight: 1.5,
              background: 'oklch(0.74 0.13 80 / 0.10)', color: 'oklch(0.82 0.12 80)',
              border: '1px solid oklch(0.74 0.13 80 / 0.35)', borderRadius: 6,
              display: 'flex', alignItems: 'flex-start', gap: 6,
            }}>
              <span style={{ flex: 1 }}>💡 {I.notice}</span>
              <button type="button" onClick={() => I.setNotice(null)} title="Fermer"
                style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0, fontSize: 13 }}>×</button>
            </div>
          )}

          <div style={{ borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.06))', margin: '14px 0' }} />

          <Eyebrow style={{ marginBottom: 8 }}>Réglages</Eyebrow>

          {/* Seed */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11, color: 'var(--fg-dim, #aaa)', width: 60 }}>🎲 seed</span>
            <input type="text" inputMode="numeric" pattern="[0-9]*"
              value={I.seed} onChange={(e) => I.setSeed(e.target.value.replace(/[^0-9]/g, '').slice(0, 10))}
              placeholder="random" disabled={I.generating}
              style={{
                flex: 1, padding: '4px 8px', fontSize: 12,
                background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
                border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 6,
                fontFamily: 'var(--font-mono, monospace)',
              }} />
            {I.seed && !I.generating && (
              <button type="button" onClick={() => I.setSeed('')} title="Random"
                style={{
                  padding: '2px 6px', fontSize: 10, color: 'var(--fg-mute, #777)',
                  background: 'transparent', border: 'none', cursor: 'pointer',
                }}>✕</button>
            )}
          </div>

          {/* Batch */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11, color: 'var(--fg-dim, #aaa)', width: 60 }}>🖼 batch</span>
            <div style={{ display: 'flex', gap: 4, flex: 1 }}>
              {[1, 2, 3, 4].map((n) => (
                <button key={n} type="button" onClick={() => I.setBatch(n as 1|2|3|4)}
                  disabled={I.generating}
                  style={{
                    flex: 1, padding: '4px 0', fontSize: 11,
                    background: I.batch === n ? PINK : 'var(--bg-card, rgba(255,255,255,0.04))',
                    color: I.batch === n ? '#000' : 'var(--fg, #f5f5f5)',
                    border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 6,
                    cursor: I.generating ? 'not-allowed' : 'pointer',
                    fontFamily: 'var(--font-mono, monospace)',
                  }}>×{n}</button>
              ))}
            </div>
          </div>

          {/* Ratio */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11, color: 'var(--fg-dim, #aaa)', width: 60 }}>📐 ratio</span>
            <div style={{ display: 'flex', gap: 4, flex: 1 }}>
              {(['square', 'portrait', 'landscape'] as DimensionId[]).map((d) => (
                <button key={d} type="button" onClick={() => I.setDimensions(d)}
                  disabled={I.generating} title={`${DIMENSIONS[d].w}×${DIMENSIONS[d].h}`}
                  style={{
                    flex: 1, padding: '4px 0', fontSize: 11,
                    background: I.dimensions === d ? PINK : 'var(--bg-card, rgba(255,255,255,0.04))',
                    color: I.dimensions === d ? '#000' : 'var(--fg, #f5f5f5)',
                    border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 6,
                    cursor: I.generating ? 'not-allowed' : 'pointer',
                    fontFamily: 'var(--font-mono, monospace)',
                  }}>{DIMENSIONS[d].label}</button>
              ))}
            </div>
          </div>

          {/* Reference */}
          <div style={{ marginTop: 8 }}>
            {I.refPreview ? (
              <div style={{
                display: 'flex', gap: 8, alignItems: 'center', padding: 6,
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 6,
              }}>
                <img src={I.refPreview} alt="référence" style={{ width: 38, height: 38, objectFit: 'cover', borderRadius: 4 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 10, color: 'var(--fg-dim, #aaa)', fontFamily: 'var(--font-mono, monospace)' }}>
                    Réf · denoise {I.refDenoise.toFixed(2)}
                  </div>
                  <input type="range" min={0.3} max={0.95} step={0.05}
                    value={I.refDenoise} onChange={(e) => I.setRefDenoise(Number(e.target.value))}
                    disabled={I.generating}
                    style={{ width: '100%' }} />
                </div>
                <button type="button" onClick={I.clearReference} disabled={I.generating}
                  style={{ background: 'transparent', border: 'none', color: 'var(--fg-mute, #777)', cursor: 'pointer' }}>✕</button>
              </div>
            ) : (
              <label style={{
                display: 'block', padding: 8, fontSize: 11, textAlign: 'center',
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                border: '1px dashed var(--line, rgba(255,255,255,0.12))',
                borderRadius: 6, cursor: 'pointer',
                color: 'var(--fg-dim, #aaa)', fontFamily: 'var(--font-mono, monospace)',
              }}>
                <input type="file" accept="image/*" onChange={I.onUploadReference}
                  disabled={I.generating || I.refUploading} style={{ display: 'none' }} />
                {I.refUploading ? '⏳ Upload…' : '📎 Référence / Édition'}
              </label>
            )}
          </div>

          {/* v87 : 2e image = SOURCE d'extraction. L'élément demandé (personne, objet,
              décor, pose) est extrait d'ici et injecté dans la Référence ci-dessus. */}
          <div style={{ marginTop: 6 }}>
            {I.refPreview2 ? (
              <div style={{
                display: 'flex', gap: 8, alignItems: 'center', padding: 6,
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 6,
              }}>
                <img src={I.refPreview2} alt="source à injecter" style={{ width: 38, height: 38, objectFit: 'cover', borderRadius: 4 }} />
                <div style={{ flex: 1, minWidth: 0, fontSize: 10, color: 'var(--fg-dim, #aaa)', fontFamily: 'var(--font-mono, monospace)' }}>
                  Source · l'élément demandé est extrait d'ici → injecté dans la Référence
                </div>
                <button type="button" onClick={I.clearSource} disabled={I.generating}
                  style={{ background: 'transparent', border: 'none', color: 'var(--fg-mute, #777)', cursor: 'pointer' }}>✕</button>
              </div>
            ) : (
              <label style={{
                display: 'block', padding: 8, fontSize: 11, textAlign: 'center',
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                border: '1px dashed var(--line, rgba(255,255,255,0.12))',
                borderRadius: 6, cursor: I.refPreview ? 'pointer' : 'not-allowed',
                opacity: I.refPreview ? 1 : 0.5,
                color: 'var(--fg-dim, #aaa)', fontFamily: 'var(--font-mono, monospace)',
              }} title={I.refPreview ? 'Image source : un élément en sera extrait et injecté dans la Référence' : 'Ajoute d\'abord une Référence (image de base)'}>
                <input type="file" accept="image/*" onChange={I.onUploadSource}
                  disabled={I.generating || I.refUploading2 || !I.refPreview} style={{ display: 'none' }} />
                {I.refUploading2 ? '⏳ Upload…' : '➕ Image source (extraire → injecter)'}
              </label>
            )}
          </div>

          {I.generating ? (
            <Btn variant="danger" onClick={I.onStop} style={{ width: '100%', marginTop: 16 }}>
              <StopCircle size={14} /> STOP
            </Btn>
          ) : (
            <Btn variant="primary" onClick={() => void I.queuePrompt()} disabled={!I.prompt.trim() || I.generating}
              style={{ width: '100%', marginTop: 16 }}>
              <Sparkles size={14} /> Générer · ⌘↵
            </Btn>
          )}
          {/* v82ex : preset surprise (random style + random prompt) */}
          {!I.generating && (
            <button type="button"
              onClick={() => {
                const preset = I.randomImagePreset()
                if (preset) void I.queuePrompt(preset)
              }}
              title="Pioche un style + prompt au hasard PUIS génère immédiatement"
              style={{
                width: '100%', marginTop: 8, padding: '6px 12px',
                background: 'oklch(0.74 0.13 60 / 0.10)',
                color: 'oklch(0.74 0.13 60)',
                border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                borderRadius: 6, fontSize: 11,
                fontFamily: 'var(--font-mono, monospace)', cursor: 'pointer',
                fontWeight: 700,
              }}>
              ⚡ surprise · go
            </button>
          )}
          {/* v82hb / v82hc : ★ favori via FavoriteButton réutilisable */}
          <FavoriteButton
            prompt={I.prompt}
            module="image"
            parameters={{ style: I.style }}
            tags={['image', I.style]}
            disabled={I.generating}
          />
          {/* v82gp : prompt history persistant cliquable pour recall */}
          {I.history.length > 0 && (
            <div style={{
              marginTop: 10,
              padding: '8px 4px',
              borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
            }}>
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.22em', textTransform: 'uppercase',
                color: 'var(--fg-mute, #888)',
                marginBottom: 6,
              }}>
                <span>↻ Historique ({I.history.length})</span>
              </div>
              <div style={{
                display: 'flex', flexDirection: 'column', gap: 3,
                maxHeight: 180, overflowY: 'auto',
              }}>
                {I.history.map((h) => (
                  <div key={h.prompt} style={{
                    display: 'grid', gridTemplateColumns: '1fr 22px',
                    gap: 4, alignItems: 'center',
                    padding: '4px 6px', borderRadius: 4,
                    fontSize: 11,
                    background: 'var(--bg-card, rgba(255,255,255,0.03))',
                    border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
                    transition: 'background .12s ease',
                  }}>
                    <button type="button"
                      onClick={() => I.recallPrompt(h)}
                      title={`${h.prompt}${h.meta?.style ? ` · ${h.meta.style}` : ''}\nClic = ouvrir la conversation et reprendre le prompt`}
                      style={{
                        background: 'transparent', border: 'none',
                        padding: 0, color: 'var(--fg, #f5f5f5)',
                        cursor: 'pointer', textAlign: 'left',
                        fontFamily: 'inherit', fontSize: 'inherit',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                      {h.prompt}
                    </button>
                    <button type="button"
                      onClick={() => I.removeHistory(h.prompt)}
                      title="Retirer de l'historique"
                      style={{
                        width: 22, height: 22,
                        background: 'transparent',
                        border: '1px solid var(--line, rgba(255,255,255,0.12))',
                        borderRadius: 3, cursor: 'pointer',
                        color: 'var(--fg-mute, #888)',
                        fontSize: 11, padding: 0,
                      }}>×</button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>
      </div>

      {/* Inpainting overlay */}
      {I.inpaintOpen && I.current && (
        <Suspense fallback={null}>
          <InpaintingPanel
            imageSrc={I.current.url}
            onClose={() => I.setInpaintOpen(false)}
            onApply={(newUrl) => void I.applyInpaint(newUrl)}
          />
        </Suspense>
      )}
    </div>
  )
}

const thumbMenuBtn: React.CSSProperties = {
  padding: '6px 10px', textAlign: 'left',
  background: 'transparent',
  border: '1px solid transparent',
  color: 'var(--fg, #f5f5f5)',
  cursor: 'pointer', borderRadius: 4,
  fontFamily: 'inherit', fontSize: 'inherit',
}
