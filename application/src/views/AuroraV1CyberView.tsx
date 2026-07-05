/**
 * AuroraV1CyberView — Editorial dojo port for the Cyber module.
 *
 * Visual chrome from _design/aurora_design_screens_v1/modules.jsx
 * (CyberScreen): two columns — editorial briefing on the left with
 * kata title, OWASP tags, leaderboard panel; terminal/lab on the right
 * with objectives strip below. Real wiring through useCyberViewLogic so
 * every Manga feature carries over: 8 katas, XP/belt, offense/defense
 * stance, lab forging via ollamaChat, lab evolve, objective grading
 * with verdict cards, 3-level deep hints, multi-stage CTF unlock,
 * leaderboard recording, postMessage auto-validation.
 */
import { lazy, Suspense, useEffect, useState } from 'react'
import { HelpCircle, Loader2, RefreshCw, ShieldCheck, Sparkles, Target, Wand2, X, Zap } from 'lucide-react'
import { useCyberViewLogic, computeBelt } from '../hooks/useCyberViewLogic'
import { useFileDrop } from '../hooks/useFileDrop'
import { getDailyTip } from '../utils/dailyTip'
import { useAchievementToasts } from '../hooks/useAchievementToasts'
import Sparkline from '../components/Sparkline'
import TextPreviewExpander from '../components/TextPreviewExpander'
import LyraCharacter from '../components/voice/LyraCharacter'
import VoicePushToTalk from '../components/VoicePushToTalk'
const AchievementsPanel = lazy(() => import('../components/AchievementsPanel'))
const CyberWeeklyChallenges = lazy(() => import('../components/CyberWeeklyChallenges'))

const GREEN = 'oklch(0.70 0.13 130)'
const PURPLE = '#a63fc9'

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

function Btn({ size = 'md', variant = 'ghost', children, onClick, disabled, style, title }: {
  size?: 'sm' | 'md' | 'lg'; variant?: 'primary' | 'ghost' | 'bare' | 'danger'
  children: React.ReactNode; onClick?: () => void; disabled?: boolean
  style?: React.CSSProperties; title?: string
}) {
  const fg = variant === 'primary' ? 'var(--ink-1000, #0a0a0a)'
    : variant === 'danger' ? '#ff6a3d' : 'var(--fg, #f5f5f5)'
  const bg = variant === 'primary' ? GREEN
    : variant === 'bare' ? 'transparent' : 'var(--bg-card, rgba(255,255,255,0.04))'
  return (
    <button type="button" onClick={onClick} disabled={disabled} title={title}
      style={{
        fontFamily: 'var(--font-sans, system-ui)',
        fontSize: size === 'sm' ? 12 : size === 'lg' ? 14 : 13,
        padding: size === 'sm' ? '6px 12px' : size === 'lg' ? '12px 20px' : '9px 16px',
        background: bg, color: fg,
        border: variant === 'bare' ? 'none' : '1px solid var(--line, rgba(255,255,255,0.12))',
        borderRadius: 'var(--r-md, 10px)', cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        display: 'inline-flex', alignItems: 'center', gap: 6, justifyContent: 'center',
        ...style,
      }}>{children}</button>
  )
}

const CYBER_HELP_KEY = 'aurora-cyber-help-dismissed-v1'

/**
 * v83a — Carte « Comment ça marche ? » : la Cyber utilisait un jargon
 * dojo/manga (kata, sensei, ceinture, stance, épreuve) qui rendait le
 * module opaque pour un nouvel arrivant. Cette carte explique en clair
 * en 3 étapes + un mini-lexique. Repliable, mémorisée dans localStorage,
 * réouvrable via le bouton « ? » de l'en-tête.
 */
function CyberHelpCard({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null
  const Step = ({ n, children }: { n: number; children: React.ReactNode }) => (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <span style={{
        flexShrink: 0, width: 22, height: 22, borderRadius: 99,
        background: GREEN, color: 'var(--ink-1000, #0a0a0a)',
        fontWeight: 800, fontSize: 12, display: 'inline-flex',
        alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-mono, monospace)',
      }}>{n}</span>
      <span style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--fg-dim, #ccc)' }}>{children}</span>
    </div>
  )
  return (
    <div style={{
      padding: 16, borderRadius: 12,
      background: 'oklch(0.70 0.13 130 / 0.07)',
      border: '1px solid oklch(0.70 0.13 130 / 0.35)',
      display: 'flex', flexDirection: 'column', gap: 12,
      position: 'relative',
    }}>
      <button type="button" onClick={onClose} title="Masquer cette aide (réouvrable via « ? »)"
        style={{
          position: 'absolute', top: 8, right: 8, background: 'transparent',
          border: 'none', cursor: 'pointer', color: 'var(--fg-mute, #888)',
          padding: 4, lineHeight: 0,
        }}>
        <X size={14} />
      </button>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <ShieldCheck size={18} color={GREEN} />
        <span style={{
          fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
          fontStyle: 'italic', fontSize: 22, color: 'var(--fg, #f5f5f5)',
        }}>Cyber — l'atelier de cybersécurité</span>
      </div>
      <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: 'var(--fg-dim, #aaa)' }}>
        Tu apprends la sécurité informatique <b>en pratiquant</b> : l'IA (le « sensei »)
        te fabrique un mini-labo interactif dans la fenêtre de droite, et tu dois résoudre
        ses objectifs (trouver un mot de passe, casser un chiffrement, repérer une faille web…).
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Step n={1}>Choisis un <b>thème</b> dans « Ateliers » ci-dessous (crypto, réseau, web, mots de passe…).</Step>
        <Step n={2}>Clique <b>« Démarrer l'atelier »</b>. L'IA génère le labo (~10–30 s).</Step>
        <Step n={3}>Manipule le labo à droite, puis coche / fais <b>« valider »</b> chaque objectif. Tu gagnes de l'XP et tu montes de « ceinture ».</Step>
      </div>
      <div style={{
        fontSize: 11.5, lineHeight: 1.7, color: 'var(--fg-mute, #999)',
        fontFamily: 'var(--font-mono, monospace)',
        borderTop: '1px dashed var(--line-soft, rgba(255,255,255,0.1))', paddingTop: 10,
      }}>
        <b style={{ color: 'var(--fg-dim, #bbb)' }}>Lexique</b><br />
        kata = un atelier (un thème) · sensei = l'IA qui te coache · ceinture = ton niveau (comme au judo : blanche → noire) ·
        offense = tu joues l'attaquant · défense = tu joues celui qui protège · épreuve = même atelier mais en mode chrono noté ·
        flag = le « drapeau » (un code <code>flag&#123;…&#125;</code>) qui prouve que tu as réussi.
      </div>
    </div>
  )
}

