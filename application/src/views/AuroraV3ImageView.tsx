/**
 * AuroraV3ImageView — Ricochet "tableau liège" port for the Image module.
 *
 * Visual chrome from _design/aurora_design_screens_v3/screens-2.jsx
 * (ImageV3): cork-board background, polaroids pinned with washi tape,
 * sharpie title, push-pin, dark prompt strip at bottom. Real wiring
 * via useImageViewLogic — every Manga feature preserved. Settings
 * (style picker, seed, batch, ratio, reference, inpaint, upscale,
 * download) live in a slide-out drawer triggered from the strip.
 */
import { lazy, Suspense, useState } from 'react'
import { useImageViewLogic, DIMENSIONS, type DimensionId } from '../hooks/useImageViewLogic.ts'
import { useFileDrop } from '../hooks/useFileDrop.ts'
import VoicePushToTalk from '../components/VoicePushToTalk.tsx'

const InpaintingPanel = lazy(() => import('../components/InpaintingPanel'))

const CORK = '#b8956b'
const PAPER = '#fbf6e8'
const SHARPIE = '#1a1410'

const TAPE_COLORS = [
  'rgba(232,167,167,0.85)',
  'rgba(167,200,232,0.85)',
  'rgba(220,232,167,0.85)',
]

function PinBtn({ onClick, active, danger, disabled, children, title }: {
  onClick?: () => void; active?: boolean; danger?: boolean; disabled?: boolean
  children: React.ReactNode; title?: string
}) {
  const bg = danger ? '#c44a3a' : active ? SHARPIE : PAPER
  const fg = danger || active ? PAPER : SHARPIE
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
      style={{
        background: bg, color: fg, border: `1px solid ${SHARPIE}`,
        padding: '6px 12px',
        fontFamily: 'Permanent Marker, Marker Felt, cursive',
        fontSize: 12, cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1, letterSpacing: '0.05em',
      }}>{children}</button>
  )
}

