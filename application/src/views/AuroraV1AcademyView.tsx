/**
 * AuroraV1AcademyView — Editorial study hub entry for the Academy module.
 *
 * Visual chrome from _design/aurora_design_screens_v1/modules.jsx
 * (AcademyScreen): two columns — editorial subject brief on the left
 * (Eyebrow + Display title, lesson summary, OWASP-like tags, 4 stat
 * tiles Cours/Fiches/Exos/Quiz, Leitner progress bar with 5 boxes
 * count) — and a thinking sphere + live exam blanc panel on the right.
 *
 * Real wiring: MangaAcademyView (2242 LOC of flashcards CRUD with SM-2
 * spaced repetition, Leitner boxes, exo generation, AI tutor chat,
 * past papers indexing, video transcript ingestion, gamification XP)
 * lazy-mounts as soon as the user enters the live session.
 */
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Send, StopCircle, Loader2, Upload, X as XIcon, Image as ImgIcon } from 'lucide-react'
import AuroraSphereV1 from '../components/AuroraSphereV1.tsx'
import AuroraV1AcademyMobile from './AuroraV1AcademyMobile.tsx'
import { useIsMobile } from '../hooks/useIsMobile.ts'
import { useAcademyViewLogic, type AcademyMode, type AcademySubject } from '../hooks/useAcademyViewLogic.ts'
import { useLearningSessionStore, type LearnerProfile } from '../stores/learningSessionStore.ts'
import { useFileDrop } from '../hooks/useFileDrop.ts'
import { getDailyTip } from '../utils/dailyTip.ts'
import { useAchievementToasts } from '../hooks/useAchievementToasts.ts'
import Sparkline from '../components/Sparkline.tsx'
import TextPreviewExpander from '../components/TextPreviewExpander.tsx'

// v82jz : MangaAcademyView delegate retiré. Le V1 view couvre déjà
// 10 modes (study-card, eval-type, free-form, question-dev, auto-correct,
// mind-map, flashcards, graph, table, streak) + vision multimodale +
// upload PDF + leaderboard + épreuve timed via useAcademyViewLogic.
// "Ouvrir l'académie" scroll vers la zone exo au lieu de mount manga.
//
// v82l4 : EntDashboard MIGRÉ vers Paramètres → Calendrier / ENT.
// Le user a explicitement demandé que la connexion ENT vive dans
// Paramètres (cohérent : c'est de la config compte, pas un module).
// v82bv + v82bw : viewers interactifs lazy-loaded — chaque mode tire
// son chunk seulement quand utilisé. AcademyMindMap est ré-utilisé
// pour le mode graph (mermaid.js fait flowchart + mindmap nativement).
const AcademyMindMap = lazy(() => import('../components/AcademyMindMap'))
const AcademyFlashcards = lazy(() => import('../components/AcademyFlashcards'))
const AcademyTable = lazy(() => import('../components/AcademyTable'))
const AchievementsPanel = lazy(() => import('../components/AchievementsPanel'))
const WeeklyChallenges = lazy(() => import('../components/WeeklyChallenges'))
// iter31 : page parcours dédiée full-screen pour la session BAC active
// (Synthèse → Fiches → Exos → Examen avec timer + exit guard).
const ParcoursActiveSession = lazy(() => import('./learning/ParcoursActiveSession'))
const ParcoursBankDrawer = lazy(() => import('./learning/ParcoursBankDrawer'))
const AcademyTutorPanel = lazy(() => import('./learning/AcademyTutorPanel'))

const GOLD = 'oklch(0.74 0.11 90)'

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

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      padding: 12,
      background: 'var(--bg-card, rgba(255,255,255,0.03))',
      border: '1px solid var(--line, rgba(255,255,255,0.12))',
      borderRadius: 8,
    }}>
      <div style={{
        fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
        letterSpacing: '0.14em', color: 'var(--fg-mute, #777)',
        textTransform: 'uppercase',
      }}>{label}</div>
      <div style={{
        fontFamily: 'var(--font-display, serif)', fontStyle: 'italic',
        fontSize: 26, letterSpacing: '-0.02em',
        color: 'var(--fg, #f5f5f5)',
      }}>{value}</div>
    </div>
  )
}

export default function AuroraV1AcademyView() {
  // iter41 : layout mobile-native dédié quand l'écran est portrait/petit.
  // L'ancien layout 2-col Editorial est prévu pour desktop (1280+), il
  // chevauche et passe mal sur mobile même avec @media patches. Le
  // composant mobile partage le hook useAcademyViewLogic donc tout le
  // pipeline (parcours-bac, banque, bubble, etc.) est identique.
  const isMobile = useIsMobile(860)
  if (isMobile) return <AuroraV1AcademyMobile />
  return <AuroraV1AcademyDesktop />
}

