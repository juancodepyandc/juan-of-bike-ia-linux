/**
 * AuroraV1VideoView — Editorial projector entry for the Video module.
 *
 * Visual chrome from _design/aurora_design_screens_v1/modules.jsx
 * (VideoScreen): dark projector booth with radial beam glow, 16:9
 * frame with animated film-strip background, REC tag + shot counter
 * 04/12, "wan2.2-i2v-14B · 720p · 16fps" tech caption, crosshairs in
 * each corner, big italic display "L'aurore / sur la baie", transport
 * controls (⏮︎ ⏵ ⏭︎), 12-cell timeline with playhead at 34% +
 * highlighted cell #4.
 *
 * Real wiring: MangaVideoView (972 LOC of cinema API, storyboard,
 * keyframes, voice library, pre-gen estimation, batch render, MP4
 * download, mobile guard) is lazy-mounted as soon as the user clicks
 * "Ouvrir la salle" — full feature parity guaranteed.
 */
import { lazy, Suspense, useEffect, useState } from 'react'
import { Pause, Play, SkipBack, SkipForward, Send, Loader2, X, Download, Clapperboard } from 'lucide-react'
import { useVideoViewLogic, type VideoAspect, type VideoLength } from '../hooks/useVideoViewLogic'
import { analyzeVideoPrompt } from '../services/videoPromptComposer'
import { useModuleStreak } from '../hooks/useModuleStreak'
import { useFileDrop } from '../hooks/useFileDrop'
import FavoriteButton from '../components/FavoriteButton'
import { getDailyTip } from '../utils/dailyTip'
import VoicePushToTalk from '../components/VoicePushToTalk'
import VideoVoiceLibraryPanel from '../components/VideoVoiceLibraryPanel'
import { cinemaAssetUrl } from '../services/cinemaApi'

const VIOLET = 'oklch(0.68 0.13 260)'

// v84 : VideoView (clip simple : 1 prompt → video_generate.py direct, presets
// motion, taskIntelligence, composeur cinematique) etait orphelin depuis
// v82jy — re-expose comme mode « Clip rapide » a cote de la salle cinema.
// runPythonScript a un chemin bridge async, donc fonctionne aussi via tunnel.
const QuickClipView = lazy(() => import('./VideoView'))

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

function Crosshair({ corner, color }: { corner: 'tl' | 'tr' | 'bl' | 'br'; color: string }) {
  const inset = 8
  const size = 14
  const pos: React.CSSProperties = corner === 'tl' ? { top: inset, left: inset }
    : corner === 'tr' ? { top: inset, right: inset }
    : corner === 'bl' ? { bottom: inset, left: inset }
    : { bottom: inset, right: inset }
  return (
    <div style={{ position: 'absolute', ...pos, width: size, height: size }}>
      <div style={{ position: 'absolute', top: 0, left: 0, width: size, height: 1, background: color }} />
      <div style={{ position: 'absolute', top: 0, left: 0, width: 1, height: size, background: color }} />
    </div>
  )
}

