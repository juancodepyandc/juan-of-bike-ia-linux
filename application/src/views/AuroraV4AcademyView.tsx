import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import AuroraMascot from '../components/generationFx/mascots.tsx'
import { useAcademyViewLogic, type AcademyMode, type AcademySubject } from '../hooks/useAcademyViewLogic.ts'
import { useLearningSessionStore, type LearnerProfile } from '../stores/learningSessionStore.ts'
import { getDailyTip } from '../utils/dailyTip.ts'
import { useAchievementToasts } from '../hooks/useAchievementToasts.ts'
import Sparkline from '../components/Sparkline.tsx'
import TextPreviewExpander from '../components/TextPreviewExpander.tsx'

const AcademyMindMap = lazy(() => import('../components/AcademyMindMap'))
const AcademyFlashcards = lazy(() => import('../components/AcademyFlashcards'))
const AcademyTable = lazy(() => import('../components/AcademyTable'))
const AchievementsPanel = lazy(() => import('../components/AchievementsPanel'))
const WeeklyChallenges = lazy(() => import('../components/WeeklyChallenges'))
const ParcoursActiveSession = lazy(() => import('./learning/ParcoursActiveSession'))
const ParcoursBankDrawer = lazy(() => import('./learning/ParcoursBankDrawer'))
const AcademyTutorPanel = lazy(() => import('./learning/AcademyTutorPanel'))

type Academy = ReturnType<typeof useAcademyViewLogic>

const ACCENT = '#10B981'
const INK = '#0A0F1E'
const TXT = '#E6EAF5'
const SUB = '#8B93A7'
const DIM = '#5A6377'
const RED = '#F0637A'
const MONO = "'Cascadia Code',Consolas,monospace"
const SANS = "'Inter','Segoe UI Variable','Segoe UI',system-ui,sans-serif"

const glass: CSSProperties = {
  background: 'linear-gradient(165deg,rgba(255,255,255,.05),rgba(255,255,255,.015))',
  border: '1px solid rgba(255,255,255,.09)',
  borderRadius: 18,
  backdropFilter: 'blur(18px)',
}

const techLabel: CSSProperties = {
  fontFamily: MONO, fontSize: 10, letterSpacing: '.2em',
  textTransform: 'uppercase', color: SUB,
}

const gradText: CSSProperties = {
  background: `linear-gradient(120deg, #ffffff 25%, ${ACCENT})`,
  WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent',
}

const inputBase: CSSProperties = {
  background: 'rgba(10,15,30,.6)', border: '1px solid rgba(255,255,255,.12)',
  borderRadius: 11, color: TXT, fontFamily: SANS, fontSize: 13,
  padding: '9px 12px', width: '100%', transition: 'all .25s',
}

const primaryBtn: CSSProperties = {
  background: `linear-gradient(120deg, ${ACCENT}, #ffffff33)`,
  color: INK, fontWeight: 750, borderRadius: 12, border: 'none',
  padding: '10px 18px', fontSize: 13, cursor: 'pointer', fontFamily: SANS,
  boxShadow: `0 6px 24px ${ACCENT}66`, transition: 'all .25s',
  display: 'inline-flex', alignItems: 'center', gap: 8, justifyContent: 'center',
}

const ghostBtn: CSSProperties = {
  border: '1px solid rgba(255,255,255,.14)', background: 'rgba(255,255,255,.03)',
  color: SUB, borderRadius: 11, padding: '9px 14px', fontSize: 12,
  cursor: 'pointer', fontFamily: SANS, transition: 'all .25s',
  display: 'inline-flex', alignItems: 'center', gap: 7, justifyContent: 'center',
}

const chip = (active: boolean, disabled?: boolean): CSSProperties => ({
  fontSize: 11, padding: '5px 11px', borderRadius: 999,
  border: `1px solid ${active ? ACCENT : 'rgba(255,255,255,.1)'}`,
  background: active ? ACCENT : 'rgba(255,255,255,.02)',
  color: active ? INK : SUB, fontWeight: active ? 700 : 500,
  cursor: disabled ? 'not-allowed' : 'pointer', fontFamily: SANS,
  opacity: disabled ? 0.5 : 1, transition: 'all .25s',
})

const stripGlyph = (s: string) => s.replace(/^[^A-Za-zÀ-ÿ]+/, '').trim()

const fmtClock = (s: number | null) => {
  if (s == null) return '--:--'
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

function Ic({ size = 14, children }: { size?: number; children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
      style={{ flexShrink: 0 }}>
      {children}
    </svg>
  )
}

const IcUpload = ({ size }: { size?: number }) => (
  <Ic size={size}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></Ic>
)
const IcX = ({ size }: { size?: number }) => (
  <Ic size={size}><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></Ic>
)
const IcImage = ({ size }: { size?: number }) => (
  <Ic size={size}><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></Ic>
)
const IcClipboard = ({ size }: { size?: number }) => (
  <Ic size={size}><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><rect x="8" y="2" width="8" height="4" rx="1" /></Ic>
)
const IcDice = ({ size }: { size?: number }) => (
  <Ic size={size}><rect x="3" y="3" width="18" height="18" rx="4" /><circle cx="8.5" cy="8.5" r="1" fill="currentColor" /><circle cx="15.5" cy="15.5" r="1" fill="currentColor" /><circle cx="15.5" cy="8.5" r="1" fill="currentColor" /><circle cx="8.5" cy="15.5" r="1" fill="currentColor" /></Ic>
)
const IcSend = ({ size }: { size?: number }) => (
  <Ic size={size}><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></Ic>
)
const IcStop = ({ size }: { size?: number }) => (
  <Ic size={size}><rect x="6" y="6" width="12" height="12" rx="2" /></Ic>
)
const IcRefresh = ({ size }: { size?: number }) => (
  <Ic size={size}><polyline points="1 4 1 10 7 10" /><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" /></Ic>
)
const IcDownload = ({ size }: { size?: number }) => (
  <Ic size={size}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></Ic>
)
const IcCopy = ({ size }: { size?: number }) => (
  <Ic size={size}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></Ic>
)
const IcClock = ({ size }: { size?: number }) => (
  <Ic size={size}><circle cx="12" cy="12" r="9" /><polyline points="12 7 12 12 15.5 14" /></Ic>
)
const IcBook = ({ size }: { size?: number }) => (
  <Ic size={size}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></Ic>
)
const IcChat = ({ size }: { size?: number }) => (
  <Ic size={size}><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" /></Ic>
)
const IcAward = ({ size }: { size?: number }) => (
  <Ic size={size}><circle cx="12" cy="8" r="6" /><path d="M15.5 13 17 22l-5-3-5 3 1.5-9" /></Ic>
)
const IcZap = ({ size }: { size?: number }) => (
  <Ic size={size}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></Ic>
)
const IcExpand = ({ size }: { size?: number }) => (
  <Ic size={size}><polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" /><line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" /></Ic>
)
const IcCheck = ({ size }: { size?: number }) => (
  <Ic size={size}><polyline points="20 6 9 17 4 12" /></Ic>
)
const IcFlame = ({ size }: { size?: number }) => (
  <Ic size={size}><path d="M12 22c4.4 0 7-2.8 7-6.5 0-3.2-2-5.3-3.5-7C14 6.7 13 5 13 2c-3 2-5 5-5 8- .9-.9-1.5-2-1.7-3.2C4.8 8.6 5 11 5 15.5 5 19.2 7.6 22 12 22z" /></Ic>
)
const IcLayers = ({ size }: { size?: number }) => (
  <Ic size={size}><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></Ic>
)
const IcMic = ({ size }: { size?: number }) => (
  <Ic size={size}><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10v1a7 7 0 0 0 14 0v-1" /><line x1="12" y1="18" x2="12" y2="22" /></Ic>
)
const IcSpinner = ({ size }: { size?: number }) => (
  <span className="v4aca-spin" style={{ display: 'inline-flex' }}>
    <Ic size={size}><path d="M21 12a9 9 0 1 1-6.2-8.56" /></Ic>
  </span>
)

function SectionLabel({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
      <span style={techLabel}>{children}</span>
      <span aria-hidden="true" style={{
        flex: 1, height: 1, minWidth: 12, alignSelf: 'center',
        background: 'linear-gradient(90deg, rgba(255,255,255,.12), rgba(255,255,255,0))',
      }} />
      {right}
    </div>
  )
}

function StatusDot({ color, pulse }: { color: string; pulse?: boolean }) {
  return (
    <span className={pulse ? 'v4aca-pulse' : undefined} style={{
      width: 7, height: 7, borderRadius: 999, background: color,
      boxShadow: `0 0 10px ${color}`, display: 'inline-block', flexShrink: 0,
    }} />
  )
}

function FormatPicker({ disabled }: { disabled: boolean }) {
  const examFormat = useLearningSessionStore((s) => s.parcours?.profile?.examFormat) ?? 'classique'
  const setFormat = (fmt: 'classique' | NonNullable<LearnerProfile['examFormat']>) => {
    useLearningSessionStore.setState((s) => {
      const cur = s.parcours
      const nextProfile: LearnerProfile = {
        ...(cur?.profile ?? {}),
        examFormat: fmt === 'classique' ? undefined : fmt,
      }
      return {
        parcours: {
          goal: cur?.goal ?? '',
          parcours: cur?.parcours ?? [],
          activePathId: cur?.activePathId ?? null,
          sources: cur?.sources ?? [],
          ...(cur ?? {}),
          profile: nextProfile,
        },
      }
    })
  }
  const isGame = examFormat === 'jeu'
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
      <span style={techLabel}>format du parcours</span>
      <button type="button" disabled={disabled} onClick={() => setFormat('classique')}
        title="Format classique : synthèse, fiches, exos puis contrôle."
        style={chip(!isGame, disabled)}>Classique</button>
      <button type="button" disabled={disabled} onClick={() => setFormat('jeu')}
        title="Mode jeu / enquête : aventure à manches avec clés à débloquer et boss final, contenu narratif injecté dans la génération."
        style={chip(isGame, disabled)}>Jeu / enquête</button>
      {isGame && (
        <span style={{ fontSize: 11, color: ACCENT, fontFamily: MONO }}>
          manches · clés · boss final
        </span>
      )}
    </div>
  )
}