export default function AuroraV1CyberView() {
  const C = useCyberViewLogic()
  useAchievementToasts() // v82dd : toast quand un badge se débloque
  // v83a : carte « comment ça marche » — affichée tant que pas explicitement masquée.
  const [helpOpen, setHelpOpen] = useState(() => {
    try { return window.localStorage.getItem(CYBER_HELP_KEY) !== '1' } catch { return true }
  })
  const dismissHelp = () => {
    setHelpOpen(false)
    try { window.localStorage.setItem(CYBER_HELP_KEY, '1') } catch { /* ignore */ }
  }
  const openHelp = () => {
    setHelpOpen(true)
    try { window.localStorage.removeItem(CYBER_HELP_KEY) } catch { /* ignore */ }
  }
  // v82eq : feedback temporaire "✓ copié" sur le bouton briefing copy
  const [briefingCopied, setBriefingCopied] = useState(false)
  useEffect(() => {
    if (!briefingCopied) return
    const t = window.setTimeout(() => setBriefingCopied(false), 1600)
    return () => window.clearTimeout(t)
  }, [briefingCopied])
  // v82fj/v82fk : drop zone fichier(s) sur la vue Cyber → uploadNotesMulti
  // (concatène plusieurs fichiers en une note unique avec séparateurs).
  const drop = useFileDrop({
    onFiles: (fs) => void C.uploadNotesMulti(fs),
    accept: ['txt', 'md', 'markdown', 'pdf', 'docx'],
    acceptMime: ['text/', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    disabled: C.notesUploading,
  })

  return (
    <div
      {...drop.bind}
      className="aurora-v1-cols"
      style={{
      height: '100%', display: 'grid', gridTemplateColumns: '1fr 1.4fr',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)', overflow: 'hidden',
      position: 'relative',
      outline: drop.isDraggingOver ? '2px dashed oklch(0.74 0.13 60)' : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      transition: 'outline 120ms ease',
    }}>
      {/* v82fj : hint visuel pendant drag-over */}
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
          📑 Déposer le fichier · txt / md / pdf / docx
        </div>
      )}
      {/* Editorial briefing */}
      <div style={{
        padding: '36px 32px', borderRight: '1px solid var(--line, rgba(255,255,255,0.12))',
        display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Eyebrow dot={GREEN} style={{ flex: 1 }}>※ Cyber · Atelier : {C.active.discipline} · étape {C.stage}/4</Eyebrow>
          <span title="Module Cyber configuré sans garde-fou — labo pédagogique local"
            style={{
              padding: '3px 9px', borderRadius: 99,
              fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
              letterSpacing: '0.14em', textTransform: 'uppercase',
              background: 'oklch(0.62 0.22 25 / 0.18)',
              color: 'oklch(0.85 0.18 30)',
              border: '1px solid oklch(0.62 0.22 25 / 0.5)',
              boxShadow: '0 0 10px oklch(0.62 0.22 25 / 0.25)',
              display: 'inline-flex', alignItems: 'center', gap: 5,
            }}>
            <span style={{
              width: 6, height: 6, borderRadius: 3,
              background: 'oklch(0.62 0.22 25)',
              boxShadow: '0 0 8px oklch(0.62 0.22 25)',
            }} />
            EXPERT · ZÉRO FILTRE
          </span>
          <button type="button" onClick={openHelp} title="Comment ça marche ?"
            style={{
              background: 'transparent', border: '1px solid var(--line, rgba(255,255,255,0.14))',
              borderRadius: 99, cursor: 'pointer', color: 'var(--fg-dim, #aaa)',
              padding: '4px 9px', display: 'inline-flex', alignItems: 'center', gap: 5,
              fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
            }}>
            <HelpCircle size={13} /> aide
          </button>
        </div>
        <CyberHelpCard open={helpOpen} onClose={dismissHelp} />
        <Display size={56}>{C.active.discipline}<br/><em style={{ color: 'var(--ember-500, #ff6a3d)' }} title={`« ${C.active.name} » est le nom-code de cet atelier`}>{C.active.name}</em></Display>
        <p style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--fg-dim, #aaa)', maxWidth: 420, margin: 0 }}>
          {C.active.lesson}
        </p>
        <KataExpertServiceChips kataId={C.activeId} />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <Tag accent={GREEN}>{C.active.discipline}</Tag>
          <Tag>{'★'.repeat(C.active.difficulty)}{'☆'.repeat(3 - C.active.difficulty)}</Tag>
          <Tag>{C.active.stance}</Tag>
          <Tag accent={C.belt === 'noire' ? '#fff' : undefined}>ceinture {C.belt}</Tag>
          <Tag>{C.xp}/{C.nextThresh} XP</Tag>
          {/* v82i3 + v82i4 : streak jours consécutifs (current + record) */}
          {C.currentStreak > 0 && (
            <Tag accent={C.currentStreak >= 7 ? 'oklch(0.78 0.16 80)' : undefined}>
              <span title={`Streak actuel : ${C.currentStreak} jour${C.currentStreak > 1 ? 's' : ''} consécutif${C.currentStreak > 1 ? 's' : ''}\nRecord all-time : ${C.longestStreak} jour${C.longestStreak > 1 ? 's' : ''}${C.currentStreak === C.longestStreak ? ' · 🏆 actuel = record' : ''}`}>
                🔥 {C.currentStreak}j{C.longestStreak > C.currentStreak ? ` / record ${C.longestStreak}j` : C.currentStreak >= 7 ? ' 🏆' : ''}
              </span>
            </Tag>
          )}
          {/* v82ee : badge rang Cyber all-time (équivalent mention
              Bac académique). Calculé sur total XP + katas uniques
              résolus. Affiché si au moins un run. */}
          {C.bestRank && (
            <span
              title={`Rang Cyber · ${C.bestRank.xp} XP cumulés · ${C.bestRank.katas} kata(s) résolu(s)`}
              style={{
                padding: '2px 8px', borderRadius: 3, fontSize: 11,
                background: 'oklch(0.74 0.13 60 / 0.12)',
                border: '1px solid oklch(0.74 0.13 60 / 0.35)',
                color: 'oklch(0.74 0.13 60)',
                fontFamily: 'var(--font-mono, monospace)', fontWeight: 700,
                display: 'inline-flex', alignItems: 'center', gap: 4,
              }}>
              <span>{C.bestRank.glyph}</span>
              <span>{C.bestRank.label}</span>
            </span>
          )}
          {/* v82do : sparkline XP cumulé sur 30 derniers runs */}
          {C.xpCumulativeSeries.length >= 3 && (
            <span title={`XP cumulés sur ${C.xpCumulativeSeries.length - 1} dernier(s) run(s)`}
              style={{ display: 'inline-flex', alignItems: 'center' }}>
              <Sparkline values={C.xpCumulativeSeries} width={110} height={20} color="oklch(0.74 0.13 60)" smooth smoothWindow={5} showAxis />
            </span>
          )}
          {/* v82cu : reset XP only — granularité plus fine que tout
              effacer dans Settings. Garde les runs/leaderboards intacts. */}
          <button type="button"
            onClick={() => {
              if (window.confirm(`Remettre l'XP à zéro (ceinture blanche) ?\n\nLes runs leaderboards et achievements ne sont PAS touchés.`)) {
                C.resetXpOnly()
              }
            }}
            title="Reset XP / belt seul"
            style={{
              padding: '2px 8px', fontSize: 9,
              fontFamily: 'var(--font-mono, monospace)',
              background: 'transparent', color: 'var(--fg-mute, #777)',
              border: '1px dashed var(--line, rgba(255,255,255,0.12))',
              borderRadius: 3, cursor: 'pointer',
            }}>↻ reset XP</button>
          {/* v82er : upload notes/writeup personnel comme contexte
              gradeAnswer. Mêmes formats que Academy (.txt/.md/.pdf/.docx). */}
          <label
            title={C.notesName ? `Notes "${C.notesName}" actives — ${C.notesText.length} car. Cliquer pour remplacer.` : 'Charge un fichier notes/writeup (.txt/.md/.pdf/.docx) qui sera passé comme contexte au grader IA.'}
            style={{
              padding: '2px 8px', fontSize: 9,
              fontFamily: 'var(--font-mono, monospace)',
              background: C.notesName ? 'oklch(0.74 0.13 60 / 0.12)' : 'transparent',
              color: C.notesName ? 'oklch(0.74 0.13 60)' : 'var(--fg-mute, #777)',
              border: `1px ${C.notesName ? 'solid' : 'dashed'} ${C.notesName ? 'oklch(0.74 0.13 60 / 0.45)' : 'var(--line, rgba(255,255,255,0.12))'}`,
              borderRadius: 3, cursor: C.notesUploading ? 'wait' : 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: 4,
            }}>
            {C.notesUploading ? '⌛ load…' : C.notesName ? `📑 ${C.notesName.slice(0, 14)}${C.notesName.length > 14 ? '…' : ''}` : '📑 notes (txt/md/pdf/docx)'}
            <input
              id="cyber-notes-upload"
              name="cyberNotesUpload"
              aria-label="Charger un fichier notes/writeup pour le grader IA"
              type="file"
              accept=".txt,.md,.markdown,.pdf,.docx,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void C.uploadNotes(f)
                e.target.value = ''
              }}
              disabled={C.notesUploading}
              style={{ display: 'none' }} />
          </label>
          {C.notesName && (
            <button type="button"
              onClick={C.clearNotes}
              title="Retirer les notes actives"
              style={{
                padding: '2px 6px', fontSize: 9,
                fontFamily: 'var(--font-mono, monospace)',
                background: 'transparent', color: 'var(--fg-mute, #777)',
                border: '1px dashed var(--line, rgba(255,255,255,0.12))',
                borderRadius: 3, cursor: 'pointer',
              }}>×</button>
          )}
          {/* v82fg : paste from clipboard direct comme notes */}
          <button type="button"
            onClick={() => void C.pasteNotesFromClipboard()}
            disabled={C.notesUploading}
            title="Coller le contenu du presse-papiers comme notes"
            style={{
              padding: '2px 8px', fontSize: 9,
              fontFamily: 'var(--font-mono, monospace)',
              background: 'transparent',
              color: 'var(--fg-mute, #777)',
              border: '1px dashed var(--line, rgba(255,255,255,0.12))',
              borderRadius: 3,
              cursor: C.notesUploading ? 'not-allowed' : 'pointer',
              opacity: C.notesUploading ? 0.5 : 1,
            }}>
            📋 coller
          </button>
        </div>
        {/* v82es + v82eu : preview inline notesText avec modal
            "voir tout". Composant partagé Academy + Cyber.
            v82fc : onTextChange = setNotesText pour find & replace. */}
        {C.notesName && (
          <TextPreviewExpander
            name={C.notesName}
            text={C.notesText}
            glyph="📑"
            label="contexte actif"
            onTextChange={C.setNotesText}
            originalText={C.notesOriginalText}
          />
        )}

        {/* Stance toggle */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Eyebrow>Tu joues le rôle de…</Eyebrow>
          <div style={{ display: 'flex', gap: 6 }}>
            <Btn size="sm" variant={C.stance === 'offense' ? 'primary' : 'ghost'} onClick={() => C.setStance('offense')}
              title="Offense : tu te mets dans la peau de l'attaquant — tu cherches la faille.">
              <Target size={11} /> Attaquant
            </Btn>
            <Btn size="sm" variant={C.stance === 'defense' ? 'primary' : 'ghost'} onClick={() => C.setStance('defense')}
              title="Défense : tu te mets dans la peau de celui qui protège — tu corriges / surveilles.">
              <ShieldCheck size={11} /> Défenseur
            </Btn>
          </div>
        </div>

        {/* v84d — Palette d'outils experts cyber dispos, indépendamment du kata */}
        <CyberToolsPalette />

        {/* Kata picker */}
        <Eyebrow style={{ marginTop: 8 }}>Ateliers — choisis un thème</Eyebrow>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
          {C.KATAS.map((k) => {
            const Icon = k.icon
            const isActive = k.id === C.activeId
            return (
              <button key={k.id} type="button" onClick={() => C.setActiveKata(k.id)}
                style={{
                  padding: '10px 12px',
                  background: isActive ? k.tone : 'var(--bg-card, rgba(255,255,255,0.04))',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))',
                  borderRadius: 8, cursor: 'pointer', textAlign: 'left',
                  color: isActive ? 'var(--ink-1000, #0a0a0a)' : 'var(--fg, #f5f5f5)',
                  display: 'flex', flexDirection: 'column', gap: 4,
                }}>
                <Icon size={16} strokeWidth={2.2} />
                <div style={{ fontSize: 12, fontWeight: 700 }}>{k.name}</div>
                <div style={{ fontSize: 9, opacity: 0.7, fontFamily: 'var(--font-mono, monospace)' }}>{k.discipline}</div>
              </button>
            )
          })}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 56, height: 68, flexShrink: 0 }}>
            <LyraCharacter
              phase={C.labLoading ? 'thinking' : 'idle'}
              emotion={C.labLoading ? 'focus' : 'curious'}
              accent="#ff5a82"
              size={56}
            />
          </div>
          <Btn variant="primary" size="lg" onClick={C.launchKata} disabled={C.labLoading}
            title="L'IA va générer un mini-labo interactif sur ce thème (≈ 10–30 s), puis il s'ouvre à droite.">
            {C.labLoading ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> L'IA prépare l'atelier…</>
              : <><Zap size={14} fill="currentColor" /> ▶ Démarrer l'atelier</>}
          </Btn>
        </div>

        {/* v82cd : Challenge du jour — kata déterministe par date. */}
        <div style={{
          padding: 12, marginTop: 4, borderRadius: 8,
          background: C.dailyDone
            ? 'oklch(0.72 0.12 145 / 0.10)'
            : 'oklch(0.74 0.13 60 / 0.08)',
          border: `1px solid ${C.dailyDone ? 'oklch(0.72 0.12 145 / 0.5)' : 'oklch(0.74 0.13 60 / 0.5)'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <Eyebrow dot={C.dailyDone ? 'oklch(0.72 0.12 145)' : 'oklch(0.74 0.13 60)'}>
              📅 Challenge du jour · {C.dailyDateKey}
            </Eyebrow>
            <span style={{ flex: 1 }} />
            {C.dailyDone && (
              <span style={{
                fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                color: 'oklch(0.72 0.12 145)', fontWeight: 700,
                letterSpacing: '0.14em', textTransform: 'uppercase',
              }}>✓ réussi</span>
            )}
          </div>
          <div style={{
            fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
            fontStyle: 'italic', fontSize: 17, marginBottom: 6,
            color: 'var(--fg, #f5f5f5)',
          }}>
            « {C.dailyKata.name} » · {C.dailyKata.discipline}
          </div>
          <div style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
            color: 'var(--fg-dim, #aaa)', marginBottom: 8, lineHeight: 1.5,
          }}>
            difficulté {C.dailyKata.difficulty}/3 · {C.dailyKata.lesson}
          </div>
          <button type="button" onClick={() => void C.launchDailyChallenge()}
            disabled={C.labLoading}
            style={{
              width: '100%', padding: '8px 12px',
              background: C.dailyDone ? 'transparent' : 'oklch(0.74 0.13 60)',
              color: C.dailyDone ? 'oklch(0.74 0.13 60)' : '#0a0a0a',
              border: `1px solid oklch(0.74 0.13 60)`,
              borderRadius: 6, fontSize: 12, fontWeight: 600,
              cursor: C.labLoading ? 'not-allowed' : 'pointer',
              opacity: C.labLoading ? 0.5 : 1,
              fontFamily: 'var(--font-sans, system-ui)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
            {C.labLoading ? <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Forge…</>
              : C.dailyDone ? <><Sparkles size={12} /> Refaire le challenge</>
              : <><Zap size={12} /> Engager le challenge du jour</>}
          </button>
          {/* v82er : pioche aléatoire d'un autre kata du roster */}
          <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
            <button type="button" onClick={C.randomKata}
              disabled={C.labLoading}
              title="Tirer un kata au hasard du roster"
              style={{
                flex: 1, padding: '6px 12px',
                background: 'transparent',
                color: 'var(--fg-dim, #aaa)',
                border: '1px dashed var(--line, rgba(255,255,255,0.18))',
                borderRadius: 6, fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                cursor: C.labLoading ? 'not-allowed' : 'pointer',
                opacity: C.labLoading ? 0.5 : 1,
              }}>
              🎲 Kata aléatoire
            </button>
            {/* v82ew : kata random + forge auto (zéro-clic) */}
            <button type="button"
              onClick={() => void C.randomKataAndForge()}
              disabled={C.labLoading}
              title="Tirer un kata au hasard ET forger le lab immédiatement"
              style={{
                padding: '6px 12px',
                background: 'oklch(0.74 0.13 60)',
                color: '#0a0a0a',
                border: '1px solid oklch(0.74 0.13 60)',
                borderRadius: 6, fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                cursor: C.labLoading ? 'not-allowed' : 'pointer',
                opacity: C.labLoading ? 0.5 : 1,
                fontWeight: 700,
              }}>
              ⚡ kata · go
            </button>
          </div>
        </div>

        {/* v82bu / v83b : atelier sur-mesure — replié par défaut pour ne pas
            surcharger le débutant ; reste accessible aux curieux. */}
        <details style={{
          padding: '8px 10px', marginTop: 4,
          background: 'oklch(0.55 0.18 25 / 0.06)',
          border: '1px dashed oklch(0.55 0.18 25 / 0.4)',
          borderRadius: 8,
        }}>
          <summary style={{
            cursor: 'pointer', fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--fg-dim, #aaa)',
            outline: 'none',
          }}>
            ⚙ Atelier sur-mesure (avancé)
          </summary>
          <div style={{ marginTop: 8 }}>
            <p style={{ margin: '0 0 8px', fontSize: 11.5, lineHeight: 1.5, color: 'var(--fg-mute, #999)' }}>
              Décris en une phrase ce que tu veux apprendre — l'IA fabrique un atelier complet rien que pour ça.
            </p>
            <input
              id="cyber-custom-brief"
              name="cyberCustomBrief"
              aria-label="Brief libre pour générer un atelier sur-mesure"
              type="text"
              value={C.customBrief}
              onChange={(e) => C.setCustomBrief(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault()
                  if (!C.labLoading && C.customBrief.trim()) void C.forgeCustomKata()
                }
              }}
              disabled={C.labLoading}
              placeholder="Ex : « casser un chiffre de Vigenère » · « injection SQL aveugle sur un login » · « extraire un message caché dans une image PNG »"
              style={{
                width: '100%', padding: '6px 10px', marginBottom: 6,
                background: 'var(--bg-input, var(--bg-card, rgba(255,255,255,0.04)))',
                color: 'var(--fg, #f5f5f5)',
                border: '1px solid var(--line, rgba(255,255,255,0.12))',
                borderRadius: 6, fontSize: 12,
                fontFamily: 'var(--font-sans, system-ui)',
              }}
            />
            <button type="button"
              onClick={() => void C.forgeCustomKata()}
              disabled={C.labLoading || !C.customBrief.trim()}
              style={{
                width: '100%', padding: '8px 12px',
                background: (C.labLoading || !C.customBrief.trim()) ? 'transparent' : 'oklch(0.55 0.18 25)',
                color: (C.labLoading || !C.customBrief.trim()) ? 'var(--fg-mute, #777)' : '#fff',
                border: '1px solid oklch(0.55 0.18 25 / 0.6)',
                borderRadius: 6, fontSize: 12, fontWeight: 600,
                cursor: (C.labLoading || !C.customBrief.trim()) ? 'not-allowed' : 'pointer',
                opacity: (C.labLoading || !C.customBrief.trim()) ? 0.5 : 1,
                fontFamily: 'var(--font-sans, system-ui)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}>
              {C.labLoading
                ? <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> L'IA prépare ton atelier…</>
                : <><Zap size={12} /> Créer cet atelier sur-mesure</>}
            </button>
          </div>
        </details>
        <style>{`@keyframes spin { to { transform: rotate(360deg) } } details > summary { list-style: none } details > summary::-webkit-details-marker { display: none }`}</style>
        {C.labError && <div style={{ color: '#ff6a3d', fontSize: 12 }}>⚠ {C.labError}</div>}

        {/* v82br : Mode épreuve / libre toggle + timer + score live.
            En mode "libre" → pratique sans pression, pas de score.
            En mode "épreuve" → countdown actif, score time-based,
            hint penalty -50/indice. Auto-stop à success/timeout. */}
        <div style={{
          padding: 12, borderRadius: 8,
          background: C.mode === 'epreuve'
            ? 'oklch(0.55 0.18 25 / 0.12)'
            : 'var(--bg-raised, rgba(255,255,255,0.04))',
          border: `1px solid ${C.mode === 'epreuve' ? 'oklch(0.55 0.18 25)' : 'var(--line, rgba(255,255,255,0.12))'}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <Eyebrow dot={C.mode === 'epreuve' ? 'oklch(0.72 0.14 25)' : undefined}>
              Mode · {C.mode === 'epreuve' ? 'ÉPREUVE LIVE' : 'libre'}
            </Eyebrow>
            <span style={{ flex: 1 }} />
            {C.mode === 'libre' && C.lab && (
              <>
                {[300, 600, 900, 1800].map((sec) => (
                  <button key={sec} type="button"
                    onClick={() => C.startEpreuve(sec)}
                    style={{
                      padding: '4px 8px', fontSize: 10,
                      fontFamily: 'var(--font-mono, monospace)',
                      background: 'transparent', color: 'var(--fg-dim, #aaa)',
                      border: '1px solid var(--line, rgba(255,255,255,0.12))',
                      borderRadius: 4, cursor: 'pointer',
                    }}>{Math.round(sec / 60)} min</button>
                ))}
              </>
            )}
            {C.mode === 'epreuve' && (
              <button type="button" onClick={() => C.stopEpreuve('abandon')}
                style={{
                  padding: '4px 10px', fontSize: 11, fontWeight: 600,
                  background: 'oklch(0.55 0.18 25)', color: '#fff',
                  border: 'none', borderRadius: 4, cursor: 'pointer',
                  fontFamily: 'var(--font-sans, system-ui)',
                }}>Abandonner</button>
            )}
          </div>
          {C.mode === 'epreuve' && (
            <>
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                marginBottom: 6,
              }}>
                <div style={{
                  fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
                  fontStyle: 'italic', fontSize: 32,
                  color: C.epreuveTimeLeftSec < 60 ? 'oklch(0.72 0.14 25)' : 'var(--fg, #f5f5f5)',
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {Math.floor(C.epreuveTimeLeftSec / 60)}:{String(C.epreuveTimeLeftSec % 60).padStart(2, '0')}
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{
                    fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                    color: 'var(--fg-mute, #777)', letterSpacing: '0.14em',
                  }}>SCORE</div>
                  <div style={{
                    fontFamily: 'var(--font-mono, monospace)', fontSize: 22, fontWeight: 700,
                    color: 'oklch(0.74 0.13 60)',
                  }}>{C.epreuveScore}</div>
                </div>
              </div>
              <div style={{
                height: 4, borderRadius: 99, overflow: 'hidden',
                background: 'var(--ink-800, rgba(255,255,255,0.06))',
              }}>
                <div style={{
                  height: '100%',
                  width: `${(C.epreuveTimeLeftSec / Math.max(1, C.epreuveDurationSec)) * 100}%`,
                  background: C.epreuveTimeLeftSec < 60 ? 'oklch(0.55 0.18 25)' : 'oklch(0.74 0.13 60)',
                  transition: 'width 0.5s linear',
                }} />
              </div>
              <div style={{
                marginTop: 6, fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                color: 'var(--fg-dim, #aaa)', display: 'flex', gap: 12, flexWrap: 'wrap',
              }}>
                <span>obj {C.completedCount}/{C.lab?.objectives.length ?? 0}</span>
                <span>hints {C.hintsUsedInRun} · −{C.hintCostInRun}</span>
                {C.allDone && <span style={{ color: 'oklch(0.72 0.12 145)' }}>● ALL DONE</span>}
              </div>
            </>
          )}
          {C.mode === 'libre' && C.epreuveResult && (
            <div style={{
              padding: 8, marginTop: 4,
              background: 'var(--bg-card, rgba(255,255,255,0.04))',
              border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
              borderRadius: 6, fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            }}>
              <div style={{
                fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
                fontStyle: 'italic', fontSize: 18,
                color: C.epreuveResult.timeoutHit ? 'oklch(0.72 0.14 25)' : 'oklch(0.72 0.12 145)',
                marginBottom: 4,
              }}>
                {C.epreuveResult.timeoutHit ? 'Temps écoulé' : C.epreuveResult.completed === C.epreuveResult.total ? 'Réussi !' : 'Abandonné'}
              </div>
              <div style={{ color: 'var(--fg-dim, #aaa)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <span>score <b style={{ color: 'oklch(0.74 0.13 60)' }}>{C.epreuveResult.score}</b></span>
                <span>{C.epreuveResult.completed}/{C.epreuveResult.total} obj</span>
                <span>{Math.floor(C.epreuveResult.timeUsedSec / 60)}m {C.epreuveResult.timeUsedSec % 60}s</span>
                <span>{C.epreuveResult.hintsUsed} indice(s)</span>
              </div>
            </div>
          )}
          {C.mode === 'libre' && !C.epreuveResult && !C.lab && (
            <>
              <div style={{
                fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                color: 'var(--fg-mute, #777)',
              }}>Lance un kata pour activer le mode épreuve.</div>
              {/* v82fu : daily tip Cyber */}
              <div style={{
                marginTop: 6, padding: '6px 10px',
                fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
                color: 'var(--fg-dim, #aaa)',
                background: 'oklch(0.74 0.13 60 / 0.06)',
                border: '1px solid oklch(0.74 0.13 60 / 0.22)',
                borderRadius: 6, lineHeight: 1.55,
              }}>
                {getDailyTip('cyber')}
              </div>
            </>
          )}
          {C.mode === 'libre' && C.lab && !C.epreuveResult && (
            <div style={{
              fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
              color: 'var(--fg-mute, #777)',
            }}>Choisis une durée pour démarrer la course chrono. Sinon entraîne-toi librement.</div>
          )}
          {/* v82cp : export markdown lab session — visible si un lab
              actif (briefing + objectifs valent la peine d'être archivés). */}
          {C.lab && (
            <div style={{ marginTop: 6, display: 'flex', justifyContent: 'flex-end' }}>
              <button type="button" onClick={C.exportLabSessionMarkdown}
                title="Exporter le lab + briefing + objectifs + journal en .md"
                style={{
                  padding: '4px 10px', fontSize: 10,
                  background: 'transparent',
                  color: 'oklch(0.74 0.13 60)',
                  border: '1px solid oklch(0.74 0.13 60 / 0.5)',
                  borderRadius: 4, cursor: 'pointer',
                  fontFamily: 'var(--font-mono, monospace)',
                }}>📥 Export .md</button>
            </div>
          )}
        </div>

        {/* v82bs : Leaderboard ÉPREUVE séparé — top scores time-based.
            Affiche seulement quand il y a au moins une run épreuve, sinon
            le panel reste discret pour ne pas spammer la vue. */}
        {C.epreuveRunsForActive.length > 0 && (
          <div style={{
            padding: 12,
            background: 'oklch(0.74 0.13 60 / 0.06)',
            border: '1px solid oklch(0.74 0.13 60 / 0.3)',
            borderRadius: 10,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Eyebrow dot="oklch(0.74 0.13 60)">Top scores · épreuve · {C.active.name}</Eyebrow>
              <span style={{ flex: 1 }} />
              {/* v82dn : sparkline scores épreuve sur ce kata */}
              {(() => {
                const series = C.epreuveRunsForActive
                  .slice()
                  .sort((a, b) => a.startedAt - b.startedAt)
                  .map((r) => r.score ?? 0)
                  .filter((s) => s > 0)
                if (series.length < 2) return null
                return (
                  <span title={`${series.length} épreuves · évolution score`}
                    style={{ display: 'inline-flex', alignItems: 'center', marginRight: 4 }}>
                    <Sparkline values={series} width={70} height={18} color="oklch(0.74 0.13 60)" />
                  </span>
                )
              })()}
              <span style={{
                fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
                color: 'var(--fg-mute, #777)',
              }}>{C.epreuveRunsForActive.length} run(s)</span>
            </div>
            {C.epreuveRunsForActive
              .slice()
              .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
              .slice(0, 3)
              .map((r, i) => (
                <div key={`${r.startedAt}`} style={{
                  display: 'flex', alignItems: 'baseline', gap: 8,
                  padding: '4px 0', borderTop: i > 0 ? '1px dashed var(--line-soft, rgba(255,255,255,0.06))' : 'none',
                  fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                }}>
                  <span style={{ width: 18, color: 'var(--fg-mute, #777)' }}>
                    {i === 0 ? '🥇' : i === 1 ? '🥈' : '🥉'}
                  </span>
                  <span style={{
                    fontWeight: 700, color: 'oklch(0.74 0.13 60)',
                    minWidth: 50, fontVariantNumeric: 'tabular-nums',
                  }}>{r.score ?? 0}</span>
                  <span style={{ color: 'var(--fg-dim, #aaa)' }}>
                    {r.objectivesDone}/{r.totalObjectives} obj
                  </span>
                  <span style={{ color: 'var(--fg-mute, #777)' }}>
                    {r.hintsTaken} indice(s)
                  </span>
                  <span style={{ flex: 1 }} />
                  <span style={{ color: 'var(--fg-mute, #777)' }}>
                    {Math.floor((r.durationMs / 1000) / 60)}m {Math.floor(r.durationMs / 1000) % 60}s
                  </span>
                  {r.timeoutHit && (
                    <span style={{ color: 'oklch(0.72 0.14 25)' }}>⏱</span>
                  )}
                </div>
              ))}
          </div>
        )}

        {/* v83x — Stats lifetime sur le kata actif : nb runs, success rate,
            temps moyen, top score, dernière run. Discret si aucune run. */}
        {C.runsForActive && C.runsForActive.length > 0 && (
          <KataLifetimeStats runs={C.runsForActive} kataName={C.active.name} />
        )}

        {/* v83b : trophées + défis hebdo regroupés et repliés par défaut. */}
        <details style={{
          padding: '8px 10px',
          background: 'var(--bg-raised, rgba(255,255,255,0.03))',
          border: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
          borderRadius: 8,
        }}>
          <summary style={{
            cursor: 'pointer', fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--fg-dim, #aaa)', outline: 'none',
          }}>
            🏆 Trophées & défis de la semaine
          </summary>
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Suspense fallback={null}>
              <AchievementsPanel filter={['cyber', 'cross']} />
            </Suspense>
            <Suspense fallback={null}>
              <CyberWeeklyChallenges />
            </Suspense>
          </div>
        </details>

        {/* Leaderboard panel */}
        <div style={{
          marginTop: 'auto', padding: 14,
          background: 'var(--bg-raised, rgba(255,255,255,0.04))',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 10,
        }}>
          <Eyebrow style={{ marginBottom: 8 }}>Leaderboard · {C.active.name}</Eyebrow>
          {C.runsForActive.length === 0 ? (
            <div style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11, color: 'var(--fg-mute, #777)' }}>
              — pas encore de run · sois le premier
            </div>
          ) : (
            C.runsForActive.slice(0, 4).map((r, i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '24px 1fr auto auto',
                gap: 10, fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                padding: '4px 0',
                color: i === 0 ? GREEN : 'var(--fg-dim, #aaa)',
              }}>
                <span style={{ color: 'var(--fg-mute, #777)' }}>{String(i + 1).padStart(2, '0')}</span>
                <span>stg {r.stage} · {r.flagsFound} flags</span>
                <span>{Math.round(r.durationMs / 1000)}s</span>
                <span style={{ color: GREEN }}>+{r.xpEarned}xp</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Terminal lab */}
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {C.lab ? (
          <>
            <div style={{
              padding: '12px 18px', borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <Eyebrow dot={GREEN}>Atelier en cours · {C.lab.title}</Eyebrow>
              <span style={{ flex: 1 }} />
              <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11, color: 'var(--fg-dim, #aaa)' }}>
                {C.completedCount}/{C.lab.objectives.length} · {C.progressPct}%
              </span>
              <button type="button" onClick={C.reloadSandbox} title="Recharger"
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg-dim, #aaa)' }}>
                <RefreshCw size={13} />
              </button>
              <button type="button" onClick={C.closeLab} title="Fermer"
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--fg-dim, #aaa)' }}>
                <X size={13} />
              </button>
            </div>

            {C.lab.briefing && (
              <div style={{
                padding: '10px 18px', fontSize: 13, fontStyle: 'italic',
                color: 'var(--fg-dim, #aaa)',
                borderBottom: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
                position: 'relative',
              }}>
                {C.lab.briefing}
                {/* v82ep + v82eq : copy briefing avec feedback "✓ copié" 1.6s */}
                <button type="button"
                  onClick={async () => {
                    try {
                      if (C.lab?.briefing) {
                        await navigator.clipboard.writeText(C.lab.briefing)
                        setBriefingCopied(true)
                      }
                    } catch { /* silent */ }
                  }}
                  title={briefingCopied ? 'Copié dans le presse-papiers' : 'Copier le briefing dans le presse-papiers'}
                  style={{
                    position: 'absolute', top: 6, right: 8,
                    padding: '2px 8px', fontSize: 9,
                    fontFamily: 'var(--font-mono, monospace)',
                    background: briefingCopied ? 'oklch(0.74 0.13 60 / 0.20)' : 'transparent',
                    color: briefingCopied ? 'oklch(0.74 0.13 60)' : 'var(--fg-mute, #777)',
                    border: `1px ${briefingCopied ? 'solid' : 'dashed'} ${briefingCopied ? 'oklch(0.74 0.13 60 / 0.55)' : 'var(--line, rgba(255,255,255,0.18))'}`,
                    borderRadius: 3, cursor: 'pointer',
                    fontStyle: 'normal',
                    fontWeight: briefingCopied ? 700 : 400,
                    transition: 'all 0.18s',
                  }}>
                  {briefingCopied ? '✓ copié' : '📋 copy'}
                </button>
              </div>
            )}

            <iframe
              key={`${C.lab.kataId}-${C.sandboxKey}`}
              title="Lab cyber sensei"
              srcDoc={C.lab.html}
              sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
              style={{ flex: 1, width: '100%', border: 'none', background: '#0b0d13' }}
            />

            {/* Evolve strip */}
            <div style={{
              padding: '8px 18px', display: 'flex', gap: 8,
              borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
              background: 'var(--bg-raised, rgba(255,255,255,0.02))',
            }}>
              <input type="text" value={C.evolveHint}
                onChange={(e) => C.setEvolveHint(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && C.evolveHint.trim()) { e.preventDefault(); void C.evolveLab() } }}
                placeholder="Demande à l'IA de faire évoluer le labo (ex : ajoute un visualiseur hexa · rends-le plus dur · ajoute un indice)…"
                style={{
                  flex: 1, padding: '6px 10px', fontSize: 12,
                  background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
                  border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 6,
                  fontFamily: 'var(--font-mono, monospace)',
                }} />
              <VoicePushToTalk
                onTranscript={(text) => C.setEvolveHint((C.evolveHint ? C.evolveHint + ' ' : '') + text)}
                label="Dicter la mutation du lab cyber"
                disabled={C.labLoading}
                variant="ghost"
                size={28}
              />
              <Btn size="sm" onClick={() => void C.evolveLab()} disabled={!C.evolveHint.trim() || C.labLoading}>
                <Wand2 size={11} /> Évoluer
              </Btn>
            </div>

            {/* Objectives strip */}
            <div style={{
              padding: '10px 18px', maxHeight: 200, overflowY: 'auto',
              borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
              background: 'var(--bg-card, rgba(255,255,255,0.02))',
            }}>
              <Eyebrow style={{ marginBottom: 6 }}>🎯 Objectifs</Eyebrow>
              {C.lab.objectives.map((obj) => {
                const done = C.doneObjectives.has(obj.id)
                return (
                  <div key={obj.id} style={{
                    display: 'flex', gap: 8, padding: '4px 0', fontSize: 12,
                    opacity: done ? 0.6 : 1,
                    textDecoration: done ? 'line-through' : 'none',
                  }}>
                    <button type="button" onClick={() => C.toggleObjective(obj.id)}
                      style={{
                        width: 18, height: 18, borderRadius: 4, flexShrink: 0,
                        background: done ? GREEN : 'transparent',
                        border: '1px solid var(--line, rgba(255,255,255,0.12))',
                        cursor: 'pointer', color: '#000', fontSize: 11,
                      }}>{done ? '✓' : ''}</button>
                    <div style={{ flex: 1 }}>{obj.text}</div>
                    <button type="button" onClick={() => C.setGraderFor(C.graderFor === obj.id ? null : obj.id)}
                      style={{
                        fontSize: 10, padding: '2px 6px', cursor: 'pointer',
                        background: 'transparent', color: GREEN,
                        border: `1px solid ${GREEN}`, borderRadius: 4,
                      }}>🎯 valider</button>
                    {[1, 2, 3].map((lvl) => {
                      const taken = (C.deepHints[obj.id] || []).some((h) => h.level === lvl)
                      return (
                        <button key={lvl} type="button"
                          disabled={!!C.deepHintBusy || taken}
                          onClick={() => void C.askDeepHint(obj, lvl as 1|2|3)}
                          style={{
                            fontSize: 10, padding: '2px 6px',
                            background: taken ? 'var(--ember-500, #ff6a3d)' : 'transparent',
                            color: taken ? '#000' : 'var(--fg-dim, #aaa)',
                            border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 4,
                            cursor: taken ? 'default' : 'pointer',
                          }}>💡{lvl}</button>
                      )
                    })}
                  </div>
                )
              })}
              {C.allDone && (
                <div style={{
                  marginTop: 8, padding: 8,
                  background: GREEN, color: '#000',
                  borderRadius: 6, fontSize: 12, fontWeight: 700,
                  display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between',
                }}>
                  <span><Sparkles size={12} style={{ verticalAlign: 'middle' }} /> Lab complété — +{C.active.difficulty * 30} XP</span>
                  {C.stage < 4 && <Btn size="sm" onClick={C.advanceStage}>⚔ Stage {C.stage + 1}/4</Btn>}
                </div>
              )}
              {C.graderFor && (() => {
                const obj = C.lab!.objectives.find((o) => o.id === C.graderFor)
                if (!obj) return null
                return (
                  <div style={{ marginTop: 6, padding: 8, background: 'var(--bg-card, rgba(255,255,255,0.04))', borderRadius: 6 }}>
                    <textarea rows={2}
                      value={C.graderAnswer[obj.id] || ''}
                      onChange={(e) => C.setGraderAnswer({ ...C.graderAnswer, [obj.id]: e.target.value })}
                      placeholder={obj.flag ? 'Colle le flag…' : 'Ta réponse…'}
                      style={{
                        width: '100%', padding: 6, fontSize: 12,
                        background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
                        border: '1px solid var(--line, rgba(255,255,255,0.12))', borderRadius: 4,
                        fontFamily: 'var(--font-mono, monospace)', resize: 'vertical',
                      }} />
                    <Btn size="sm" disabled={!!C.graderBusy || !(C.graderAnswer[obj.id] || '').trim()}
                      onClick={() => void C.gradeCyberObjective(obj, (C.graderAnswer[obj.id] || '').trim())}>
                      🧠 {C.graderBusy === obj.id ? '…' : 'Évaluer'}
                    </Btn>
                  </div>
                )
              })()}
            </div>
          </>
        ) : (
          <div style={{
            flex: 1, padding: 0, display: 'flex', flexDirection: 'column',
            background: 'oklch(0.06 0.01 250)', overflow: 'auto',
          }}>
            {/* v83a : panneau d'accueil clair quand aucun atelier n'est ouvert */}
            <div style={{
              padding: '28px 28px 22px', borderBottom: '1px solid var(--line-soft, rgba(255,255,255,0.07))',
              display: 'flex', flexDirection: 'column', gap: 14,
            }}>
              <div style={{
                fontFamily: 'var(--font-display, "Cormorant Garamond", serif)',
                fontStyle: 'italic', fontSize: 26, color: 'var(--fg, #f5f5f5)',
              }}>
                Aucun atelier ouvert pour l'instant
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--fg-dim, #aaa)', maxWidth: 520 }}>
                À gauche : choisis un thème dans <b>« Ateliers »</b>, choisis si tu joues
                l'<b>attaquant</b> ou le <b>défenseur</b>, puis clique
                <b style={{ color: GREEN }}> « ▶ Démarrer l'atelier »</b>. L'IA fabrique ici
                même un mini-labo interactif (terminal, formulaire, visualiseur…) avec ses objectifs.
              </div>
              <button type="button" onClick={C.launchKata} disabled={C.labLoading}
                style={{
                  alignSelf: 'flex-start', padding: '11px 20px', borderRadius: 10,
                  background: C.labLoading ? 'transparent' : GREEN,
                  color: C.labLoading ? 'var(--fg-mute, #777)' : 'var(--ink-1000, #0a0a0a)',
                  border: `1px solid ${GREEN}`, fontWeight: 700, fontSize: 14,
                  cursor: C.labLoading ? 'wait' : 'pointer',
                  fontFamily: 'var(--font-sans, system-ui)',
                  display: 'inline-flex', alignItems: 'center', gap: 8,
                }}>
                {C.labLoading
                  ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> L'IA prépare l'atelier…</>
                  : <><Zap size={14} fill="currentColor" /> ▶ Démarrer l'atelier « {C.active.discipline} »</>}
              </button>
              <div style={{
                fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                color: 'var(--fg-mute, #777)', display: 'flex', gap: 14, flexWrap: 'wrap',
              }}>
                <span>thème : <b style={{ color: 'var(--fg-dim, #aaa)' }}>{C.active.discipline}</b></span>
                <span>rôle : <b style={{ color: 'var(--fg-dim, #aaa)' }}>{C.stance === 'offense' ? 'attaquant' : 'défenseur'}</b></span>
                <span>ta ceinture : <b style={{ color: 'var(--fg-dim, #aaa)' }}>{C.belt}</b> ({C.xp} XP)</span>
              </div>
            </div>

            {/* Terminal log (esthétique conservée mais relégué en bas) */}
            <div style={{
              flex: 1, padding: 22, fontFamily: 'var(--font-mono, monospace)',
              fontSize: 12, lineHeight: 1.7, color: 'var(--fg-dim, #888)',
            }}>
              <div style={{ color: 'var(--fg-mute, #666)', marginBottom: 8 }}># journal de la session</div>
              {C.logs.length === 0 && (
                <div style={{ color: 'var(--fg-mute, #555)' }}>— rien pour l'instant —</div>
              )}
              {C.logs.slice(-10).map((l) => (
                <div key={l.id} style={{
                  fontSize: 11, marginBottom: 4,
                  color: l.tone === 'xp' ? GREEN : l.tone === 'attack' ? '#ff6a3d' : 'var(--fg-mute, #888)',
                }}>{l.text}</div>
              ))}
              <div style={{ marginTop: 10, color: GREEN }}>$ <span style={{
                borderRight: '8px solid var(--ember-500, #ff6a3d)',
                animation: 'aurora-blink 1s steps(2) infinite',
              }}>&nbsp;</span></div>
              <style>{`@keyframes aurora-blink { 50% { opacity: 0 } }`}</style>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// v83x — Stats lifetime du kata actif : runs, success rate, temps moyen.
function KataLifetimeStats({ runs, kataName }: {
  runs: Array<{ durationMs: number; hintsTaken: number; flagsFound: number; objectivesDone: number; totalObjectives: number; xpEarned: number; endedAt: number }>
  kataName: string
}) {
  const totalRuns = runs.length
  const completedRuns = runs.filter((r) => r.objectivesDone >= r.totalObjectives).length
  const successRate = totalRuns > 0 ? Math.round((completedRuns / totalRuns) * 100) : 0
  const totalMs = runs.reduce((s, r) => s + r.durationMs, 0)
  const avgMs = totalRuns > 0 ? Math.round(totalMs / totalRuns) : 0
  const totalHints = runs.reduce((s, r) => s + r.hintsTaken, 0)
  const totalFlags = runs.reduce((s, r) => s + r.flagsFound, 0)
  const totalXp = runs.reduce((s, r) => s + r.xpEarned, 0)
  const lastRun = runs.length > 0 ? runs[runs.length - 1] : null
  const fmt = (ms: number) => {
    const s = Math.floor(ms / 1000)
    return `${Math.floor(s / 60)}m ${s % 60}s`
  }
  return (
    <div style={{
      padding: 12,
      background: 'oklch(0.72 0.13 195 / 0.05)',
      border: '1px solid oklch(0.72 0.13 195 / 0.28)',
      borderRadius: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
        <Eyebrow dot="oklch(0.72 0.13 195)" style={{ flex: 1 }}>Lifetime · {kataName}</Eyebrow>
        <span style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
          color: 'var(--fg-mute, #777)',
        }}>{totalRuns} run{totalRuns > 1 ? 's' : ''}</span>
      </div>
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6,
        fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
      }}>
        <div style={{ padding: '4px 8px', background: 'rgba(255,255,255,0.025)', borderRadius: 4 }}>
          <div style={{ fontSize: 9, color: 'var(--fg-mute, #777)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>success</div>
          <div style={{ color: successRate >= 75 ? 'oklch(0.78 0.16 145)' : successRate >= 50 ? 'oklch(0.82 0.16 90)' : 'oklch(0.72 0.14 25)' }}>
            {successRate}%
          </div>
        </div>
        <div style={{ padding: '4px 8px', background: 'rgba(255,255,255,0.025)', borderRadius: 4 }}>
          <div style={{ fontSize: 9, color: 'var(--fg-mute, #777)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>temps moy</div>
          <div style={{ color: 'var(--fg, #f5f5f5)' }}>{fmt(avgMs)}</div>
        </div>
        <div style={{ padding: '4px 8px', background: 'rgba(255,255,255,0.025)', borderRadius: 4 }}>
          <div style={{ fontSize: 9, color: 'var(--fg-mute, #777)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>xp total</div>
          <div style={{ color: 'oklch(0.74 0.13 60)' }}>{totalXp}</div>
        </div>
        <div style={{ padding: '4px 8px', background: 'rgba(255,255,255,0.025)', borderRadius: 4 }}>
          <div style={{ fontSize: 9, color: 'var(--fg-mute, #777)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>flags</div>
          <div style={{ color: 'var(--fg, #f5f5f5)' }}>{totalFlags}</div>
        </div>
        <div style={{ padding: '4px 8px', background: 'rgba(255,255,255,0.025)', borderRadius: 4 }}>
          <div style={{ fontSize: 9, color: 'var(--fg-mute, #777)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>indices</div>
          <div style={{ color: 'var(--fg, #f5f5f5)' }}>{totalHints}</div>
        </div>
        <div style={{ padding: '4px 8px', background: 'rgba(255,255,255,0.025)', borderRadius: 4 }}>
          <div style={{ fontSize: 9, color: 'var(--fg-mute, #777)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>cumul</div>
          <div style={{ color: 'var(--fg, #f5f5f5)' }}>{fmt(totalMs)}</div>
        </div>
      </div>
      {lastRun && (
        <div style={{
          marginTop: 8, paddingTop: 8,
          borderTop: '1px dashed var(--line-soft, rgba(255,255,255,0.06))',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
          color: 'var(--fg-mute, #888)',
        }}>
          Dernière run : {fmt(lastRun.durationMs)} · {lastRun.objectivesDone}/{lastRun.totalObjectives} obj · {lastRun.hintsTaken} indice(s) · {new Date(lastRun.endedAt).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
        </div>
      )}
    </div>
  )
}

// v84d — Palette d'outils experts cyber, accès rapide indépendant des katas.
// Liste tous les services TS dispos avec leur surface fonctionnelle.
function CyberToolsPalette() {
  const tools = [
    { icon: '🔐', name: 'classicalCipherAnalysis', desc: 'IC · χ² · auto-detect César/Vigenère/XOR/base32/64/hex/binary/atbash/rot47', tone: '#67d2ff' },
    { icon: '🛡️', name: 'jwtInspector', desc: 'decode + audit OWASP (alg:none, MD5, claims sensibles, exp/nbf/iat)', tone: '#b48cff' },
    { icon: '🔓', name: 'breachChecker', desc: 'HIBP-style offline + leet/suffix/prefix + credential reuse', tone: '#ff5a82' },
    { icon: '⚙️', name: 'kdfCostAnalyzer', desc: 'Argon2id / bcrypt / PBKDF2 — coût attaque cloud GPU USD', tone: '#ff8c42' },
    { icon: '🔍', name: 'hashParameterParser', desc: 'parse $argon2id$/$2b$12$, audit OWASP 2024', tone: '#67d2ff' },
    { icon: '📊', name: 'passwordAnalyzer', desc: 'zxcvbn-style entropy + crack time GPU', tone: '#ff8c42' },
    { icon: '🌐', name: 'cryptoService', desc: 'AES-GCM / RSA / DH (WebCrypto local)', tone: '#a78bfa' },
    { icon: '🎯', name: 'cryptoVulnerabilities', desc: 'détecte ECB / IV répété / signatures faibles', tone: '#10b981' },
  ]
  return (
    <div style={{
      padding: 10,
      background: 'oklch(0.62 0.22 25 / 0.04)',
      border: '1px solid oklch(0.62 0.22 25 / 0.22)',
      borderRadius: 10,
      marginTop: 8,
    }}>
      <Eyebrow dot="oklch(0.62 0.22 25)" style={{ marginBottom: 8 }}>
        Outils cyber dispos · zéro filtre
      </Eyebrow>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 4 }}>
        {tools.map((t) => (
          <div key={t.name} title={t.desc}
            style={{
              padding: '6px 10px', borderRadius: 6,
              background: `${t.tone}0c`,
              border: `1px solid ${t.tone}28`,
              display: 'flex', alignItems: 'flex-start', gap: 8,
            }}>
            <span style={{ fontSize: 14, marginTop: 1 }}>{t.icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
                color: t.tone, fontWeight: 600,
              }}>{t.name}</div>
              <div style={{
                fontSize: 10, color: 'var(--fg-dim, #aaa)',
                marginTop: 1, lineHeight: 1.4,
              }}>{t.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// v83n — chips qui montrent les services experts pré-câblés pour le kata actif.
// Helper visuel : l'utilisateur sait QUOI il aura dans le lab.
function KataExpertServiceChips({ kataId }: { kataId: string }) {
  const MAP: Record<string, Array<{ label: string; tone: string }>> = {
    crypto: [
      { label: 'classicalCipherAnalysis', tone: '#67d2ff' },
      { label: 'jwtInspector', tone: '#b48cff' },
      { label: 'frequency χ²/IC', tone: '#67d2ff' },
      { label: 'AES-GCM · RSA · DH', tone: '#a78bfa' },
    ],
    password: [
      { label: 'passwordAnalyzer (zxcvbn-style)', tone: '#ff8c42' },
      { label: 'kdfCostAnalyzer (Argon2/bcrypt)', tone: '#ff8c42' },
      { label: 'breachChecker (HIBP-style local)', tone: '#ff5a82' },
      { label: 'hashParameterParser', tone: '#67d2ff' },
    ],
    hash: [
      { label: 'hashService (MD5/SHA/argon2)', tone: '#67d2ff' },
      { label: 'hashParameterParser', tone: '#67d2ff' },
      { label: 'kdfCostAnalyzer', tone: '#ff8c42' },
    ],
    network: [
      { label: 'NetworkLab tools (nmap/tshark sim)', tone: '#67d2ff' },
      { label: 'TLS cert inspector', tone: '#a78bfa' },
    ],
    forensics: [
      { label: 'EXIF / strings / hexdump', tone: '#67d2ff' },
      { label: 'timeline forensics', tone: '#a78bfa' },
    ],
    stego: [
      { label: 'canvas LSB extraction', tone: '#a78bfa' },
      { label: 'binwalk-like signatures', tone: '#67d2ff' },
    ],
    web: [
      { label: 'XSS/SQLi/SSTI/SSRF/path-trav', tone: '#ff5a82' },
      { label: 'JWT none + alg confusion', tone: '#b48cff' },
    ],
    ctf: [
      { label: 'multi-discipline mashup', tone: '#a78bfa' },
      { label: 'leaderboard', tone: '#67d2ff' },
    ],
    threat: [
      { label: 'IOC parser', tone: '#67d2ff' },
      { label: 'MITRE ATT&CK refs', tone: '#a78bfa' },
    ],
  }
  const chips = MAP[kataId] || []
  if (chips.length === 0) return null
  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: 6,
      padding: '8px 10px', marginTop: 2,
      background: 'rgba(255,255,255,0.025)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 8,
    }}>
      <span style={{
        fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
        letterSpacing: '0.18em', textTransform: 'uppercase',
        color: 'var(--fg-mute, #777)', alignSelf: 'center',
        marginRight: 4,
      }}>services prêts</span>
      {chips.map((c, i) => (
        <span key={i} style={{
          padding: '2px 7px', borderRadius: 99,
          fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
          color: c.tone,
          background: `${c.tone}1a`,
          border: `1px solid ${c.tone}40`,
        }}>{c.label}</span>
      ))}
    </div>
  )
}

void computeBelt
