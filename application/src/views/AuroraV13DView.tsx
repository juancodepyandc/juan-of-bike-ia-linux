/**
 * AuroraV13DView — Editorial wireframe stage entry for the 3D module.
 *
 * Visual chrome from _design/aurora_design_screens_v1/modules.jsx
 * (ThreeDScreen): big amber sphere on a dark stage with a wireframe
 * SVG overlay, italic display title "Grue / en vol", viewport corner
 * stats (front 0° / top 90° / right 0°), pipeline column on the right
 * (intent → traits → portrait → variations → segmentation → rig →
 * assemblage → publish) with NodeDot status, "Exporter .glb" primary.
 *
 * Real wiring: ModelView (3617 LOC of Hunyuan3D + DreamGaussian +
 * Blender procedural + Meshroom + bones display + rescue + HDRI) is
 * lazy-mounted in fullscreen as soon as the user enters. Skin only
 * re-styles the *entry* — every Manga feature stays alive verbatim.
 */
import { lazy, Suspense, useState, useEffect } from 'react'
import { Send, Loader2 } from 'lucide-react'
import AuroraSphereV1 from '../components/AuroraSphereV1.tsx'
import { useModelViewLogic } from '../hooks/useModelViewLogic.ts'
import { useModuleStreak } from '../hooks/useModuleStreak.ts'
import { useFileDrop } from '../hooks/useFileDrop.ts'
import { getDailyTip } from '../utils/dailyTip.ts'
import LyraCharacter from '../components/voice/LyraCharacter.tsx'
import FavoriteButton from '../components/FavoriteButton.tsx'

const ModelView = lazy(() => import('./ModelView'))

const AMBER = 'oklch(0.74 0.13 60)'
const GREEN = 'oklch(0.72 0.12 145)'

function Eyebrow({ children, dot, style }: { children: React.ReactNode; dot?: string; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
      letterSpacing: '0.14em', textTransform: 'uppercase',
      color: 'var(--fg-mute, #888)', display: 'flex', alignItems: 'center', gap: 8,
      ...style,
    }}>
      {dot && <span style={{ width: 8, height: 8, borderRadius: 99, background: dot, boxShadow: `0 0 12px ${dot}` }} />}
      {children}
    </div>
  )
}

function Display({ size = 36, children, style }: { size?: number; children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontFamily: 'var(--font-display, "Cormorant Garamond", serif)', fontSize: size,
      fontStyle: 'italic', fontWeight: 400, lineHeight: 0.95,
      letterSpacing: '-0.02em', color: 'var(--fg, #f5f5f5)', ...style,
    }}>{children}</div>
  )
}

function NodeDot({ active, color }: { active: boolean; color: string }) {
  return (
    <span style={{
      width: 10, height: 10, borderRadius: 99,
      background: active ? color : 'transparent',
      border: `1px solid ${active ? color : 'var(--line, rgba(255,255,255,0.12))'}`,
      boxShadow: active ? `0 0 10px ${color}` : 'none',
    }} />
  )
}

const PIPELINE: Array<[string, 'done' | 'running' | 'queued']> = [
  ['intent', 'done'], ['traits', 'done'], ['portrait', 'done'],
  ['variations', 'done'], ['segmentation', 'running'], ['rig', 'queued'],
  ['assemblage', 'queued'], ['publish', 'queued'],
]

