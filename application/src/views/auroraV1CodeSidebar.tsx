import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import { Download, FileCode2, FolderGit2, FolderOpen, Globe, Save } from 'lucide-react'
import SessionSwitcher from '../components/SessionSwitcher.tsx'
import type { UseCodeViewLogic } from '../hooks/useCodeViewLogic.ts'
import type { ParsedFile } from '../services/codeOutputFiles.ts'
import { GREEN } from './auroraV1CodeHelpers.ts'
import { Eyebrow } from './auroraV1CodePrimitives.tsx'

type ConfirmAction = 'download' | 'repo'

export function AuroraV1CodeSidebar({
  activeFileIdx,
  code,
  downloadingZip,
  parsedFiles,
  repoPathInput,
  setActiveFileIdx,
  setConfirmAction,
  setLive,
  setRepoPathInput,
  userPickedRef,
}: {
  activeFileIdx: number
  code: UseCodeViewLogic
  downloadingZip: boolean
  parsedFiles: ParsedFile[]
  repoPathInput: string
  setActiveFileIdx: Dispatch<SetStateAction<number>>
  setConfirmAction: (action: ConfirmAction | null) => void
  setLive: (live: boolean) => void
  setRepoPathInput: Dispatch<SetStateAction<string>>
  userPickedRef: MutableRefObject<boolean>
}) {
  return (
    <div style={{
      padding: '24px 18px',
      borderRight: '1px solid var(--line, rgba(255,255,255,0.12))',
      display: 'flex', flexDirection: 'column', gap: 12,
      overflowY: 'auto', minHeight: 0, height: '100%',
    }}>
      <div style={{
        paddingBottom: 12,
        borderBottom: '1px solid var(--line, rgba(255,255,255,0.10))',
      }}>
        <SessionSwitcher
          module="code"
          onSessionChange={(session) => code.activateSession(session.id)}
        />
      </div>
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 8, paddingBottom: 12,
        borderBottom: '1px solid var(--line, rgba(255,255,255,0.10))',
      }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {(['online', 'repo'] as const).map((m) => {
            const active = code.workMode === m
            return (
              <button key={m} type="button" onClick={() => code.setWorkMode(m)}
                style={{
                  flex: 1, padding: '7px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  fontFamily: 'var(--font-mono, monospace)', cursor: 'pointer',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                  background: active ? GREEN : 'transparent',
                  color: active ? '#0a0a0a' : 'var(--fg-dim, #aaa)',
                  border: `1px solid ${active ? GREEN : 'var(--line, rgba(255,255,255,0.14))'}`,
                }}>
                {m === 'online' ? <Globe size={12} /> : <FolderGit2 size={12} />}
                {m === 'online' ? 'En ligne' : 'Mon repo'}
              </button>
            )
          })}
        </div>
        {code.workMode === 'repo' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ display: 'flex', gap: 6 }}>
              <input value={repoPathInput} onChange={(e) => setRepoPathInput(e.target.value)}
                placeholder="/home/utilisateur/projet" spellCheck={false}
                style={{
                  flex: 1, padding: '6px 8px', fontSize: 11, borderRadius: 6,
                  background: 'var(--bg-card, rgba(255,255,255,0.04))', color: 'var(--fg, #f5f5f5)',
                  border: '1px solid var(--line, rgba(255,255,255,0.14))',
                  fontFamily: 'var(--font-mono, monospace)', minWidth: 0,
                }} />
              <button type="button" onClick={() => { void code.pickRepo() }} disabled={code.repoBusy}
                title="Parcourir (sélecteur de dossier natif)"
                style={{
                  padding: '6px 8px', borderRadius: 6, cursor: code.repoBusy ? 'wait' : 'pointer',
                  background: 'transparent', color: 'var(--fg, #f5f5f5)',
                  border: '1px solid var(--line, rgba(255,255,255,0.14))',
                  display: 'inline-flex', alignItems: 'center',
                }}>
                <FolderOpen size={13} />
              </button>
            </div>
            <button type="button" onClick={() => { void code.scanRepo(repoPathInput) }}
              disabled={code.repoBusy || !repoPathInput.trim()}
              style={{
                padding: '7px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                cursor: code.repoBusy ? 'wait' : 'pointer',
                background: 'oklch(0.65 0.20 296 / 0.14)', color: 'oklch(0.80 0.16 296)',
                border: '1px solid oklch(0.65 0.20 296 / 0.5)', fontFamily: 'var(--font-mono, monospace)',
                opacity: (!repoPathInput.trim() || code.repoBusy) ? 0.55 : 1,
              }}>
              {code.repoLoaded ? '↻ Recharger le repo' : '↧ Charger le repo comme contexte'}
            </button>
            {code.repoMessage && (
              <div style={{ fontSize: 10, color: 'var(--fg-dim, #aaa)', fontFamily: 'var(--font-mono, monospace)', lineHeight: 1.4 }}>
                {code.repoBusy ? '⏳ ' : ''}{code.repoMessage}
              </div>
            )}
            {code.repoLoaded && code.files.length > 0 && !code.streaming && (
              <button type="button" onClick={() => setConfirmAction('repo')} disabled={code.repoBusy}
                style={{
                  padding: '7px 10px', borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: 'pointer',
                  background: GREEN, color: '#0a0a0a', border: 'none',
                  fontFamily: 'var(--font-mono, monospace)', display: 'inline-flex',
                  alignItems: 'center', justifyContent: 'center', gap: 5,
                }}>
                <Save size={12} /> Vérifier puis écrire dans le repo
              </button>
            )}
            {code.repoWriteResult && (
              <div style={{ fontSize: 10, color: 'oklch(0.80 0.16 145)', fontFamily: 'var(--font-mono, monospace)' }}>
                ✓ {code.repoWriteResult.written.length} fichier(s) écrits · backup dans .aurora_backup
              </div>
            )}
            {code.repoLoaded && !code.streaming && (
              <button type="button" onClick={() => { void code.installRepoDeps() }} disabled={code.repoBusy}
                title="Détecte le manifeste (package.json, requirements.txt, Cargo.toml…) et lance l'installation dans une console"
                style={{
                  padding: '6px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                  cursor: code.repoBusy ? 'wait' : 'pointer',
                  background: 'oklch(0.74 0.13 60 / 0.12)', color: 'oklch(0.84 0.15 60)',
                  border: '1px solid oklch(0.74 0.13 60 / 0.5)', fontFamily: 'var(--font-mono, monospace)',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                }}>
                ⚙ Installer les dépendances
              </button>
            )}
          </div>
        )}
        {code.workMode === 'online' && code.files.length > 0 && !code.streaming && (
          <button type="button" onClick={() => setConfirmAction('download')} disabled={downloadingZip}
            style={{
              padding: '7px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
              cursor: downloadingZip ? 'wait' : 'pointer',
              background: 'oklch(0.72 0.12 145 / 0.12)', color: 'oklch(0.86 0.16 145)',
              border: '1px solid oklch(0.72 0.12 145 / 0.5)', fontFamily: 'var(--font-mono, monospace)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
            <Download size={12} /> {downloadingZip ? 'Préparation…' : `Télécharger .zip (${code.files.length})`}
          </button>
        )}
      </div>
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 6, paddingBottom: 12,
        borderBottom: '1px solid var(--line, rgba(255,255,255,0.10))',
      }}>
        <button type="button" onClick={() => code.setNarrateVoice(!code.narrateVoice)}
          title={code.narrateVoice
            ? 'Aurora énonce ce qu\'il fait à voix haute (clique pour couper)'
            : 'Aurora écrit ce qu\'il fait ; clique pour l\'entendre à voix haute'}
          style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'space-between', gap: 6,
            padding: '7px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            fontFamily: 'var(--font-mono, monospace)',
            background: code.narrateVoice ? 'oklch(0.72 0.12 145 / 0.14)' : 'transparent',
            color: code.narrateVoice ? 'oklch(0.86 0.16 145)' : 'var(--fg-dim, #aaa)',
            border: `1px solid ${code.narrateVoice ? 'oklch(0.72 0.12 145 / 0.5)' : 'var(--line, rgba(255,255,255,0.14))'}`,
          }}>
          <span>{code.narrateVoice ? '🔊 Énoncer à voix haute' : '🔇 Narration écrite'}</span>
          <span style={{ fontSize: 9, opacity: 0.8 }}>{code.narrateVoice ? 'ON' : 'OFF'}</span>
        </button>
        {code.narrationLog.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 104, overflowY: 'auto' }}>
            {code.narrationLog.slice(-5).map((line, i, arr) => (
              <div key={`${i}-${line.slice(0, 14)}`} style={{
                fontSize: 10, lineHeight: 1.35, fontFamily: 'var(--font-sans, system-ui)',
                color: i === arr.length - 1 ? 'var(--fg, #f5f5f5)' : 'var(--fg-mute, #888)',
                display: 'flex', gap: 5,
              }}>
                <span style={{ color: 'oklch(0.72 0.12 145)', flexShrink: 0 }}>{i === arr.length - 1 ? '▸' : '·'}</span>
                <span>{line}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <Eyebrow dot={GREEN}>
        {parsedFiles.length > 0 ? `Code · ${parsedFiles.length} fichier${parsedFiles.length > 1 ? 's' : ''}` : 'Code · Multi-modèle'}
      </Eyebrow>
      <div style={{ marginTop: 6 }}>
        {parsedFiles.length > 0 ? (
          parsedFiles.map((f, i) => {
            const isActive = i === activeFileIdx
            return (
              <button key={`${f.path}-${i}`} type="button"
                onClick={() => { userPickedRef.current = true; setActiveFileIdx(i) }}
                style={{
                  width: '100%', textAlign: 'left',
                  padding: '6px 10px', borderRadius: 6,
                  fontSize: 12, fontFamily: 'var(--font-mono, monospace)',
                  color: isActive ? 'var(--fg, #f5f5f5)' : 'var(--fg-dim, #aaa)',
                  background: isActive ? 'var(--ink-800, #1a1a1a)' : 'transparent',
                  display: 'flex', gap: 8, alignItems: 'center',
                  border: 'none', cursor: 'pointer',
                }}
                title={`${f.path} · ${f.content.length} c. · ${f.language}`}>
                <span style={{ color: 'var(--fg-mute, #777)' }}>{isActive ? '◆' : '·'}</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{f.path}</span>
                <span style={{ color: 'var(--fg-mute, #555)', fontSize: 10 }}>{f.content.length}c</span>
              </button>
            )
          })
        ) : (
          <div style={{
            minHeight: 72, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
            color: 'var(--fg-mute, #777)', fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          }}>
            <FileCode2 size={14} /> Aucun fichier
          </div>
        )}
      </div>

      <div style={{ flex: 1 }} />

      <div style={{
        padding: 12,
        background: 'var(--bg-card, rgba(255,255,255,0.03))',
        border: '1px solid var(--line, rgba(255,255,255,0.12))',
        borderRadius: 8,
      }}>
        <Eyebrow style={{ marginBottom: 8 }}>Modèle code</Eyebrow>
        <div style={{
          display: 'flex', justifyContent: 'space-between', gap: 8,
          fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
          padding: '4px 0',
        }}>
          <span title={code.modelUsed ?? code.model} style={{
            color: 'var(--fg-dim, #aaa)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>{code.modelUsed ?? code.model}</span>
          <span style={{ color: GREEN, flexShrink: 0 }}>{code.modelUsed ? 'utilisé' : 'sélectionné'}</span>
        </div>
      </div>

      <button type="button" onClick={() => setLive(true)}
        style={{
          padding: '10px 16px', background: GREEN, color: '#0a0a0a',
          border: 'none', fontSize: 13, fontWeight: 600,
          cursor: 'pointer', fontFamily: 'var(--font-sans, system-ui)',
        }}>
        ◆ Ouvrir l'orchestrateur
      </button>
    </div>
  )
}