function AuroraV1AcademyDesktop() {
  const [pulse, setPulse] = useState(0)
  const [isDragOver, setIsDragOver] = useState(false)
  // v83g — onglets Dashboard / Conversation : la conversation est un canal
  // privilégié pour parler au prof IA sans le poids du dashboard. Permet de
  // swipper visuellement entre les deux côtés du module.
  const [academyTab, setAcademyTab] = useState<'dashboard' | 'conversation'>('dashboard')
  // v82eo : feedback temporaire "✓ copié" sur le bouton output copy
  const [outputCopied, setOutputCopied] = useState(false)
  useEffect(() => {
    if (!outputCopied) return
    const t = window.setTimeout(() => setOutputCopied(false), 1600)
    return () => window.clearTimeout(t)
  }, [outputCopied])
  const academy = useAcademyViewLogic()
  // iter40 : layout adaptatif — le brief lourd se condense sur mobile.
  const isMobile = (() => {
    if (typeof window === 'undefined') return false
    return window.innerWidth <= 860
  })()
  void isMobile  // utilisé par les classes CSS scoped via @media

  // iter31 : la page parcours dédiée s'ouvre automatiquement dès que
  // parcoursPayload devient non-null (fin de génération OU charger une
  // session pré-générée côté serveur). On garde un flag local pour
  // permettre à l'utilisateur de revenir à l'écran principal sans
  // perdre la session — il pourra rouvrir via le bouton "Reprendre".
  // hasOpenedRef : on n'auto-ouvre qu'UNE FOIS par génération pour
  // ne pas re-piéger l'utilisateur s'il choisit explicitement de
  // sortir vers les autres modules pendant qu'il regarde sa session.
  const [parcoursOverlayOpen, setParcoursOverlayOpen] = useState(false)
  // iter35.D : drawer "Banque de générations" — remplace le floating
  // "Reprendre la session" par une vraie banque triée par matière, comme
  // les autres modules (image / video).
  const [bankOpen, setBankOpen] = useState(false)
  const hasAutoOpenedRef = useRef<string | null>(null)
  // iter31.fix: useMemo for the signature so the useEffect dep is a stable
  // string instead of the parcoursPayload object reference. Without this,
  // the streaming output kept rebuilding the payload object → useEffect
  // dep changed every chunk → cleanup cleared the 200ms timer before it
  // could fire → setParcoursOverlayOpen(true) NEVER called → overlay
  // never opened even though the payload was correctly extracted.
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
  useAchievementToasts() // v82dd : toast quand un badge se débloque
  // v82jz : ref vers la zone d'exo pour scroll-to depuis "Ouvrir l'académie"
  // (remplace la delegation MangaAcademyView).
  const exoRef = useRef<HTMLDivElement | null>(null)
  const scrollToExo = () => {
    exoRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // v83f — quand l'IA prof (AcademyTutorPanel) propose de créer un parcours,
  // on injecte le sujet, on règle le format (jeu/classique) dans le store,
  // on passe en mode parcours-bac et on lance la génération direct.
  const handleCreateParcoursFromTutor = (topic: string, gameMode: boolean) => {
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
    academy.setTopic(topic)
    academy.setMode('parcours-bac')
    scrollToExo()
    // petit délai pour laisser le mode/topic se poser avant de streamer
    window.setTimeout(() => { void academy.generate() }, 60)
  }
  useEffect(() => {
    let raf = 0
    const loop = () => {
      setPulse(Math.abs(Math.sin(performance.now() / 1200)))
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  // v83g — vue conversation pure : occupe tout le viewport, prof IA seul
  // au centre. L'utilisateur swipe entre Dashboard et Conversation via
  // le tab-switcher.
  if (academyTab === 'conversation') {
    return (
      <div style={{
        position: 'relative', height: '100%', minHeight: 0,
        background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
        fontFamily: 'var(--font-sans, system-ui)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        <AcademyTabSwitcher current={academyTab} onChange={setAcademyTab} />
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '12px 18px 36px' }}>
          <Suspense fallback={<div style={{ padding: 24, color: '#aaa', fontSize: 12 }}>Chargement du prof IA…</div>}>
            <AcademyTutorPanel
              subjectLabel={(academy.subjectLabels as Record<string, string>)[academy.subject as string] || 'BAC STI2D'}
              model={academy.model}
              onCreateParcours={handleCreateParcoursFromTutor}
            />
          </Suspense>
        </div>
      </div>
    )
  }

  return (
    <div className="auroraAcademyShell" style={{
      position: 'relative', height: '100%',
      display: 'grid', gridTemplateColumns: '1fr 1.1fr',
      gridTemplateRows: 'auto 1fr',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)', overflow: 'hidden',
    }}>
      <div style={{ gridColumn: '1 / -1', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <AcademyTabSwitcher current={academyTab} onChange={setAcademyTab} />
      </div>
      {/* iter40 : responsive — 2 colonnes sur desktop, single-col stack
          sur mobile (≤860px). Réduit lourdement les fonts/paddings du
          brief column (Display 68px sur mobile = chevauchement). */}
      <style>{`
        @media (max-width: 860px) {
          .auroraAcademyShell {
            grid-template-columns: 1fr !important;
            grid-template-rows: auto auto !important;
            overflow-y: auto !important;
            height: 100dvh !important;
          }
          .auroraAcademyShell > div {
            padding: 16px 14px !important;
            border-right: none !important;
            border-bottom: 1px solid rgba(255,255,255,0.08) !important;
          }
          /* Brief column compactée */
          .auroraAcademyShell .academyDisplay {
            font-size: 38px !important;
            line-height: 0.95 !important;
            margin: 0 !important;
          }
          .auroraAcademyShell p {
            font-size: 13px !important;
            line-height: 1.5 !important;
          }
          .auroraAcademyShell .academyTagsRow {
            gap: 6px !important;
          }
          /* Float bouton banque pas chevauchant le titre */
          .auroraAcademyShell > button {
            top: 10px !important;
            right: 10px !important;
            padding: 6px 12px !important;
            font-size: 11px !important;
          }
          /* Form area scroll OK */
          .auroraAcademyShell textarea {
            font-size: 16px !important;  /* iOS no-zoom on focus */
          }
          .auroraAcademyShell input[type="text"],
          .auroraAcademyShell input[type="search"] {
            font-size: 16px !important;
          }
          /* Right column : sphère et crosshairs masqués sur mobile pour
             ne pas chevaucher le form qui prend toute la largeur. */
          .auroraAcademyShell .academyRight {
            padding: 14px !important;
          }
          .auroraAcademyShell .academySphere {
            display: none !important;
          }
          .auroraAcademyShell .academyCrosshair {
            display: none !important;
          }
        }
        /* iOS bug : 100vh inclut barre URL — utilise dvh */
        .auroraAcademyShell { min-height: 100dvh; }
      `}</style>
      {/* iter31 : page parcours dédiée full-screen — montée seulement
          quand on a un payload + flag overlay open. Suspense fallback
          minimal car le chunk est tiré en background dès que l'output
          du parcours-bac arrive. */}
      {parcoursOverlayOpen && academy.parcoursPayload && (
        <Suspense fallback={null}>
          <ParcoursActiveSession
            academy={academy}
            onClose={() => setParcoursOverlayOpen(false)}
          />
        </Suspense>
      )}

      {/* iter35.D : bouton "Banque de générations" — accessible toujours,
          ouvre le drawer avec tous les parcours générés triés par matière.
          Remplace le floating "Reprendre la session" qui était à côté de
          Générer (UX scolaire et redondante). */}
      {!parcoursOverlayOpen && (
        <button type="button"
          onClick={() => setBankOpen(true)}
          title="Tous tes parcours générés, triés par matière"
          style={{
            position: 'absolute', top: 16, right: 16, zIndex: 40,
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '10px 16px', borderRadius: 99,
            background: `linear-gradient(135deg, ${GOLD}AA, oklch(0.78 0.16 60 / 0.65))`,
            color: '#0a0a0a',
            border: `1px solid ${GOLD}`,
            fontSize: 12, fontWeight: 700,
            fontFamily: 'var(--font-mono, monospace)',
            cursor: 'pointer',
            boxShadow: `0 4px 24px ${GOLD}55`,
          }}>
          📚 Banque de générations
        </button>
      )}

      {/* iter35.D : drawer Banque qui remplace le floating "Reprendre".
          Sur "Reprendre" d'un parcours, on injecte son payload dans
          academy.output → parcoursPayload se ré-extrait → l'overlay
          full-screen s'ouvre. */}
      <Suspense fallback={null}>
        <ParcoursBankDrawer
          open={bankOpen}
          onClose={() => setBankOpen(false)}
          onResume={(entry) => {
            // Restaure leçon (texte + nom) + force le payload via output.
            academy.setLessonText(entry.lessonText || '')
            academy.setOutput(`\`\`\`json\n${JSON.stringify(entry.payload, null, 2)}\n\`\`\``)
            // Petit délai pour que le memo parcoursPayload se ré-évalue
            // avant qu'on ouvre l'overlay.
            window.setTimeout(() => setParcoursOverlayOpen(true), 60)
          }}
        />
      </Suspense>

      {/* Left: editorial brief */}
      <div style={{
        padding: '40px 36px',
        borderRight: '1px solid var(--line, rgba(255,255,255,0.12))',
        display: 'flex', flexDirection: 'column', gap: 18, overflowY: 'auto',
      }}>
        <Eyebrow dot={GOLD}>Academy · BAC STI2D · Session 2026</Eyebrow>
        <div className="academyDisplay">
          <Display size={68}>Académie<br/><em style={{ color: 'var(--ember-500, #ff6a3d)' }}>locale</em></Display>
        </div>
        <p style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--fg-dim, #aaa)', maxWidth: 480, margin: 0 }}>
          Cours · 12 fiches · 4 exos générés · 1 quiz Leitner · révision dans 2h41.
          Calibré sur Métropole 2024, 2023, et Polynésie 2024.
        </p>
        <div className="academyTagsRow" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Tag accent={GOLD}>Physique-Chimie</Tag>
          <Tag>STI2D · Tle</Tag>
          <Tag>Coef. 16</Tag>
          <Tag>Niveau 4 / 5</Tag>
          {/* v82i6 : streak Academy (parité Cyber v82i3+i4) */}
          {academy.academyStreak.current > 0 && (
            <Tag accent={academy.academyStreak.current >= 7 ? GOLD : undefined}>
              <span title={`Streak actuel : ${academy.academyStreak.current} jour${academy.academyStreak.current > 1 ? 's' : ''} consécutif${academy.academyStreak.current > 1 ? 's' : ''}\nRecord all-time : ${academy.academyStreak.longest} jour${academy.academyStreak.longest > 1 ? 's' : ''}${academy.academyStreak.current === academy.academyStreak.longest ? ' · 🏆 actuel = record' : ''}`}>
                🔥 {academy.academyStreak.current}j{academy.academyStreak.longest > academy.academyStreak.current ? ` / record ${academy.academyStreak.longest}j` : academy.academyStreak.current >= 7 ? ' 🏆' : ''}
              </span>
            </Tag>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 12 }}>
          <Tile label="Cours" value="12" />
          <Tile label="Fiches" value="8" />
          <Tile label="Exos" value="4" />
          <Tile label="Quiz" value="37" />
        </div>

        {/* v82l4 : ENT dashboard déplacé vers Paramètres (calendrier section). */}

        {/* v83f — l'IA prof : l'endroit dédié pour poser n'importe quelle
            question sur un cours, demander des vidéos, et lancer un parcours
            d'entraînement sur le sujet discuté en un clic. */}
        <Suspense fallback={null}>
          <AcademyTutorPanel
            subjectLabel={(academy.subjectLabels as Record<string, string>)[academy.subject as string] || 'BAC STI2D'}
            model={academy.model}
            onCreateParcours={handleCreateParcoursFromTutor}
          />
        </Suspense>

        <div style={{ flex: 1 }} />

        {/* Leitner panel */}
        <div style={{
          padding: 14,
          background: 'var(--bg-raised, rgba(255,255,255,0.04))',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 8,
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', marginBottom: 10,
          }}>
            <Eyebrow>Leitner · prochaine révision</Eyebrow>
            <span style={{
              fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
              color: 'var(--fg-dim, #aaa)',
            }}>2h41</span>
          </div>
          <div style={{
            height: 6, borderRadius: 99,
            background: 'var(--ink-800, rgba(255,255,255,0.06))',
            overflow: 'hidden',
          }}>
            <div style={{
              width: '64%', height: '100%',
              background: `linear-gradient(90deg, var(--ember-500, #ff6a3d), ${GOLD})`,
            }} />
          </div>
          <div style={{
            display: 'flex', justifyContent: 'space-between', marginTop: 8,
            fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
            color: 'var(--fg-mute, #777)',
          }}>
            <span>boîte 1 · 7</span><span>2 · 12</span><span>3 · 9</span><span>4 · 5</span><span>5 · 4</span>
          </div>
        </div>

        <button type="button" onClick={scrollToExo}
          style={{
            padding: '12px 20px', background: GOLD, color: '#0a0a0a',
            border: 'none', fontSize: 13, fontWeight: 600,
            cursor: 'pointer', fontFamily: 'var(--font-sans, system-ui)',
          }}>
          ✦ Ouvrir l'académie
        </button>
      </div>

      {/* Right: thinking sphere + exam panel */}
      <div className="academyRight" style={{ position: 'relative', padding: 36 }}>
        {/* Sphere — décor, masquée sur mobile pour ne pas chevaucher le form */}
        <div className="academySphere" style={{
          position: 'absolute', top: 36, left: 36, right: 36, bottom: 220,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            width: '60%', aspectRatio: '1 / 1', maxWidth: 320,
            transform: `scale(${1 + pulse * 0.04})`,
            filter: `drop-shadow(0 0 ${80 + pulse * 30}px ${GOLD}66)`,
          }}>
            <AuroraSphereV1 tint={GOLD} state="thinking" radius={0.42} glow={1.2} />
          </div>
        </div>

        {/* Crosshairs */}
        {(['tl', 'tr', 'bl', 'br'] as const).map((c) => {
          const inset = 36; const size = 14
          const pos: React.CSSProperties = c === 'tl' ? { top: inset, left: inset }
            : c === 'tr' ? { top: inset, right: inset }
            : c === 'bl' ? { bottom: inset, left: inset }
            : { bottom: inset, right: inset }
          return (
            <div key={c} className="academyCrosshair" style={{ position: 'absolute', ...pos, width: size, height: size }}>
              <div style={{ position: 'absolute', top: 0, left: 0, width: size, height: 1, background: 'var(--fg-mute, #777)' }} />
              <div style={{ position: 'absolute', top: 0, left: 0, width: 1, height: size, background: 'var(--fg-mute, #777)' }} />
            </div>
          )
        })}

        {/* v82bq : Lab pédagogique multi-mode.
            - Upload leçon (txt/md → text content)
            - Mode picker : study-card / eval-type / free-form / question-dev / auto-correct
            - Subject picker : auto / physique / chimie / maths / svt / lettres / histoire / philo / langues / eco / info
            - Topic input + (selon mode) user response input
            - Output streamé avec sections § ou tableaux ASCII selon matière
            - "Académie complète" reste l'escape hatch full MangaAcademyView. */}
        <div
          onDragEnter={(e) => {
            if (e.dataTransfer?.types?.includes('Files')) {
              e.preventDefault()
              setIsDragOver(true)
            }
          }}
          onDragOver={(e) => {
            // v82cb : drag-drop natif — accepte images + txt/md
            if (e.dataTransfer?.types?.includes('Files')) {
              e.preventDefault()
              e.dataTransfer.dropEffect = 'copy'
              setIsDragOver(true)
            }
          }}
          onDragLeave={(e) => {
            // Only clear if leaving the panel itself, not bubbled child
            if (e.currentTarget === e.target) setIsDragOver(false)
          }}
          onDrop={async (e) => {
            setIsDragOver(false)
            const files = Array.from(e.dataTransfer?.files || [])
            if (files.length === 0) return
            e.preventDefault()
            // v82fk : sépare images vs lessons. Images → batch via
            // addLessonImage. Lessons → uploadLessonsMulti pour
            // concaténer plusieurs fichiers en une leçon unique.
            const imageFiles = files.filter((f) => f.type.startsWith('image/'))
            const lessonFiles = files.filter((f) =>
              !f.type.startsWith('image/') && (
                f.type.startsWith('text/')
                || f.type === 'application/pdf'
                || f.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                || /\.(txt|md|markdown|pdf|docx)$/i.test(f.name)
              )
            )
            for (const f of imageFiles) await academy.addLessonImage(f)
            if (lessonFiles.length > 0) {
              await academy.uploadLessonsMulti(lessonFiles)
            }
          }}
          style={{
            position: 'absolute', bottom: 36, left: 36, right: 36,
            padding: 14,
            background: isDragOver ? 'oklch(0.74 0.13 60 / 0.12)' : 'var(--bg-raised, rgba(255,255,255,0.04))',
            border: `${isDragOver ? '2px dashed' : '1px solid'} ${isDragOver ? 'oklch(0.74 0.13 60)' : 'var(--line, rgba(255,255,255,0.12))'}`,
            borderRadius: 10,
            maxHeight: 'calc(100% - 200px)', overflow: 'auto',
            transition: 'background 120ms ease, border 120ms ease',
          }}>
          {/* v82cb : drag-drop hint quand actif */}
          {isDragOver && (
            <div style={{
              position: 'absolute', inset: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              pointerEvents: 'none',
              fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
              fontStyle: 'italic', fontSize: 28,
              color: 'oklch(0.74 0.13 60)',
              background: 'oklch(0.74 0.13 60 / 0.04)',
              borderRadius: 10,
              zIndex: 10,
            }}>
              Lâche image / leçon ici
            </div>
          )}
          {/* v82by : Épreuve / libre toggle + timer + score */}
          <div style={{
            padding: 8, marginBottom: 8, borderRadius: 6,
            background: academy.session === 'epreuve'
              ? 'oklch(0.55 0.18 25 / 0.10)'
              : 'transparent',
            border: `1px solid ${academy.session === 'epreuve' ? 'oklch(0.55 0.18 25)' : 'var(--line, rgba(255,255,255,0.12))'}`,
            display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
          }}>
            <Eyebrow dot={academy.session === 'epreuve' ? 'oklch(0.72 0.14 25)' : undefined} style={{ fontSize: 10 }}>
              {academy.session === 'epreuve' ? 'ÉPREUVE LIVE' : 'mode libre'}
            </Eyebrow>
            {academy.session === 'epreuve' ? (
              <>
                <span style={{
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 18, fontWeight: 700,
                  color: academy.epreuveTimeLeftSec < 60 ? 'oklch(0.72 0.14 25)' : 'var(--fg, #f5f5f5)',
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {Math.floor(academy.epreuveTimeLeftSec / 60)}:{String(academy.epreuveTimeLeftSec % 60).padStart(2, '0')}
                </span>
                <span style={{ flex: 1 }} />
                <span style={{
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 13, fontWeight: 700,
                  color: GOLD,
                }}>{academy.epreuveScore} pts</span>
                <button type="button" onClick={() => academy.stopEpreuve('abandon')}
                  style={{
                    padding: '3px 10px', fontSize: 10, fontWeight: 600,
                    background: 'oklch(0.55 0.18 25)', color: '#fff',
                    border: 'none', borderRadius: 4, cursor: 'pointer',
                    fontFamily: 'var(--font-sans, system-ui)',
                  }}>Terminer</button>
              </>
            ) : (
              <>
                <span style={{ flex: 1 }} />
                {[600, 1200, 1800, 2700].map((sec) => (
                  <button key={sec} type="button"
                    onClick={() => academy.startEpreuve(sec)}
                    disabled={academy.streaming}
                    style={{
                      padding: '3px 8px', fontSize: 10,
                      fontFamily: 'var(--font-mono, monospace)',
                      background: 'transparent', color: 'var(--fg-dim, #aaa)',
                      border: '1px solid var(--line, rgba(255,255,255,0.12))',
                      borderRadius: 4, cursor: 'pointer',
                    }}>{Math.round(sec / 60)} min</button>
                ))}
              </>
            )}
          </div>

          {/* v82by : résultat post-épreuve + top-3 leaderboard */}
          {academy.epreuveResult && academy.session === 'libre' && (
            <div style={{
              padding: 8, marginBottom: 8, borderRadius: 6,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              border: `1px solid ${GOLD}40`,
              fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            }}>
              <div style={{
                fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
                fontStyle: 'italic', fontSize: 16,
                color: academy.epreuveResult.timeoutHit ? 'oklch(0.72 0.14 25)' : GOLD,
                marginBottom: 4,
              }}>
                {academy.epreuveResult.timeoutHit ? 'Temps écoulé' : 'Session sauvegardée'}
              </div>
              <div style={{ color: 'var(--fg-dim, #aaa)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <span>score <b style={{ color: GOLD }}>{academy.epreuveResult.score}</b></span>
                <span>{Math.floor(academy.epreuveResult.durationMs / 60000)}m {Math.floor((academy.epreuveResult.durationMs / 1000) % 60)}s</span>
              </div>
            </div>
          )}
          {academy.topRuns.length > 0 && (
            <div style={{
              padding: 6, marginBottom: 8, borderRadius: 6,
              background: 'oklch(0.74 0.13 60 / 0.05)',
              border: '1px solid oklch(0.74 0.13 60 / 0.25)',
              fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
            }}>
              <div style={{
                marginBottom: 4, color: 'oklch(0.74 0.13 60)', letterSpacing: '0.14em', textTransform: 'uppercase',
                display: 'flex', alignItems: 'center', gap: 6,
              }}>
                <span>Top scores Academy</span>
                <span style={{ flex: 1 }} />
                {/* v82ed : meilleure mention Bac actuelle, affichée
                    seulement si Bac complet débloqué. */}
                {academy.bestMention && (
                  <span
                    title={`Score moyen all-time · ${academy.bestMention.avg} pts`}
                    style={{
                      letterSpacing: 0, textTransform: 'none',
                      padding: '1px 6px', borderRadius: 4,
                      background: 'oklch(0.74 0.13 60 / 0.12)',
                      border: '1px solid oklch(0.74 0.13 60 / 0.35)',
                      color: 'oklch(0.74 0.13 60)', fontWeight: 700,
                      fontVariantNumeric: 'tabular-nums',
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                    }}>
                    <span>{academy.bestMention.glyph}</span>
                    <span>{academy.bestMention.label}</span>
                  </span>
                )}
                {/* v82dr : total cumulé + sparkline cumulative */}
                <span style={{ letterSpacing: 0, textTransform: 'none', color: 'var(--fg-dim, #aaa)' }}>
                  cumulé : <b style={{ color: 'oklch(0.74 0.13 60)' }}>{academy.totalAcademyPoints}</b> pts
                </span>
                {academy.scoreCumulativeSeries.length >= 3 && (
                  <span title={`Évolution score cumulé · ${academy.scoreCumulativeSeries.length - 1} derniers run(s)`}
                    style={{ display: 'inline-flex', alignItems: 'center' }}>
                    <Sparkline values={academy.scoreCumulativeSeries} width={120} height={20} color="oklch(0.74 0.13 60)" smooth smoothWindow={5} showAxis />
                  </span>
                )}
              </div>
              {academy.topRuns.map((r, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, padding: '2px 0', color: 'var(--fg-dim, #aaa)' }}>
                  <span style={{ width: 14 }}>{i === 0 ? '🥇' : i === 1 ? '🥈' : '🥉'}</span>
                  <span style={{ fontWeight: 700, color: 'oklch(0.74 0.13 60)', minWidth: 36, fontVariantNumeric: 'tabular-nums' }}>{r.score}</span>
                  <span>{r.subject.slice(0, 12)}</span>
                  <span>·</span>
                  <span style={{ flex: 1 }}>{r.topic.slice(0, 28)}</span>
                  <span>{Math.floor(r.durationMs / 60000)}m</span>
                </div>
              ))}
            </div>
          )}

          {/* v82ce : leaderboard groupé par matière — affiche
              uniquement quand au moins 2 matières ont des runs (sinon
              redondant avec le top 3 global). */}
          {Object.keys(academy.runsBySubject).length >= 2 && (
            <div style={{
              padding: 6, marginBottom: 8, borderRadius: 6,
              background: 'var(--bg-card, rgba(255,255,255,0.03))',
              border: '1px solid var(--line, rgba(255,255,255,0.10))',
              fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
            }}>
              <div style={{
                marginBottom: 6, color: GOLD,
                letterSpacing: '0.14em', textTransform: 'uppercase',
              }}>Best par matière</div>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                gap: 6,
              }}>
                {Object.entries(academy.runsBySubject).map(([subj, runs]) => {
                  const series = academy.seriesBySubject[subj] || []
                  return (
                  <div key={subj} style={{
                    padding: 4, borderRadius: 4,
                    background: 'rgba(255,255,255,0.02)',
                    border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
                  }}>
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2,
                    }}>
                      <span style={{
                        fontSize: 9, color: GOLD,
                        flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>{subj}</span>
                      {series.length >= 2 && (
                        <span title={`${series.length} sessions · évolution score`}
                          style={{ display: 'inline-flex', alignItems: 'center' }}>
                          <Sparkline values={series} width={48} height={14} color={GOLD} />
                        </span>
                      )}
                    </div>
                    {runs.map((r, i) => (
                      <div key={i} style={{
                        display: 'flex', gap: 4, color: 'var(--fg-dim, #aaa)',
                      }}>
                        <span style={{ width: 12 }}>{i === 0 ? '🥇' : i === 1 ? '🥈' : '🥉'}</span>
                        <span style={{ fontWeight: 700, color: 'var(--fg, #f5f5f5)', minWidth: 28, fontVariantNumeric: 'tabular-nums' }}>{r.score}</span>
                        <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {r.topic.slice(0, 18)}
                        </span>
                        {r.timeoutHit && <span style={{ color: 'oklch(0.72 0.14 25)' }}>⏱</span>}
                      </div>
                    ))}
                  </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* v82bz : Achievements Academy + cross-module */}
          <div style={{ marginBottom: 8 }}>
            <Suspense fallback={null}>
              <AchievementsPanel filter={['academy', 'cross']} />
            </Suspense>
          </div>

          {/* v82dl : Défis hebdomadaires Academy */}
          <div style={{ marginBottom: 8 }}>
            <Suspense fallback={null}>
              <WeeklyChallenges />
            </Suspense>
          </div>

          {/* Header : mode picker — v82jz : ref pour scroll-to depuis "Ouvrir l'académie" */}
          <div ref={exoRef} style={{ display: 'flex', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
            {(Object.keys(academy.modeLabels) as AcademyMode[]).map((m) => (
              <button key={m} type="button" onClick={() => academy.setMode(m)}
                disabled={academy.streaming}
                style={{
                  padding: '4px 8px', fontSize: 10,
                  fontFamily: 'var(--font-mono, monospace)',
                  letterSpacing: '0.06em',
                  background: academy.mode === m ? GOLD : 'transparent',
                  color: academy.mode === m ? '#0a0a0a' : 'var(--fg-dim, #aaa)',
                  border: `1px solid ${academy.mode === m ? GOLD : 'var(--line, rgba(255,255,255,0.12))'}`,
                  borderRadius: 4, cursor: 'pointer',
                }}>{academy.modeLabels[m]}</button>
            ))}
            {/* v82et : pioche un mode aléatoire */}
            <button type="button"
              onClick={academy.randomMode}
              disabled={academy.streaming}
              title="Tirer un mode au hasard parmi les 10 disponibles"
              style={{
                padding: '4px 8px', fontSize: 10,
                fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.06em',
                background: 'transparent', color: 'var(--fg-mute, #777)',
                border: '1px dashed var(--line, rgba(255,255,255,0.18))',
                borderRadius: 4,
                cursor: academy.streaming ? 'not-allowed' : 'pointer',
                opacity: academy.streaming ? 0.5 : 1,
              }}>🎲</button>
            {/* v82eu : ALL random (matière + mode + topic d'un coup) */}
            <button type="button"
              onClick={academy.randomAll}
              disabled={academy.streaming}
              title="Surprise totale : matière + mode + topic aléatoires"
              style={{
                padding: '4px 10px', fontSize: 10,
                fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.06em',
                background: 'oklch(0.74 0.13 60 / 0.10)',
                color: 'oklch(0.74 0.13 60)',
                border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                borderRadius: 4,
                cursor: academy.streaming ? 'not-allowed' : 'pointer',
                opacity: academy.streaming ? 0.5 : 1,
                fontWeight: 700,
              }}>🎲 surprise</button>
            {/* v82ev : surprise + auto-submit immédiat */}
            <button type="button"
              onClick={() => void academy.randomAllAndGenerate()}
              disabled={academy.streaming}
              title="Pioche matière + mode + topic aléatoires PUIS génère immédiatement"
              style={{
                padding: '4px 10px', fontSize: 10,
                fontFamily: 'var(--font-mono, monospace)',
                letterSpacing: '0.06em',
                background: 'oklch(0.74 0.13 60)',
                color: '#0a0a0a',
                border: '1px solid oklch(0.74 0.13 60)',
                borderRadius: 4,
                cursor: academy.streaming ? 'not-allowed' : 'pointer',
                opacity: academy.streaming ? 0.5 : 1,
                fontWeight: 700,
              }}>⚡ surprise · go</button>
          </div>

          {/* v83e — format de parcours : classique ou « jeu / enquête ». Écrit
              dans le store learningSession (`parcours.profile.examFormat`) →
              piloté par useAcademyViewLogic (prompt génération) ET par
              ParcoursActiveSession (rendu manches/clés/boss). Visible
              uniquement en mode parcours-bac, là où ça change quelque chose. */}
          {academy.mode === 'parcours-bac' && (
            <ParcoursFormatPicker disabled={academy.streaming} />
          )}

          {/* Subject picker */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <Eyebrow style={{ fontSize: 10 }}>matière</Eyebrow>
            <select
              id="academy-subject-select"
              name="academySubject"
              aria-label="Matière"
              value={academy.subject}
              onChange={(e) => academy.setSubject(e.target.value as AcademySubject)}
              disabled={academy.streaming}
              style={{
                padding: '3px 8px', fontSize: 11,
                background: 'var(--bg-input, var(--bg-card))',
                color: 'var(--fg, #f5f5f5)',
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                borderRadius: 4, fontFamily: 'var(--font-mono, monospace)',
              }}>
              {(Object.keys(academy.subjectLabels) as AcademySubject[]).map((s) => (
                <option key={s} value={s}>{academy.subjectLabels[s]}</option>
              ))}
            </select>
            {/* v82es : pioche une matière aléatoire (skip auto) */}
            <button type="button"
              onClick={academy.randomSubject}
              disabled={academy.streaming}
              title="Tirer une matière au hasard"
              style={{
                padding: '3px 8px', fontSize: 11,
                background: 'transparent', color: 'var(--fg-mute, #777)',
                border: '1px dashed var(--line, rgba(255,255,255,0.18))',
                borderRadius: 4, cursor: academy.streaming ? 'not-allowed' : 'pointer',
                opacity: academy.streaming ? 0.5 : 1,
                fontFamily: 'var(--font-mono, monospace)',
              }}>
              🎲
            </button>

            {/* Lesson upload */}
            <label style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              padding: '3px 8px', fontSize: 11, cursor: 'pointer',
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              color: 'var(--fg-dim, #aaa)',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              borderRadius: 4, fontFamily: 'var(--font-mono, monospace)',
            }}>
              <Upload size={10} />
              {academy.lessonName ? `📄 ${academy.lessonName.slice(0, 18)}` : 'leçon (txt/md/pdf/docx)'}
              {/* v82m6 : multiple files supportés (uploadLessonsMulti).
                  L'IA analyse les fichiers ensemble + comprend l'ordre. */}
              <input
                id="academy-lessons-upload"
                name="academyLessonsUpload"
                aria-label="Charger fichiers de leçon"
                type="file"
                multiple
                accept=".txt,.md,.markdown,.pdf,.docx,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(e) => {
                  const files = Array.from(e.target.files || [])
                  // iter31 : passe toujours par uploadLessonsMulti — qui
                  // gère maintenant 1..N fichiers en mode ACCUMULATIF (le
                  // 2ème upload s'ajoute au 1er au lieu de le remplacer).
                  if (files.length > 0) {
                    void academy.uploadLessonsMulti(files)
                  }
                  e.target.value = ''
                }}
                disabled={academy.streaming}
                style={{ display: 'none' }} />
            </label>
            {academy.lessonName && (
              <button type="button" onClick={academy.clearLesson}
                style={{
                  padding: 2, background: 'transparent',
                  color: 'var(--fg-mute, #777)', border: 'none',
                  cursor: 'pointer', display: 'inline-flex',
                }} title="Retirer le fichier"><XIcon size={11} /></button>
            )}
            {/* v82fg : paste from clipboard direct comme leçon */}
            <button type="button"
              onClick={() => void academy.pasteLessonFromClipboard()}
              disabled={academy.streaming}
              title="Coller le contenu du presse-papiers comme leçon"
              style={{
                padding: '3px 8px', fontSize: 11, cursor: academy.streaming ? 'not-allowed' : 'pointer',
                background: 'var(--bg-card, rgba(255,255,255,0.04))',
                color: 'var(--fg-dim, #aaa)',
                border: '1px dashed var(--line, rgba(255,255,255,0.12))',
                borderRadius: 3,
                fontFamily: 'var(--font-mono, monospace)',
                opacity: academy.streaming ? 0.5 : 1,
              }}>
              📋 coller
            </button>

            {/* v82bx : upload images vision */}
            <label style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              padding: '3px 8px', fontSize: 11, cursor: 'pointer',
              background: academy.lessonImages.length > 0
                ? 'oklch(0.74 0.13 60 / 0.15)'
                : 'var(--bg-card, rgba(255,255,255,0.04))',
              color: academy.lessonImages.length > 0 ? 'oklch(0.74 0.13 60)' : 'var(--fg-dim, #aaa)',
              border: `1px solid ${academy.lessonImages.length > 0 ? 'oklch(0.74 0.13 60 / 0.5)' : 'var(--line, rgba(255,255,255,0.12))'}`,
              borderRadius: 4, fontFamily: 'var(--font-mono, monospace)',
            }}>
              <ImgIcon size={10} />
              {academy.lessonImages.length > 0
                ? `🖼 ${academy.lessonImages.length} image(s)`
                : 'images (graph/schema)'}
              <input
                id="academy-lesson-images"
                name="academyLessonImages"
                aria-label="Charger images de leçon"
                type="file"
                accept="image/*"
                multiple
                onChange={async (e) => {
                  const files = Array.from(e.target.files || [])
                  for (const f of files) await academy.addLessonImage(f)
                  e.target.value = ''
                }}
                disabled={academy.streaming}
                style={{ display: 'none' }} />
            </label>
            <span style={{ flex: 1 }} />
            <span style={{
              fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
              color: 'var(--fg-mute, #777)',
            }}>{academy.model || 'no model'}</span>
          </div>

          {/* v82ck : feedback live pendant upload PDF render */}
          {academy.lessonUploading && (
            <div style={{
              padding: '6px 10px', marginBottom: 6, borderRadius: 6,
              background: 'oklch(0.74 0.13 60 / 0.10)',
              border: '1px solid oklch(0.74 0.13 60 / 0.4)',
              display: 'flex', gap: 8, alignItems: 'center',
              fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
              color: 'oklch(0.74 0.13 60)',
            }}>
              <Loader2 size={11} className="aurora-spin" />
              <span style={{ flex: 1 }}>
                {academy.lessonUploadStage || 'lecture en cours…'}
              </span>
              <button type="button" onClick={academy.cancelLessonUpload}
                style={{
                  padding: '2px 8px', fontSize: 10,
                  background: 'transparent', color: 'oklch(0.55 0.18 25)',
                  border: '1px solid oklch(0.55 0.18 25)',
                  borderRadius: 3, cursor: 'pointer',
                  fontFamily: 'var(--font-mono, monospace)',
                }}>annuler</button>
            </div>
          )}

          {/* iter31 : chips pour chaque fichier PDF/texte accumulé
              dans la leçon — chacun avec un × pour le retirer sans
              vider toute la leçon. Affichés au-dessus du preview pour
              que l'utilisateur voie clairement la pile et l'ordre. */}
          {academy.lessonFileNames.length > 0 && (
            <div style={{
              display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6,
              padding: 6,
              background: 'oklch(0.74 0.13 200 / 0.06)',
              border: '1px dashed oklch(0.74 0.13 200 / 0.3)',
              borderRadius: 6,
            }}>
              <span style={{
                fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
                color: 'oklch(0.74 0.13 200)', alignSelf: 'center',
                marginRight: 4,
              }}>{academy.lessonFileNames.length} fichier{academy.lessonFileNames.length > 1 ? 's' : ''} accumulé{academy.lessonFileNames.length > 1 ? 's' : ''} :</span>
              {academy.lessonFileNames.map((name) => (
                <span key={name} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 4,
                  padding: '3px 8px', fontSize: 11,
                  background: 'var(--bg-card, rgba(255,255,255,0.04))',
                  color: 'var(--fg, #f5f5f5)',
                  border: '1px solid oklch(0.74 0.13 200 / 0.4)',
                  borderRadius: 99,
                  fontFamily: 'var(--font-mono, monospace)',
                }} title={name}>
                  📄 {name.length > 36 ? name.slice(0, 33) + '…' : name}
                  <button type="button"
                    onClick={() => academy.removeLessonSection(name)}
                    title={`Retirer ${name}`}
                    disabled={academy.streaming}
                    style={{
                      width: 14, height: 14, borderRadius: 99,
                      background: 'oklch(0.55 0.18 25 / 0.2)',
                      color: 'oklch(0.78 0.16 25)',
                      border: '1px solid oklch(0.55 0.18 25 / 0.4)',
                      fontSize: 10, lineHeight: 1, cursor: 'pointer',
                      padding: 0,
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    }}>×</button>
                </span>
              ))}
            </div>
          )}

          {/* v82et + v82eu : preview inline lessonText avec modal
              "voir tout". Composant partagé Academy + Cyber.
              v82fc : onTextChange = setLessonText pour find & replace. */}
          {academy.lessonName && (
            <TextPreviewExpander
              name={academy.lessonName}
              text={academy.lessonText}
              glyph="📄"
              label="leçon active"
              onTextChange={academy.setLessonText}
              originalText={academy.lessonOriginalText}
            />
          )}

          {/* v82bx : thumbnails images uploadées + bouton retirer */}
          {academy.lessonImages.length > 0 && (
            <div style={{
              display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap',
              padding: 6,
              background: 'oklch(0.74 0.13 60 / 0.06)',
              border: '1px dashed oklch(0.74 0.13 60 / 0.4)',
              borderRadius: 6,
            }}>
              {academy.lessonImages.map((img, i) => (
                <div key={`${img.name}-${i}`} style={{ position: 'relative' }}>
                  <img src={img.dataUrl} alt={img.name}
                    title={`${img.name}${img.width ? ` · ${img.width}×${img.height}` : ''}`}
                    style={{
                      width: 56, height: 56, objectFit: 'cover',
                      borderRadius: 4,
                      border: '1px solid oklch(0.74 0.13 60 / 0.5)',
                    }} />
                  <button type="button"
                    onClick={() => academy.removeLessonImage(i)}
                    title="Retirer cette image"
                    style={{
                      position: 'absolute', top: -4, right: -4,
                      width: 16, height: 16, borderRadius: 99,
                      background: 'oklch(0.55 0.18 25)', color: '#fff',
                      border: 'none', fontSize: 10, lineHeight: 1,
                      cursor: 'pointer', padding: 0,
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    }}>×</button>
                </div>
              ))}
              <span style={{
                alignSelf: 'center', fontSize: 10,
                color: 'oklch(0.74 0.13 60)',
                fontFamily: 'var(--font-mono, monospace)',
              }}>vision · {academy.model}</span>
            </div>
          )}

          {/* Topic input */}
          <input
            id="academy-topic-input"
            name="academyTopic"
            aria-label="Sujet à étudier"
            type="text"
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
              : 'Référence à l\'exercice… (et colle ta réponse plus bas)'
            }
            disabled={academy.streaming}
            style={{
              width: '100%', padding: '6px 10px', marginBottom: 6,
              background: 'var(--bg-input, var(--bg-card, rgba(255,255,255,0.04)))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              borderRadius: 6, fontSize: 12,
              fontFamily: 'var(--font-sans, system-ui)',
            }}
          />

          {/* User response (Q&D + auto-correct only) */}
          {(academy.mode === 'question-dev' || academy.mode === 'auto-correct') && (
            <textarea
              value={academy.userResponse}
              onChange={(e) => academy.setUserResponse(e.target.value)}
              placeholder={academy.mode === 'question-dev'
                ? 'Rédige ton développement ici, puis Générer pour évaluation…'
                : 'Colle ta réponse à corriger ici…'}
              disabled={academy.streaming}
              rows={4}
              style={{
                width: '100%', padding: '6px 10px', marginBottom: 6, resize: 'vertical',
                background: 'var(--bg-input, var(--bg-card, rgba(255,255,255,0.04)))',
                color: 'var(--fg, #f5f5f5)',
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                borderRadius: 6, fontSize: 12,
                fontFamily: 'var(--font-sans, system-ui)',
              }}
            />
          )}

          {/* Action row */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            {academy.streaming ? (
              <button type="button" onClick={academy.abort}
                style={{
                  flex: 1, padding: '8px 12px',
                  background: 'oklch(0.55 0.18 25)', color: '#fff',
                  border: 'none', fontSize: 12, fontWeight: 600,
                  cursor: 'pointer', borderRadius: 6,
                  fontFamily: 'var(--font-sans, system-ui)',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                }}><StopCircle size={12} /> Arrêter la génération</button>
            ) : (
              <>
                <button type="button" onClick={() => void academy.generate()}
                  style={{
                    flex: 1, padding: '8px 12px',
                    background: GOLD, color: '#0a0a0a',
                    border: 'none', fontSize: 12, fontWeight: 600,
                    cursor: 'pointer', borderRadius: 6,
                    fontFamily: 'var(--font-sans, system-ui)',
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  }}><Send size={12} /> {academy.modeLabels[academy.mode]}</button>
                {/* iter36 : bouton "Charger ma session géo" RETIRÉ — la Banque
                    de générations (top-right) couvre maintenant tous les
                    parcours générés, triés par matière. Pas spécifique à la
                    géo. */}
              </>
            )}
            {academy.hasResult && !academy.streaming && (
              <button type="button" onClick={academy.reset}
                style={{
                  padding: '8px 12px', background: 'transparent',
                  color: 'var(--fg-dim, #aaa)',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                  fontSize: 11, cursor: 'pointer', borderRadius: 6,
                  fontFamily: 'var(--font-sans, system-ui)',
                }}>↺ Effacer</button>
            )}
            {academy.hasResult && !academy.streaming && (
              <button type="button" onClick={academy.exportSessionMarkdown}
                title="Exporter la session en markdown (archive offline)"
                style={{
                  padding: '8px 12px', background: 'transparent',
                  color: 'oklch(0.74 0.13 60)',
                  border: '1px solid oklch(0.74 0.13 60 / 0.5)',
                  fontSize: 11, cursor: 'pointer', borderRadius: 6,
                  fontFamily: 'var(--font-sans, system-ui)',
                }}>📥 Exporter .md</button>
            )}
            {/* v82en + v82eo : copy output + feedback "✓ copié" 1.6s */}
            {academy.hasResult && !academy.streaming && academy.output && (
              <button type="button"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(academy.output)
                    setOutputCopied(true)
                  } catch { /* silent */ }
                }}
                title={outputCopied ? 'Copié dans le presse-papiers' : 'Copier le contenu généré dans le presse-papiers'}
                style={{
                  padding: '8px 12px',
                  background: outputCopied ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                  color: outputCopied ? 'oklch(0.74 0.13 60)' : 'var(--fg, #f5f5f5)',
                  border: `1px solid ${outputCopied ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line, rgba(255,255,255,0.18))'}`,
                  fontSize: 11, cursor: 'pointer', borderRadius: 6,
                  fontFamily: 'var(--font-sans, system-ui)',
                  fontWeight: outputCopied ? 700 : 400,
                  transition: 'all 0.18s',
                }}>{outputCopied ? '✓ copié' : '📋 Copier'}</button>
            )}
            {/* v82cz : reset session courante (sans toucher leaderboard) */}
            {(academy.topic || academy.lessonText || academy.userResponse || academy.hasResult) && !academy.streaming && (
              <button type="button"
                onClick={() => {
                  if (window.confirm('Reset session courante ?\n\nEfface : sujet, leçon, réponse rédigée, contenu généré, streak.\nGarde : matière, mode, runs leaderboard, achievements.')) {
                    academy.resetCurrentSession()
                  }
                }}
                title="Reset uniquement la session courante (leaderboard intact)"
                style={{
                  padding: '8px 10px', background: 'transparent',
                  color: 'var(--fg-mute, #777)',
                  border: '1px dashed var(--line, rgba(255,255,255,0.12))',
                  fontSize: 11, cursor: 'pointer', borderRadius: 6,
                  fontFamily: 'var(--font-mono, monospace)',
                }}>↻ reset session</button>
            )}
            <button type="button" onClick={() => academy.exportSessionMarkdown()}
              disabled={!academy.hasResult}
              title="Export markdown de la session courante (matière + mode + leçon + sortie + score)"
              style={{
                padding: '8px 12px', background: 'transparent',
                color: 'var(--fg-dim, #aaa)',
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                fontSize: 11,
                cursor: academy.hasResult ? 'pointer' : 'not-allowed',
                opacity: academy.hasResult ? 1 : 0.5,
                borderRadius: 6,
                fontFamily: 'var(--font-sans, system-ui)',
              }}>↓ Export .md</button>
          </div>

          {/* Output pane — v82bv : 3 modes de rendu :
                - mind-map (post-stream) → AcademyMindMap iframe Mermaid
                - flashcards (post-stream) → AcademyFlashcards interactif
                - autre → pre mono streamé classique */}
          {/* v82fu : daily tip Academy quand pas encore de résultat */}
          {!academy.hasResult && !academy.streaming && !academy.error && (
            <div style={{
              padding: '6px 10px',
              fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
              color: 'var(--fg-dim, #aaa)',
              background: 'oklch(0.74 0.13 60 / 0.06)',
              border: '1px solid oklch(0.74 0.13 60 / 0.22)',
              borderRadius: 6, lineHeight: 1.55,
            }}>
              {getDailyTip('academy')}
            </div>
          )}

          {(academy.hasResult || academy.streaming || academy.error) && (
            <div style={{
              padding: 10, background: 'var(--bg-card, rgba(255,255,255,0.03))',
              border: `1px solid ${GOLD}30`, borderRadius: 6,
            }}>
              <Eyebrow style={{ marginBottom: 6 }}>
                {academy.streaming ? 'Génération · live' : academy.modeLabels[academy.mode]}
              </Eyebrow>

              {/* v82lg: bandeau progression spécifique parcours-bac. Le mode
                  enchaîne synthèse + 4-8 fiches + 8-15 exos + 10 questions de
                  contrôle + 1 développement long. Le user voit ainsi pourquoi
                  ça met 1-3 min sans suspecter un bug. */}
              {academy.mode === 'parcours-bac' && academy.streaming && (
                <div style={{
                  padding: '6px 8px', marginBottom: 6,
                  background: 'oklch(0.7 0.15 60 / 0.08)',
                  border: '1px solid oklch(0.7 0.15 60 / 0.3)',
                  borderRadius: 4, fontSize: 11,
                  color: 'oklch(0.78 0.14 60)',
                  fontFamily: 'var(--font-mono, monospace)',
                }}>
                  📚 Parcours BAC complet — synthèse + fiches + exos + contrôle
                  + développement. Compte 1 à 3 min pour la première sortie
                  (le modèle assemble un JSON dense).
                  {academy.thinkingChars > 0 && academy.output.length === 0 && (
                    <span style={{ marginLeft: 6, opacity: 0.85 }}>
                      🧠 réflexion en cours · {Math.round(academy.thinkingChars / 4)} tokens
                    </span>
                  )}
                </div>
              )}

              {academy.mode === 'mind-map' && !academy.streaming && academy.mermaidCode ? (
                <Suspense fallback={
                  <pre style={{
                    fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                    color: 'var(--fg-dim, #aaa)', padding: 8,
                  }}>chargement du moteur Mermaid…</pre>
                }>
                  <AcademyMindMap code={academy.mermaidCode} dark={true} height={420} />
                </Suspense>
              ) : academy.mode === 'graph' && !academy.streaming && academy.graphCode ? (
                <Suspense fallback={
                  <pre style={{
                    fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                    color: 'var(--fg-dim, #aaa)', padding: 8,
                  }}>chargement du moteur Mermaid…</pre>
                }>
                  <AcademyMindMap code={academy.graphCode} dark={true} height={420} />
                </Suspense>
              ) : academy.mode === 'table' && !academy.streaming && academy.table ? (
                <Suspense fallback={
                  <pre style={{
                    fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                    color: 'var(--fg-dim, #aaa)', padding: 8,
                  }}>parsing du tableau…</pre>
                }>
                  <AcademyTable data={academy.table} />
                </Suspense>
              ) : academy.mode === 'flashcards' && !academy.streaming && academy.flashcards && academy.flashcards.length > 0 ? (
                <Suspense fallback={
                  <pre style={{
                    fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                    color: 'var(--fg-dim, #aaa)', padding: 8,
                  }}>préparation du deck…</pre>
                }>
                  <AcademyFlashcards cards={academy.flashcards}
                    onConfidenceChange={academy.setFlashcardsConfidence} />
                </Suspense>
              ) : academy.mode === 'parcours-bac' && !academy.streaming && academy.parcoursPayload ? (
                <ParcoursBacRenderer academy={academy} />
              ) : (
                <pre style={{
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 12,
                  lineHeight: 1.6, margin: 0,
                  color: 'var(--fg, #f5f5f5)', whiteSpace: 'pre-wrap',
                  maxHeight: 320, overflow: 'auto',
                }}>{academy.output}{academy.streaming && (
                  <span style={{
                    display: 'inline-block', width: 7, height: 13,
                    background: GOLD, verticalAlign: 'text-bottom',
                    animation: 'aurora-blink 1s steps(2) infinite',
                  }} />
                )}</pre>
              )}
              {academy.error && (
                <div style={{ color: 'oklch(0.72 0.14 25)', marginTop: 8, fontSize: 11 }}>
                  ⚠ {academy.error}
                </div>
              )}

              {/* v82ca : streak controls — bouton "Suivant" pour
                  enchaîner sur un nouveau concept + reset série */}
              {academy.mode === 'streak' && !academy.streaming && academy.hasResult && (
                <div style={{
                  marginTop: 8, display: 'flex', gap: 6, alignItems: 'center',
                  paddingTop: 8, borderTop: '1px dashed var(--line-soft, rgba(255,255,255,0.06))',
                }}>
                  <span style={{
                    fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                    color: 'var(--fg-mute, #777)',
                  }}>
                    🔥 streak {academy.streakIndex + 1} · {academy.streakHistory.length} concept(s) couvert(s)
                  </span>
                  <span style={{ flex: 1 }} />
                  <button type="button" onClick={academy.resetStreak}
                    style={{
                      padding: '4px 10px', fontSize: 11,
                      background: 'transparent', color: 'var(--fg-dim, #aaa)',
                      border: '1px solid var(--line, rgba(255,255,255,0.12))',
                      borderRadius: 4, cursor: 'pointer',
                      fontFamily: 'var(--font-sans, system-ui)',
                    }}>↺ Recommencer</button>
                  <button type="button" onClick={() => void academy.nextStreakExo()}
                    style={{
                      padding: '6px 14px', fontSize: 11, fontWeight: 700,
                      background: GOLD, color: '#0a0a0a',
                      border: 'none', borderRadius: 4, cursor: 'pointer',
                      fontFamily: 'var(--font-sans, system-ui)',
                    }}>Exo suivant →</button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes aurora-blink { 50% { opacity: 0 } } @keyframes aurora-spin { to { transform: rotate(360deg); } } .aurora-spin { animation: aurora-spin 1s linear infinite; }`}</style>
    </div>
  )
}

// v83e — picker compact « format de parcours » :
//   ✦ classique (par défaut) : synthèse / fiches / exos / contrôle.
//   ✦ jeu / enquête           : même contenu mais habillage narratif à manches
//                                + 🔑 clés + 🏆 Boss final (cf ParcoursActiveSession).
// Écrit `parcours.profile.examFormat` dans le store learningSession, ce qui :
//   • pilote l'habillage de ParcoursActiveSession (locks, keys, toasts, boss preview) ;
//   • injecte des consignes "narratif / paliers / boss" dans le prompt de
//     génération de parcours-bac (cf useAcademyViewLogic).
function ParcoursFormatPicker({ disabled }: { disabled: boolean }) {
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
    <div style={{ display: 'flex', gap: 6, marginBottom: 8, alignItems: 'center', flexWrap: 'wrap' }}>
      <Eyebrow style={{ fontSize: 10 }}>format du parcours</Eyebrow>
      <button type="button" disabled={disabled}
        onClick={() => setFormat('classique')}
        title="Format classique : synthèse → fiches → exos → contrôle (registre académique standard)."
        style={{
          padding: '4px 10px', fontSize: 10,
          fontFamily: 'var(--font-mono, monospace)', letterSpacing: '0.06em',
          background: !isGame ? GOLD : 'transparent',
          color: !isGame ? '#0a0a0a' : 'var(--fg-dim, #aaa)',
          border: `1px solid ${!isGame ? GOLD : 'var(--line, rgba(255,255,255,0.12))'}`,
          borderRadius: 4, cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1, fontWeight: !isGame ? 700 : 400,
        }}>📚 classique</button>
      <button type="button" disabled={disabled}
        onClick={() => setFormat('jeu')}
        title="Mode JEU / ENQUÊTE : le parcours devient une aventure à manches (Préparation → Carnet → Choix → Défis → 🏆 Boss final), avec clés à débloquer, verrouillages, exos variés et twist narratif. Pareil pour le contenu généré (consignes ludiques injectées dans le prompt)."
        style={{
          padding: '4px 10px', fontSize: 10,
          fontFamily: 'var(--font-mono, monospace)', letterSpacing: '0.06em',
          background: isGame ? 'oklch(0.78 0.18 85)' : 'transparent',
          color: isGame ? '#0a0a0a' : 'oklch(0.85 0.16 80)',
          border: `1px solid ${isGame ? 'oklch(0.78 0.18 85)' : 'oklch(0.74 0.15 75 / 0.5)'}`,
          borderRadius: 4, cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.5 : 1, fontWeight: isGame ? 700 : 400,
          boxShadow: isGame ? '0 0 12px oklch(0.78 0.18 85 / 0.35)' : 'none',
        }}>🎮 jeu / enquête</button>
      {isGame && (
        <span style={{
          fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
          color: 'oklch(0.85 0.16 80)', letterSpacing: '0.04em',
        }}>
          · manches · 🔑 clés · 🏆 boss final
        </span>
      )}
    </div>
  )
}

// v82m4 : Parcours BAC complet renderer.
function ParcoursBacRenderer({ academy }: { academy: ReturnType<typeof useAcademyViewLogic> }) {
  const p = academy.parcoursPayload
  if (!p) return null
  const timeLeft = academy.parcoursControleTimeLeftSec
  const formatTime = (s: number | null) => {
    if (s == null) return '-'
    const m = Math.floor(s / 60), sec = s % 60
    return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  }
  const correction = academy.parcoursCorrection
  const sectionStyle = (color: string): React.CSSProperties => ({
    padding: 14, borderRadius: 8,
    background: `${color}10`,
    border: `1px solid ${color}55`,
  })
  const sectionTitle: React.CSSProperties = {
    fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase',
    color: 'var(--fg-mute, #888)', marginBottom: 8, fontFamily: 'var(--font-mono, monospace)',
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={sectionStyle('oklch(0.74 0.13 90)')}>
        <div style={sectionTitle}>📌 Synthèse 20/20 · {p.synthese_20_20.titre}</div>
        <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'oklch(0.78 0.16 90)' }}>
          ⚡ Ce que tu DOIS savoir absolument
        </div>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.5 }}>
          {p.synthese_20_20.ce_qu_il_faut_savoir.map((s, i) => <li key={i}>{s}</li>)}
        </ul>
        {p.synthese_20_20.pieges_classiques?.length > 0 && (
          <>
            <div style={{ fontSize: 12, fontWeight: 700, marginTop: 10, marginBottom: 4, color: 'oklch(0.78 0.16 25)' }}>
              ⚠ Pièges classiques
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11, lineHeight: 1.4, color: 'var(--fg-dim, #aaa)' }}>
              {p.synthese_20_20.pieges_classiques.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </>
        )}
        {p.synthese_20_20.vocabulaire_a_maitriser?.length > 0 && (
          <>
            <div style={{ fontSize: 12, fontWeight: 700, marginTop: 10, marginBottom: 4 }}>
              📖 Vocabulaire à maîtriser
            </div>
            <div style={{ display: 'grid', gap: 6, gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
              {p.synthese_20_20.vocabulaire_a_maitriser.map((v, i) => (
                <div key={i} style={{ padding: 6, fontSize: 11, background: 'var(--bg-card, rgba(255,255,255,0.04))', borderRadius: 4 }}>
                  <strong style={{ color: 'oklch(0.78 0.16 90)' }}>{v.terme}</strong>
                  <div style={{ color: 'var(--fg-dim, #aaa)', marginTop: 2 }}>{v.definition_exacte}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div style={sectionStyle('oklch(0.72 0.12 200)')}>
        <div style={sectionTitle}>🗂 Fiches stylisées ({p.fiches.length})</div>
        <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
          {p.fiches.map((f, i) => (
            <div key={i} style={{ padding: 10, borderRadius: 6, background: 'var(--bg-card, rgba(255,255,255,0.04))', border: '1px solid oklch(0.72 0.12 200 / 0.30)' }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>
                {f.icone || '📄'} {f.titre}
              </div>
              <div style={{ fontSize: 11, fontStyle: 'italic', color: 'var(--fg-dim, #aaa)', marginBottom: 6 }}>{f.definition}</div>
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11, lineHeight: 1.4 }}>
                {f.idees_cles.map((k, j) => <li key={j}>{k}</li>)}
              </ul>
              {f.schema_ascii_ou_data && (
                <pre style={{ marginTop: 6, fontSize: 10, padding: 6, background: 'var(--bg-raised, rgba(255,255,255,0.02))', borderRadius: 4, overflow: 'auto', maxHeight: 200 }}>{f.schema_ascii_ou_data}</pre>
              )}
              {f.mnemonique && (
                <div style={{ marginTop: 6, padding: 4, fontSize: 10, fontStyle: 'italic', background: 'oklch(0.74 0.13 90 / 0.15)', borderRadius: 3 }}>
                  💡 {f.mnemonique}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {p.exos_apprentissage?.length > 0 && (
        <div style={sectionStyle('oklch(0.74 0.13 60)')}>
          <div style={sectionTitle}>🎯 Exos d'apprentissage ({p.exos_apprentissage.length})</div>
          <div style={{ display: 'grid', gap: 6, gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
            {p.exos_apprentissage.map((e, i) => (
              <details key={i} style={{ padding: 8, fontSize: 11, background: 'var(--bg-card, rgba(255,255,255,0.04))', borderRadius: 4, cursor: 'pointer' }}>
                <summary style={{ fontWeight: 600 }}>
                  <span style={{ color: 'oklch(0.78 0.16 60)', marginRight: 6 }}>[{e.type}]</span>
                  {e.question}
                </summary>
                <div style={{ marginTop: 6, color: 'var(--fg, #f5f5f5)' }}>
                  <strong>Réponse :</strong> {e.reponse}
                  {e.indice && <div style={{ color: 'var(--fg-mute, #888)', fontSize: 10, marginTop: 2 }}>💡 {e.indice}</div>}
                </div>
              </details>
            ))}
          </div>
        </div>
      )}

      <div style={sectionStyle('oklch(0.55 0.18 25)')}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
          <div style={sectionTitle}>📝 Contrôle d'évaluation</div>
          <span style={{ fontSize: 11, color: 'var(--fg-mute, #888)' }}>
            ({p.controle.duration_min} min · {p.controle.points_questions + p.controle.points_developpement} pts)
          </span>
        </div>
        {!academy.parcoursControleStartedAt && !correction && (
          <button type="button" onClick={() => academy.startParcoursControle()}
            style={{ marginTop: 6, padding: '8px 16px', fontWeight: 600, background: 'oklch(0.55 0.18 25 / 0.20)', color: 'oklch(0.78 0.16 25)', border: '1px solid oklch(0.55 0.18 25 / 0.55)', borderRadius: 99, cursor: 'pointer' }}>
            🏁 Démarrer le contrôle ({p.controle.duration_min} min)
          </button>
        )}
        {academy.parcoursControleStartedAt && !correction && (
          <>
            <div style={{ marginTop: 8, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: timeLeft != null && timeLeft < 300 ? 'oklch(0.55 0.18 25 / 0.20)' : 'var(--bg-card, rgba(255,255,255,0.04))', borderRadius: 6 }}>
              <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 16, fontWeight: 700, color: timeLeft != null && timeLeft < 300 ? 'oklch(0.78 0.16 25)' : 'var(--fg, #f5f5f5)' }}>
                ⏱ {formatTime(timeLeft)}
              </span>
              <span style={{ fontSize: 11, color: 'var(--fg-dim, #aaa)' }}>temps restant</span>
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>Questions courtes ({p.controle.points_questions} pts)</div>
              {p.controle.questions.map((q) => (
                <div key={q.id} style={{ marginBottom: 10 }}>
                  <label style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>
                    <strong>Q{q.id}</strong> ({q.points} pts) — {q.q}
                  </label>
                  <textarea
                    value={academy.parcoursAnswers[q.id] || ''}
                    onChange={(e) => academy.setParcoursAnswer(q.id, e.target.value)}
                    rows={2}
                    style={{ width: '100%', padding: 6, fontSize: 12, background: 'var(--bg-card, rgba(255,255,255,0.04))', color: 'var(--fg, #f5f5f5)', border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 4, fontFamily: 'inherit', resize: 'vertical' }} />
                </div>
              ))}
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 4 }}>
                Développement construit ({p.controle.points_developpement} pts)
              </div>
              <div style={{ fontSize: 12, fontStyle: 'italic', marginBottom: 8, padding: 6, background: 'var(--bg-card, rgba(255,255,255,0.04))', borderRadius: 4 }}>
                <strong>Sujet :</strong> {p.controle.developpement.consigne}
              </div>
              {p.controle.developpement.plan_indicatif?.length > 0 && (
                <div style={{ fontSize: 11, color: 'var(--fg-dim, #aaa)', marginBottom: 6 }}>
                  Plan indicatif : {p.controle.developpement.plan_indicatif.join(' · ')}
                </div>
              )}
              <textarea
                value={academy.parcoursDevAnswer}
                onChange={(e) => academy.setParcoursDevAnswer(e.target.value)}
                rows={12}
                placeholder="Rédige ici ton développement construit (intro, axes, conclusion)..."
                style={{ width: '100%', padding: 8, fontSize: 12, background: 'var(--bg-card, rgba(255,255,255,0.04))', color: 'var(--fg, #f5f5f5)', border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 4, fontFamily: 'inherit', resize: 'vertical', minHeight: 200 }} />
            </div>
            <button type="button"
              onClick={() => void academy.submitParcoursControle()}
              disabled={academy.parcoursCorrecting}
              style={{ padding: '10px 20px', fontWeight: 700, background: 'oklch(0.65 0.18 145 / 0.20)', color: 'oklch(0.78 0.16 145)', border: '1px solid oklch(0.65 0.18 145 / 0.55)', borderRadius: 99, cursor: academy.parcoursCorrecting ? 'wait' : 'pointer' }}>
              {academy.parcoursCorrecting ? '⏳ Correction en cours...' : '✓ Soumettre pour correction'}
            </button>
          </>
        )}
        {correction && (
          <div style={{ marginTop: 10, padding: 12, borderRadius: 8, background: 'var(--bg-card, rgba(255,255,255,0.04))', border: '1px solid oklch(0.65 0.18 145 / 0.45)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, paddingBottom: 10, borderBottom: '1px solid var(--line-soft, rgba(255,255,255,0.10))', marginBottom: 10 }}>
              <div style={{ fontSize: 36, fontWeight: 900, color: correction.total >= 16 ? 'oklch(0.78 0.16 145)' : correction.total >= 12 ? 'oklch(0.78 0.16 80)' : 'oklch(0.78 0.16 25)', fontFamily: 'var(--font-display, serif)' }}>
                {correction.total}/{correction.total_max}
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>Mention : {correction.mention}</div>
                <div style={{ fontSize: 11, color: 'var(--fg-dim, #aaa)' }}>
                  Questions : {correction.questions_score}/{p.controle.points_questions} · Développement : {correction.developpement_score}/{p.controle.points_developpement}
                </div>
              </div>
            </div>
            <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 6 }}>Détail par question</div>
            {correction.questions_breakdown.map((qb) => (
              <div key={qb.id} style={{ fontSize: 11, marginBottom: 4, padding: 4, background: 'var(--bg-raised, rgba(255,255,255,0.02))', borderRadius: 3 }}>
                <strong>Q{qb.id}</strong> {qb.awarded}/{qb.max} — {qb.comment}
              </div>
            ))}
            <div style={{ fontSize: 11, fontWeight: 700, marginTop: 10, marginBottom: 4 }}>Développement</div>
            <div style={{ fontSize: 11, padding: 6, background: 'var(--bg-raised, rgba(255,255,255,0.02))', borderRadius: 3 }}>
              <div style={{ display: 'flex', gap: 12, fontFamily: 'var(--font-mono, monospace)', fontSize: 10, marginBottom: 4 }}>
                <span>plan {correction.developpement_breakdown.plan_score}</span>
                <span>contenu {correction.developpement_breakdown.contenu_score}</span>
                <span>rigueur {correction.developpement_breakdown.rigueur_score}</span>
                <span>expression {correction.developpement_breakdown.expression_score}</span>
              </div>
              <div style={{ marginBottom: 6 }}>{correction.developpement_breakdown.feedback}</div>
              {correction.developpement_breakdown.erreurs?.length > 0 && (
                <div style={{ color: 'oklch(0.78 0.16 25)', fontSize: 10 }}>
                  ⚠ {correction.developpement_breakdown.erreurs.join(' · ')}
                </div>
              )}
              <div style={{ marginTop: 6, fontStyle: 'italic', color: 'oklch(0.78 0.16 145)' }}>
                ➤ {correction.developpement_breakdown.progression}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// v83g — TabSwitcher Dashboard/Conversation : permet de swipper (clic ou
// flèche horizontale) entre les deux vues du module Academy.
function AcademyTabSwitcher({
  current,
  onChange,
}: {
  current: 'dashboard' | 'conversation'
  onChange: (tab: 'dashboard' | 'conversation') => void
}) {
  const TABS = [
    { id: 'dashboard' as const, label: 'Dashboard', hint: 'Brief + sphère + form + parcours' },
    { id: 'conversation' as const, label: 'Conversation', hint: 'Discute avec le prof IA en libre' },
  ]
  return (
    <div
      role="tablist"
      aria-label="Vue Academy"
      style={{
        display: 'flex', gap: 6, padding: '10px 18px 8px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.025), transparent)',
      }}
    >
      {TABS.map((t) => {
        const active = current === t.id
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active}
            title={t.hint}
            onClick={() => onChange(t.id)}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: 11.5, letterSpacing: '0.08em',
              textTransform: 'uppercase',
              background: active ? 'oklch(0.86 0.18 75 / 0.16)' : 'transparent',
              color: active ? 'oklch(0.86 0.18 75)' : 'var(--fg-mute, #888)',
              border: `1px solid ${active ? 'oklch(0.86 0.18 75 / 0.4)' : 'rgba(255,255,255,0.08)'}`,
              cursor: 'pointer',
              transition: 'background 120ms ease, color 120ms ease, border 120ms ease',
            }}
          >
            {t.label}
          </button>
        )
      })}
      <div style={{ flex: 1 }} />
      <span style={{
        alignSelf: 'center', fontFamily: 'var(--font-mono, monospace)',
        fontSize: 10, color: 'var(--fg-mute, #777)', letterSpacing: '0.12em',
      }}>
        {current === 'dashboard' ? '↔ swipe vers Conversation' : '↔ swipe vers Dashboard'}
      </span>
    </div>
  )
}