export default function AuroraV3ImageView() {
  const I = useImageViewLogic()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const dim = DIMENSIONS[I.dimensions]
  // v82eb : drag-drop parity V3 — image → IP-Adapter référence
  const drop = useFileDrop({
    onFile: (f) => void I.uploadReferenceFile(f),
    accept: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif'],
    acceptMime: ['image/'],
    disabled: I.generating || I.refUploading,
  })

  return (
    <div {...drop.bind} style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      background: CORK,
      outline: drop.isDraggingOver ? `2px dashed ${SHARPIE}` : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      backgroundImage: `radial-gradient(circle at 25% 30%, rgba(0,0,0,0.18) 0.5px, transparent 1px),
                        radial-gradient(circle at 75% 60%, rgba(255,255,255,0.1) 0.5px, transparent 1px),
                        radial-gradient(circle at 40% 80%, rgba(0,0,0,0.14) 0.5px, transparent 1px)`,
      backgroundSize: '7px 7px, 11px 11px, 9px 9px',
      fontFamily: 'Georgia, serif', color: SHARPIE,
    }}>
      {/* Sharpie label top */}
      <div style={{
        position: 'absolute', top: 24, left: 32, transform: 'rotate(-2deg)',
        fontFamily: 'Permanent Marker, Marker Felt, cursive', fontSize: 36,
        color: SHARPIE, textShadow: '0 1px 0 rgba(255,255,255,0.2)',
      }}>
        Aurora · Imago — planches d'essai
      </div>
      <div style={{
        position: 'absolute', top: 78, left: 36, fontStyle: 'italic',
        fontSize: 14, color: '#3a2a1a',
      }}>
        FLUX 1.dev · seed {I.seed || '0xRND'} · style {I.style} · {dim.w}×{dim.h}
        {I.previewIntent.isEditIntent && ` · ✂ ${I.previewIntent.editContract.label} — ${I.editEngine === 'kontext' ? 'Kontext (édition réelle)' : 'img2img (approximatif)'}`}
        {I.generating && ' · ✏ rendu en cours…'}
        {I.progress && ` · ${I.progress}`}
      </div>

      {/* Push pin top-right */}
      <div style={{
        position: 'absolute', top: 22, right: 40,
        width: 16, height: 16, borderRadius: '50%',
        background: 'radial-gradient(circle at 30% 30%, #ff9a8a, #c44a3a 60%, #6a1a14)',
        boxShadow: '0 3px 6px rgba(0,0,0,0.4)',
      }} />

      {/* Resume banner */}
      {I.resumeBanner && (
        <div style={{
          position: 'absolute', top: 110, left: 36, right: 36, padding: 12,
          background: PAPER, transform: 'rotate(-0.5deg)',
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          fontFamily: 'Permanent Marker, cursive', fontSize: 13,
          border: `1px solid ${SHARPIE}`, zIndex: 5,
        }}>
          ⏳ REPRISE EN COURS · IMAGE LANCÉE IL Y A {I.resumeBanner.minutes} MIN — ELLE APPARAÎTRA QUAND PRÊTE.
        </div>
      )}

      {/* Polaroids of generated images */}
      <div style={{
        position: 'absolute', inset: '140px 0 100px',
        overflowY: 'auto', overflowX: 'hidden', padding: '0 32px',
      }}>
        {I.images.length === 0 && !I.generating && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', flexDirection: 'column', gap: 8,
            transform: 'rotate(-1deg)',
          }}>
            <span style={{
              fontFamily: 'Permanent Marker, cursive', fontSize: 28,
              color: '#3a2a1a',
            }}>« la planche est vierge »</span>
            <span style={{ fontStyle: 'italic', fontSize: 14, color: '#5a4a3a' }}>
              décris ta prochaine prise dans le bandeau du bas
            </span>
          </div>
        )}
        {I.generating && I.images.length === 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', flexDirection: 'column', gap: 12,
          }}>
            <div style={{
              width: 40, height: 40, border: `4px solid ${SHARPIE}`,
              borderTopColor: 'transparent', borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }} />
            <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            <span style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 14 }}>
              {I.progress || 'rendu…'}
            </span>
          </div>
        )}
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: 24, padding: '20px 0',
          alignItems: 'flex-start',
        }}>
          {I.images.map((img, i) => {
            const isCurrent = img.id === I.current?.id
            return (
              <button key={img.id} type="button" onClick={() => I.setCurrent(img)}
                title={img.prompt}
                style={{
                  position: 'relative',
                  width: 220, padding: '10px 10px 38px',
                  background: PAPER,
                  boxShadow: isCurrent
                    ? '0 12px 30px rgba(0,0,0,0.5), 0 0 0 3px #c44a3a'
                    : '0 8px 22px rgba(0,0,0,0.35), 0 1px 0 rgba(0,0,0,0.1)',
                  transform: `rotate(${img.rotation}deg) ${isCurrent ? 'scale(1.04)' : ''}`,
                  border: '1px solid rgba(0,0,0,0.05)',
                  cursor: 'pointer',
                  transition: 'transform 200ms ease, box-shadow 200ms ease',
                }}>
                <div style={{
                  position: 'absolute', top: -14, left: '50%',
                  transform: 'translateX(-50%) rotate(2deg)',
                  width: 70, height: 26,
                  background: TAPE_COLORS[i % 3],
                  backgroundImage: 'repeating-linear-gradient(45deg, rgba(255,255,255,0.3) 0 4px, transparent 4px 8px)',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.15)',
                }} />
                <div style={{ aspectRatio: '1', overflow: 'hidden', background: SHARPIE }}>
                  <img src={img.url} alt={img.prompt}
                    style={{ width: '100%', height: '100%', objectFit: 'cover', filter: 'sepia(0.15) contrast(1.05)' }} />
                </div>
                <div style={{
                  position: 'absolute', bottom: 8, left: 14, right: 14,
                  fontFamily: 'Permanent Marker, Marker Felt, cursive',
                  fontSize: 11, color: SHARPIE, lineHeight: 1.2,
                  textAlign: 'left',
                  display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}>
                  {img.prompt.slice(0, 50)}{img.prompt.length > 50 ? '…' : ''}
                </div>
                <div style={{
                  position: 'absolute', bottom: 8, right: 14, fontSize: 9, color: '#8a6a4a',
                }}>
                  #{String(i + 1).padStart(2, '0')}
                </div>
              </button>
            )
          })}
          {I.generating && I.images.length > 0 && (
            <div style={{
              width: 220, padding: '10px 10px 38px', background: PAPER,
              boxShadow: '0 8px 22px rgba(0,0,0,0.35)',
              transform: 'rotate(-2deg)',
              border: `2px dashed ${SHARPIE}`,
            }}>
              <div style={{
                aspectRatio: '1', display: 'flex', alignItems: 'center',
                justifyContent: 'center', background: SHARPIE,
              }}>
                <div style={{
                  width: 30, height: 30, border: `3px solid ${PAPER}`,
                  borderTopColor: 'transparent', borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                }} />
              </div>
              <div style={{
                position: 'absolute', bottom: 8, left: 14, right: 14,
                fontFamily: 'Permanent Marker, cursive', fontSize: 11, color: SHARPIE,
              }}>{I.progress || 'tirage…'}</div>
            </div>
          )}
        </div>
      </div>

      {/* Current preview side panel — toolbar only when current */}
      {I.current && !I.generating && (
        <div style={{
          position: 'absolute', top: 100, right: 24,
          display: 'flex', flexDirection: 'column', gap: 6, zIndex: 4,
        }}>
          <PinBtn onClick={I.downloadCurrent} title="Télécharger PNG">⬇ PNG</PinBtn>
          <PinBtn onClick={() => I.setInpaintOpen(true)} title="Retouche LaMa">✎ RETOUCHE</PinBtn>
          <PinBtn onClick={() => void I.upscaleCurrent(2)} disabled={I.upscaling}>↗ 2×</PinBtn>
          <PinBtn onClick={() => void I.upscaleCurrent(4)} disabled={I.upscaling}>↗ 4×</PinBtn>
        </div>
      )}

      {I.error && (
        <div style={{
          position: 'absolute', top: 100, left: '50%', transform: 'translateX(-50%) rotate(-1deg)',
          background: '#c44a3a', color: PAPER, padding: '8px 16px',
          fontFamily: 'Permanent Marker, cursive', fontSize: 13,
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)', zIndex: 6,
        }}>
          ✕ {I.error}
        </div>
      )}

      {/* v86 : conseil non bloquant (personnage nommé inconnu → joins une réf). */}
      {I.notice && (
        <div style={{
          position: 'absolute', top: 100, left: '50%', transform: 'translateX(-50%) rotate(0.6deg)',
          maxWidth: 520, background: '#e8b94a', color: '#3a2c10', padding: '10px 16px',
          fontFamily: 'inherit', fontSize: 12, lineHeight: 1.5,
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)', zIndex: 7,
          display: 'flex', alignItems: 'flex-start', gap: 8,
        }}>
          <span style={{ flex: 1 }}>💡 {I.notice}</span>
          <button type="button" onClick={() => I.setNotice(null)} title="Fermer"
            style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0, fontSize: 15, fontWeight: 700 }}>×</button>
        </div>
      )}

      {/* Compose strip bottom */}
      <div style={{
        position: 'absolute', bottom: 24, left: 32, right: 32,
        background: SHARPIE, color: PAPER, padding: '14px 20px',
        display: 'flex', alignItems: 'center', gap: 16,
        transform: 'rotate(-0.5deg)', boxShadow: '0 6px 18px rgba(0,0,0,0.4)',
        flexWrap: 'wrap',
      }}>
        <span style={{ fontFamily: 'Permanent Marker, Marker Felt, cursive', fontSize: 16 }}>
          ✏ prompt :
        </span>
        <input type="text"
          value={I.prompt}
          onChange={(e) => I.setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (!I.generating && (e.metaKey || e.ctrlKey) && e.key === 'Enter') {
              e.preventDefault(); void I.queuePrompt()
            }
          }}
          disabled={I.generating}
          placeholder="« décris la prochaine prise… »"
          style={{
            flex: 1, minWidth: 200,
            background: 'transparent', color: PAPER,
            border: 'none', borderBottom: `1px dashed ${PAPER}`,
            outline: 'none', fontStyle: 'italic',
            fontSize: 14, padding: '4px 0',
            fontFamily: 'Georgia, serif',
          }} />
        <VoicePushToTalk
          onTranscript={(text) => I.setPrompt((I.prompt ? I.prompt + ' ' : '') + text)}
          label="Dicter le prompt image"
          disabled={I.generating}
          variant="ghost"
          size={32}
        />
        <button type="button" onClick={() => setDrawerOpen(true)}
          style={{
            background: 'transparent', color: PAPER,
            border: `1px solid ${PAPER}`, padding: '6px 12px',
            fontFamily: 'Permanent Marker, cursive', fontSize: 12,
            cursor: 'pointer',
          }}>⚙ RÉGLAGES</button>
        {I.generating ? (
          <button type="button" onClick={I.onStop}
            style={{
              background: '#c44a3a', color: PAPER, border: 'none',
              padding: '8px 18px',
              fontFamily: 'Permanent Marker, Marker Felt, cursive',
              fontSize: 14, cursor: 'pointer',
            }}>◼ STOP</button>
        ) : (
          <>
            <button type="button" onClick={() => void I.queuePrompt()} disabled={!I.prompt.trim() || I.generating}
              style={{
                background: PAPER, color: SHARPIE, border: 'none',
                padding: '8px 18px',
                fontFamily: 'Permanent Marker, Marker Felt, cursive',
                fontSize: 14, cursor: (!I.prompt.trim() || I.generating) ? 'not-allowed' : 'pointer',
                opacity: (!I.prompt.trim() || I.generating) ? 0.5 : 1,
              }}>TIRER ×{I.batch}</button>
            {/* v82fh : preset surprise (random style FLUX + prompt + auto-tirage) */}
            <button type="button"
              onClick={() => {
                const preset = I.randomImagePreset()
                if (preset) void I.queuePrompt(preset)
              }}
              title="Style + prompt aléatoires PUIS tirage immédiat"
              style={{
                background: 'transparent', color: PAPER,
                border: `1px solid ${PAPER}`,
                padding: '8px 14px', marginLeft: 8,
                fontFamily: 'Permanent Marker, Marker Felt, cursive',
                fontSize: 13, cursor: 'pointer',
              }}>⚡ SURPRISE</button>
          </>
        )}
      </div>

      {/* Settings drawer */}
      {drawerOpen && (
        <div style={{
          position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 100,
          display: 'flex', justifyContent: 'flex-end',
        }} onClick={() => setDrawerOpen(false)}>
          <div onClick={(e) => e.stopPropagation()}
            style={{
              width: 360, height: '100%', background: PAPER, color: SHARPIE,
              padding: 24, overflowY: 'auto', boxShadow: '-8px 0 24px rgba(0,0,0,0.4)',
              fontFamily: 'Georgia, serif',
            }}>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: 20,
            }}>
              <span style={{
                fontFamily: 'Permanent Marker, cursive', fontSize: 24,
                transform: 'rotate(-1deg)', display: 'inline-block',
              }}>⚙ RÉGLAGES</span>
              <button type="button" onClick={() => setDrawerOpen(false)}
                style={{
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  fontSize: 20, color: SHARPIE,
                }}>✕</button>
            </div>

            {/* Negative prompt */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <input type="checkbox" checked={I.showNeg} onChange={() => I.setShowNeg(!I.showNeg)} />
                <span style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 13 }}>
                  PROMPT NÉGATIF
                </span>
              </label>
              {I.showNeg && (
                <textarea
                  value={I.negPrompt} onChange={(e) => I.setNegPrompt(e.target.value)}
                  disabled={I.generating}
                  placeholder="blurry, low quality, watermark, extra fingers"
                  rows={2}
                  style={{
                    width: '100%', padding: 8, fontSize: 12, fontStyle: 'italic',
                    background: 'transparent', color: SHARPIE,
                    border: `1px dashed ${SHARPIE}`, resize: 'vertical',
                    fontFamily: 'Georgia, serif',
                  }} />
              )}
            </div>

            {/* Style picker */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 13, marginBottom: 6 }}>STYLE</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {I.styles.map((s) => (
                  <button key={s.id} type="button" onClick={() => I.setStyle(s.id)}
                    style={{
                      padding: '4px 10px', fontSize: 11,
                      background: s.id === I.style ? SHARPIE : 'transparent',
                      color: s.id === I.style ? PAPER : SHARPIE,
                      border: `1px solid ${SHARPIE}`,
                      cursor: 'pointer',
                      fontFamily: 'Permanent Marker, cursive',
                      letterSpacing: '0.05em',
                    }}>{s.label}</button>
                ))}
              </div>
            </div>

            {/* Seed */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 13, marginBottom: 6 }}>🎲 SEED</div>
              <input type="text" inputMode="numeric" pattern="[0-9]*"
                value={I.seed} onChange={(e) => I.setSeed(e.target.value.replace(/[^0-9]/g, '').slice(0, 10))}
                placeholder="random" disabled={I.generating}
                style={{
                  width: '100%', padding: 6, fontSize: 13,
                  background: 'transparent', color: SHARPIE,
                  border: `1px solid ${SHARPIE}`,
                  fontFamily: 'monospace',
                }} />
            </div>

            {/* Batch */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 13, marginBottom: 6 }}>🖼 BATCH</div>
              <div style={{ display: 'flex', gap: 4 }}>
                {[1, 2, 3, 4].map((n) => (
                  <button key={n} type="button" onClick={() => I.setBatch(n as 1|2|3|4)}
                    disabled={I.generating}
                    style={{
                      flex: 1, padding: 6, fontSize: 13,
                      background: I.batch === n ? SHARPIE : 'transparent',
                      color: I.batch === n ? PAPER : SHARPIE,
                      border: `1px solid ${SHARPIE}`,
                      cursor: I.generating ? 'not-allowed' : 'pointer',
                      fontFamily: 'Permanent Marker, cursive',
                    }}>×{n}</button>
                ))}
              </div>
            </div>

            {/* Ratio */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 13, marginBottom: 6 }}>📐 RATIO</div>
              <div style={{ display: 'flex', gap: 4 }}>
                {(['square', 'portrait', 'landscape'] as DimensionId[]).map((d) => (
                  <button key={d} type="button" onClick={() => I.setDimensions(d)}
                    disabled={I.generating}
                    style={{
                      flex: 1, padding: 6, fontSize: 13,
                      background: I.dimensions === d ? SHARPIE : 'transparent',
                      color: I.dimensions === d ? PAPER : SHARPIE,
                      border: `1px solid ${SHARPIE}`,
                      cursor: I.generating ? 'not-allowed' : 'pointer',
                      fontFamily: 'Permanent Marker, cursive',
                    }}>{DIMENSIONS[d].label}</button>
                ))}
              </div>
            </div>

            {/* Reference */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 13, marginBottom: 6 }}>
                📎 RÉFÉRENCE / ÉDITION
                <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 6 }}>
                  {I.editEngine === 'kontext' ? 'édits via Kontext (denoise ignoré)' : 'img2img latent'}
                </span>
              </div>
              {I.refPreview ? (
                <div style={{
                  display: 'flex', gap: 8, alignItems: 'center', padding: 8,
                  border: `1px solid ${SHARPIE}`,
                }}>
                  <img src={I.refPreview} alt="ref" style={{ width: 50, height: 50, objectFit: 'cover' }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11 }}>denoise {I.refDenoise.toFixed(2)}</div>
                    <input type="range" min={0.3} max={0.95} step={0.05}
                      value={I.refDenoise} onChange={(e) => I.setRefDenoise(Number(e.target.value))}
                      disabled={I.generating} style={{ width: '100%' }} />
                  </div>
                  <button type="button" onClick={I.clearReference} disabled={I.generating}
                    style={{ background: 'transparent', border: 'none', fontSize: 18, cursor: 'pointer', color: SHARPIE }}>✕</button>
                </div>
              ) : (
                <label style={{
                  display: 'block', padding: 12, textAlign: 'center',
                  border: `1px dashed ${SHARPIE}`, cursor: 'pointer',
                  fontFamily: 'Permanent Marker, cursive', fontSize: 12,
                }}>
                  <input type="file" accept="image/*" onChange={I.onUploadReference}
                    disabled={I.generating || I.refUploading} style={{ display: 'none' }} />
                  {I.refUploading ? 'UPLOAD…' : 'CLIQUER POUR ENVOYER'}
                </label>
              )}
            </div>

            {/* v87 : 2e image = SOURCE d'extraction → injectée dans la Référence */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontFamily: 'Permanent Marker, cursive', fontSize: 13, marginBottom: 6 }}>
                ➕ IMAGE SOURCE
                <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 6 }}>extraire → injecter</span>
              </div>
              {I.refPreview2 ? (
                <div style={{
                  display: 'flex', gap: 8, alignItems: 'center', padding: 8,
                  border: `1px solid ${SHARPIE}`,
                }}>
                  <img src={I.refPreview2} alt="source" style={{ width: 50, height: 50, objectFit: 'cover' }} />
                  <div style={{ flex: 1, fontSize: 11, opacity: 0.8 }}>
                    L'élément demandé est extrait d'ici et injecté dans la Référence.
                  </div>
                  <button type="button" onClick={I.clearSource} disabled={I.generating}
                    style={{ background: 'transparent', border: 'none', fontSize: 18, cursor: 'pointer', color: SHARPIE }}>✕</button>
                </div>
              ) : (
                <label style={{
                  display: 'block', padding: 12, textAlign: 'center',
                  border: `1px dashed ${SHARPIE}`, cursor: I.refPreview ? 'pointer' : 'not-allowed',
                  opacity: I.refPreview ? 1 : 0.5,
                  fontFamily: 'Permanent Marker, cursive', fontSize: 12,
                }} title={I.refPreview ? 'Un élément en sera extrait et injecté dans la Référence' : 'Ajoute d\'abord une Référence'}>
                  <input type="file" accept="image/*" onChange={I.onUploadSource}
                    disabled={I.generating || I.refUploading2 || !I.refPreview} style={{ display: 'none' }} />
                  {I.refUploading2 ? 'UPLOAD…' : 'CLIQUER POUR ENVOYER'}
                </label>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Inpainting */}
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