function OralBadge({ a }: { a: Academy }) {
  const [checking, setChecking] = useState(false)
  const cls = a.oralClassification
  const runCheck = async () => {
    if (checking) return
    setChecking(true)
    try { await a.ensureOralClassification() } catch { void 0 } finally { setChecking(false) }
  }
  return (
    <div style={{
      display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12,
      padding: '8px 12px', borderRadius: 11,
      border: `1px solid ${cls?.is_oral ? `${ACCENT}55` : 'rgba(255,255,255,.09)'}`,
      background: cls?.is_oral ? `${ACCENT}12` : 'rgba(255,255,255,.02)',
    }}>
      <span style={{ color: cls?.is_oral ? ACCENT : SUB, display: 'inline-flex' }}><IcMic size={13} /></span>
      <span style={{ fontSize: 12, color: cls ? TXT : DIM, fontFamily: SANS }}>
        {cls
          ? cls.is_oral
            ? `Passation orale détectée · ${cls.language} · format ${cls.format === 'full' ? 'présentation continue' : cls.format === 'mixed' ? 'présentation + questions' : cls.format === 'questions_only' ? 'questions seules' : 'écrit'} · ${cls.duration_min} min`
            : 'Épreuve écrite (classification IA)'
          : 'Format oral / écrit non analysé — détecté automatiquement avant génération'}
      </span>
      <span style={{ flex: 1 }} />
      <button type="button" onClick={() => void runCheck()} disabled={checking || a.streaming}
        style={{ ...ghostBtn, padding: '5px 11px', fontSize: 11 }}>
        {checking ? <IcSpinner size={11} /> : <IcRefresh size={11} />}
        {checking ? 'analyse…' : 'Analyser le format'}
      </button>
    </div>
  )
}

