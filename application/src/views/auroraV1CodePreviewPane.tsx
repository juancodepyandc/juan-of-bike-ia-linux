import type { UseCodeViewLogic } from '../hooks/useCodeViewLogic'
import type { ParsedFile } from '../services/codeOutputFiles'
import { FileCode2 } from 'lucide-react'
import { GREEN } from './auroraV1CodeHelpers'
import { CodePreviewFrame } from './auroraV1CodePreviewFrame'
import { Eyebrow } from './auroraV1CodePrimitives'

type WebPreview = { html: string; entry: ParsedFile; kind: 'html' | 'react' | 'css' }

export function AuroraV1CodePreviewPane({
  activeFile,
  code,
  parsedFiles,
  webPreview,
}: {
  activeFile: ParsedFile | null
  code: UseCodeViewLogic
  parsedFiles: ParsedFile[]
  webPreview: WebPreview | null
}) {
  return (
    <div style={{
      borderRight: '1px solid var(--line, rgba(255,255,255,0.12))',
      display: 'flex', flexDirection: 'column',
      minWidth: 0, minHeight: 0, height: '100%',
    }}>
      <div style={{
        padding: '14px 22px',
        borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <Eyebrow>
          {code.streaming
            ? `construction · ${parsedFiles.length} fichier${parsedFiles.length > 1 ? 's' : ''} parsé${parsedFiles.length > 1 ? 's' : ''}`
            : webPreview
              ? `preview · ${webPreview.kind} · ${webPreview.entry.path}`
              : activeFile
                ? `${activeFile.path} · ${activeFile.language}`
                : 'preview'}
        </Eyebrow>
        {code.streaming && (
          <span style={{
            display: 'inline-block', width: 6, height: 6,
            borderRadius: '50%', background: GREEN,
            animation: 'aurora-pulse-code 1.2s ease-in-out infinite',
          }} />
        )}
        {webPreview && !code.streaming && (
          <span style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 9,
            padding: '2px 6px', borderRadius: 3,
            background: 'oklch(0.72 0.12 145 / 0.15)',
            color: 'oklch(0.78 0.16 145)',
            letterSpacing: '0.06em', textTransform: 'uppercase',
          }}>● live · {webPreview.kind}</span>
        )}
      </div>
      {code.streaming ? (
        <div style={{
          flex: 1, padding: '24px 22px', overflow: 'auto',
          display: 'flex', flexDirection: 'column', gap: 16,
          color: 'var(--fg-dim, #aaa)',
          fontFamily: 'var(--font-mono, monospace)', fontSize: 12,
        }}>
          <div style={{
            padding: '10px 14px', borderRadius: 8,
            background: 'oklch(0.72 0.12 145 / 0.06)',
            border: '1px solid oklch(0.72 0.12 145 / 0.25)',
            color: 'oklch(0.78 0.16 145)', fontSize: 11,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{
              display: 'inline-block', width: 8, height: 8,
              borderRadius: '50%', background: GREEN,
              animation: 'aurora-pulse-code 1.2s ease-in-out infinite',
            }} />
            <span>L'orchestrateur écrit ton code · {code.streamOutput.length}c streamés</span>
          </div>
          {parsedFiles.length === 0 ? (
            <div style={{ color: 'var(--fg-mute, #777)', fontStyle: 'italic' }}>
              En attente du premier bloc de code…
            </div>
          ) : (
            <div>
              <div style={{
                fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase',
                color: 'var(--fg-mute, #777)', marginBottom: 10,
              }}>Fichiers détectés (cliquables une fois fini)</div>
              {parsedFiles.map((f, i) => (
                <div key={`${f.path}-${i}`} style={{
                  padding: '4px 10px', marginBottom: 2,
                  borderLeft: `2px solid ${i === parsedFiles.length - 1 ? GREEN : 'var(--line-soft, rgba(255,255,255,0.12))'}`,
                  color: i === parsedFiles.length - 1 ? 'var(--fg, #f5f5f5)' : 'var(--fg-dim, #aaa)',
                  display: 'flex', justifyContent: 'space-between', gap: 8,
                }}>
                  <span>{f.path}</span>
                  <span style={{ color: 'var(--fg-mute, #555)', fontSize: 10 }}>{f.content.length}c · {f.language}</span>
                </div>
              ))}
            </div>
          )}
          <div style={{ flex: 1 }} />
          <div style={{ fontSize: 10, color: 'var(--fg-mute, #555)', fontStyle: 'italic' }}>
            Le preview live (iframe) apparaîtra ici dès que la génération sera terminée si le code est exécutable côté navigateur (HTML, React, CSS). Pour Python/Rust/Go etc., utilise « Orchestrateur full-power » qui lance un vrai dev-server.
          </div>
        </div>
      ) : webPreview ? (
        <CodePreviewFrame html={webPreview.html} title="aurora-code-preview" />
      ) : activeFile ? (
        <pre style={{
          flex: 1, padding: '18px 22px', margin: 0,
          fontFamily: 'var(--font-mono, monospace)', fontSize: 12, lineHeight: 1.7,
          color: 'var(--fg, #f5f5f5)',
          whiteSpace: 'pre',
          overflow: 'auto',
        }}>
          {activeFile.content}
        </pre>
      ) : (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          color: 'var(--fg-mute, #777)', fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
        }}>
          <FileCode2 size={16} /> Aucun fichier sélectionné
        </div>
      )}
    </div>
  )
}
