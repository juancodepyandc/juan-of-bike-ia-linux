/**
 * iter41 — Layout mobile-native dédié pour le module Académie.
 *
 * Pas un patch CSS du V1 desktop, mais un VRAI composant pensé portrait :
 *   ┌──────────────────────────┐
 *   │ 🎓 Académie         [📚] │ ← header simple (Banque)
 *   │  BAC STI2D · gold dot    │
 *   ├──────────────────────────┤
 *   │ ╔════════════════════╗   │
 *   │ ║ Upload leçon       ║   │ ← grosse zone de tap
 *   │ ║ tap ou drag        ║   │
 *   │ ╚════════════════════╝   │
 *   │ Matière  [Géographie ▾]  │
 *   │ Niveau   [Term STI2D ▾]  │
 *   │ Sujet                    │
 *   │ ┌────────────────────┐   │
 *   │ │ textarea autogrow  │   │
 *   │ └────────────────────┘   │
 *   │ Mode (chips scrollables) │
 *   │  [parcours-bac][quiz]…   │
 *   ├──────────────────────────┤
 *   │ 🎲 Surprise  ⚡ Surprise+ │ ← actions secondaires
 *   ├──────────────────────────┤
 *   │ [    🎓 Générer    ]     │ ← CTA principal
 *   └──────────────────────────┘
 *
 * Parcours session, bubble Coach, banque, etc. sont mountés en plein écran
 * par-dessus comme sur desktop — déjà responsive (cf iter38/40).
 */
import { lazy, Suspense, useEffect, useRef, useState, useMemo } from 'react'
import { Send, Loader2, Upload, X as XIcon, Image as ImgIcon } from 'lucide-react'
import { useAcademyViewLogic, type AcademyMode, type AcademySubject } from '../hooks/useAcademyViewLogic'

const ParcoursActiveSession = lazy(() => import('./learning/ParcoursActiveSession'))
const ParcoursBankDrawer = lazy(() => import('./learning/ParcoursBankDrawer'))

const GOLD = 'oklch(0.86 0.18 75)'
const GOLD_SOFT = 'oklch(0.86 0.18 75 / 0.16)'
const VIOLET = 'oklch(0.62 0.22 295)'
const BG = 'oklch(0.10 0.012 250)'

