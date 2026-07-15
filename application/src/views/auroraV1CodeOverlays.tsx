import { Clock, Download, Save } from 'lucide-react'
import type { UseCodeViewLogic } from '../hooks/useCodeViewLogic'
import type { ParsedFile } from '../services/codeOutputFiles'
import { formatEta } from '../utils/codeDownload'
import { GREEN } from './auroraV1CodeHelpers'

type ConfirmAction = 'download' | 'repo'
type WebPreview = { html: string; entry: ParsedFile; kind: 'html' | 'react' | 'css' }

export function AuroraV1CodeErrorDialog({
  dismissErrorDialog,
  errorDialog,
  retryAfterError,
}: {
  dismissErrorDialog: () => void
  errorDialog: { title: string; message: string; suggestion?: string } | null
  retryAfterError: () => Promise<void>
}) {
  if (!errorDialog) return null

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,0.65)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 32, backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        maxWidth: 480, padding: '24px 28px',
        background: 'oklch(0.18 0.02 30)',
        border: '1px solid oklch(0.55 0.18 25 / 0.6)',
        borderRadius: 12, color: 'var(--fg, #f5f5f5)',
        fontFamily: 'var(--font-sans, system-ui)',
        boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
      }}>
        <div style={{
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          letterSpacing: '0.18em', textTransform: 'uppercase',
          color: 'oklch(0.78 0.16 25)', marginBottom: 12,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          ⚠ Erreur de génération
        </div>
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, lineHeight: 1.3 }}>
          {errorDialog.title}
        </div>
        <div style={{
          fontSize: 13, color: 'var(--fg-dim, #aaa)', marginBottom: 14,
          lineHeight: 1.5, fontFamily: 'var(--font-mono, monospace)',
          padding: '8px 10px', borderRadius: 6,
          background: 'rgba(255,255,255,0.04)',
          maxHeight: 180, overflowY: 'auto',
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>
          {errorDialog.message}
        </div>
        {errorDialog.suggestion && (
          <div style={{
            fontSize: 13, marginBottom: 18, lineHeight: 1.5,
            color: 'oklch(0.84 0.15 60)',
          }}>
            💡 {errorDialog.suggestion}
          </div>
        )}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button type="button" onClick={dismissErrorDialog}
            style={{
              padding: '8px 16px', fontSize: 12,
              background: 'transparent',
              color: 'var(--fg-dim, #aaa)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              borderRadius: 6, cursor: 'pointer',
              fontFamily: 'var(--font-sans, system-ui)',
            }}>Annuler</button>
          <button type="button" onClick={() => { void retryAfterError() }}
            style={{
              padding: '8px 18px', fontSize: 13, fontWeight: 700,
              background: GREEN, color: '#0a0a0a',
              border: 'none', borderRadius: 6, cursor: 'pointer',
              fontFamily: 'var(--font-sans, system-ui)',
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}>OK · Réessayer</button>
        </div>
      </div>
    </div>
  )
}

export function AuroraV1CodeConfirmModal({
  code,
  confirmAction,
  handleDownloadZip,
  setConfirmAction,
  webPreview,
}: {
  code: UseCodeViewLogic
  confirmAction: ConfirmAction | null
  handleDownloadZip: () => Promise<void>
  setConfirmAction: (action: ConfirmAction | null) => void
  webPreview: WebPreview | null
}) {
  if (!confirmAction) return null

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 210, background: 'rgba(0,0,0,0.72)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        width: 'min(860px, 95%)', maxHeight: '88%', display: 'flex', flexDirection: 'column',
        background: 'oklch(0.16 0.012 250)', border: '1px solid var(--line, rgba(255,255,255,0.18))',
        borderRadius: 12, overflow: 'hidden', boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
      }}>
        <div style={{
          padding: '14px 18px', borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 11, letterSpacing: '0.12em',
            textTransform: 'uppercase', color: 'oklch(0.84 0.14 145)',
          }}>
            {confirmAction === 'download'
              ? '⤓ Aperçu avant téléchargement'
              : `↧ Aperçu avant écriture dans ${code.repoLabel || 'le repo'}`}
          </span>
          <span style={{ flex: 1 }} />
          <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 10, color: 'var(--fg-mute, #888)' }}>
            {code.files.length} fichier{code.files.length > 1 ? 's' : ''}
          </span>
        </div>
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          <div style={{ flex: 1, minWidth: 0, borderRight: '1px solid var(--line, rgba(255,255,255,0.12))', display: 'flex', flexDirection: 'column' }}>
            {webPreview ? (
              <iframe srcDoc={webPreview.html} title="aurora-confirm-preview"
                sandbox="allow-scripts allow-forms allow-modals"
                style={{ flex: 1, width: '100%', border: 'none', background: '#fff' }} />
            ) : (
              <div style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
                padding: 28, color: 'var(--fg-dim, #aaa)', fontSize: 12.5, lineHeight: 1.6,
                fontFamily: 'var(--font-sans, system-ui)',
              }}>
                Aperçu live indisponible pour ce type de projet (build requis :<br />
                <code style={{ color: 'oklch(0.84 0.15 60)' }}>npm install && npm run dev</code>).<br />
                Le code est complet — vérifie les fichiers à droite avant d'accepter.
              </div>
            )}
          </div>
          <div style={{ width: 246, overflowY: 'auto', padding: '10px 12px', flexShrink: 0 }}>
            <div style={{
              fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--fg-mute, #777)',
              marginBottom: 8, fontFamily: 'var(--font-mono, monospace)',
            }}>{confirmAction === 'repo' ? 'Fichiers à écrire' : 'Contenu du .zip'}</div>
            {code.files.map((f, i) => (
              <div key={`${f.name}-${i}`} style={{
                fontSize: 11, fontFamily: 'var(--font-mono, monospace)', color: 'var(--fg-dim, #bbb)',
                display: 'flex', justifyContent: 'space-between', gap: 6, padding: '2px 0',
              }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
                <span style={{ color: 'var(--fg-mute, #666)', flexShrink: 0 }}>{f.content.length}c</span>
              </div>
            ))}
            {confirmAction === 'repo' && (
              <div style={{ marginTop: 12, fontSize: 10, color: 'oklch(0.84 0.15 60)', lineHeight: 1.45 }}>
                ⚠ Les fichiers existants sont sauvegardés dans <code>.aurora_backup</code> avant écrasement.
              </div>
            )}
          </div>
        </div>
        <div style={{
          padding: '12px 18px', borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
          display: 'flex', justifyContent: 'flex-end', gap: 10,
        }}>
          <button type="button" onClick={() => setConfirmAction(null)}
            style={{
              padding: '8px 16px', fontSize: 12, background: 'transparent', color: 'var(--fg-dim, #aaa)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))', borderRadius: 6, cursor: 'pointer',
              fontFamily: 'var(--font-sans, system-ui)',
            }}>Annuler</button>
          <button type="button"
            onClick={() => {
              const a = confirmAction
              setConfirmAction(null)
              if (a === 'download') void handleDownloadZip()
              else void code.writeRepo()
            }}
            style={{
              padding: '8px 18px', fontSize: 13, fontWeight: 700, background: GREEN, color: '#0a0a0a',
              border: 'none', borderRadius: 6, cursor: 'pointer', fontFamily: 'var(--font-sans, system-ui)',
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}>
            {confirmAction === 'download'
              ? <><Download size={13} /> Accepter & télécharger</>
              : <><Save size={13} /> Accepter & écrire</>}
          </button>
        </div>
      </div>
    </div>
  )
}

