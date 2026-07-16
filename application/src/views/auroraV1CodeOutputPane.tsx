import { lazy, Suspense } from 'react'
import { Plus, Send, Sparkles, StopCircle } from 'lucide-react'
import FavoriteButton from '../components/FavoriteButton'
import type { UseCodeViewLogic } from '../hooks/useCodeViewLogic'
import type { ParsedFile } from '../services/codeOutputFiles'
import { getDailyTip } from '../utils/dailyTip'
import {
  FOLLOWUP_LABELS,
  GREEN,
  RED,
  detectStreamLanguage,
} from './auroraV1CodeHelpers'
import { MachinePanelSection } from './auroraV1CodeMachinePanel'
import { AuroraV1CodeOutputHeader } from './auroraV1CodeOutputHeader'

const CodeBlock = lazy(() => import('../components/CodeBlock'))

type FinalStats = {
  avg: number
  max: number
  tokens: number
  durationSec: number
} | null

type CodeStreakView = {
  current: number
  longest: number
}

export function AuroraV1CodeOutputPane({
  code,
  codeStreak,
  editorName,
  finalStats,
  handleOpenInEditor,
  live,
  openingFolder,
  parsedFiles,
  setLive,
  tokensPerSec,
  tpsHistory,
}: {
  code: UseCodeViewLogic
  codeStreak: CodeStreakView
  editorName: string
  finalStats: FinalStats
  handleOpenInEditor: () => Promise<void>
  live: boolean
  openingFolder: boolean
  parsedFiles: ParsedFile[]
  setLive: (live: boolean) => void
  tokensPerSec: number | null
  tpsHistory: number[]
}) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      minWidth: 0, minHeight: 0, height: '100%',
    }}>
      <AuroraV1CodeOutputHeader
        code={code}
        finalStats={finalStats}
        tokensPerSec={tokensPerSec}
        tpsHistory={tpsHistory}
      />

      {code.hasOutput && !code.streaming ? (
        <div style={{
          flex: '1 1 0', overflow: 'auto', minHeight: 0,
          display: 'flex', flexDirection: 'column',
        }}>
          <Suspense fallback={
            <pre style={{
              padding: '18px 22px', margin: 0,
              fontFamily: 'var(--font-mono, monospace)', fontSize: 12, lineHeight: 1.7,
              color: 'var(--fg, #f5f5f5)',
              whiteSpace: 'pre',
              overflow: 'auto', flex: '1 1 0', minHeight: 0,
            }}>{code.streamOutput}</pre>
          }>
            <CodeBlock
              code={code.streamOutput}
              language={detectStreamLanguage(code.draft, code.streamOutput)}
              showLineNumbers={true}
            />
          </Suspense>
          {code.error && (
            <div style={{ color: RED, padding: '8px 22px', fontSize: 11 }}>
              ⚠ {code.error}
            </div>
          )}
        </div>
      ) : code.streaming ? (
        <pre style={{
          flex: '1 1 0', padding: '18px 22px', margin: 0,
          minHeight: 0,
          fontFamily: 'var(--font-mono, monospace)', fontSize: 12, lineHeight: 1.7,
          color: 'var(--fg, #f5f5f5)', overflow: 'auto',
          whiteSpace: 'pre',
        }}>
          {code.streamOutput}
          <span style={{
            display: 'inline-block', width: 7, height: 14,
            background: GREEN, verticalAlign: 'text-bottom',
            animation: 'aurora-blink 1s steps(2) infinite',
          }} />
          <style>{`@keyframes aurora-blink { 50% { opacity: 0 } }`}</style>
        </pre>
      ) : (
        <div style={{
          flex: '1 1 0', minHeight: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          color: 'var(--fg-mute, #777)', fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
        }}>
          <Sparkles size={16} /> Aucun résultat
        </div>
      )}

      {!code.hasOutput && !code.streaming && !live && (
        <div style={{
          padding: '6px 14px',
          borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
          fontSize: 11, fontFamily: 'var(--font-mono, monospace)',
          color: 'var(--fg-dim, #aaa)',
          background: 'oklch(0.74 0.13 60 / 0.04)',
        }}>
          {getDailyTip('code')}
        </div>
      )}

      <div style={{
        padding: 14, gap: 8,
        borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
        display: 'flex', flexDirection: 'column',
        flexShrink: 0,
        maxHeight: '40%',
        overflowY: 'auto',
        background: 'var(--bg, #0c0a09)',
      }}>
        {(code.hasProject || (code.workMode === 'repo' && code.repoLoaded)) && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
            padding: '5px 10px', borderRadius: 6, marginBottom: 2,
            background: 'oklch(0.72 0.12 145 / 0.08)',
            border: '1px solid oklch(0.72 0.12 145 / 0.30)',
            fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
            color: 'oklch(0.84 0.14 145)',
          }}>
            <span style={{ width: 6, height: 6, borderRadius: 99, background: 'currentColor' }} />
            {code.workMode === 'repo' && code.repoLabel
              ? <span>repo <b>{code.repoLabel}</b>{code.repoScan?.branch ? ` · ${code.repoScan.branch}` : ''} · {code.files.length} fichier(s) — la prochaine demande modifie ce code</span>
              : <span>Projet en cours · {code.files.length} fichier(s) — ta prochaine demande le <b>modifie</b> (pas un nouveau projet)</span>}
            {code.followUpKind && FOLLOWUP_LABELS[code.followUpKind] && (
              <span style={{
                marginLeft: 'auto', padding: '1px 7px', borderRadius: 99,
                background: 'oklch(0.72 0.12 145 / 0.18)', color: 'oklch(0.88 0.16 145)',
              }}>{FOLLOWUP_LABELS[code.followUpKind]}</span>
            )}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            id="code-draft-input"
            name="codeDraft"
            aria-label="Description du code à générer ou modifier"
            type="text"
            value={code.draft}
            onChange={(e) => code.setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault()
                void code.submit()
              }
            }}
            placeholder="Décris la modification ou demande du code… (⌘↵)"
            disabled={code.streaming}
            style={{
              flex: 1, padding: '8px 12px',
              background: 'var(--bg-input, var(--bg-card, rgba(255,255,255,0.04)))',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              borderRadius: 6, fontSize: 12,
              fontFamily: 'var(--font-sans, system-ui)',
            }}
          />
          {code.streaming ? (
            <button type="button" onClick={code.abort}
              style={{
                padding: '6px 12px', background: RED, color: '#fff',
                border: 'none', fontSize: 12, fontWeight: 600,
                cursor: 'pointer', fontFamily: 'var(--font-sans, system-ui)',
                borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 6,
              }}><StopCircle size={13} /> Stop</button>
          ) : (
            <button type="button" onClick={() => void code.submit()}
              disabled={!code.draft.trim()}
              style={{
                padding: '6px 12px', background: GREEN, color: '#0a0a0a',
                border: 'none', fontSize: 12, fontWeight: 600,
                cursor: code.draft.trim() ? 'pointer' : 'not-allowed',
                opacity: code.draft.trim() ? 1 : 0.5,
                fontFamily: 'var(--font-sans, system-ui)',
                borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 6,
              }}><Send size={13} /> Envoyer</button>
          )}
          {!code.streaming && (
            <button type="button"
              onClick={() => {
                code.randomCodePreset()
                window.setTimeout(() => { void code.submit() }, 0)
              }}
              title="Pioche une idée de code au hasard PUIS génère immédiatement"
              style={{
                padding: '6px 12px',
                background: 'oklch(0.74 0.13 60 / 0.10)',
                color: 'oklch(0.74 0.13 60)',
                border: '1px solid oklch(0.74 0.13 60 / 0.45)',
                fontSize: 11, fontWeight: 700,
                fontFamily: 'var(--font-mono, monospace)', cursor: 'pointer',
                borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 4,
              }}>⚡ surprise · go</button>
          )}
          <FavoriteButton
            prompt={code.draft}
            module="code"
            parameters={{ model: code.model }}
            tags={['code']}
            disabled={code.streaming}
          />
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {code.hasProject && !code.streaming && (
            <button type="button" onClick={code.newProject}
              title="Repartir de zéro (efface le projet et la conversation en cours)"
              style={{
                padding: '4px 10px', background: 'oklch(0.55 0.18 25 / 0.10)',
                color: 'oklch(0.78 0.16 25)', border: '1px solid oklch(0.55 0.18 25 / 0.40)',
                fontSize: 11, cursor: 'pointer', borderRadius: 6,
                fontFamily: 'var(--font-sans, system-ui)',
                display: 'inline-flex', alignItems: 'center', gap: 5,
              }}><Plus size={11} /> Nouveau projet</button>
          )}
          {code.hasOutput && !code.streaming && (
            <button type="button" onClick={code.reset}
              style={{
                padding: '4px 10px', background: 'transparent',
                color: 'var(--fg-dim, #aaa)', border: 'none',
                fontSize: 11, cursor: 'pointer',
                fontFamily: 'var(--font-sans, system-ui)',
              }}>↺ Effacer l'aperçu</button>
          )}
          <button type="button" onClick={() => setLive(true)}
            style={{
              padding: '4px 10px', background: 'transparent',
              color: 'var(--fg, #f5f5f5)',
              border: '1px solid var(--line, rgba(255,255,255,0.12))',
              fontSize: 11, cursor: 'pointer',
              fontFamily: 'var(--font-sans, system-ui)',
              borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 6,
            }}><Sparkles size={11} /> Orchestrateur full-power</button>
          {parsedFiles.length > 0 && !code.streaming && (
            <button type="button" onClick={() => { void handleOpenInEditor() }}
              disabled={openingFolder}
              title={`Écrit ${parsedFiles.length} fichier${parsedFiles.length > 1 ? 's' : ''} sur le disque (~/Desktop/AuroraCodeOut/) et ouvre dans ${editorName}.`}
              style={{
                padding: '4px 10px',
                background: openingFolder ? 'transparent' : 'oklch(0.72 0.12 145 / 0.12)',
                color: 'oklch(0.86 0.16 145)',
                border: '1px solid oklch(0.72 0.12 145 / 0.55)',
                fontSize: 11, cursor: openingFolder ? 'wait' : 'pointer',
                fontFamily: 'var(--font-sans, system-ui)',
                borderRadius: 6, display: 'inline-flex', alignItems: 'center', gap: 6,
                opacity: openingFolder ? 0.6 : 1,
              }}>
              ⤓ {openingFolder ? 'Ouverture…' : `Ouvrir dans ${editorName}`}
            </button>
          )}
          <span style={{ flex: 1 }} />
          <span style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 10,
            color: 'var(--fg-mute, #777)',
            display: 'inline-flex', alignItems: 'center', gap: 4,
          }} title={
            code.modelUsed && code.modelUsed !== code.model
              ? `Auto-reroute: ${code.model} → ${code.modelUsed} (modèle général mieux pour design)`
              : 'Modèle de génération'
          }>
            {code.modelUsed && code.modelUsed !== code.model && (
              <span style={{ color: 'oklch(0.74 0.13 60)', fontSize: 9 }}>↳</span>
            )}
            {code.modelUsed || code.model || 'no model'} · stream direct
          </span>
          {codeStreak.current > 0 && (
            <span style={{
              marginLeft: 8, fontSize: 10,
              color: codeStreak.current >= 7 ? 'oklch(0.78 0.16 80)' : 'var(--fg-mute, #777)',
              fontFamily: 'var(--font-mono, monospace)',
            }} title={`Streak Code : ${codeStreak.current} jour(s) · record ${codeStreak.longest}j`}>
              🔥 {codeStreak.current}j{codeStreak.longest > codeStreak.current ? `/${codeStreak.longest}` : codeStreak.current >= 7 ? ' 🏆' : ''}
            </span>
          )}
        </div>
        {code.history.length > 0 && (
          <div style={{
            marginTop: 8, paddingTop: 8,
            borderTop: '1px solid var(--line-soft, rgba(255,255,255,0.08))',
          }}>
            <div style={{
              fontSize: 9, fontFamily: 'var(--font-mono, monospace)',
              letterSpacing: '0.22em', textTransform: 'uppercase',
              color: 'var(--fg-mute, #888)', marginBottom: 4,
            }}>↻ Historique ({code.history.length})</div>
            <div style={{
              display: 'flex', flexDirection: 'column', gap: 2,
              maxHeight: 140, overflowY: 'auto',
            }}>
              {code.history.map((h) => (
                <div key={h.prompt} style={{
                  display: 'grid', gridTemplateColumns: '1fr 22px',
                  gap: 4, alignItems: 'center',
                  padding: '3px 6px', borderRadius: 4,
                  fontSize: 11,
                  background: 'var(--bg-card, rgba(255,255,255,0.03))',
                  border: '1px solid var(--line-soft, rgba(255,255,255,0.06))',
                }}>
                  <button type="button"
                    onClick={() => code.recallPrompt(h)}
                    title={h.prompt}
                    style={{
                      background: 'transparent', border: 'none',
                      padding: 0, color: 'var(--fg, #f5f5f5)',
                      cursor: 'pointer', textAlign: 'left',
                      fontFamily: 'var(--font-mono, monospace)',
                      fontSize: 'inherit',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                    }}>{h.prompt}</button>
                  <button type="button"
                    onClick={() => code.removeHistory(h.prompt)}
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
      </div>
      <MachinePanelSection />
    </div>
  )
}