function ParcoursInline({ a, onOpenFull }: { a: Academy; onOpenFull: () => void }) {
  const p = a.parcoursPayload
  if (!p) return null
  const correction = a.parcoursCorrection
  const timeLeft = a.parcoursControleTimeLeftSec
  const box = (accent: string): CSSProperties => ({
    padding: 14, borderRadius: 14,
    background: `${accent}0d`,
    border: `1px solid ${accent}44`,
  })
  const boxTitle: CSSProperties = { ...techLabel, marginBottom: 10 }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <button type="button" className="v4aca-primary" onClick={onOpenFull} style={{ ...primaryBtn, padding: '9px 16px', fontSize: 12 }}>
          <IcExpand size={13} /> Ouvrir la session plein écran
        </button>
        {(p.cartes?.length ?? 0) > 0 && (
          <span style={{ fontSize: 11, color: SUB, fontFamily: MONO }}>
            {p.cartes!.length} croquis cartographique{p.cartes!.length > 1 ? 's' : ''} en plein écran
          </span>
        )}
        {p.is_oral && (
          <span style={{ ...chip(true), cursor: 'default', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <IcMic size={11} /> oral · {p.language || 'langue auto'}
          </span>
        )}
      </div>

      <div style={box(ACCENT)}>
        <div style={boxTitle}>synthèse 20/20 · {p.synthese_20_20.titre}</div>
        <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6, color: ACCENT }}>Ce que tu dois savoir absolument</div>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.55, color: TXT }}>
          {p.synthese_20_20.ce_qu_il_faut_savoir.map((s, i) => <li key={i}>{s}</li>)}
        </ul>
        {p.synthese_20_20.pieges_classiques?.length > 0 && (
          <>
            <div style={{ fontSize: 12, fontWeight: 700, marginTop: 10, marginBottom: 4, color: RED }}>Pièges classiques</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11, lineHeight: 1.5, color: SUB }}>
              {p.synthese_20_20.pieges_classiques.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </>
        )}
        {p.synthese_20_20.vocabulaire_a_maitriser?.length > 0 && (
          <>
            <div style={{ fontSize: 12, fontWeight: 700, marginTop: 10, marginBottom: 6, color: TXT }}>Vocabulaire à maîtriser</div>
            <div style={{ display: 'grid', gap: 6, gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))' }}>
              {p.synthese_20_20.vocabulaire_a_maitriser.map((v, i) => (
                <div key={i} className="v4aca-item" style={{ padding: 8, fontSize: 11, background: 'rgba(10,15,30,.5)', borderRadius: 9, border: '1px solid rgba(255,255,255,.06)', animationDelay: `${Math.min(i, 10) * 40}ms` }}>
                  <strong style={{ color: ACCENT }}>{v.terme}</strong>
                  <div style={{ color: SUB, marginTop: 2, lineHeight: 1.45 }}>{v.definition_exacte}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div style={box('#38BDF8')}>
        <div style={boxTitle}>fiches de révision ({p.fiches.length})</div>
        <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
          {p.fiches.map((f, i) => (
            <div key={i} className="v4aca-item" style={{ padding: 12, borderRadius: 12, background: 'rgba(10,15,30,.5)', border: '1px solid rgba(56,189,248,.22)', animationDelay: `${Math.min(i, 10) * 50}ms` }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4, color: TXT }}>{stripGlyph(f.titre) || f.titre}</div>
              <div style={{ fontSize: 11, color: SUB, marginBottom: 6, lineHeight: 1.45 }}>{f.definition}</div>
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11, lineHeight: 1.5, color: TXT }}>
                {f.idees_cles.map((k, j) => <li key={j}>{k}</li>)}
              </ul>
              {f.developpement_court && (
                <div style={{ marginTop: 8, fontSize: 11, lineHeight: 1.55, color: SUB, borderTop: '1px dashed rgba(255,255,255,.08)', paddingTop: 8 }}>
                  {f.developpement_court}
                </div>
              )}
              {f.schema_ascii_ou_data && (
                <pre style={{ marginTop: 8, marginBottom: 0, fontSize: 10, padding: 8, background: 'rgba(0,0,0,.35)', borderRadius: 8, overflow: 'auto', maxHeight: 180, color: TXT, fontFamily: MONO }}>{f.schema_ascii_ou_data}</pre>
              )}
              {f.mnemonique && (
                <div style={{ marginTop: 8, padding: '6px 9px', fontSize: 10.5, background: `${ACCENT}14`, borderRadius: 8, color: ACCENT }}>
                  Mnémo : {f.mnemonique}
                </div>
              )}
              {(f.ressources_externes?.length ?? 0) > 0 && (
                <div style={{ marginTop: 6, fontSize: 10, color: DIM, lineHeight: 1.5, overflowWrap: 'anywhere' }}>
                  {f.ressources_externes!.join(' · ')}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {p.exos_apprentissage?.length > 0 && (
        <div style={box('#A78BFA')}>
          <div style={boxTitle}>exercices d&apos;apprentissage ({p.exos_apprentissage.length})</div>
          <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
            {p.exos_apprentissage.map((e, i) => (
              <details key={i} className="v4aca-item" style={{ padding: 10, fontSize: 11, background: 'rgba(10,15,30,.5)', borderRadius: 10, border: '1px solid rgba(167,139,250,.22)', cursor: 'pointer', animationDelay: `${Math.min(i, 10) * 45}ms` }}>
                <summary style={{ fontWeight: 600, color: TXT, lineHeight: 1.45 }}>
                  <span style={{ color: '#A78BFA', marginRight: 6, fontFamily: MONO, fontSize: 10, textTransform: 'uppercase', letterSpacing: '.08em' }}>{e.type}</span>
                  {e.question}
                </summary>
                <div style={{ marginTop: 8, color: TXT, lineHeight: 1.5 }}>
                  <strong style={{ color: ACCENT }}>Réponse :</strong> {e.reponse}
                  {e.indice && <div style={{ color: SUB, fontSize: 10.5, marginTop: 4 }}>Indice : {e.indice}</div>}
                </div>
              </details>
            ))}
          </div>
        </div>
      )}

      <div style={box(RED)}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <div style={boxTitle}>contrôle d&apos;évaluation</div>
          <span style={{ fontSize: 11, color: SUB, fontFamily: MONO }}>
            {p.controle.duration_min} min · {p.controle.points_questions + p.controle.points_developpement} pts
          </span>
        </div>
        {!a.parcoursControleStartedAt && !correction && (
          <button type="button" className="v4aca-primary" onClick={a.startParcoursControle}
            style={{ ...primaryBtn, marginTop: 6, padding: '9px 16px', fontSize: 12 }}>
            <IcClock size={13} /> Démarrer le contrôle ({p.controle.duration_min} min)
          </button>
        )}
        {a.parcoursControleStartedAt && !correction && (
          <>
            <div style={{
              marginTop: 10, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 12px', borderRadius: 11,
              background: timeLeft != null && timeLeft < 300 ? `${RED}1c` : 'rgba(10,15,30,.5)',
              border: `1px solid ${timeLeft != null && timeLeft < 300 ? `${RED}66` : 'rgba(255,255,255,.08)'}`,
            }}>
              <StatusDot color={timeLeft != null && timeLeft < 300 ? RED : ACCENT} pulse />
              <span style={{ fontFamily: MONO, fontSize: 17, fontWeight: 700, color: timeLeft != null && timeLeft < 300 ? RED : TXT, fontVariantNumeric: 'tabular-nums' }}>
                {fmtClock(timeLeft)}
              </span>
              <span style={{ fontSize: 11, color: SUB }}>temps restant</span>
            </div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8, color: TXT }}>Questions courtes ({p.controle.points_questions} pts)</div>
              {p.controle.questions.map((q) => (
                <div key={q.id} style={{ marginBottom: 10 }}>
                  <label style={{ display: 'block', fontSize: 12, marginBottom: 5, color: TXT, lineHeight: 1.45 }}>
                    <strong style={{ color: ACCENT }}>Q{q.id}</strong> ({q.points} pts) — {q.q}
                  </label>
                  <textarea className="v4aca-input" rows={2}
                    value={a.parcoursAnswers[q.id] || ''}
                    onChange={(ev) => a.setParcoursAnswer(q.id, ev.target.value)}
                    style={{ ...inputBase, resize: 'vertical', fontSize: 12 }} />
                </div>
              ))}
            </div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6, color: TXT }}>
                Développement construit ({p.controle.points_developpement} pts)
              </div>
              <div style={{ fontSize: 12, marginBottom: 8, padding: '8px 11px', background: 'rgba(10,15,30,.5)', borderRadius: 10, border: '1px solid rgba(255,255,255,.06)', color: TXT, lineHeight: 1.5 }}>
                <strong style={{ color: ACCENT }}>Sujet :</strong> {p.controle.developpement.consigne}
              </div>
              {p.controle.developpement.plan_indicatif?.length > 0 && (
                <div style={{ fontSize: 11, color: SUB, marginBottom: 8 }}>
                  Plan indicatif : {p.controle.developpement.plan_indicatif.join(' · ')}
                </div>
              )}
              <textarea className="v4aca-input" rows={12}
                value={a.parcoursDevAnswer}
                onChange={(ev) => a.setParcoursDevAnswer(ev.target.value)}
                placeholder="Rédige ici ton développement construit (intro, axes, conclusion)…"
                style={{ ...inputBase, resize: 'vertical', minHeight: 180, fontSize: 12 }} />
            </div>
            <button type="button" className="v4aca-primary" onClick={() => void a.submitParcoursControle()}
              disabled={a.parcoursCorrecting}
              style={{ ...primaryBtn, padding: '10px 20px', fontSize: 12, cursor: a.parcoursCorrecting ? 'wait' : 'pointer' }}>
              {a.parcoursCorrecting ? <IcSpinner size={13} /> : <IcCheck size={13} />}
              {a.parcoursCorrecting ? 'Correction en cours…' : 'Soumettre pour correction'}
            </button>
          </>
        )}
        {correction && (
          <div style={{ marginTop: 10, padding: 14, borderRadius: 12, background: 'rgba(10,15,30,.5)', border: `1px solid ${ACCENT}55` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, paddingBottom: 10, borderBottom: '1px solid rgba(255,255,255,.08)', marginBottom: 10 }}>
              <div style={{ fontSize: 34, fontWeight: 800, letterSpacing: '-0.02em', color: correction.total >= 16 ? ACCENT : correction.total >= 12 ? '#EAB308' : RED }}>
                {correction.total}/{correction.total_max}
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: TXT }}>Mention : {correction.mention}</div>
                <div style={{ fontSize: 11, color: SUB }}>
                  Questions : {correction.questions_score}/{p.controle.points_questions} · Développement : {correction.developpement_score}/{p.controle.points_developpement}
                </div>
              </div>
            </div>
            <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 6, color: TXT }}>Détail par question</div>
            {correction.questions_breakdown.map((qb) => (
              <div key={qb.id} style={{ fontSize: 11, marginBottom: 4, padding: '5px 8px', background: 'rgba(255,255,255,.03)', borderRadius: 7, color: SUB, lineHeight: 1.5 }}>
                <strong style={{ color: TXT }}>Q{qb.id}</strong>{' '}
                <span style={{ color: ACCENT, fontFamily: MONO }}>{qb.awarded}/{qb.max}</span> — {qb.comment}
              </div>
            ))}
            <div style={{ fontSize: 11, fontWeight: 700, marginTop: 10, marginBottom: 4, color: TXT }}>Développement</div>
            <div style={{ fontSize: 11, padding: '8px 10px', background: 'rgba(255,255,255,.03)', borderRadius: 8, color: SUB, lineHeight: 1.55 }}>
              <div style={{ display: 'flex', gap: 12, fontFamily: MONO, fontSize: 10, marginBottom: 6, flexWrap: 'wrap', color: TXT }}>
                <span>plan {correction.developpement_breakdown.plan_score}</span>
                <span>contenu {correction.developpement_breakdown.contenu_score}</span>
                <span>rigueur {correction.developpement_breakdown.rigueur_score}</span>
                <span>expression {correction.developpement_breakdown.expression_score}</span>
              </div>
              <div style={{ marginBottom: 6, color: TXT }}>{correction.developpement_breakdown.feedback}</div>
              {correction.developpement_breakdown.erreurs?.length > 0 && (
                <div style={{ color: RED, fontSize: 10.5 }}>
                  Erreurs : {correction.developpement_breakdown.erreurs.join(' · ')}
                </div>
              )}
              <div style={{ marginTop: 6, color: ACCENT }}>
                Progression : {correction.developpement_breakdown.progression}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function EpreuvePanel({ a }: { a: Academy }) {
  return (
    <div className="v4aca-card" style={{ ...glass, padding: 18, animationDelay: '90ms' }}>
      <SectionLabel right={
        a.session === 'epreuve'
          ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 10, fontFamily: MONO, color: RED, letterSpacing: '.14em', textTransform: 'uppercase' }}><StatusDot color={RED} pulse /> live</span>
          : <span style={{ fontSize: 10, fontFamily: MONO, color: DIM, letterSpacing: '.14em', textTransform: 'uppercase' }}>mode libre</span>
      }>épreuve chronométrée</SectionLabel>
      {a.session === 'epreuve' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <span style={{ fontFamily: MONO, fontSize: 30, fontWeight: 700, color: a.epreuveTimeLeftSec < 60 ? RED : TXT, fontVariantNumeric: 'tabular-nums' }}>
              {fmtClock(a.epreuveTimeLeftSec)}
            </span>
            <span style={{ fontSize: 11, color: SUB }}>sur {Math.round(a.epreuveDurationSec / 60)} min</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontFamily: MONO, fontSize: 15, fontWeight: 700, color: ACCENT }}>{a.epreuveScore} pts</span>
          </div>
          {a.mode === 'flashcards' && (
            <div style={{ fontSize: 11, color: SUB }}>
              Confiance flashcards : <strong style={{ color: ACCENT }}>{a.flashcardsConfidence}%</strong> (bonus jusqu&apos;à 500 pts)
            </div>
          )}
          <button type="button" onClick={() => a.stopEpreuve('abandon')}
            style={{ ...ghostBtn, borderColor: `${RED}55`, color: RED }}>
            <IcStop size={12} /> Terminer l&apos;épreuve
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontSize: 12, color: SUB, lineHeight: 1.5 }}>
            Lance un timer, génère puis termine avant la fin : score = production + vitesse + confiance flashcards.
          </div>
          <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
            {[600, 1200, 1800, 2700].map((sec) => (
              <button key={sec} type="button" onClick={() => a.startEpreuve(sec)} disabled={a.streaming}
                style={chip(false, a.streaming)}>{Math.round(sec / 60)} min</button>
            ))}
          </div>
        </div>
      )}
      {a.epreuveResult && a.session === 'libre' && (
        <div style={{
          marginTop: 12, padding: '10px 12px', borderRadius: 11,
          background: a.epreuveResult.timeoutHit ? `${RED}12` : `${ACCENT}10`,
          border: `1px solid ${a.epreuveResult.timeoutHit ? `${RED}44` : `${ACCENT}44`}`,
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: a.epreuveResult.timeoutHit ? RED : ACCENT, marginBottom: 4 }}>
            {a.epreuveResult.timeoutHit ? 'Temps écoulé' : 'Session enregistrée'}
          </div>
          <div style={{ fontSize: 11, color: SUB, display: 'flex', gap: 12, flexWrap: 'wrap', fontFamily: MONO }}>
            <span>score <strong style={{ color: TXT }}>{a.epreuveResult.score}</strong></span>
            <span>{Math.floor(a.epreuveResult.durationMs / 60000)}m {Math.floor((a.epreuveResult.durationMs / 1000) % 60)}s</span>
            <span>limite {Math.round(a.epreuveResult.durationLimitSec / 60)} min</span>
            {a.epreuveResult.flashcardsConfidence !== undefined && (
              <span>flashcards {a.epreuveResult.flashcardsConfidence}%</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function PalmaresPanel({ a }: { a: Academy }) {
  const rankColor = (i: number) => (i === 0 ? ACCENT : i === 1 ? '#38BDF8' : '#A78BFA')
  return (
    <div className="v4aca-card" style={{ ...glass, padding: 18, animationDelay: '150ms' }}>
      <SectionLabel right={
        a.scoreCumulativeSeries.length >= 3
          ? <Sparkline values={a.scoreCumulativeSeries} width={110} height={20} color={ACCENT} smooth smoothWindow={5} showAxis />
          : undefined
      }>palmarès</SectionLabel>
      <div style={{ display: 'flex', gap: 14, alignItems: 'baseline', flexWrap: 'wrap', marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.02em', color: TXT, ...gradText }}>{a.totalAcademyPoints}</div>
          <div style={{ ...techLabel, fontSize: 9 }}>points cumulés</div>
        </div>
        {a.academyStreak.current > 0 && (
          <div>
            <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.02em', color: ACCENT, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <IcFlame size={17} />{a.academyStreak.current}j
            </div>
            <div style={{ ...techLabel, fontSize: 9 }}>série · record {a.academyStreak.longest}j</div>
          </div>
        )}
        {a.bestMention && (
          <div title={`Score moyen all-time : ${a.bestMention.avg} pts`}>
            <div style={{ fontSize: 15, fontWeight: 750, color: ACCENT, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <IcAward size={14} />{a.bestMention.label}
            </div>
            <div style={{ ...techLabel, fontSize: 9 }}>mention · moy {a.bestMention.avg}</div>
          </div>
        )}
      </div>
      {a.topRuns.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 12 }}>
          {a.topRuns.map((r, i) => (
            <div key={i} className="v4aca-item" style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 11, color: SUB, fontFamily: MONO, animationDelay: `${Math.min(i, 8) * 55}ms` }}>
              <span style={{
                width: 16, height: 16, borderRadius: 5, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                background: `${rankColor(i)}22`, color: rankColor(i), fontSize: 9, fontWeight: 700,
              }}>{i + 1}</span>
              <span style={{ fontWeight: 700, color: TXT, minWidth: 38, fontVariantNumeric: 'tabular-nums' }}>{r.score}</span>
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 90 }}>{r.subject}</span>
              <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.topic}</span>
              <span>{Math.floor(r.durationMs / 60000)}m</span>
              {r.timeoutHit && <span style={{ color: RED }} title="Temps écoulé"><IcClock size={11} /></span>}
            </div>
          ))}
        </div>
      ) : (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 9,
          padding: '16px 10px 20px', textAlign: 'center', marginBottom: 12,
        }}>
          <div style={{ position: 'relative', display: 'flex' }}>
            <div aria-hidden="true" style={{
              position: 'absolute', inset: -18, borderRadius: 999, pointerEvents: 'none',
              background: `radial-gradient(circle, ${ACCENT}24, transparent 70%)`, filter: 'blur(5px)',
            }} />
            <AuroraMascot module="learning" size={90} />
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: TXT }}>Aucune épreuve au tableau pour l&apos;instant.</div>
          <div style={{ fontSize: 11.5, color: SUB, lineHeight: 1.55, maxWidth: 260 }}>
            Lance une épreuve chronométrée juste au-dessus : je note ta production, ta vitesse et ta confiance, puis j&apos;inscris ton premier score ici.
          </div>
          <span style={{
            ...techLabel, fontSize: 9, color: ACCENT, padding: '4px 11px', borderRadius: 999,
            border: `1px solid ${ACCENT}33`, background: `${ACCENT}0d`,
          }}>score = production + vitesse + confiance</span>
        </div>
      )}
      {Object.keys(a.runsBySubject).length >= 2 && (
        <>
          <div style={{ ...techLabel, fontSize: 9, marginBottom: 8 }}>best par matière</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 7 }}>
            {Object.entries(a.runsBySubject).map(([subj, runs], si) => {
              const series = a.seriesBySubject[subj] || []
              return (
                <div key={subj} className="v4aca-item" style={{ padding: 8, borderRadius: 10, background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.06)', animationDelay: `${Math.min(si, 8) * 50}ms` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
                    <span style={{ fontSize: 10, color: ACCENT, flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: MONO }}>{subj}</span>
                    {series.length >= 2 && <Sparkline values={series} width={42} height={12} color={ACCENT} />}
                  </div>
                  {runs.map((r, i) => (
                    <div key={i} style={{ display: 'flex', gap: 5, fontSize: 10, color: SUB, fontFamily: MONO, alignItems: 'center' }}>
                      <span style={{ color: rankColor(i), fontWeight: 700 }}>{i + 1}</span>
                      <span style={{ fontWeight: 700, color: TXT, minWidth: 28, fontVariantNumeric: 'tabular-nums' }}>{r.score}</span>
                      <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.topic}</span>
                      {r.timeoutHit && <span style={{ color: RED }}><IcClock size={9} /></span>}
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

function OutputPanel({ a, onOpenParcours }: { a: Academy; onOpenParcours: () => void }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    if (!copied) return
    const t = window.setTimeout(() => setCopied(false), 1600)
    return () => window.clearTimeout(t)
  }, [copied])
  if (!a.hasResult && !a.streaming && !a.error) return null
  const fallbackPre = (label: string) => (
    <div style={{ fontFamily: MONO, fontSize: 11, color: SUB, padding: 10 }}>{label}</div>
  )
  return (
    <div className="v4aca-card" style={{ ...glass, padding: 18, animationDelay: '120ms' }}>
      <SectionLabel right={
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          {a.streaming && <StatusDot color={ACCENT} pulse />}
          {a.hasResult && !a.streaming && a.output && (
            <button type="button"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(a.output)
                  setCopied(true)
                } catch { void 0 }
              }}
              style={{ ...ghostBtn, padding: '5px 11px', fontSize: 11, color: copied ? ACCENT : SUB, borderColor: copied ? `${ACCENT}66` : 'rgba(255,255,255,.14)' }}>
              {copied ? <IcCheck size={11} /> : <IcCopy size={11} />}
              {copied ? 'copié' : 'copier'}
            </button>
          )}
        </span>
      }>
        {a.streaming ? 'génération en direct' : `sortie · ${stripGlyph(a.modeLabels[a.mode])}`}
      </SectionLabel>

      {a.mode === 'parcours-bac' && a.streaming && (
        <div style={{
          padding: '9px 12px', marginBottom: 10, borderRadius: 11,
          background: `${ACCENT}10`, border: `1px solid ${ACCENT}44`,
          fontSize: 11.5, color: TXT, lineHeight: 1.55, fontFamily: SANS,
        }}>
          Parcours BAC complet en assemblage : synthèse, fiches, exos, contrôle et développement.
          Compte 1 à 3 minutes pour la première sortie.
          {a.thinkingChars > 0 && a.output.length === 0 && (
            <span style={{ marginLeft: 6, color: ACCENT, fontFamily: MONO, fontSize: 11 }}>
              le modèle réfléchit · {Math.round(a.thinkingChars / 4)} tokens
            </span>
          )}
        </div>
      )}

      {a.mode === 'mind-map' && !a.streaming && a.mermaidCode ? (
        <Suspense fallback={fallbackPre('chargement du moteur Mermaid…')}>
          <AcademyMindMap code={a.mermaidCode} dark height={420} />
        </Suspense>
      ) : a.mode === 'graph' && !a.streaming && a.graphCode ? (
        <Suspense fallback={fallbackPre('chargement du moteur Mermaid…')}>
          <AcademyMindMap code={a.graphCode} dark height={420} />
        </Suspense>
      ) : a.mode === 'table' && !a.streaming && a.table ? (
        <Suspense fallback={fallbackPre('mise en forme du tableau…')}>
          <AcademyTable data={a.table} />
        </Suspense>
      ) : a.mode === 'flashcards' && !a.streaming && a.flashcards && a.flashcards.length > 0 ? (
        <>
          <Suspense fallback={fallbackPre('préparation du deck…')}>
            <AcademyFlashcards cards={a.flashcards} onConfidenceChange={a.setFlashcardsConfidence} />
          </Suspense>
          {a.flashcardsConfidence > 0 && (
            <div style={{ marginTop: 8, fontSize: 11, color: SUB, fontFamily: MONO }}>
              confiance mémorisation : <strong style={{ color: ACCENT }}>{a.flashcardsConfidence}%</strong>
            </div>
          )}
        </>
      ) : a.mode === 'parcours-bac' && !a.streaming && a.parcoursPayload ? (
        <ParcoursInline a={a} onOpenFull={onOpenParcours} />
      ) : (
        <pre style={{
          fontFamily: MONO, fontSize: 12, lineHeight: 1.65, margin: 0,
          color: TXT, whiteSpace: 'pre-wrap', maxHeight: 380, overflow: 'auto',
        }}>
          {a.output}
          {a.streaming && <span className="v4aca-caret" style={{ display: 'inline-block', width: 7, height: 13, background: ACCENT, verticalAlign: 'text-bottom' }} />}
        </pre>
      )}

      {a.error && (
        <div style={{
          marginTop: 10, padding: '9px 12px', borderRadius: 11, fontSize: 12,
          background: `${RED}12`, border: `1px solid ${RED}44`, color: RED, lineHeight: 1.5,
        }}>
          {a.error}
        </div>
      )}

      {a.mode === 'streak' && !a.streaming && a.hasResult && (
        <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center', paddingTop: 12, borderTop: '1px dashed rgba(255,255,255,.08)', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: SUB, fontFamily: MONO, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <IcFlame size={12} /> série {a.streakIndex + 1} · {a.streakHistory.length} concept{a.streakHistory.length > 1 ? 's' : ''} couvert{a.streakHistory.length > 1 ? 's' : ''}
          </span>
          {a.streakHistory.length > 0 && (
            <span style={{ fontSize: 10, color: DIM, flexBasis: '100%', lineHeight: 1.5 }}>
              {a.streakHistory.join(' · ')}
            </span>
          )}
          <span style={{ flex: 1 }} />
          <button type="button" onClick={a.resetStreak} style={{ ...ghostBtn, padding: '6px 12px', fontSize: 11 }}>
            <IcRefresh size={11} /> Recommencer
          </button>
          <button type="button" className="v4aca-primary" onClick={() => void a.nextStreakExo()} style={{ ...primaryBtn, padding: '7px 14px', fontSize: 11 }}>
            Exo suivant
          </button>
        </div>
      )}
    </div>
  )
}

export default function AuroraV4LearningView() {
  const academy = useAcademyViewLogic()
  useAchievementToasts()
  const [tab, setTab] = useState<'atelier' | 'conversation'>('atelier')
  const [bankOpen, setBankOpen] = useState(false)
  const [parcoursOverlayOpen, setParcoursOverlayOpen] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const hasAutoOpenedRef = useRef<string | null>(null)
  const studioRef = useRef<HTMLDivElement | null>(null)

  const parcoursSignature = useMemo(() => {
    const p = academy.parcoursPayload
    if (!p) return ''
    return `${p.synthese_20_20?.titre ?? ''}|${p.controle?.questions?.length ?? 0}|${p.controle?.duration_min ?? 0}`
  }, [academy.parcoursPayload])

  useEffect(() => {
    if (!parcoursSignature) {
      hasAutoOpenedRef.current = null
      return
    }
    if (hasAutoOpenedRef.current === parcoursSignature) return
    hasAutoOpenedRef.current = parcoursSignature
    const t = window.setTimeout(() => setParcoursOverlayOpen(true), 200)
    return () => window.clearTimeout(t)
  }, [parcoursSignature])

  const handleCreateParcoursFromTutor = (topicVal: string, gameMode: boolean) => {
    useLearningSessionStore.setState((s) => {
      const cur = s.parcours
      return {
        parcours: {
          goal: cur?.goal ?? '',
          parcours: cur?.parcours ?? [],
          activePathId: cur?.activePathId ?? null,
          sources: cur?.sources ?? [],
          ...(cur ?? {}),
          profile: { ...(cur?.profile ?? {}), examFormat: gameMode ? 'jeu' : undefined },
        },
      }
    })
    academy.setTopic(topicVal)
    academy.setMode('parcours-bac')
    setTab('atelier')
    window.setTimeout(() => {
      studioRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      void academy.generate()
    }, 60)
  }

  const onDropFiles = async (files: File[]) => {
    const imageFiles = files.filter((f) => f.type.startsWith('image/'))
    const lessonFiles = files.filter((f) =>
      !f.type.startsWith('image/') && (
        f.type.startsWith('text/')
        || f.type === 'application/pdf'
        || f.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        || /\.(txt|md|markdown|pdf|docx)$/i.test(f.name)
      ),
    )
    for (const f of imageFiles) await academy.addLessonImage(f)
    if (lessonFiles.length === 1) await academy.uploadLesson(lessonFiles[0])
    else if (lessonFiles.length > 1) await academy.uploadLessonsMulti(lessonFiles)
  }

  const canExport = academy.hasResult || academy.lessonText.trim().length > 0 || academy.topic.trim().length > 0

  return (
    <div className="v4aca-root" style={{ padding: '22px 26px', minHeight: '100%', color: TXT, fontFamily: SANS }}>
      <style>{`
        @keyframes v4acaIn { from { opacity: 0; transform: translateY(12px) } to { opacity: 1; transform: translateY(0) } }
        @keyframes v4acaPulse { 0%, 100% { opacity: 1 } 50% { opacity: .3 } }
        @keyframes v4acaBlink { 50% { opacity: 0 } }
        @keyframes v4acaSpin { to { transform: rotate(360deg) } }
        @keyframes v4acaSheen { 0% { left: -70%; opacity: 0 } 12% { opacity: 1 } 100% { left: 135%; opacity: 0 } }
        @keyframes v4acaFloat { 0%, 100% { transform: translateY(0) } 50% { transform: translateY(-4px) } }
        .v4aca-root { position: relative; isolation: isolate }
        .v4aca-root::before {
          content: ''; position: absolute; inset: 0; z-index: -1; pointer-events: none;
          background:
            radial-gradient(640px 420px at 10% 4%, ${ACCENT}14, transparent 62%),
            radial-gradient(560px 400px at 92% 26%, ${ACCENT}0d, transparent 60%),
            radial-gradient(760px 520px at 48% 100%, ${ACCENT}0a, transparent 65%);
        }
        .v4aca-root::after {
          content: ''; position: absolute; inset: 0; z-index: -1; pointer-events: none;
          background-image: radial-gradient(rgba(230,234,245,.05) 1px, transparent 1.4px);
          background-size: 26px 26px;
          -webkit-mask-image: radial-gradient(ellipse 95% 75% at 50% 0%, #000 25%, transparent 100%);
          mask-image: radial-gradient(ellipse 95% 75% at 50% 0%, #000 25%, transparent 100%);
        }
        .v4aca-root ::selection { background: ${ACCENT}59; color: #fff }
        .v4aca-root ::-webkit-scrollbar { width: 7px; height: 7px }
        .v4aca-root ::-webkit-scrollbar-track { background: transparent }
        .v4aca-root ::-webkit-scrollbar-thumb { background: rgba(255,255,255,.13); border-radius: 999px }
        .v4aca-root ::-webkit-scrollbar-thumb:hover { background: ${ACCENT}8c }
        .v4aca-card {
          animation: v4acaIn .55s cubic-bezier(.22,1,.36,1) backwards;
          transition: transform .35s cubic-bezier(.22,1,.36,1), box-shadow .35s ease;
        }
        .v4aca-card:hover {
          transform: translateY(-2px);
          box-shadow: inset 0 0 0 1px ${ACCENT}3d, 0 20px 44px -22px ${ACCENT}33, 0 30px 60px -30px rgba(0,0,0,.65);
        }
        .v4aca-card.v4aca-static:hover { transform: none; box-shadow: none }
        .v4aca-item { animation: v4acaIn .45s cubic-bezier(.22,1,.36,1) backwards }
        .v4aca-pulse { animation: v4acaPulse 1.6s ease-in-out infinite }
        .v4aca-caret { animation: v4acaBlink 1s steps(2) infinite }
        .v4aca-spin { animation: v4acaSpin 1s linear infinite }
        .v4aca-float { animation: v4acaFloat 5.5s ease-in-out infinite }
        .v4aca-input:focus { outline: none; border-color: ${ACCENT} !important; box-shadow: 0 0 16px ${ACCENT}40 }
        .v4aca-primary { position: relative; overflow: hidden }
        .v4aca-primary::after {
          content: ''; position: absolute; top: -40%; bottom: -40%; left: -70%; width: 45%;
          background: linear-gradient(100deg, transparent, rgba(255,255,255,.5), transparent);
          transform: skewX(-18deg); opacity: 0; pointer-events: none;
        }
        .v4aca-primary:hover { transform: translateY(-2px); filter: saturate(1.12) brightness(1.06) }
        .v4aca-primary:hover::after { animation: v4acaSheen .9s ease }
        .v4aca-ghost:hover { border-color: ${ACCENT}59 !important; color: ${TXT}; transform: translateY(-1px) }
        @media (prefers-reduced-motion: reduce) {
          .v4aca-card, .v4aca-item, .v4aca-float, .v4aca-pulse, .v4aca-caret { animation: none }
          .v4aca-card:hover, .v4aca-primary:hover, .v4aca-ghost:hover { transform: none }
        }
        @media (max-width: 1180px) { .v4aca-grid { grid-template-columns: 1fr !important } }
        @media (max-width: 700px) {
          .v4aca-root { padding: 14px 12px !important }
          .v4aca-root input[type="text"], .v4aca-root textarea, .v4aca-root select { font-size: 16px !important }
        }
      `}</style>

      {parcoursOverlayOpen && academy.parcoursPayload && (
        <Suspense fallback={null}>
          <ParcoursActiveSession academy={academy} onClose={() => setParcoursOverlayOpen(false)} />
        </Suspense>
      )}

      <Suspense fallback={null}>
        <ParcoursBankDrawer
          open={bankOpen}
          onClose={() => setBankOpen(false)}
          onResume={(entry) => {
            academy.setLessonText(entry.lessonText || '')
            academy.setOutput(`\`\`\`json\n${JSON.stringify(entry.payload, null, 2)}\n\`\`\``)
            setBankOpen(false)
            window.setTimeout(() => setParcoursOverlayOpen(true), 60)
          }}
        />
      </Suspense>

      <header className="v4aca-card v4aca-static" style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 18, flexWrap: 'wrap' }}>
        <div className="v4aca-float" style={{ position: 'relative', display: 'flex', flexShrink: 0 }}>
          <div aria-hidden="true" style={{
            position: 'absolute', inset: -16, borderRadius: 999, pointerEvents: 'none',
            background: `radial-gradient(circle, ${ACCENT}30, transparent 70%)`, filter: 'blur(4px)',
          }} />
          <AuroraMascot module="learning" size={46} />
        </div>
        <div style={{ minWidth: 0 }}>
          <h1 style={{
            margin: 0, fontWeight: 800, letterSpacing: '-0.02em', fontSize: 26, color: TXT,
            background: `linear-gradient(115deg, #ffffff 40%, ${ACCENT})`,
            WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>Académie</h1>
          <div aria-hidden="true" style={{
            height: 2, width: 148, margin: '6px 0 5px', borderRadius: 2,
            background: `linear-gradient(90deg, ${ACCENT}, ${ACCENT}59 55%, transparent)`,
          }} />
          <div style={techLabel}>
            apprentissage · parcours bac · {academy.model || 'modèle auto'}
          </div>
        </div>
        <span style={{ flex: 1 }} />
        {academy.academyStreak.current > 0 && (
          <span title={`Série actuelle : ${academy.academyStreak.current} jour(s) · record ${academy.academyStreak.longest} jour(s)`}
            style={{ ...chip(false), cursor: 'default', display: 'inline-flex', alignItems: 'center', gap: 5, color: ACCENT, borderColor: `${ACCENT}55`, fontFamily: MONO }}>
            <IcFlame size={11} /> {academy.academyStreak.current}j
          </span>
        )}
        {academy.bestMention && (
          <span title={`Score moyen all-time : ${academy.bestMention.avg} pts`}
            style={{ ...chip(false), cursor: 'default', display: 'inline-flex', alignItems: 'center', gap: 5, color: ACCENT, borderColor: `${ACCENT}55`, fontFamily: MONO }}>
            <IcAward size={11} /> {academy.bestMention.label}
          </span>
        )}
        <button type="button" className="v4aca-ghost" onClick={() => void academy.generateStudyCard()}
          disabled={academy.streaming}
          title="Génère immédiatement une fiche éclair sur le sujet courant"
          style={{ ...ghostBtn, opacity: academy.streaming ? 0.5 : 1 }}>
          <IcZap size={12} /> Fiche éclair
        </button>
        <button type="button" className="v4aca-primary" onClick={() => setBankOpen(true)}
          title="Tous tes parcours générés, triés par matière"
          style={primaryBtn}>
          <IcLayers size={13} /> Banque de générations
        </button>
      </header>

      <div role="tablist" aria-label="Vue Académie" style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        <button type="button" role="tab" aria-selected={tab === 'atelier'}
          onClick={() => setTab('atelier')} style={chip(tab === 'atelier')}>
          Atelier
        </button>
        <button type="button" role="tab" aria-selected={tab === 'conversation'}
          onClick={() => setTab('conversation')} style={chip(tab === 'conversation')}>
          Conversation
        </button>
        <span style={{ ...techLabel, alignSelf: 'center', fontSize: 9 }}>
          {tab === 'atelier' ? 'labo de révision multi-mode' : 'discussion libre avec le professeur IA'}
        </span>
      </div>

      {tab === 'conversation' ? (
        <div className="v4aca-card" style={{ ...glass, padding: 18, animationDelay: '60ms' }}>
          <SectionLabel right={<span style={{ display: 'inline-flex', color: SUB }}><IcChat size={13} /></span>}>professeur ia</SectionLabel>
          <Suspense fallback={<div style={{ fontSize: 12, color: SUB, padding: 12 }}>Chargement du professeur IA…</div>}>
            <AcademyTutorPanel
              subjectLabel={(academy.subjectLabels as Record<string, string>)[academy.subject as string] || 'BAC'}
              model={academy.model}
              onCreateParcours={handleCreateParcoursFromTutor}
            />
          </Suspense>
        </div>
      ) : (
        <div className="v4aca-grid" style={{ display: 'grid', gridTemplateColumns: '1.55fr 1fr', gap: 18, alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, minWidth: 0 }}>
            <div
              ref={studioRef}
              className="v4aca-card"
              onDragEnter={(e) => {
                if (e.dataTransfer?.types?.includes('Files')) {
                  e.preventDefault()
                  setIsDragOver(true)
                }
              }}
              onDragOver={(e) => {
                if (e.dataTransfer?.types?.includes('Files')) {
                  e.preventDefault()
                  e.dataTransfer.dropEffect = 'copy'
                  setIsDragOver(true)
                }
              }}
              onDragLeave={(e) => {
                if (e.currentTarget === e.target) setIsDragOver(false)
              }}
              onDrop={(e) => {
                setIsDragOver(false)
                const files = Array.from(e.dataTransfer?.files || [])
                if (files.length === 0) return
                e.preventDefault()
                void onDropFiles(files)
              }}
              style={{
                ...glass, padding: 18, position: 'relative', animationDelay: '60ms',
                borderColor: isDragOver ? ACCENT : 'rgba(255,255,255,.09)',
                boxShadow: isDragOver ? `0 0 24px ${ACCENT}40` : undefined,
              }}>
              {isDragOver && (
                <div style={{
                  position: 'absolute', inset: 0, zIndex: 10, borderRadius: 18,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: `${ACCENT}14`, pointerEvents: 'none',
                  fontSize: 16, fontWeight: 750, color: ACCENT,
                }}>
                  Dépose ta leçon ou tes images ici
                </div>
              )}

              <SectionLabel right={
                <span style={{ fontSize: 10, fontFamily: MONO, color: DIM }}>{academy.model || 'modèle auto'}</span>
              }>atelier de révision</SectionLabel>

              <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginBottom: 12 }}>
                {(Object.keys(academy.modeLabels) as AcademyMode[]).map((m) => (
                  <button key={m} type="button" onClick={() => academy.setMode(m)}
                    disabled={academy.streaming}
                    style={chip(academy.mode === m, academy.streaming)}>
                    {stripGlyph(academy.modeLabels[m])}
                  </button>
                ))}
                <button type="button" onClick={academy.randomMode} disabled={academy.streaming}
                  title="Tirer un mode au hasard"
                  style={{ ...chip(false, academy.streaming), display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <IcDice size={11} /> mode
                </button>
                <button type="button" onClick={academy.randomAll} disabled={academy.streaming}
                  title="Surprise totale : matière + mode + sujet aléatoires"
                  style={{ ...chip(false, academy.streaming), display: 'inline-flex', alignItems: 'center', gap: 5, color: ACCENT, borderColor: `${ACCENT}55` }}>
                  <IcDice size={11} /> surprise
                </button>
                <button type="button" onClick={() => void academy.randomAllAndGenerate()} disabled={academy.streaming}
                  title="Matière + mode + sujet aléatoires puis génération immédiate"
                  style={{ ...chip(true, academy.streaming), display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <IcZap size={11} /> surprise et go
                </button>
              </div>

              {academy.mode === 'parcours-bac' && (
                <>
                  <FormatPicker disabled={academy.streaming} />
                  <OralBadge a={academy} />
                </>
              )}

              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
                <span style={techLabel}>matière</span>
                <select className="v4aca-input"
                  aria-label="Matière"
                  value={academy.subject}
                  onChange={(e) => academy.setSubject(e.target.value as AcademySubject)}
                  disabled={academy.streaming}
                  style={{ ...inputBase, width: 'auto', padding: '6px 10px', fontSize: 12 }}>
                  {(Object.keys(academy.subjectLabels) as AcademySubject[]).map((s) => (
                    <option key={s} value={s}>{academy.subjectLabels[s]}</option>
                  ))}
                </select>
                <button type="button" onClick={academy.randomSubject} disabled={academy.streaming}
                  title="Tirer une matière au hasard"
                  style={{ ...chip(false, academy.streaming), display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <IcDice size={11} /> matière
                </button>
                <span style={{ flex: 1 }} />
                <label style={{ ...ghostBtn, padding: '6px 12px', fontSize: 11, cursor: academy.streaming ? 'not-allowed' : 'pointer', opacity: academy.streaming ? 0.5 : 1 }}>
                  <IcUpload size={12} />
                  {academy.lessonName ? academy.lessonName.slice(0, 26) : 'leçon (txt / md / pdf / docx)'}
                  <input
                    type="file"
                    multiple
                    aria-label="Charger des fichiers de leçon"
                    accept=".txt,.md,.markdown,.pdf,.docx,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    onChange={(e) => {
                      const files = Array.from(e.target.files || [])
                      if (files.length > 0) void academy.uploadLessonsMulti(files)
                      e.target.value = ''
                    }}
                    disabled={academy.streaming}
                    style={{ display: 'none' }} />
                </label>
                {academy.lessonName && (
                  <button type="button" onClick={academy.clearLesson} title="Retirer toute la leçon"
                    style={{ ...ghostBtn, padding: '6px 9px' }}>
                    <IcX size={11} />
                  </button>
                )}
                <button type="button" onClick={() => void academy.pasteLessonFromClipboard()}
                  disabled={academy.streaming}
                  title="Coller le presse-papiers comme leçon"
                  style={{ ...ghostBtn, padding: '6px 12px', fontSize: 11, opacity: academy.streaming ? 0.5 : 1 }}>
                  <IcClipboard size={12} /> coller
                </button>
                <label style={{
                  ...ghostBtn, padding: '6px 12px', fontSize: 11,
                  cursor: academy.streaming ? 'not-allowed' : 'pointer', opacity: academy.streaming ? 0.5 : 1,
                  color: academy.lessonImages.length > 0 ? ACCENT : SUB,
                  borderColor: academy.lessonImages.length > 0 ? `${ACCENT}55` : 'rgba(255,255,255,.14)',
                }}>
                  <IcImage size={12} />
                  {academy.lessonImages.length > 0 ? `${academy.lessonImages.length} image(s)` : 'images'}
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    aria-label="Charger des images de leçon"
                    onChange={async (e) => {
                      const files = Array.from(e.target.files || [])
                      for (const f of files) await academy.addLessonImage(f)
                      e.target.value = ''
                    }}
                    disabled={academy.streaming}
                    style={{ display: 'none' }} />
                </label>
              </div>

              {academy.lessonUploading && (
                <div style={{
                  padding: '8px 12px', marginBottom: 10, borderRadius: 11,
                  background: `${ACCENT}10`, border: `1px solid ${ACCENT}44`,
                  display: 'flex', gap: 10, alignItems: 'center', fontSize: 11.5,
                  color: ACCENT, fontFamily: MONO,
                }}>
                  <IcSpinner size={12} />
                  <span style={{ flex: 1 }}>{academy.lessonUploadStage || 'lecture en cours…'}</span>
                  <button type="button" onClick={academy.cancelLessonUpload}
                    style={{ ...ghostBtn, padding: '4px 10px', fontSize: 10, color: RED, borderColor: `${RED}55` }}>
                    annuler
                  </button>
                </div>
              )}

              {academy.lessonFileNames.length > 0 && (
                <div style={{
                  display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10, alignItems: 'center',
                  padding: 8, borderRadius: 11, background: 'rgba(255,255,255,.02)',
                  border: '1px dashed rgba(255,255,255,.12)',
                }}>
                  <span style={{ ...techLabel, fontSize: 9 }}>
                    {academy.lessonFileNames.length} fichier{academy.lessonFileNames.length > 1 ? 's' : ''} accumulé{academy.lessonFileNames.length > 1 ? 's' : ''}
                  </span>
                  {academy.lessonFileNames.map((name) => (
                    <span key={name} title={name} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      padding: '4px 10px', fontSize: 11, borderRadius: 999,
                      background: 'rgba(10,15,30,.5)', color: TXT,
                      border: '1px solid rgba(255,255,255,.1)',
                    }}>
                      {name.length > 34 ? name.slice(0, 31) + '…' : name}
                      <button type="button" onClick={() => academy.removeLessonSection(name)}
                        disabled={academy.streaming}
                        title={`Retirer ${name}`}
                        style={{
                          width: 15, height: 15, borderRadius: 999, padding: 0,
                          background: `${RED}22`, color: RED, border: `1px solid ${RED}44`,
                          cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                        <IcX size={8} />
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {academy.lessonName && (
                <div style={{ marginBottom: 10 }}>
                  <TextPreviewExpander
                    name={academy.lessonName}
                    text={academy.lessonText}
                    label="leçon active"
                    onTextChange={academy.setLessonText}
                    originalText={academy.lessonOriginalText}
                  />
                </div>
              )}

              {academy.lessonImages.length > 0 && (
                <div style={{
                  display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap', alignItems: 'center',
                  padding: 8, borderRadius: 11, background: `${ACCENT}08`,
                  border: `1px dashed ${ACCENT}44`,
                }}>
                  {academy.lessonImages.map((img, i) => (
                    <div key={`${img.name}-${i}`} style={{ position: 'relative' }}>
                      <img src={img.dataUrl} alt={img.name}
                        title={`${img.name}${img.width ? ` · ${img.width}×${img.height}` : ''}`}
                        style={{
                          width: 54, height: 54, objectFit: 'cover', borderRadius: 9,
                          border: `1px solid ${ACCENT}55`,
                        }} />
                      <button type="button" onClick={() => academy.removeLessonImage(i)}
                        title="Retirer cette image"
                        style={{
                          position: 'absolute', top: -5, right: -5, width: 16, height: 16,
                          borderRadius: 999, background: RED, color: '#fff', border: 'none',
                          cursor: 'pointer', padding: 0, display: 'inline-flex',
                          alignItems: 'center', justifyContent: 'center',
                        }}>
                        <IcX size={9} />
                      </button>
                    </div>
                  ))}
                  <span style={{ fontSize: 10, color: ACCENT, fontFamily: MONO }}>
                    vision · {academy.model}
                  </span>
                  <button type="button" onClick={academy.clearLessonImages}
                    title="Retirer toutes les images"
                    style={{ ...ghostBtn, padding: '4px 10px', fontSize: 10 }}>
                    tout retirer
                  </button>
                </div>
              )}

              <input className="v4aca-input"
                type="text"
                aria-label="Sujet à étudier"
                value={academy.topic}
                onChange={(e) => academy.setTopic(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault()
                    void academy.generate()
                  }
                }}
                placeholder={
                  academy.mode === 'study-card' ? 'Sujet à étudier… ex. « conduction thermique »'
                    : academy.mode === 'eval-type' ? 'Focus optionnel… ex. « chapitre 3 sur la cinétique »'
                    : academy.mode === 'free-form' ? 'Thème du projet libre… ex. « énergies renouvelables »'
                    : academy.mode === 'question-dev' ? 'Sujet de la question de développement…'
                    : academy.mode === 'parcours-bac' ? 'Chapitre ou objectif du parcours… (Ctrl+Entrée pour générer)'
                    : 'Référence de l’exercice… (Ctrl+Entrée pour générer)'
                }
                disabled={academy.streaming}
                style={{ ...inputBase, marginBottom: 10 }}
              />

              {(academy.mode === 'question-dev' || academy.mode === 'auto-correct') && (
                <textarea className="v4aca-input"
                  aria-label="Réponse à évaluer"
                  value={academy.userResponse}
                  onChange={(e) => academy.setUserResponse(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault()
                      void academy.generate()
                    }
                  }}
                  placeholder={academy.mode === 'question-dev'
                    ? 'Rédige ton développement ici, puis lance la génération pour évaluation… (Ctrl+Entrée)'
                    : 'Colle ta réponse à corriger ici… (Ctrl+Entrée)'}
                  disabled={academy.streaming}
                  rows={5}
                  style={{ ...inputBase, resize: 'vertical', marginBottom: 10 }}
                />
              )}

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {academy.streaming ? (
                  <button type="button" className="v4aca-primary" onClick={academy.abort}
                    style={{ ...primaryBtn, flex: 1, background: `linear-gradient(120deg, ${RED}, #ffffff33)`, boxShadow: `0 6px 24px ${RED}55` }}>
                    <IcStop size={13} /> Arrêter la génération
                  </button>
                ) : (
                  <button type="button" className="v4aca-primary" onClick={() => void academy.generate()}
                    style={{ ...primaryBtn, flex: 1 }}>
                    <IcSend size={13} /> {stripGlyph(academy.modeLabels[academy.mode])}
                  </button>
                )}
                {academy.hasResult && !academy.streaming && (
                  <button type="button" className="v4aca-ghost" onClick={academy.reset} style={ghostBtn}>
                    <IcRefresh size={12} /> Effacer
                  </button>
                )}
                <button type="button" className="v4aca-ghost" onClick={academy.exportSessionMarkdown}
                  disabled={!canExport}
                  title="Exporter la session en markdown (archive hors-ligne)"
                  style={{ ...ghostBtn, opacity: canExport ? 1 : 0.5, cursor: canExport ? 'pointer' : 'not-allowed' }}>
                  <IcDownload size={12} /> Export .md
                </button>
                {(academy.topic || academy.lessonText || academy.userResponse || academy.hasResult) && !academy.streaming && (
                  <button type="button" className="v4aca-ghost"
                    onClick={() => {
                      if (window.confirm('Réinitialiser la session courante ?\n\nEfface : sujet, leçon, réponse rédigée, contenu généré, série.\nGarde : matière, mode, palmarès, succès.')) {
                        academy.resetCurrentSession()
                      }
                    }}
                    title="Réinitialise la session courante sans toucher au palmarès"
                    style={ghostBtn}>
                    <IcX size={11} /> Reset session
                  </button>
                )}
              </div>

              {!academy.hasResult && !academy.streaming && !academy.error && (
                <div style={{
                  marginTop: 12, padding: '10px 13px', borderRadius: 11, fontSize: 11.5,
                  color: SUB, lineHeight: 1.55, display: 'flex', gap: 10, alignItems: 'flex-start',
                  background: `linear-gradient(120deg, ${ACCENT}0f, ${ACCENT}05)`, border: `1px solid ${ACCENT}26`,
                }}>
                  <span style={{ color: ACCENT, display: 'inline-flex', marginTop: 1 }}><IcZap size={13} /></span>
                  <span style={{ flex: 1 }}>{getDailyTip('academy')}</span>
                </div>
              )}
            </div>

            <OutputPanel a={academy} onOpenParcours={() => setParcoursOverlayOpen(true)} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, minWidth: 0 }}>
            <EpreuvePanel a={academy} />
            <PalmaresPanel a={academy} />
            <div className="v4aca-card" style={{ ...glass, padding: 18, animationDelay: '210ms' }}>
              <SectionLabel right={<span style={{ display: 'inline-flex', color: SUB }}><IcAward size={13} /></span>}>succès</SectionLabel>
              <Suspense fallback={<div style={{ fontSize: 11, color: DIM }}>Chargement des succès…</div>}>
                <AchievementsPanel filter={['academy', 'cross']} />
              </Suspense>
            </div>
            <div className="v4aca-card" style={{ ...glass, padding: 18, animationDelay: '270ms' }}>
              <SectionLabel right={<span style={{ display: 'inline-flex', color: SUB }}><IcBook size={13} /></span>}>défis de la semaine</SectionLabel>
              <Suspense fallback={<div style={{ fontSize: 11, color: DIM }}>Chargement des défis…</div>}>
                <WeeklyChallenges />
              </Suspense>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