export function AuroraV1CodePipelineBanner({
  code,
  completedWhileAwayAt,
  elapsedSec,
}: {
  code: UseCodeViewLogic
  completedWhileAwayAt: number | null
  elapsedSec: number | null
}) {
  if (!code.streaming && !completedWhileAwayAt) return null

  const accent = !code.streaming
    ? '0.78 0.16 80'
    : code.phase === 'research' || code.phase === 'brand'
      ? '0.74 0.13 60'
      : code.phase === 'planning'
        ? '0.65 0.20 296'
        : code.phase === 'validation'
          ? '0.70 0.13 200'
          : '0.72 0.12 145'
  const phaseWord = code.phase === 'research' ? 'recherche'
    : code.phase === 'brand' ? 'marque'
    : code.phase === 'planning' ? 'architecture'
    : code.phase === 'validation' ? 'validation'
    : 'génération'
  const eta = code.etaSecondsRemaining

  return (
    <div style={{
      position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)',
      zIndex: 50, borderRadius: 12, maxWidth: '94%', minWidth: 340,
      background: `oklch(${accent} / 0.16)`,
      border: `1px solid oklch(${accent} / 0.5)`,
      color: `oklch(${accent.split(' ')[0]} 0.16 ${accent.split(' ')[2]})`,
      fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
      letterSpacing: '0.04em', boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '7px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            display: 'inline-block', width: 7, height: 7, flexShrink: 0,
            borderRadius: '50%', background: 'currentColor',
            animation: code.streaming ? 'aurora-pulse-code 1.2s ease-in-out infinite' : 'none',
          }} />
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11.5 }}>
            {code.streaming
              ? (code.narration || code.phaseMessage || `● ${phaseWord} en cours…`)
              : (code.narration || '✓ Code généré pendant ton absence')}
          </span>
          <button type="button"
            onClick={(e) => { e.stopPropagation(); code.setNarrateVoice(!code.narrateVoice) }}
            title={code.narrateVoice
              ? 'Narration vocale ACTIVÉE — clique pour couper'
              : 'Énoncer à voix haute (désactivé par défaut)'}
            style={{
              flexShrink: 0, background: 'transparent', border: '1px solid currentColor',
              borderRadius: 99, padding: '1px 7px', color: 'currentColor', cursor: 'pointer',
              fontSize: 10, opacity: code.narrateVoice ? 1 : 0.5, lineHeight: 1.4,
            }}>
            {code.narrateVoice ? '🔊' : '🔇'}
          </button>
        </div>
        {code.streaming && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 5, fontSize: 10.5, opacity: 0.92 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
              <Clock size={10} /> {elapsedSec !== null ? formatEta(elapsedSec) : '0 s'} écoulées
            </span>
            {eta !== null && eta > 0 && <span>· ~{formatEta(eta)} restantes</span>}
            <span style={{ marginLeft: 'auto', fontWeight: 700 }}>{code.progressPct}%</span>
          </div>
        )}
      </div>
      {code.streaming && (
        <div style={{ height: 3, background: 'rgba(255,255,255,0.08)' }}>
          <div style={{
            height: '100%', width: `${Math.max(2, code.progressPct)}%`,
            background: 'currentColor', transition: 'width 600ms ease',
          }} />
        </div>
      )}
    </div>
  )
}

export function AuroraV1CodeDropHint({ visible }: { visible: boolean }) {
  if (!visible) return null

  return (
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
      {'</> Déposer code ou doc ·'} ts / py / md / pdf / docx
    </div>
  )
}