export default function AuroraV1VideoView() {
  const [live, setLive] = useState(false)
  const [clip, setClip] = useState(false)
  const [t, setT] = useState(0)
  const video = useVideoViewLogic()
  const videoStreak = useModuleStreak('video')
  // v82fp : drop zone Video → injecte script/synopsis dans le prompt.
  // Cas d'usage : drop un .txt/.md/.pdf/.docx avec un brief client ou
  // un scénario, qui sert de base pour générer le storyboard cinema.
  const drop = useFileDrop({
    onFiles: async (files) => {
      const { readTextFile } = await import('../utils/textFileExtract')
      const sections: string[] = []
      for (const f of files) {
        try {
          const text = await readTextFile(f)
          const clamped = text.length > 8000
            ? text.slice(0, 8000) + '\n[... tronqué à 8 KB pour le storyboard ...]'
            : text
          sections.push(`--- ${f.name} ---\n${clamped.trim()}`)
        } catch {
          sections.push(`--- ${f.name} ---\n(lecture impossible)`)
        }
      }
      const inject = sections.join('\n\n')
      video.setPrompt(`${inject}\n\n${video.prompt}`)
    },
    accept: ['txt', 'md', 'markdown', 'pdf', 'docx'],
    acceptMime: ['text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    disabled: video.generating,
  })
  useEffect(() => {
    if (live) return
    let raf = 0
    const loop = () => { setT(performance.now() / 1000); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [live])

  // v84 : mode « Clip rapide » — full VideoView (prompt unique → Wan/LTX
  // direct, 13 presets motion, badges 🎬, 1280×720 par defaut).
  if (clip) {
    return (
      <div style={{
        minHeight: '100%', display: 'flex', flexDirection: 'column',
        background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      }}>
        <div style={{
          padding: '10px 24px', display: 'flex', alignItems: 'center', gap: 12,
          borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
          background: `linear-gradient(180deg, ${VIOLET}10, transparent)`,
        }}>
          <Eyebrow dot={VIOLET}>Clip rapide · Wan2.2 / LTX</Eyebrow>
          <span style={{ flex: 1 }} />
          <button type="button" onClick={() => setClip(false)}
            style={{
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              color: 'var(--fg-dim, #aaa)', padding: '6px 12px', cursor: 'pointer',
              borderRadius: 8, fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 6,
              fontFamily: 'var(--font-sans, system-ui)',
            }}>
            <X size={14} /> Retour cinéma
          </button>
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <Suspense fallback={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 240, gap: 8, color: 'var(--fg-dim, #aaa)' }}>
              <Loader2 size={16} className="aurora-spin" /> Chargement du studio clip…
            </div>
          }>
            <QuickClipView />
          </Suspense>
        </div>
      </div>
    )
  }

  // v82jy : native aurora_v1 cinema room — no manga delegate.
  if (live) {
    const eta = video.jobStatus?.eta
    const status = video.jobStatus?.status
    const pct = eta && eta.total > 0 ? Math.round((eta.done / eta.total) * 100) : 0
    return (
      <div className="aurora-v1-live-fade" style={{
        // v82m3 : live mode aussi scrollable + safe-area pour ne rien
        // cacher derrière la taskbar OS / barre mobile.
        minHeight: '100%', display: 'flex', flexDirection: 'column',
        background: 'oklch(0.06 0.01 250)', color: 'var(--fg, #f5f5f5)',
        fontFamily: 'var(--font-sans, system-ui)',
        overflowY: 'auto', overflowX: 'hidden',
        paddingBottom: 'calc(48px + env(safe-area-inset-bottom, 0px))',
      }}>
        <div style={{
          padding: '14px 24px', display: 'flex', alignItems: 'center', gap: 12,
          borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
          background: `linear-gradient(180deg, ${VIOLET}10, transparent)`,
        }}>
          <Eyebrow dot={VIOLET}>Salle de projection · Wan2.2</Eyebrow>
          <span style={{ flex: 1 }} />
          <button type="button" onClick={() => setLive(false)}
            style={{
              padding: '6px 12px', fontSize: 11,
              fontFamily: 'var(--font-mono, monospace)',
              background: 'transparent', color: 'var(--fg-dim, #aaa)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              cursor: 'pointer', borderRadius: 6,
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}><X size={12} /> Fermer la salle</button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 24,
          display: 'flex', flexDirection: 'column', gap: 18 }}>
          {!video.storyboard ? (
            <div style={{
              padding: 24, fontSize: 13, color: 'var(--fg-dim, #aaa)',
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              borderRadius: 8, textAlign: 'center',
            }}>
              Aucun storyboard à projeter. Reviens à la chrome editorial,
              tape un sujet et clique <em>Storyboard</em>.
            </div>
          ) : (
            <>
              {/* Storyboard header */}
              <div>
                <Display size={36} style={{ marginBottom: 8 }}>
                  {video.storyboard.title}
                </Display>
                <div style={{ color: 'var(--fg-dim, #aaa)', fontSize: 13, lineHeight: 1.55 }}>
                  {video.storyboard.summary}
                </div>
                <div style={{
                  marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap',
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                  color: 'var(--fg-mute, #888)',
                }}>
                  <Tag accent={VIOLET}>{video.storyboard.shots.length} shots</Tag>
                  <Tag>{video.storyboard.aspect}</Tag>
                  <Tag>{video.storyboard.resolution}</Tag>
                  <Tag>{video.storyboard.style}</Tag>
                </div>
              </div>

              {/* Render controls */}
              <div style={{
                display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap',
                padding: 12, borderRadius: 8,
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
              }}>
                {!video.rendering && !video.videoUrl && (
                  <>
                    {/* v82lm : selftest pipeline avant tout */}
                    <button type="button"
                      onClick={() => void video.runSelftest()}
                      disabled={video.selftesting}
                      style={{
                        padding: '10px 16px',
                        background: 'oklch(0.65 0.13 145 / 0.10)',
                        color: 'oklch(0.78 0.16 145)',
                        border: '1px solid oklch(0.65 0.13 145 / 0.55)',
                        fontWeight: 600,
                        cursor: video.selftesting ? 'wait' : 'pointer',
                        borderRadius: 99,
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        opacity: video.selftesting ? 0.5 : 1,
                        fontSize: 11,
                      }}>
                      {video.selftesting ? '⏳ Test...' : '🩺 Self-test pipeline'}
                    </button>
                    <button type="button"
                      onClick={() => void video.runBenchmark()}
                      disabled={video.benchmarking}
                      style={{
                        padding: '10px 16px',
                        background: 'oklch(0.68 0.13 260 / 0.10)',
                        color: VIOLET,
                        border: '1px solid oklch(0.68 0.13 260 / 0.5)',
                        fontWeight: 600,
                        cursor: video.benchmarking ? 'wait' : 'pointer',
                        borderRadius: 99,
                        opacity: video.benchmarking ? 0.5 : 1,
                        fontSize: 11,
                      }}>
                      {video.benchmarking ? '⏳ A/B en file…' : '⚖ Comparer Wan / LTX'}
                    </button>
                    {/* v82lx : sample render (1 shot balanced 720p, ~5-7 min)
                        — confirme prompt/render alignement avant commit full. */}
                    <button type="button"
                      onClick={async () => {
                        if (!video.storyboard) return
                        const { cinemaSampleRender } = await import('../services/cinemaApi')
                        const r = await cinemaSampleRender(video.storyboard)
                        if (r.ok) alert(`🎬 Sample render lancé (1 shot balanced 720p) → jobId ${r.jobId}\nResultat dans ~5-7 min via /api/cinema/job/<id>`)
                        else alert(`Échec : ${r.error}`)
                      }}
                      disabled={video.previewing || video.rendering}
                      style={{
                        padding: '10px 16px',
                        background: 'oklch(0.74 0.13 90 / 0.10)',
                        color: 'oklch(0.78 0.16 90)',
                        border: '1px solid oklch(0.74 0.13 90 / 0.55)',
                        fontWeight: 600,
                        cursor: 'pointer',
                        borderRadius: 99,
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        fontSize: 11,
                      }}>
                      🎬 Sample (1 shot ~5min)
                    </button>
                    {/* v82lj : preview keyframes (FLUX-only, ~1 min) AVANT
                        de commit 30 min Wan2.2. User voit fidélité personnages. */}
                    <button type="button"
                      onClick={() => void video.previewKeyframes()}
                      disabled={video.previewing}
                      style={{
                        padding: '10px 16px',
                        background: 'oklch(0.74 0.13 60 / 0.12)',
                        color: 'oklch(0.78 0.16 60)',
                        border: '1px solid oklch(0.74 0.13 60 / 0.55)',
                        fontWeight: 600,
                        cursor: video.previewing ? 'wait' : 'pointer',
                        borderRadius: 99,
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        opacity: video.previewing ? 0.5 : 1,
                      }}>
                      {video.previewing ? (
                        <><Loader2 size={14} className="aurora-spin" /> FLUX en cours...</>
                      ) : (
                        <>👁 Aperçu personnages (FLUX seul)</>
                      )}
                    </button>
                    <button type="button" onClick={() => void video.runRender()}
                      style={{
                        padding: '10px 16px', background: 'var(--ember-500, #ff6a3d)',
                        color: '#0a0a0a', border: 'none', fontWeight: 700,
                        cursor: 'pointer', borderRadius: 99,
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                      }}>
                      <Play size={14} fill="currentColor" /> Lancer le rendu Wan2.2
                    </button>
                    {/* v82lf : toggle subtitles */}
                    <label style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      fontSize: 11, color: 'var(--fg-dim, #aaa)',
                      cursor: 'pointer', userSelect: 'none',
                    }}>
                      <input type="checkbox"
                        checked={video.subtitlesEnabled}
                        onChange={(e) => video.setSubtitlesEnabled(e.target.checked)}
                        style={{ accentColor: 'oklch(0.74 0.13 60)' }} />
                      Sous-titres .srt embarqués
                    </label>
                  </>
                )}
                {video.rendering && (
                  <>
                    <Loader2 size={14} className="aurora-spin" color={VIOLET} />
                    <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11 }}>
                      {status || 'queued'}
                      {eta && eta.total > 0 && ` · ${eta.done}/${eta.total} (${pct}%)`}
                      {eta && eta.remaining_s > 0 && ` · ${Math.round(eta.remaining_s)}s restants`}
                    </span>
                    <button type="button" onClick={() => video.cancelRender()}
                      style={{
                        padding: '6px 12px', fontSize: 11,
                        background: 'transparent', color: 'oklch(0.78 0.16 25)',
                        border: '1px solid oklch(0.78 0.16 25 / 0.5)',
                        cursor: 'pointer', borderRadius: 6,
                      }}>Annuler</button>
                  </>
                )}
                {video.videoUrl && !video.rendering && (() => {
                  // v82lu : auto-block export si grade C/D (force fix avant download).
                  const exportable = video.jobStatus?.result?.quality_grade?.exportable !== false
                  return exportable ? (
                    <a href={video.videoUrl} download
                      style={{
                        padding: '8px 14px', background: VIOLET,
                        color: '#0a0a0a', textDecoration: 'none', fontWeight: 700,
                        borderRadius: 99, fontSize: 12,
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                      }}>
                      <Download size={13} /> Télécharger MP4
                    </a>
                  ) : (
                    <button type="button"
                      onClick={() => alert('Grade < B — au moins 1 shot faible. Click sur ↻ shot X dans le bandeau de qualité pour fix avant export.')}
                      title="Export bloqué : grade insuffisant"
                      style={{
                        padding: '8px 14px',
                        background: 'oklch(0.55 0.18 25 / 0.15)',
                        color: 'oklch(0.78 0.16 25)',
                        border: '1px solid oklch(0.55 0.18 25 / 0.55)',
                        cursor: 'not-allowed',
                        borderRadius: 99, fontSize: 12, fontWeight: 700,
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                      }}>
                      🔒 Export bloqué (grade {video.jobStatus?.result?.quality_grade?.grade})
                    </button>
                  )
                })()}
                {video.error && (
                  <span style={{ color: 'oklch(0.78 0.16 25)', fontSize: 12 }}>⚠ {video.error}</span>
                )}
              </div>

              {video.storageStatus && (
                <div style={{
                  padding: '8px 10px',
                  borderRadius: 6,
                  border: `1px solid ${video.storageStatus.key_mounted
                    ? 'oklch(0.65 0.13 145 / 0.4)'
                    : 'oklch(0.78 0.16 90 / 0.45)'}`,
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: 10,
                  color: 'var(--fg-dim, #aaa)',
                  display: 'flex',
                  gap: 12,
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}>
                  <span style={{ color: video.storageStatus.key_mounted
                    ? 'oklch(0.78 0.16 145)'
                    : 'oklch(0.78 0.16 90)' }}>
                    {video.storageStatus.key_mounted ? '● froid monté' : '● froid hors ligne'}
                  </span>
                  <span>NVMe {video.storageStatus.tiers.internal.free_gb} Go libres</span>
                  <span>sorties : {video.storageStatus.outputs_tier}</span>
                  {video.storageStatus.model_strategy?.active.generator && (
                    <span title={video.storageStatus.model_strategy.active.reason}>
                      moteur : {video.storageStatus.model_strategy.active.generator}
                    </span>
                  )}
                  {video.storageStatus.model_strategy?.active.voice_clone && (
                    <span>
                      voix cible : {video.storageStatus.model_strategy.active.voice_clone}
                      {video.storageStatus.model_strategy.runtime?.voice_clone_ready ? ' · prête' : ' · à provisionner'}
                    </span>
                  )}
                  <button type="button" onClick={() => void video.refreshStorageStatus()} style={{
                    marginLeft: 'auto',
                    border: '1px solid var(--line, rgba(255,255,255,.15))',
                    background: 'transparent',
                    color: 'inherit',
                    borderRadius: 99,
                    padding: '3px 8px',
                    cursor: 'pointer',
                  }}>actualiser</button>
                </div>
              )}

              <div>
                <VideoVoiceLibraryPanel
                  accent={VIOLET}
                  engineName={video.storageStatus?.model_strategy?.active.voice_clone}
                  engineReady={video.storageStatus?.model_strategy?.runtime?.voice_clone_ready === true}
                />
              </div>

              {video.gallery && video.gallery.files.length > 0 && (
                <div style={{
                  padding: 10,
                  borderRadius: 6,
                  border: '1px solid var(--line, rgba(255,255,255,.12))',
                  background: 'var(--bg-card, rgba(255,255,255,.025))',
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: 8,
                    fontSize: 10,
                    fontFamily: 'var(--font-mono, monospace)',
                    color: 'var(--fg-dim, #aaa)',
                  }}>
                    <span>Galerie persistante · {video.gallery.files.length} rendu(s)</span>
                    <button type="button" onClick={() => void video.refreshGallery()} style={{
                      border: 0,
                      background: 'transparent',
                      color: 'inherit',
                      cursor: 'pointer',
                    }}>actualiser</button>
                  </div>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                    gap: 8,
                  }}>
                    {video.gallery.files.slice(0, 4).map((file) => (
                      <a key={`${file.tier}:${file.path}`} href={cinemaAssetUrl(file.asset_url)} target="_blank" rel="noreferrer" style={{
                        color: 'inherit',
                        textDecoration: 'none',
                        minWidth: 0,
                      }}>
                        <video src={cinemaAssetUrl(file.asset_url)} preload="metadata" muted style={{
                          display: 'block',
                          width: '100%',
                          aspectRatio: '16 / 9',
                          objectFit: 'cover',
                          borderRadius: 4,
                          background: '#050608',
                        }} />
                        <div title={file.name} style={{
                          marginTop: 4,
                          fontSize: 9,
                          fontFamily: 'var(--font-mono, monospace)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}>{file.name} · {file.tier}</div>
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {video.benchmarkResult && (
                <div style={{
                  padding: 10,
                  borderRadius: 6,
                  border: `1px solid ${video.benchmarkResult.selection_graded
                    ? 'oklch(0.65 0.13 145 / 0.4)'
                    : 'oklch(0.78 0.16 90 / 0.45)'}`,
                  fontFamily: 'var(--font-mono, monospace)',
                  fontSize: 10,
                }}>
                  <div style={{ fontWeight: 700, marginBottom: 6 }}>
                    A/B qualité · {video.benchmarkResult.winner
                      ? `${video.benchmarkResult.selection_graded ? 'gagnant' : 'gagnant provisoire'} : ${video.benchmarkResult.winner}`
                      : 'aucun gagnant mesuré'}
                  </div>
                  {video.benchmarkResult.variants.map((item) => (
                    <div key={item.variant} style={{ display: 'flex', gap: 8 }}>
                      <span>{item.variant}</span>
                      <span>{item.score_pct == null ? 'N/A' : `${item.score_pct}%`}</span>
                      <span>couverture {item.coverage_pct}%</span>
                      {item.render.ok && (
                        <a href={cinemaAssetUrl(item.output)} target="_blank" rel="noreferrer" style={{ color: VIOLET }}>
                          voir
                        </a>
                      )}
                    </div>
                  ))}
                  {(video.benchmarkResult.warning || video.benchmarkResult.error) && (
                    <div style={{ marginTop: 5, color: 'oklch(0.78 0.16 90)' }}>
                      {video.benchmarkResult.warning || video.benchmarkResult.error}
                    </div>
                  )}
                </div>
              )}

              {/* v82lm : Selftest result — état des briques pipeline */}
              {video.selftestResult && (
                <div style={{
                  padding: 10, borderRadius: 6,
                  background: video.selftestResult.overall_ok
                    ? 'oklch(0.65 0.13 145 / 0.06)'
                    : 'oklch(0.55 0.18 25 / 0.06)',
                  border: `1px solid ${video.selftestResult.overall_ok
                    ? 'oklch(0.65 0.13 145 / 0.40)'
                    : 'oklch(0.55 0.18 25 / 0.40)'}`,
                }}>
                  <div style={{
                    fontSize: 11, fontWeight: 700,
                    color: video.selftestResult.overall_ok
                      ? 'oklch(0.78 0.16 145)' : 'oklch(0.78 0.16 25)',
                    marginBottom: 8,
                  }}>{video.selftestResult.overall_ok ? '✓' : '⚠'} {video.selftestResult.summary}</div>
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                    gap: 4,
                  }}>
                    {Object.entries(video.selftestResult.stages).map(([name, stage]) => (
                      <div key={name} style={{
                        padding: '4px 8px', borderRadius: 4,
                        fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
                        background: 'var(--bg-card, rgba(255,255,255,0.04))',
                        border: `1px solid ${stage.ok
                          ? 'oklch(0.65 0.13 145 / 0.30)'
                          : 'oklch(0.55 0.18 25 / 0.40)'}`,
                        color: stage.ok ? 'oklch(0.78 0.16 145)' : 'oklch(0.78 0.16 25)',
                      }}>
                        {stage.ok ? '✓' : '✗'} {name} ({stage.ms}ms)
                        {stage.error && (
                          <div style={{ fontSize: 9, color: 'var(--fg-mute, #888)', marginTop: 2 }}>
                            {stage.error.slice(0, 50)}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* v82lt : Quality grade banner — synthèse 1-coup-d'œil */}
              {video.jobStatus?.result?.quality_grade && (() => {
                const qg = video.jobStatus.result.quality_grade
                const gradeColor = qg.grade === 'A' ? 'oklch(0.78 0.16 145)'
                  : qg.grade === 'B' ? 'oklch(0.78 0.16 90)'
                  : qg.grade === 'C' ? 'oklch(0.78 0.16 60)'
                  : 'oklch(0.78 0.16 25)'
                const label = qg.grade === 'A' ? 'EXCELLENT — broadcast ready'
                  : qg.grade === 'B' ? 'ACCEPTABLE — minor issues'
                  : qg.grade === 'C' ? 'NEEDS WORK — at least 1 shot to redo'
                  : 'UNUSABLE — re-render storyboard'
                return (
                  <div style={{
                    padding: 16, borderRadius: 8,
                    background: `${gradeColor}1A`,
                    border: `2px solid ${gradeColor}`,
                    display: 'flex', alignItems: 'center', gap: 16,
                  }}>
                    <div style={{
                      width: 64, height: 64, borderRadius: '50%',
                      background: gradeColor, color: '#0a0a0a',
                      fontSize: 36, fontWeight: 900,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontFamily: 'var(--font-display, serif)',
                    }}>{qg.grade}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: gradeColor, marginBottom: 4 }}>
                        Grade {qg.grade} — {qg.overall_pct}% · {label}
                      </div>
                      <div style={{
                        fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
                        color: 'var(--fg-dim, #aaa)',
                        display: 'flex', gap: 12, flexWrap: 'wrap',
                      }}>
                        <span>shot {qg.breakdown.shot_pct}%</span>
                        <span>char {qg.breakdown.char_pct == null ? 'N/A' : `${qg.breakdown.char_pct}%`}</span>
                        <span>audio {qg.breakdown.audio_pct == null ? 'N/A' : `${qg.breakdown.audio_pct}%`}</span>
                        <span>temporal {qg.breakdown.temporal_pct == null ? 'N/A' : `${qg.breakdown.temporal_pct}%`}</span>
                        <span>integrity {qg.breakdown.integrity_pct}%</span>
                        <span>QA mesurée {qg.coverage?.overall_pct ?? 0}%</span>
                      </div>
                      {qg.weak_shots.length > 0 && (
                        <div style={{ marginTop: 6, fontSize: 11, color: 'oklch(0.78 0.16 25)' }}>
                          ⚠ {qg.weak_shots.length} shot(s) faible(s) :{' '}
                          {qg.weak_shots.map((w) => (
                            <button key={w.shot_id} type="button"
                              onClick={async () => {
                                const { cinemaRegenerateShot } = await import('../services/cinemaApi')
                                const r = await cinemaRegenerateShot(video.jobStatus!.jobId, w.shot_id)
                                if (r.ok) alert(`↻ Re-render shot ${w.shot_id} → ${r.jobId} (seed ${r.seed})`)
                                else alert(`Échec : ${r.error}`)
                              }}
                              style={{
                                padding: '2px 8px', marginLeft: 4,
                                fontSize: 10, fontFamily: 'inherit',
                                background: 'oklch(0.55 0.18 25 / 0.15)',
                                color: 'oklch(0.78 0.16 25)',
                                border: '1px solid oklch(0.55 0.18 25 / 0.45)',
                                borderRadius: 99, cursor: 'pointer',
                              }}>↻ shot {w.shot_id} ({w.avg_score}/10)</button>
                          ))}
                        </div>
                      )}
                      {!qg.exportable && (
                        <div style={{ marginTop: 6, fontSize: 11, color: 'oklch(0.78 0.16 25)', fontWeight: 700 }}>
                          🔒 Export bloqué — fix les shots faibles avant download
                        </div>
                      )}
                    </div>
                  </div>
                )
              })()}

              {/* v82lj : Preview keyframes gallery — affiche les portraits
                   FLUX pré-générés avec score qwen3-vl PAR personnage avant
                   le commit Wan2.2 long render. */}
              {video.previewResult?.char_quality && Object.keys(video.previewResult.char_quality).length > 0 && (
                <div style={{
                  padding: 12, borderRadius: 8,
                  background: 'var(--bg-card, rgba(255,255,255,0.04))',
                  border: '1px solid oklch(0.74 0.13 60 / 0.30)',
                }}>
                  <div style={{
                    fontSize: 10, color: 'var(--fg-mute, #888)',
                    letterSpacing: '0.18em', textTransform: 'uppercase',
                    marginBottom: 10,
                  }}>👁 Aperçu personnages (FLUX) · valider avant Wan2.2</div>
                  <div style={{
                    display: 'grid', gap: 12,
                    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                  }}>
                    {Object.entries(video.previewResult.char_quality).map(([name, q]) => {
                      const scoreColor = q.score !== null && q.score >= 8 ? 'oklch(0.78 0.16 145)'
                        : q.score !== null && q.score >= 6 ? 'oklch(0.78 0.16 80)'
                        : 'oklch(0.78 0.16 25)'
                      const url = cinemaAssetUrl(q.keyframe_url)
                      return (
                        <div key={name} style={{
                          display: 'flex', flexDirection: 'column', gap: 6,
                          padding: 8, borderRadius: 6,
                          background: 'var(--bg-raised, rgba(255,255,255,0.03))',
                          border: `1px solid ${scoreColor}55`,
                        }}>
                          <img src={url} alt={name}
                            style={{
                              width: '100%', aspectRatio: '1/1',
                              objectFit: 'cover', borderRadius: 4,
                              background: '#000',
                            }}
                            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
                          <div style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                          }}>
                            <span style={{ fontWeight: 700, color: 'var(--fg, #f5f5f5)' }}>{name}</span>
                            <span style={{
                              fontFamily: 'var(--font-mono, monospace)',
                              color: scoreColor, fontWeight: 700, fontSize: 13,
                            }}>{q.score === null ? 'Non notée' : `${q.score}/10`}</span>
                          </div>
                          <div style={{
                            fontSize: 11, color: 'var(--fg-dim, #aaa)',
                            fontStyle: 'italic', lineHeight: 1.3,
                          }}>{q.reason}</div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
              {video.previewResult?.error && (
                <div style={{
                  padding: 10, borderRadius: 6,
                  background: 'oklch(0.55 0.18 25 / 0.10)',
                  border: '1px solid oklch(0.55 0.18 25 / 0.45)',
                  color: 'oklch(0.78 0.16 25)', fontSize: 12,
                }}>⚠ Aperçu échoué : {video.previewResult.error}</div>
              )}

              {/* v82ld : Character fidelity scores — affiche les scores
                   qwen3-vl par personnage pour montrer "Shadow keyframe: 9/10". */}
              {video.jobStatus?.result?.char_quality && (
                <div style={{
                  padding: 10, borderRadius: 6,
                  background: 'var(--bg-card, rgba(255,255,255,0.04))',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                }}>
                  <div style={{
                    fontSize: 10, color: 'var(--fg-mute, #888)',
                    letterSpacing: '0.18em', textTransform: 'uppercase',
                    marginBottom: 8,
                  }}>Fidélité personnages (qwen3-vl)</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {Object.entries(video.jobStatus.result.char_quality).map(([name, q]) => {
                      const color = q.score >= 8 ? 'oklch(0.78 0.16 145)'
                        : q.score >= 6 ? 'oklch(0.78 0.16 80)'
                        : 'oklch(0.78 0.16 25)'
                      return (
                        <div key={name} style={{
                          display: 'flex', gap: 10, alignItems: 'center',
                          fontSize: 12,
                        }}>
                          <span style={{
                            fontFamily: 'var(--font-mono, monospace)',
                            color: color, minWidth: 36, fontWeight: 700,
                          }}>{q.score}/10</span>
                          <span style={{
                            fontWeight: 600, color: 'var(--fg, #f5f5f5)',
                          }}>{name}</span>
                          <span style={{
                            color: 'var(--fg-dim, #aaa)', flex: 1,
                            fontSize: 11, fontStyle: 'italic',
                          }}>{q.reason}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* v82lk + v82lp : Per-shot triple score — scene / physics / identity */}
              {video.jobStatus?.result?.shot_quality && video.jobStatus.result.shot_quality.length > 0 && (
                <div style={{
                  padding: 10, borderRadius: 6,
                  background: 'var(--bg-card, rgba(255,255,255,0.04))',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                }}>
                  <div style={{
                    fontSize: 10, color: 'var(--fg-mute, #888)',
                    letterSpacing: '0.18em', textTransform: 'uppercase',
                    marginBottom: 8,
                  }}>Fidélité par plan (scène / physique / identité)</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {video.jobStatus.result.shot_quality.map((q) => {
                      const colorize = (s: number | null | undefined) => s == null
                        ? 'var(--fg-mute, #888)'
                        : s >= 8 ? 'oklch(0.78 0.16 145)'
                        : s >= 6 ? 'oklch(0.78 0.16 80)'
                        : 'oklch(0.78 0.16 25)'
                      return (
                        <div key={q.shot_id} style={{
                          display: 'flex', flexDirection: 'column', gap: 2,
                          padding: '4px 8px', borderRadius: 4,
                          background: 'var(--bg-raised, rgba(255,255,255,0.02))',
                        }}>
                          <div style={{
                            display: 'flex', gap: 12, alignItems: 'center',
                            fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                          }}>
                            <span style={{
                              minWidth: 50, color: 'var(--fg-mute, #888)',
                            }}>shot {String(q.shot_id).padStart(2, '0')}</span>
                            <span title="Cohérence scène"
                              style={{ color: colorize(q.score), fontWeight: 700 }}>
                              📺 {q.score == null ? '—' : `${q.score}/10`}
                            </span>
                            <span title="Cohérence physique (gravité, contact, pas de clipping)"
                              style={{ color: colorize(q.physics_score), fontWeight: 700 }}>
                              ⚛ {q.physics_score == null ? '—' : `${q.physics_score}/10`}
                            </span>
                            <span title="Identité personnage (3 frames)"
                              style={{ color: colorize(q.identity_score), fontWeight: 700 }}>
                              👤 {q.identity_score == null ? '—' : `${q.identity_score}/10`}
                            </span>
                          </div>
                          {q.issues && q.issues.length > 0 && (
                            <ul style={{
                              margin: 0, paddingLeft: 64,
                              fontSize: 10, color: 'oklch(0.78 0.16 25)',
                            }}>
                              {q.issues.map((iss, i) => <li key={i}>{iss}</li>)}
                            </ul>
                          )}
                          {/* v82lr : ↻ retry shot button when score weak */}
                          {video.jobStatus?.jobId && (
                            (q.score != null && q.score < 7)
                            || (q.physics_score != null && q.physics_score < 6)
                            || (q.identity_score != null && q.identity_score < 6)
                          ) && (
                            <button type="button"
                              onClick={async () => {
                                const { cinemaRegenerateShot } = await import('../services/cinemaApi')
                                const r = await cinemaRegenerateShot(video.jobStatus!.jobId, q.shot_id)
                                if (r.ok) {
                                  console.info(`[aurora] regen shot ${q.shot_id} -> jobId ${r.jobId} seed ${r.seed}`)
                                  alert(`Re-render shot ${q.shot_id} lancé (seed ${r.seed}). Nouveau jobId : ${r.jobId}`)
                                } else {
                                  alert(`Échec : ${r.error}`)
                                }
                              }}
                              style={{
                                marginLeft: 64, marginTop: 4,
                                padding: '3px 10px',
                                fontSize: 10,
                                background: 'oklch(0.74 0.13 60 / 0.10)',
                                color: 'oklch(0.78 0.16 60)',
                                border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                                borderRadius: 99,
                                cursor: 'pointer',
                                fontFamily: 'var(--font-mono, monospace)',
                                width: 'fit-content',
                              }}>
                              ↻ Re-render ce shot (seed différent)
                            </button>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* v82ls : Temporal coherence — scene cuts inside shots */}
              {video.jobStatus?.result?.temporal_quality && video.jobStatus.result.temporal_quality.length > 0 && (
                <div style={{
                  padding: 10, borderRadius: 6,
                  background: 'var(--bg-card, rgba(255,255,255,0.04))',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                }}>
                  <div style={{
                    fontSize: 10, color: 'var(--fg-mute, #888)',
                    letterSpacing: '0.18em', textTransform: 'uppercase',
                    marginBottom: 8,
                  }}>Cohérence temporelle (cuts internes)</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {video.jobStatus.result.temporal_quality.map((t) => {
                      const ok = t.ok
                      const color = ok == null
                        ? 'var(--fg-mute, #888)'
                        : ok
                        ? 'oklch(0.78 0.16 145)'
                        : t.cuts_count >= 3 ? 'oklch(0.78 0.16 25)'
                        : 'oklch(0.78 0.16 80)'
                      return (
                        <div key={t.shot_id} style={{
                          display: 'flex', gap: 10, alignItems: 'center',
                          fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                        }}>
                          <span style={{ minWidth: 50, color: 'var(--fg-mute, #888)' }}>
                            shot {String(t.shot_id).padStart(2, '0')}
                          </span>
                          <span style={{ color, fontWeight: 700, minWidth: 22 }}>
                            {ok == null ? 'N/A' : ok ? '🎬' : '⚠'}
                          </span>
                          <span style={{ color: 'var(--fg-dim, #aaa)', flex: 1 }}>
                            {ok == null ? `non mesuré${t.error ? ` · ${t.error}` : ''}`
                              : t.cuts_count === 0 ? 'continu, pas de cut'
                              : t.cuts_count === 1 ? '1 cut détecté (acceptable)'
                              : `${t.cuts_count} cuts internes — téléportation/jump cut`}
                            {t.cuts && t.cuts.length > 0 && (
                              <span style={{ marginLeft: 8, color: 'var(--fg-mute, #888)' }}>
                                @ {t.cuts.map((c) => `${c.t}s`).join(', ')}
                              </span>
                            )}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* v82lq : Audio quality per shot — silence detect ffmpeg */}
              {video.jobStatus?.result?.audio_quality && video.jobStatus.result.audio_quality.length > 0 && (
                <div style={{
                  padding: 10, borderRadius: 6,
                  background: 'var(--bg-card, rgba(255,255,255,0.04))',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                }}>
                  <div style={{
                    fontSize: 10, color: 'var(--fg-mute, #888)',
                    letterSpacing: '0.18em', textTransform: 'uppercase',
                    marginBottom: 8,
                  }}>Intégrité audio par plan (silencedetect)</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {video.jobStatus.result.audio_quality.map((a) => {
                      const ok = a.ok
                      const hasAudio = a.has_audio
                      const ratio = a.silence_ratio || 0
                      const color = ok == null ? 'var(--fg-mute, #888)'
                        : !ok ? 'oklch(0.78 0.16 25)'
                        : !hasAudio ? 'var(--fg-mute, #888)'
                        : ratio < 0.2 ? 'oklch(0.78 0.16 145)'
                        : ratio < 0.4 ? 'oklch(0.78 0.16 80)'
                        : 'oklch(0.78 0.16 25)'
                      return (
                        <div key={a.shot_id} style={{
                          display: 'flex', gap: 10, alignItems: 'center',
                          fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                        }}>
                          <span style={{ minWidth: 50, color: 'var(--fg-mute, #888)' }}>
                            shot {String(a.shot_id).padStart(2, '0')}
                          </span>
                          <span style={{ color, fontWeight: 700, minWidth: 22 }}>
                            {ok == null ? 'N/A' : !hasAudio ? '🔇' : ok ? '🔊' : '⚠'}
                          </span>
                          <span style={{ color: 'var(--fg-dim, #aaa)', flex: 1 }}>
                            {ok == null
                              ? `non mesuré${a.error ? ` · ${a.error}` : ''}`
                              : !hasAudio
                              ? 'no audio track'
                              : `silence ${(ratio * 100).toFixed(0)}%${a.expected_dialogue ? ' · dialogue attendu' : ''}`}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* v82lb : Integrity panel — affiche les checks ffprobe sur
                   la vidéo finale (durée, audio, codec, errors). User voit
                   immédiatement si quelque chose cloche au lieu d'avoir
                   "ok" silencieusement quand c'est pas bon. */}
              {video.jobStatus?.result?.integrity && (() => {
                const integ = video.jobStatus.result.integrity
                const okColor = integ.ok ? 'oklch(0.78 0.16 145)' : 'oklch(0.78 0.16 25)'
                return (
                  <div style={{
                    padding: 10, borderRadius: 6,
                    background: integ.ok ? 'oklch(0.65 0.13 145 / 0.06)' : 'oklch(0.55 0.18 25 / 0.06)',
                    border: `1px solid ${integ.ok ? 'oklch(0.65 0.13 145 / 0.30)' : 'oklch(0.55 0.18 25 / 0.40)'}`,
                  }}>
                    <div style={{
                      fontSize: 10, color: 'var(--fg-mute, #888)',
                      letterSpacing: '0.18em', textTransform: 'uppercase',
                      marginBottom: 6,
                    }}>{integ.ok ? '✓ Intégrité validée' : '⚠ Problèmes détectés'}</div>
                    <div style={{
                      display: 'flex', gap: 12, flexWrap: 'wrap',
                      fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                      color: 'var(--fg, #f5f5f5)',
                    }}>
                      <span>📺 {integ.duration_s.toFixed(1)}s</span>
                      <span>🎞 {integ.video_codec || 'no video'}</span>
                      <span>🔊 {integ.has_audio ? integ.audio_codec : 'no audio'}</span>
                      <span>📦 {(integ.size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
                    </div>
                    {integ.errors.length > 0 && (
                      <ul style={{
                        margin: '6px 0 0', paddingLeft: 20,
                        fontSize: 11, color: okColor,
                      }}>
                        {integ.errors.map((e, i) => <li key={i}>{e}</li>)}
                      </ul>
                    )}
                  </div>
                )
              })()}

              {/* Video preview */}
              {video.videoUrl && (
                <video src={video.videoUrl} controls autoPlay loop
                  style={{
                    width: '100%', maxHeight: '60vh',
                    background: '#000', borderRadius: 8,
                    border: `1px solid ${VIOLET}55`,
                    boxShadow: `0 0 80px ${VIOLET}40`,
                  }} />
              )}

              {/* Shots grid */}
              <div style={{
                display: 'grid', gap: 12,
                gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
              }}>
                {video.storyboard.shots.map((shot, i) => (
                  <div key={i} style={{
                    padding: 12, borderRadius: 8,
                    background: 'var(--bg-card, rgba(255,255,255,0.04))',
                    border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
                  }}>
                    <div style={{
                      fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                      color: VIOLET, letterSpacing: '0.14em',
                      textTransform: 'uppercase', marginBottom: 6,
                    }}>Shot {String(i + 1).padStart(2, '0')} · {shot.duration_s}s</div>
                    {/* v82n4 : CinemaShot has `scene` (visual) + `dialogue`
                         (spoken). The earlier code referenced a non-existent
                         `description` field which caused a tsc error and
                         rendered `undefined` to the grid. */}
                    <div style={{ fontSize: 12, color: 'var(--fg, #f5f5f5)', lineHeight: 1.5 }}>
                      {shot.scene}
                    </div>
                    {shot.dialogue && (
                      <div style={{
                        marginTop: 6, fontSize: 11, lineHeight: 1.45,
                        color: 'var(--fg-dim, #aaa)', fontStyle: 'italic',
                      }}>
                        {shot.speaker ? <span style={{ color: VIOLET, fontStyle: 'normal', marginRight: 6 }}>{shot.speaker}:</span> : null}
                        “{shot.dialogue}”
                      </div>
                    )}
                    {shot.camera && (
                      <div style={{
                        marginTop: 6, fontSize: 10,
                        fontFamily: 'var(--font-mono, monospace)',
                        color: 'var(--fg-mute, #888)',
                      }}>📷 {shot.camera}{shot.needs_lipsync ? ' · lipsync' : ''}</div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
        <style>{`@keyframes aurora-spin { to { transform: rotate(360deg); } } .aurora-spin { animation: aurora-spin 1s linear infinite; }`}</style>
      </div>
    )
  }

  const playhead = 30 + Math.sin(t * 0.5) * 8
  const stripOffset = (t * 14) % 28

  return (
    // v82m3 : container scrollable. Avant overflow:hidden + height:100% bloquait
    // tout scroll quand le contenu (storyboard preview + prompt + 12-cell timeline +
    // history) dépassait la viewport. User : "le prompt est à moitié caché par la
    // barre des tâches". Maintenant overflow-y:auto + min-height:100% + paddingBottom
    // pour respirer au-dessus de la taskbar OS (40px) + safe-area inset si mobile.
    <div {...drop.bind} style={{
      minHeight: '100%', display: 'flex', flexDirection: 'column',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)',
      overflowY: 'auto',
      overflowX: 'hidden',
      paddingBottom: 'calc(48px + env(safe-area-inset-bottom, 0px))',
      position: 'relative',
      outline: drop.isDraggingOver ? '2px dashed oklch(0.74 0.13 60)' : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      transition: 'outline 120ms ease',
    }}>
      {/* v82fp : hint visuel pendant drag-over */}
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
          🎬 Déposer brief / scénario · txt / md / pdf / docx
        </div>
      )}
      {/* Projector booth */}
      <div style={{
        flex: 1, position: 'relative', background: 'oklch(0.06 0.01 250)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {/* Radial beam */}
        <div style={{
          position: 'absolute', inset: 0,
          background: `radial-gradient(ellipse 50% 35% at 50% 50%, ${VIOLET}33, transparent 70%)`,
        }} />

        {/* 16:9 frame */}
        <div style={{
          width: '70%', aspectRatio: '16/9', position: 'relative',
          border: '1px solid var(--line-strong, rgba(255,255,255,0.18))',
          background: `repeating-linear-gradient(90deg,
            oklch(0.16 0.02 260) 0,
            oklch(0.16 0.02 260) 14px,
            oklch(0.20 0.03 260) 14px,
            oklch(0.20 0.03 260) 28px)`,
          backgroundPosition: `-${stripOffset}px 0`,
          boxShadow: `0 0 80px ${VIOLET}40`,
        }}>
          <div style={{
            position: 'absolute', top: 14, left: 14,
            display: 'flex', gap: 6, flexWrap: 'wrap',
          }}>
            <Tag accent="var(--ember-500, #ff6a3d)">● REC</Tag>
            <Tag>04 / 12</Tag>
            <Tag accent={VIOLET}>wan2.2-i2v-14B</Tag>
            {/* v82ia : streak vidéo */}
            {videoStreak.current > 0 && (
              <Tag accent={videoStreak.current >= 7 ? 'oklch(0.78 0.16 80)' : undefined}>
                <span title={`Streak Vidéo : ${videoStreak.current} jour(s) · record ${videoStreak.longest}j`}>
                  🔥 {videoStreak.current}j{videoStreak.longest > videoStreak.current ? `/${videoStreak.longest}` : videoStreak.current >= 7 ? ' 🏆' : ''}
                </span>
              </Tag>
            )}
          </div>
          <div style={{
            position: 'absolute', bottom: 14, right: 14,
            fontFamily: 'var(--font-mono, monospace)', fontSize: 11, color: 'var(--fg-dim, #aaa)',
          }}>720p · 16fps · cinema_run #04</div>
          <Crosshair corner="tl" color="var(--fg-mute, #777)" />
          <Crosshair corner="tr" color="var(--fg-mute, #777)" />
          <Crosshair corner="bl" color="var(--fg-mute, #777)" />
          <Crosshair corner="br" color="var(--fg-mute, #777)" />
        </div>
      </div>

      {/* Editorial title + transport */}
      <div style={{
        padding: '28px 40px 16px',
        display: 'flex', alignItems: 'flex-end', gap: 24, flexWrap: 'wrap',
        borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
      }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <Eyebrow dot={VIOLET} style={{ marginBottom: 6 }}>Vidéo · Wan2.2 · Projecteur</Eyebrow>
          <Display size={56}>Cinéma<br/><em style={{ color: 'var(--ember-500, #ff6a3d)' }}>Wan2.2</em></Display>
        </div>
        <button type="button"
          style={{
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            border: '1px solid var(--line, rgba(255,255,255,0.12))',
            color: 'var(--fg-dim, #aaa)', padding: 10, cursor: 'pointer',
            borderRadius: 8,
          }}>
          <SkipBack size={16} />
        </button>
        <button type="button" onClick={() => setLive(true)}
          style={{
            background: 'var(--ember-500, #ff6a3d)', color: '#0a0a0a',
            border: 'none', padding: '14px 18px', cursor: 'pointer',
            borderRadius: 99, fontWeight: 700,
            display: 'inline-flex', alignItems: 'center', gap: 8,
            fontFamily: 'var(--font-sans, system-ui)',
          }}>
          <Play size={18} fill="currentColor" /> Ouvrir la salle
        </button>
        {/* v84 : VideoView re-expose — clip simple sans storyboard. */}
        <button type="button" onClick={() => setClip(true)}
          title="Un prompt → un clip direct (sans storyboard) : presets motion, badges 🎬, Wan2.2/LTX"
          style={{
            background: `${VIOLET}`, color: '#0a0a0a',
            border: 'none', padding: '14px 18px', cursor: 'pointer',
            borderRadius: 99, fontWeight: 700,
            display: 'inline-flex', alignItems: 'center', gap: 8,
            fontFamily: 'var(--font-sans, system-ui)',
          }}>
          <Clapperboard size={18} /> Clip rapide
        </button>
        <button type="button"
          style={{
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            border: '1px solid var(--line, rgba(255,255,255,0.12))',
            color: 'var(--fg-dim, #aaa)', padding: 10, cursor: 'pointer',
            borderRadius: 8,
          }}>
          <SkipForward size={16} />
        </button>
        <button type="button"
          style={{
            background: 'transparent', border: '1px solid var(--line, rgba(255,255,255,0.12))',
            color: 'var(--fg-dim, #aaa)', padding: 10, cursor: 'pointer',
            borderRadius: 8,
          }}>
          <Pause size={16} />
        </button>
        <span style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          color: 'var(--fg-dim, #aaa)', marginLeft: 'auto',
        }}>00:04 / 00:12 · render 38%</span>
      </div>

      {/* v82be : real prompt + storyboard preview row.
          Le user tape un sujet, choisit aspect/length/style, click
          "Générer storyboard" → cinemaGenerateStoryboard via bridge.
          Affiche soit la storyboard JSON, soit la clarification, soit
          l'erreur. "Ouvrir la salle" reste pour le full MangaVideoView. */}
      <div style={{
        padding: '12px 40px',
        borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            id="video-scene-prompt"
            name="videoScenePrompt"
            aria-label="Description de la scène vidéo"
            type="text"
            value={video.prompt}
            onChange={(e) => video.setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                void video.generateStoryboard()
              }
            }}
            placeholder="Décris ta scène… ex. « Une grue cendrée traverse une baie au lever du soleil » (⌘↵)"
            disabled={video.generating}
            style={{
              flex: 1, minWidth: 280, padding: '8px 12px',
              background: 'var(--bg-input, var(--bg-card, rgba(255,255,255,0.04)))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              borderRadius: 6, fontSize: 12,
              fontFamily: 'var(--font-sans, system-ui)',
            }}
          />
          <VoicePushToTalk
            onTranscript={(text) => video.setPrompt((video.prompt ? video.prompt + ' ' : '') + text)}
            label="Dicter la scène vidéo"
            disabled={video.generating}
            variant="ghost"
            size={32}
          />
          {(['16:9', '9:16', '1:1', '4:3'] as VideoAspect[]).map((a) => (
            <button key={a} type="button" onClick={() => video.setAspect(a)}
              style={{
                padding: '6px 10px', fontSize: 11,
                fontFamily: 'var(--font-mono, monospace)',
                background: video.aspect === a ? VIOLET : 'transparent',
                color: video.aspect === a ? '#0a0a0a' : 'var(--fg-dim, #aaa)',
                border: `1px solid ${video.aspect === a ? VIOLET : 'var(--line, rgba(255,255,255,0.12))'}`,
                cursor: 'pointer', borderRadius: 6,
              }}>{a}</button>
          ))}
          {(['short', 'medium', 'long'] as VideoLength[]).map((l) => (
            <button key={l} type="button" onClick={() => video.setLength(l)}
              style={{
                padding: '6px 10px', fontSize: 11,
                fontFamily: 'var(--font-mono, monospace)',
                background: video.length === l ? VIOLET : 'transparent',
                color: video.length === l ? '#0a0a0a' : 'var(--fg-dim, #aaa)',
                border: `1px solid ${video.length === l ? VIOLET : 'var(--line, rgba(255,255,255,0.12))'}`,
                cursor: 'pointer', borderRadius: 6,
              }}>{l}</button>
          ))}
          <button type="button" onClick={() => void video.generateStoryboard()}
            disabled={!video.prompt.trim() || video.generating}
            style={{
              padding: '8px 14px', background: VIOLET, color: '#0a0a0a',
              border: 'none', fontSize: 12, fontWeight: 600,
              cursor: (!video.prompt.trim() || video.generating) ? 'not-allowed' : 'pointer',
              opacity: (!video.prompt.trim() || video.generating) ? 0.5 : 1,
              fontFamily: 'var(--font-sans, system-ui)',
              borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 6,
            }}>{video.generating
              ? <><Loader2 size={13} className="aurora-spin" /> Storyboard…</>
              : <><Send size={13} /> Storyboard</>}</button>
          {/* v82ez : preset surprise (random prompt + style + auto-generate) */}
          {!video.generating && (
            <button type="button"
              onClick={() => {
                video.randomVideoPreset()
                window.setTimeout(() => { void video.generateStoryboard() }, 0)
              }}
              title="Pioche prompt + style au hasard PUIS génère le storyboard"
              style={{
                padding: '8px 14px',
                background: 'oklch(0.74 0.13 60 / 0.10)',
                color: 'oklch(0.74 0.13 60)',
                border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                fontSize: 11, fontWeight: 700,
                fontFamily: 'var(--font-mono, monospace)', cursor: 'pointer',
                borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 4,
              }}>⚡ surprise · go</button>
          )}
          {/* v82hc : ★ favori dans bibliothèque */}
          <FavoriteButton
            prompt={video.prompt}
            module="video"
            parameters={{ style: video.style, aspect: video.aspect, length: video.length }}
            tags={['video', video.style]}
            disabled={video.generating}
          />
        </div>
        {/* v84 : grammaire cinema detectee live (videoPromptComposer) — ces
            directives partent en contrainte dure au realisateur LLM. */}
        {(() => {
          const a = analyzeVideoPrompt(video.prompt)
          const hits = [
            a.shot,
            ...(a.staticCamera ? ['static camera'] : a.camera),
            ...a.lighting,
            a.style,
            a.tempo,
          ].filter(Boolean) as string[]
          if (!video.prompt.trim() || hits.length === 0) return null
          return (
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
              <span style={{
                fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.18em', textTransform: 'uppercase',
                color: 'var(--fg-mute, #888)',
              }}>🎬 détecté</span>
              {hits.map((h) => (
                <span key={h} style={{
                  fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
                  padding: '2px 8px', borderRadius: 99,
                  background: 'oklch(0.6 0.12 300 / 0.14)',
                  color: 'oklch(0.78 0.10 300)',
                  border: '1px solid oklch(0.6 0.12 300 / 0.3)',
                }}>{h}</span>
              ))}
            </div>
          )
        })()}
        {/* v82gs : prompt history persistant cliquable */}
        {video.history.length > 0 && (
          <div style={{ marginTop: 8, paddingTop: 8,
            borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.08))' }}>
            <div style={{
              fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
              letterSpacing: '0.22em', textTransform: 'uppercase',
              color: 'var(--fg-mute, #888)', marginBottom: 4,
            }}>↻ Historique ({video.history.length})</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2,
              maxHeight: 120, overflowY: 'auto' }}>
              {video.history.map((h) => (
                <div key={h.prompt} style={{
                  display: 'grid', gridTemplateColumns: '1fr 22px', gap: 4,
                  alignItems: 'center', padding: '3px 6px', borderRadius: 4,
                  fontSize: 11,
                  background: 'var(--bg-card, rgba(255,255,255,0.03))',
                  border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
                }}>
                  <button type="button" onClick={() => video.recallPrompt(h)} title={h.prompt}
                    style={{
                      background: 'transparent', border: 'none', padding: 0,
                      color: 'var(--fg, #f5f5f5)', cursor: 'pointer', textAlign: 'left',
                      fontFamily: 'inherit', fontSize: 'inherit',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>{h.prompt}</button>
                  <button type="button" onClick={() => video.removeHistory(h.prompt)}
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

        {/* Result row : storyboard summary OR clarification OR error OR
            empty placeholder + 12-cell timeline visible quand pas de
            storyboard pour garder l'editorial layout. */}
        {video.storyboard ? (
          <div style={{
            padding: '10px 12px',
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            border: `1px solid ${VIOLET}30`,
            borderRadius: 6, fontSize: 12, color: 'var(--fg, #f5f5f5)',
          }}>
            <div style={{ fontFamily: 'var(--font-display, serif)', fontStyle: 'italic', fontSize: 18, marginBottom: 6 }}>
              {video.storyboard.title}
            </div>
            <div style={{ color: 'var(--fg-dim, #aaa)', marginBottom: 8, lineHeight: 1.5 }}>
              {video.storyboard.summary}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontFamily: 'var(--font-mono, monospace)', fontSize: 11 }}>
              <span>{video.storyboard.shots.length} shots</span>
              <span>·</span>
              <span>{video.storyboard.aspect}</span>
              <span>·</span>
              <span>{video.storyboard.resolution}</span>
              <span>·</span>
              <span>{video.storyboard.style}</span>
              {video.storyboard.characters.length > 0 && (
                <>
                  <span>·</span>
                  <span>{video.storyboard.characters.length} personnage(s)</span>
                </>
              )}
            </div>
            <button type="button" onClick={() => setLive(true)}
              style={{
                marginTop: 10, padding: '6px 12px',
                background: 'var(--ember-500, #ff6a3d)', color: '#0a0a0a',
                border: 'none', fontSize: 11, fontWeight: 600,
                cursor: 'pointer', borderRadius: 6,
                fontFamily: 'var(--font-sans, system-ui)',
              }}>Lancer le rendu dans la salle complète</button>
          </div>
        ) : video.clarification ? (
          <div style={{
            padding: '10px 12px',
            background: 'var(--bg-card, rgba(255,255,255,0.04))',
            border: '1px solid var(--ember-500, #ff6a3d)33',
            borderRadius: 6, fontSize: 12, color: 'var(--fg-dim, #aaa)',
            fontStyle: 'italic',
          }}>
            <strong style={{ color: 'var(--ember-500, #ff6a3d)' }}>Clarification :</strong>{' '}
            {video.clarification}
          </div>
        ) : video.error ? (
          <div style={{
            padding: '10px 12px',
            background: 'oklch(0.55 0.18 25 / 0.1)',
            border: '1px solid oklch(0.55 0.18 25)',
            borderRadius: 6, fontSize: 12,
            color: 'oklch(0.55 0.18 25)',
          }}>⚠ {video.error}</div>
        ) : (
          <div style={{
            marginTop: 6, padding: '6px 12px',
            fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
            color: 'var(--fg-dim, #aaa)',
            background: 'oklch(0.74 0.13 60 / 0.06)',
            border: '1px solid oklch(0.74 0.13 60 / 0.22)',
            borderRadius: 8, display: 'inline-block',
            maxWidth: 520, lineHeight: 1.55,
          }}>
            {getDailyTip('video')}
          </div>
        )}
      </div>

      {/* 12-cell timeline */}
      <div style={{ padding: '0 40px 24px' }}>
        <div style={{
          height: 60,
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 8, position: 'relative',
          background: 'var(--bg-raised, rgba(255,255,255,0.02))', overflow: 'hidden',
        }}>
          {Array.from({ length: video.storyboard?.shots.length || 12 }).map((_, i) => {
            const cellWidth = 100 / (video.storyboard?.shots.length || 12)
            const isHighlight = video.storyboard ? i === 0 : i === 4
            return (
              <div key={i} style={{
                position: 'absolute', left: `${i * cellWidth}%`, top: 0, bottom: 0,
                width: `${cellWidth}%`,
                borderRight: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
                background: isHighlight ? `${VIOLET}40` : 'transparent',
              }}>
                <span style={{
                  position: 'absolute', top: 4, left: 4,
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
                  color: 'var(--fg-mute, #777)',
                }}>{String(i + 1).padStart(2, '0')}</span>
                {isHighlight && (
                  <span style={{
                    position: 'absolute', bottom: 4, left: 4,
                    fontSize: 9, color: VIOLET,
                    fontFamily: 'var(--font-mono, monospace)',
                  }}>SHOT</span>
                )}
              </div>
            )
          })}
          <div style={{
            position: 'absolute', left: `${playhead}%`, top: 0, bottom: 0,
            width: 2, background: 'var(--ember-500, #ff6a3d)',
            boxShadow: '0 0 12px var(--ember-500, #ff6a3d)',
          }} />
        </div>
      </div>
      <style>{`@keyframes aurora-spin { to { transform: rotate(360deg); } } .aurora-spin { animation: aurora-spin 1s linear infinite; }`}</style>
    </div>
  )
}