export default function AuroraV13DView() {
  const [live, setLive] = useState(false)
  const [t, setT] = useState(0)
  const model = useModelViewLogic()
  const threeDStreak = useModuleStreak('3d')
  // v82fq : drop zone 3D → enrichit le prompt selon le type de fichier.
  // - Texte : injecte le contenu pour décrire l'objet à modéliser.
  // - Image : ajoute un hint "(Image source: nom)" qui bias le router
  //   vers le pipeline Hunyuan3D (image→3D mesh).
  // - GLB/OBJ/PLY/STL : ajoute "(Mesh existant: nom)" pour signaler une
  //   importation directe (post-process / variation).
  const drop = useFileDrop({
    onFiles: async (files) => {
      const additions: string[] = []
      for (const f of files) {
        const lower = f.name.toLowerCase()
        const isImage = f.type.startsWith('image/') || /\.(png|jpe?g|webp|gif|bmp|avif)$/.test(lower)
        const isMesh = /\.(glb|gltf|obj|ply|stl|fbx)$/.test(lower)
        if (isImage) {
          additions.push(`(Image source : ${f.name} — utilise le pipeline image→3D)`)
        } else if (isMesh) {
          additions.push(`(Mesh existant : ${f.name} — variations / post-process)`)
        } else {
          try {
            const { readTextFile } = await import('../utils/textFileExtract')
            const text = await readTextFile(f)
            const clamped = text.length > 4000 ? text.slice(0, 4000) + '…' : text
            additions.push(`### ${f.name}\n${clamped.trim()}`)
          } catch {
            additions.push(`(${f.name} : lecture impossible)`)
          }
        }
      }
      const inject = additions.join('\n\n')
      model.setPrompt(`${inject}\n\n${model.prompt}`)
    },
    accept: ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'avif', 'glb', 'gltf', 'obj', 'ply', 'stl', 'fbx', 'txt', 'md', 'markdown', 'pdf', 'docx'],
    acceptMime: ['image/', 'text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    disabled: model.analyzing,
  })
  useEffect(() => {
    if (live) return
    let raf = 0
    const loop = () => { setT(performance.now() / 1000); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [live])

  if (live) {
    return (
      <div className="aurora-v1-live-fade">
        <Suspense fallback={
          <div style={{
            width: '100%', height: '100%',
            background: 'var(--bg, #0c0a09)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--fg-dim, #aaa)',
            fontFamily: 'var(--font-display, serif)', fontStyle: 'italic', fontSize: 24,
          }}>Voxelisation en cours…</div>
        }>
          <ModelView />
        </Suspense>
      </div>
    )
  }

  const rotateAngle = (t * 30) % 360

  return (
    <div {...drop.bind} className="aurora-v1-cols" style={{
      height: '100%', display: 'grid', gridTemplateColumns: '1fr 320px',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)',
      position: 'relative',
      outline: drop.isDraggingOver ? '2px dashed oklch(0.74 0.13 60)' : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      transition: 'outline 120ms ease',
    }}>
      {/* v82fq : hint visuel pendant drag-over */}
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
          🧊 Déposer · image / mesh / texte de description
        </div>
      )}
      {/* Stage */}
      <div style={{
        position: 'relative', borderRight: '1px solid var(--line, rgba(255,255,255,0.12))',
        overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', inset: 0,
          background: `radial-gradient(ellipse 50% 40% at 50% 60%, ${AMBER}26, transparent 70%)`,
        }} />

        {/* Sphere */}
        <div style={{
          position: 'absolute', top: '15%', left: '20%', right: '20%', bottom: '15%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            width: '100%', aspectRatio: '1 / 1', maxWidth: 320,
            transform: `scale(${1 + Math.sin(t) * 0.03})`,
            filter: `drop-shadow(0 0 100px ${AMBER}55)`,
          }}>
            <AuroraSphereV1 tint={AMBER} state="thinking" radius={0.42} glow={1.3} />
          </div>
        </div>

        {/* Wireframe overlay rotated */}
        <svg width="100%" height="100%" viewBox="0 0 600 400"
          style={{ position: 'absolute', inset: 0, opacity: 0.55, pointerEvents: 'none' }}>
          <g stroke={AMBER} fill="none" strokeWidth="0.7"
            transform={`rotate(${rotateAngle} 300 240)`}>
            <path d="M 200 240 L 300 180 L 400 240 L 300 300 Z" />
            <path d="M 200 240 L 300 280 L 400 240" />
            <path d="M 300 180 L 300 280" />
            <path d="M 200 240 L 220 220 L 380 220 L 400 240" />
            <path d="M 220 220 L 220 280 L 380 280 L 380 220" strokeDasharray="2 4" />
          </g>
        </svg>

        {/* Title */}
        <div style={{ position: 'absolute', top: 24, left: 32 }}>
          <Eyebrow dot={AMBER} style={{ marginBottom: 10 }}>3D · Hunyuan3D · DreamGaussian</Eyebrow>
          <Display size={62}>Mesh<br/><em style={{ color: 'var(--ember-500, #ff6a3d)' }}>3D</em></Display>
          {/* v82ia : streak créativité 3D */}
          {threeDStreak.current > 0 && (
            <div style={{
              fontSize: 11, marginTop: 8,
              color: threeDStreak.current >= 7 ? AMBER : 'var(--fg-mute, #777)',
              fontFamily: 'var(--font-mono, monospace)', letterSpacing: '0.05em',
            }} title={`Streak 3D : ${threeDStreak.current} jour(s) · record ${threeDStreak.longest}j`}>
              🔥 {threeDStreak.current}j{threeDStreak.longest > threeDStreak.current ? ` / record ${threeDStreak.longest}j` : threeDStreak.current >= 7 ? ' 🏆' : ''}
            </div>
          )}
        </div>

        {/* Viewport corners */}
        <div style={{
          position: 'absolute', bottom: 24, left: 32, display: 'flex', gap: 16,
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11, color: 'var(--fg-mute, #777)',
        }}>
          <span>front · {Math.round(rotateAngle)}°</span>
          <span>top · 90°</span>
          <span>right · 0°</span>
        </div>
        <div style={{
          position: 'absolute', bottom: 24, right: 32,
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11, color: 'var(--fg-dim, #aaa)',
          display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4,
        }}>
          <span>12 482 verts · 8 196 tris · 24mb</span>
          <DensityGauge current={8196} target={140000} category="object" />
        </div>

        {/* Enter button overlay */}
        <button type="button" onClick={() => setLive(true)}
          style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%, calc(50% + 240px))',
            background: AMBER, color: '#0a0a0a', border: 'none',
            padding: '14px 28px', fontSize: 14, fontWeight: 700,
            letterSpacing: '0.2em', cursor: 'pointer',
            boxShadow: `0 8px 24px ${AMBER}66`,
            fontFamily: 'var(--font-sans, system-ui)',
          }}>
          ◉ ENTRER DANS L'ATELIER 3D
        </button>
      </div>

      {/* Pipeline column — v82bf : real intent preview when user types
          a prompt. Static PIPELINE = idle/demo. Dès qu'on a un intent,
          on affiche le pipeline routing déterminé (Hunyuan3D /
          DreamGaussian / Blender procedural / Meshroom) + summary. */}
      <div style={{
        padding: 24, display: 'flex', flexDirection: 'column', gap: 14,
        overflowY: 'auto',
      }}>
        <Eyebrow>Pipeline {model.intent && '· analyzed'}</Eyebrow>

        {/* Real intent results OR static demo */}
        {model.intent ? (
          <>
            <div style={{
              padding: 10,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              border: `1px solid ${AMBER}30`, borderRadius: 6,
              fontSize: 12, lineHeight: 1.5, color: 'var(--fg, #f5f5f5)',
            }}>
              <div style={{
                fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                color: AMBER, letterSpacing: '0.14em', marginBottom: 4,
                textTransform: 'uppercase',
              }}>{model.intent.subjectKind} · {model.intent.systemClass}</div>
              <div style={{ color: 'var(--fg-dim, #aaa)' }}>{model.intent.summary}</div>
            </div>
            <div style={{
              padding: 8, fontSize: 11,
              fontFamily: 'var(--font-mono, monospace)', color: 'var(--fg-dim, #aaa)',
              borderTop: '1px dashed var(--line-soft, rgba(255,255,255,0.06))',
            }}>
              <div>Pipeline → <span style={{ color: AMBER }}>{model.intent.pipelineRouting.pipeline}</span></div>
              {model.intent.pipelineRouting.fallbackPipeline && (
                <div style={{ color: 'var(--fg-mute, #777)' }}>
                  Fallback → {model.intent.pipelineRouting.fallbackPipeline}
                </div>
              )}
              <div>Goal → {model.intent.representationGoal}</div>
              <div>Motion → {model.intent.motionReadiness}</div>
            </div>
          </>
        ) : (
          PIPELINE.map(([s, st], i) => (
            <div key={s} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '6px 0', borderBottom: '1px dashed var(--line-soft, rgba(255,255,255,0.06))',
            }}>
              <span style={{
                width: 22, fontFamily: 'var(--font-mono, monospace)',
                fontSize: 11, color: 'var(--fg-mute, #777)',
              }}>{String(i + 1).padStart(2, '0')}</span>
              <span style={{
                flex: 1, fontSize: 13,
                color: st === 'queued' ? 'var(--fg-mute, #777)' : 'var(--fg, #f5f5f5)',
              }}>{s}</span>
              <NodeDot active={st !== 'queued'} color={st === 'running' ? 'var(--ember-500, #ff6a3d)' : GREEN} />
            </div>
          ))
        )}

        {/* v82fu : daily tip 3D quand pas d'intent encore */}
        {!model.intent && !model.analyzing && (
          <div style={{
            marginTop: 6, padding: '6px 10px',
            fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
            color: 'var(--fg-dim, #aaa)',
            background: 'oklch(0.74 0.13 60 / 0.06)',
            border: '1px solid oklch(0.74 0.13 60 / 0.22)',
            borderRadius: 6, lineHeight: 1.55,
          }}>
            {getDailyTip('3d')}
          </div>
        )}

        {/* v84l — Lyra 3D commentator : réagit selon état analyse / catégorie */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: 'oklch(0.74 0.13 60 / 0.04)', border: '1px solid oklch(0.74 0.13 60 / 0.16)', borderRadius: 8 }}>
          <div style={{ width: 48, height: 60, flexShrink: 0 }}>
            <LyraCharacter
              phase={model.analyzing ? 'thinking' : model.intent ? 'speaking' : 'idle'}
              emotion={model.analyzing ? 'focus' : model.intent ? 'happy' : 'curious'}
              accent="#ffb060"
              size={48}
            />
          </div>
          <div style={{ flex: 1, fontSize: 11, color: 'var(--fg-dim, #aaa)', fontFamily: 'var(--font-mono, monospace)' }}>
            {model.analyzing ? "j'analyse ton sujet 3D…" : model.intent ? `${model.intent.subjectKind} · ${model.intent.systemClass}` : 'tape un sujet, je trie le pipeline'}
          </div>
        </div>

        {/* v83l — cheatsheet experts : densités cibles + HDRI moods */}
        <div style={{
          marginTop: 4, padding: 10,
          background: 'var(--bg-card, rgba(255,255,255,0.03))',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 8,
        }}>
          <div style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
            letterSpacing: '0.14em', textTransform: 'uppercase',
            color: 'var(--fg-mute, #888)', marginBottom: 6,
          }}>Densité cible · HDRI mood</div>
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5,
            fontSize: 10.5, fontFamily: 'var(--font-mono, monospace)',
            color: 'var(--fg-dim, #aaa)',
          }}>
            <div>object · <span style={{ color: AMBER }}>140k</span></div>
            <div>studio_clean</div>
            <div>character · <span style={{ color: AMBER }}>180k</span></div>
            <div>dramatic_night</div>
            <div>vehicle · <span style={{ color: AMBER }}>220k</span></div>
            <div>golden_hour</div>
            <div>mechanical · <span style={{ color: AMBER }}>260k</span></div>
            <div>workshop_overcast</div>
            <div>architecture · <span style={{ color: AMBER }}>240k</span></div>
            <div>museum_indoor</div>
          </div>
        </div>

        {/* v83r — Motion profiles : 5 patterns d'animation procédurale qui
            seront appliqués selon le type d'objet. Affichés en chips
            informatives — pas (encore) interactifs. */}
        <div style={{
          marginTop: 4, padding: 10,
          background: 'var(--bg-card, rgba(255,255,255,0.03))',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 8,
        }}>
          <div style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
            letterSpacing: '0.14em', textTransform: 'uppercase',
            color: 'var(--fg-mute, #888)', marginBottom: 6,
          }}>Motion profiles</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, fontSize: 10.5 }}>
            {[
              { id: 'rotate', desc: 'rotation lente Y · objet showcase', tone: '#67d2ff' },
              { id: 'hover', desc: 'flottement Y subtil · float feel', tone: '#a78bfa' },
              { id: 'pulse', desc: 'pulse scale 1±2% · vivant', tone: '#f59e0b' },
              { id: 'orbit', desc: 'orbit caméra autour · ciné', tone: '#ec4899' },
              { id: 'wobble', desc: 'wobble multi-axe · creature', tone: '#10b981' },
            ].map((m) => (
              <span key={m.id} title={m.desc}
                style={{
                  padding: '2px 8px', borderRadius: 99,
                  fontFamily: 'var(--font-mono, monospace)',
                  background: `${m.tone}18`,
                  color: m.tone,
                  border: `1px solid ${m.tone}40`,
                }}>{m.id}</span>
            ))}
          </div>
          <p style={{
            marginTop: 6, fontSize: 10, lineHeight: 1.55,
            color: 'var(--fg-mute, #777)',
          }}>
            Aurora choisit le profile selon la catégorie analysée — eg. créature → wobble + breathing.
          </p>
        </div>

        {/* Real prompt input + analyze */}
        <div style={{
          marginTop: 6, padding: 10, gap: 8,
          background: 'var(--bg-card, rgba(255,255,255,0.03))',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 8, display: 'flex', flexDirection: 'column',
        }}>
          <Eyebrow style={{ marginBottom: 4 }}>Sujet 3D</Eyebrow>
          <textarea
            value={model.prompt}
            onChange={(e) => model.setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                model.previewIntent()
              }
            }}
            placeholder="Décris ton objet… ex. « grue cendrée en vol, ailes déployées, posture aérodynamique »"
            disabled={model.analyzing}
            rows={2}
            style={{
              width: '100%', padding: '8px 10px', resize: 'vertical',
              background: 'var(--bg-input, var(--bg, #0c0a09))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              borderRadius: 6, fontSize: 12,
              fontFamily: 'var(--font-sans, system-ui)',
            }}
          />
          <div style={{ display: 'flex', gap: 6 }}>
            <button type="button" onClick={() => model.previewIntent()}
              disabled={!model.prompt.trim() || model.analyzing}
              style={{
                flex: 1, padding: '6px 10px', background: AMBER, color: '#0a0a0a',
                border: 'none', fontSize: 11, fontWeight: 600,
                cursor: (!model.prompt.trim() || model.analyzing) ? 'not-allowed' : 'pointer',
                opacity: (!model.prompt.trim() || model.analyzing) ? 0.5 : 1,
                fontFamily: 'var(--font-sans, system-ui)',
                borderRadius: 6, display: 'inline-flex', alignItems: 'center',
                justifyContent: 'center', gap: 6,
              }}>{model.analyzing
                ? <><Loader2 size={11} className="aurora-spin" /> Analyse…</>
                : <><Send size={11} /> Analyser</>}</button>
            {/* v82fb : preset surprise (random 3D prompt + auto-analyze) */}
            {!model.analyzing && (
              <button type="button"
                onClick={() => {
                  model.randomThreeDPreset()
                  window.setTimeout(() => model.previewIntent(), 0)
                }}
                title="Pioche un objet 3D au hasard PUIS analyse l'intent immédiatement"
                style={{
                  padding: '6px 10px',
                  background: 'oklch(0.74 0.13 60 / 0.10)',
                  color: 'oklch(0.74 0.13 60)',
                  border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                  fontSize: 10, fontWeight: 700,
                  fontFamily: 'var(--font-mono, monospace)', cursor: 'pointer',
                  borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 4,
                }}>⚡ surprise · go</button>
            )}
            {/* v82hc : ★ favori dans bibliothèque */}
            <FavoriteButton
              prompt={model.prompt}
              module="3d"
              tags={['3d']}
              disabled={model.analyzing}
            />
            {model.intent && (
              <button type="button" onClick={model.reset}
                title="Effacer l'analyse"
                style={{
                  padding: '6px 10px', background: 'transparent',
                  color: 'var(--fg-dim, #aaa)',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                  fontSize: 11, cursor: 'pointer', borderRadius: 6,
                  fontFamily: 'var(--font-sans, system-ui)',
                }}>↺</button>
            )}
          </div>
          {model.error && (
            <div style={{ fontSize: 10, color: 'oklch(0.55 0.18 25)' }}>
              ⚠ {model.error}
            </div>
          )}
          {/* v82gt : prompt history persistant cliquable */}
          {model.history.length > 0 && (
            <div style={{ marginTop: 8, paddingTop: 8,
              borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.08))' }}>
              <div style={{
                fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.22em', textTransform: 'uppercase',
                color: 'var(--fg-mute, #888)', marginBottom: 4,
              }}>↻ Historique ({model.history.length})</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2,
                maxHeight: 120, overflowY: 'auto' }}>
                {model.history.map((h) => (
                  <div key={h.prompt} style={{
                    display: 'grid', gridTemplateColumns: '1fr 22px', gap: 4,
                    alignItems: 'center', padding: '3px 6px', borderRadius: 4,
                    fontSize: 11,
                    background: 'var(--bg-card, rgba(255,255,255,0.03))',
                    border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
                  }}>
                    <button type="button" onClick={() => model.recallPrompt(h)}
                      title={`${h.prompt}${h.meta?.pipeline ? ` · ${h.meta.pipeline}` : ''}`}
                      style={{
                        background: 'transparent', border: 'none', padding: 0,
                        color: 'var(--fg, #f5f5f5)', cursor: 'pointer', textAlign: 'left',
                        fontFamily: 'inherit', fontSize: 'inherit',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>{h.prompt}</button>
                    <button type="button" onClick={() => model.removeHistory(h.prompt)}
                      title="Retirer de l'historique"
                      style={{
                        width: 22, height: 22, background: 'transparent',
                        border: '1px solid var(--line, rgba(255,255,255,0.12))',
                        borderRadius: 3, cursor: 'pointer',
                        color: 'var(--fg-mute, #888)', fontSize: 11, padding: 0,
                      }}>×</button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <button type="button" onClick={() => setLive(true)}
          style={{
            marginTop: 4, padding: '12px 20px',
            background: 'var(--ember-500, #ff6a3d)', color: '#0a0a0a',
            border: 'none', fontSize: 13, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'var(--font-sans, system-ui)',
          }}>
          Lancer pipeline · Exporter .glb
        </button>

        <div style={{
          marginTop: 'auto', padding: 12,
          background: 'var(--bg-card, rgba(255,255,255,0.03))',
          border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
          borderRadius: 8, fontSize: 11, color: 'var(--fg-dim, #aaa)',
          lineHeight: 1.5,
        }}>
          <Eyebrow style={{ marginBottom: 6 }}>Stack</Eyebrow>
          FLUX → background removal → Hunyuan3D voxels → marching cubes →
          UV unwrap → diffuse/normal/rough → optional rigify auto-rig →
          .glb export
        </div>
      </div>
      <style>{`@keyframes aurora-spin { to { transform: rotate(360deg); } } .aurora-spin { animation: aurora-spin 1s linear infinite; }`}</style>
    </div>
  )
}

// v83z — Gauge mesh density : compare current vs target par catégorie.
function DensityGauge({ current, target, category }: { current: number; target: number; category: string }) {
  const pct = Math.max(0, Math.min(1.2, current / target))
  const status =
    pct < 0.3 ? { label: 'low', tone: 'oklch(0.72 0.14 25)' }
    : pct < 0.6 ? { label: 'fair', tone: 'oklch(0.82 0.16 90)' }
    : pct < 1.1 ? { label: 'optimal', tone: 'oklch(0.78 0.16 145)' }
    : { label: 'over', tone: 'oklch(0.72 0.14 350)' }
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3,
      minWidth: 180,
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        width: '100%', fontSize: 9, letterSpacing: '0.14em',
        textTransform: 'uppercase', color: 'var(--fg-mute, #777)',
      }}>
        <span>{category} · target {(target / 1000).toFixed(0)}k</span>
        <span style={{ color: status.tone }}>{status.label}</span>
      </div>
      <div style={{
        width: '100%', height: 4, borderRadius: 2,
        background: 'rgba(255,255,255,0.08)',
        overflow: 'hidden', position: 'relative',
      }}>
        <div style={{
          position: 'absolute', top: 0, left: 0, height: '100%',
          width: `${Math.min(100, pct * 100)}%`,
          background: status.tone,
          transition: 'width 240ms ease',
        }} />
        {/* Target line at 100% */}
        <div style={{
          position: 'absolute', top: -1, left: '83.3%', height: 6, width: 1,
          background: 'rgba(255,255,255,0.55)',
        }} title="target" />
      </div>
    </div>
  )
}