export default function AuroraV1AcademyMobile() {
  const academy = useAcademyViewLogic()
  const [parcoursOverlayOpen, setParcoursOverlayOpen] = useState(false)
  const [bankOpen, setBankOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const hasAutoOpenedRef = useRef<string | null>(null)

  // Auto-open overlay quand parcours prêt (parité desktop)
  const parcoursSignature = useMemo(() => {
    const p = academy.parcoursPayload
    if (!p) return ''
    return `${p.synthese_20_20?.titre ?? ''}|${p.controle?.questions?.length ?? 0}|${p.controle?.duration_min ?? 0}`
  }, [academy.parcoursPayload])
  useEffect(() => {
    if (!parcoursSignature) { hasAutoOpenedRef.current = null; return }
    if (hasAutoOpenedRef.current === parcoursSignature) return
    hasAutoOpenedRef.current = parcoursSignature
    const t = window.setTimeout(() => setParcoursOverlayOpen(true), 200)
    return () => window.clearTimeout(t)
  }, [parcoursSignature])

  const onPickFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length > 0) void academy.uploadLessonsMulti(files)
    e.target.value = ''  // reset pour ré-upload du même fichier
  }

  const onPickImages = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    for (const f of files) void academy.addLessonImage(f)
    e.target.value = ''
  }

  return (
    <div style={{
      position: 'relative',
      minHeight: '100dvh',
      width: '100%',
      background: BG,
      color: '#f5f5f5',
      fontFamily: 'var(--font-sans, system-ui)',
      paddingBottom: 110,  // room for sticky CTA
      overflow: 'auto',
    }}>
      {/* Parcours overlay (full-screen) */}
      {parcoursOverlayOpen && academy.parcoursPayload && (
        <Suspense fallback={null}>
          <ParcoursActiveSession
            academy={academy}
            onClose={() => setParcoursOverlayOpen(false)}
          />
        </Suspense>
      )}

      {/* Banque drawer */}
      <Suspense fallback={null}>
        <ParcoursBankDrawer
          open={bankOpen}
          onClose={() => setBankOpen(false)}
          onResume={(entry) => {
            academy.setLessonText(entry.lessonText || '')
            academy.setOutput(`\`\`\`json\n${JSON.stringify(entry.payload, null, 2)}\n\`\`\``)
            window.setTimeout(() => setParcoursOverlayOpen(true), 60)
          }}
        />
      </Suspense>

      {/* HEADER */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 5,
        padding: '14px 16px 10px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
        background: `linear-gradient(180deg, ${BG} 70%, transparent)`,
        backdropFilter: 'blur(6px)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            width: 8, height: 8, borderRadius: 99,
            background: GOLD, boxShadow: `0 0 12px ${GOLD}`,
          }} />
          <div>
            <div style={{
              fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase',
              color: 'rgba(255,255,255,0.5)', fontFamily: 'var(--font-mono, monospace)',
              marginBottom: 2,
            }}>
              BAC STI2D · 2026
            </div>
            <h1 style={{
              fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
              fontStyle: 'italic', fontWeight: 400, fontSize: 26,
              margin: 0, lineHeight: 1, letterSpacing: '-0.02em',
            }}>
              🎓 Académie
            </h1>
          </div>
        </div>
        <button type="button" onClick={() => setBankOpen(true)}
          title="Banque de générations"
          style={{
            padding: '8px 12px', borderRadius: 99,
            background: GOLD_SOFT,
            color: GOLD, border: `1px solid ${GOLD}55`,
            fontSize: 12, fontWeight: 700, cursor: 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6,
            fontFamily: 'var(--font-mono, monospace)',
          }}>
          📚
        </button>
      </header>

      {/* MAIN form */}
      <main style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Upload card big */}
        <button type="button" onClick={() => fileInputRef.current?.click()}
          style={{
            width: '100%', padding: 18,
            border: `1.5px dashed ${GOLD}66`, borderRadius: 14,
            background: 'rgba(255,255,255,0.025)',
            color: 'rgba(255,255,255,0.85)',
            cursor: 'pointer', textAlign: 'left',
            display: 'flex', alignItems: 'center', gap: 14,
          }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: GOLD_SOFT,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: GOLD, flexShrink: 0,
          }}>
            <Upload size={22} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 2 }}>
              {academy.lessonName ? academy.lessonName : 'Upload leçon'}
            </div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)' }}>
              {academy.lessonName
                ? `${(academy.lessonText.length / 1000).toFixed(1)}k caractères extraits · tap pour remplacer`
                : 'PDF / DOCX / TXT · multi-fichiers OK'}
            </div>
          </div>
          {academy.lessonName && (
            <button type="button"
              onClick={(e) => { e.stopPropagation(); academy.clearLesson() }}
              style={{
                padding: 6, borderRadius: 8,
                background: 'transparent', color: 'rgba(255,255,255,0.5)',
                border: '1px solid rgba(255,255,255,0.15)',
                cursor: 'pointer',
              }}>
              <XIcon size={14} />
            </button>
          )}
        </button>
        <input ref={fileInputRef} type="file" multiple
          accept=".txt,.md,.markdown,.pdf,.docx,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          style={{ display: 'none' }}
          onChange={onPickFiles}
        />

        {/* Photo (vision multimodale) si déjà des images */}
        {academy.lessonImages && academy.lessonImages.length > 0 && (
          <div style={{
            padding: 12, borderRadius: 12,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            display: 'flex', flexWrap: 'wrap', gap: 8,
          }}>
            {academy.lessonImages.map((img, i) => (
              <div key={i} style={{ position: 'relative', width: 60, height: 60, borderRadius: 8, overflow: 'hidden' }}>
                <img src={img.dataUrl} alt={img.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                <button type="button"
                  onClick={() => academy.removeLessonImage(i)}
                  style={{
                    position: 'absolute', top: 2, right: 2,
                    width: 18, height: 18, borderRadius: '50%',
                    background: 'rgba(0,0,0,0.7)', color: '#fff',
                    border: 'none', cursor: 'pointer', fontSize: 10,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>×</button>
              </div>
            ))}
          </div>
        )}

        {/* Subject + Level row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{
              fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
              color: 'rgba(255,255,255,0.5)', fontFamily: 'var(--font-mono, monospace)',
            }}>Matière</span>
            <select value={academy.subject}
              onChange={(e) => academy.setSubject(e.target.value as AcademySubject)}
              disabled={academy.streaming}
              style={{
                padding: '11px 12px', fontSize: 14,
                background: 'rgba(255,255,255,0.05)',
                color: '#f5f5f5', border: `1px solid ${GOLD}33`,
                borderRadius: 10, fontFamily: 'inherit',
                appearance: 'none', WebkitAppearance: 'none',
              }}>
              {(Object.keys(academy.subjectLabels) as AcademySubject[]).map((s) => (
                <option key={s} value={s} style={{ background: BG, color: '#fff' }}>
                  {academy.subjectLabels[s]}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{
              fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
              color: 'rgba(255,255,255,0.5)', fontFamily: 'var(--font-mono, monospace)',
            }}>Mode</span>
            <select value={academy.mode}
              onChange={(e) => academy.setMode(e.target.value as AcademyMode)}
              disabled={academy.streaming}
              style={{
                padding: '11px 12px', fontSize: 14,
                background: 'rgba(255,255,255,0.05)',
                color: '#f5f5f5', border: `1px solid ${GOLD}33`,
                borderRadius: 10, fontFamily: 'inherit',
                appearance: 'none', WebkitAppearance: 'none',
              }}>
              {(Object.keys(academy.modeLabels) as AcademyMode[]).map((m) => (
                <option key={m} value={m} style={{ background: BG, color: '#fff' }}>
                  {academy.modeLabels[m]}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* Topic textarea */}
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{
            fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
            color: 'rgba(255,255,255,0.5)', fontFamily: 'var(--font-mono, monospace)',
          }}>Sujet / consigne</span>
          <textarea
            value={academy.topic}
            onChange={(e) => academy.setTopic(e.target.value)}
            disabled={academy.streaming}
            placeholder={
              academy.mode === 'parcours-bac'
                ? 'Ex: "10 questions cours + 1 développement, 1h, géographie mondialisation"'
                : 'Décris ce que tu veux apprendre…'
            }
            rows={4}
            style={{
              padding: 12, fontSize: 16,  // 16px évite zoom iOS
              background: 'rgba(255,255,255,0.05)',
              color: '#f5f5f5', border: `1px solid ${GOLD}33`,
              borderRadius: 10, fontFamily: 'inherit',
              resize: 'vertical', minHeight: 90,
              lineHeight: 1.45,
            }}
          />
        </label>

        {/* Photo additionnelle (vision multimodale) */}
        <label style={{
          padding: '10px 14px',
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.10)',
          borderRadius: 10, cursor: 'pointer',
          display: 'inline-flex', alignItems: 'center', gap: 10,
          fontSize: 13, color: 'rgba(255,255,255,0.7)',
          alignSelf: 'flex-start',
        }}>
          <ImgIcon size={16} />
          Ajouter une photo de fiche
          <input type="file" multiple accept="image/*" onChange={onPickImages}
            style={{ display: 'none' }} />
        </label>

        {/* Surprise actions */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" onClick={() => academy.randomAll()}
            disabled={academy.streaming}
            style={{
              flex: 1, padding: '10px 12px', borderRadius: 10,
              background: 'rgba(255,255,255,0.04)',
              color: 'rgba(255,255,255,0.7)',
              border: '1px dashed rgba(255,255,255,0.18)',
              fontSize: 12, cursor: academy.streaming ? 'not-allowed' : 'pointer',
              fontFamily: 'var(--font-mono, monospace)',
              opacity: academy.streaming ? 0.4 : 1,
            }}>
            🎲 Surprise
          </button>
          <button type="button" onClick={() => void academy.randomAllAndGenerate()}
            disabled={academy.streaming}
            style={{
              flex: 1, padding: '10px 12px', borderRadius: 10,
              background: `linear-gradient(135deg, ${VIOLET}33, ${GOLD}33)`,
              color: GOLD, border: `1px solid ${GOLD}55`,
              fontSize: 12, cursor: academy.streaming ? 'not-allowed' : 'pointer',
              fontFamily: 'var(--font-mono, monospace)', fontWeight: 700,
              opacity: academy.streaming ? 0.4 : 1,
            }}>
            ⚡ Surprise · go
          </button>
        </div>

        {/* Status streaming */}
        {academy.streaming && (
          <div style={{
            padding: '10px 14px', borderRadius: 10,
            background: `linear-gradient(135deg, ${VIOLET}22, ${GOLD}22)`,
            border: `1px solid ${GOLD}55`,
            fontSize: 12, display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} color={GOLD} />
            <div style={{ flex: 1 }}>
              <div style={{ color: GOLD, fontWeight: 700, marginBottom: 2 }}>Aurora travaille…</div>
              <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: 11 }}>
                Synthèse → fiches → exos → contrôle. ~30-90s.
              </div>
            </div>
            <button type="button" onClick={() => academy.abort()}
              style={{
                padding: '4px 10px', fontSize: 11, borderRadius: 6,
                background: 'rgba(231,76,60,0.18)', color: 'rgba(231,76,60,0.95)',
                border: '1px solid rgba(231,76,60,0.45)', cursor: 'pointer',
              }}>
              Stop
            </button>
          </div>
        )}

        {academy.error && (
          <div style={{
            padding: '10px 14px', borderRadius: 10,
            background: 'rgba(231,76,60,0.10)',
            border: '1px solid rgba(231,76,60,0.4)',
            fontSize: 12, color: 'rgba(231,76,60,0.95)',
          }}>
            ⚠ {academy.error}
          </div>
        )}

        {/* Footer hint si parcours déjà généré */}
        {academy.parcoursPayload && !parcoursOverlayOpen && (
          <button type="button" onClick={() => setParcoursOverlayOpen(true)}
            style={{
              padding: '12px 14px', borderRadius: 12,
              background: `linear-gradient(135deg, ${GOLD}AA, oklch(0.78 0.16 60 / 0.6))`,
              color: '#0a0a0a', border: 'none',
              fontSize: 14, fontWeight: 700, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>
            ▶ Reprendre la session active
          </button>
        )}
      </main>

      {/* Sticky CTA */}
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 4,
        padding: '14px 16px calc(env(safe-area-inset-bottom, 0) + 14px)',
        background: `linear-gradient(0deg, ${BG} 60%, transparent)`,
        pointerEvents: 'none',
      }}>
        <button type="button"
          onClick={() => void academy.generate()}
          disabled={academy.streaming || (!academy.topic.trim() && !academy.lessonText.trim())}
          style={{
            pointerEvents: 'auto',
            width: '100%', padding: 16,
            background: academy.streaming || (!academy.topic.trim() && !academy.lessonText.trim())
              ? 'rgba(255,255,255,0.06)'
              : `linear-gradient(135deg, ${GOLD}, oklch(0.78 0.16 60))`,
            color: academy.streaming || (!academy.topic.trim() && !academy.lessonText.trim())
              ? 'rgba(255,255,255,0.4)' : '#0a0a0a',
            border: 'none', borderRadius: 14,
            fontSize: 16, fontWeight: 800,
            cursor: academy.streaming ? 'wait' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            boxShadow: !academy.streaming && (academy.topic.trim() || academy.lessonText.trim())
              ? `0 8px 32px ${GOLD}55`
              : 'none',
            transition: 'background 0.18s, box-shadow 0.18s',
          }}>
          {academy.streaming ? <><Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> Génération…</>
            : <><Send size={16} /> {academy.modeLabels[academy.mode] || 'Générer'}</>}
        </button>
      </div>
    </div>
  )
}
