import { useEffect, useState, type RefObject } from 'react'
import {
  AlertTriangle, Code2, FileCode2, Gauge, Layers, Maximize, Monitor, ScrollText, Server, Terminal, X,
} from 'lucide-react'
import type { CodeFile } from '../services/codeOrchestrator'
import type { CodeIntent } from '../services/codeIntent'
import type { CodeSandboxResult } from '../services/codeSandbox'
import type { DevServerState } from '../services/codeDevServer'
import CodeMirrorViewer from '../components/CodeMirrorViewer'
import CodeFileTree from '../components/CodeFileTree'
import { BigLivePreviewFrame, type BigViewport } from './codeViewPreviewPanel'

// ---------------------------------------------------------------------------
// Aurora Code Studio — VIEWER DEDIE COMPLET (distinct du simulateur compact).
// Espace plein ecran stylise pour lui-meme: arborescence projet, editeur,
// preview multi-appareils, logs, erreurs, et etat runtime (dev-server, intent,
// sandbox). C'est l'environnement de travail complet demande — pas un simple
// agrandissement du preview compact.
// ---------------------------------------------------------------------------

type StudioTab = 'logs' | 'erreurs' | 'runtime'
type StudioMain = 'preview' | 'code' | 'split'

export type CodeStudioData = {
  files: CodeFile[]
  activeFile: number
  setActiveFile: (i: number) => void
  consoleOutput: string
  devServerState: DevServerState
  error: string | null
  validationResult: CodeSandboxResult | null
  intent: CodeIntent | null
  notes: string
  streamPreview: string
  isGenerating: boolean
  viewport: BigViewport
  setViewport: (v: BigViewport) => void
  iframeRef: RefObject<HTMLIFrameElement | null>
}

// Bouton + overlay regroupes: le panneau de livraison n a qu une ligne a poser.
export function CodeStudioLauncher(props: CodeStudioData) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        // Actif aussi PENDANT la generation (pas seulement une fois des fichiers
        // livres): le Studio sait afficher le flux en direct (streamPreview +
        // "generation…"). Sans ca le bouton restait grise a 40% d'opacite tout le
        // long de la generation -> invisible a l'oeil, impossible d'ouvrir le viewer live.
        disabled={props.files.length === 0 && !props.isGenerating}
        title="Ouvrir le Studio — environnement complet plein ecran (arbo, editeur, preview multi-appareils, logs, erreurs, runtime)"
        className="inline-flex items-center gap-1.5 rounded-xl border border-aurora-accent/40 bg-gradient-to-r from-aurora-accent/20 to-cyan-400/10 px-3 py-2 text-xs font-semibold text-aurora-text transition-colors hover:border-aurora-accent/70 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <Maximize size={14} />
        <span>Studio</span>
      </button>
      {open && <CodeStudioViewer {...props} onClose={() => setOpen(false)} />}
    </>
  )
}

export function CodeStudioViewer({
  files, activeFile, setActiveFile, consoleOutput, devServerState, error,
  validationResult, intent, notes, streamPreview, isGenerating, viewport,
  setViewport, iframeRef, onClose,
}: CodeStudioData & { onClose: () => void }) {
  const [main, setMain] = useState<StudioMain>('preview')
  const [tab, setTab] = useState<StudioTab>('runtime')
  const active = files[activeFile] || null

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const failingSteps = (validationResult?.steps || []).filter((s) => !s.ok)
  const c = 'rgba(255,255,255,0.06)'

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', flexDirection: 'column', background: '#0a0d12', color: '#e6edf3', fontFamily: 'system-ui, sans-serif' }}>
      {/* Barre studio */}
      <header style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '10px 16px', borderBottom: `1px solid ${c}`, background: 'linear-gradient(180deg,#11151c,#0a0d12)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <span style={{ display: 'grid', placeItems: 'center', width: 26, height: 26, borderRadius: 8, background: 'linear-gradient(135deg,#3b82f6,#22d3ee)' }}><Code2 size={15} color="#031018" /></span>
          <div style={{ lineHeight: 1.1 }}>
            <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '.02em' }}>Aurora Code Studio</div>
            <div style={{ fontSize: 10.5, color: '#8b98a9' }}>
              {intent ? intent.projectType : 'projet'} · {files.length} fichier{files.length > 1 ? 's' : ''}
              {isGenerating ? ' · génération…' : ''}
            </div>
          </div>
        </div>
        <div style={{ flex: 1 }} />
        {/* Vue principale */}
        <div style={{ display: 'flex', gap: 2, padding: 3, background: c, borderRadius: 10 }}>
          {([['preview', 'Aperçu', Monitor], ['code', 'Code', FileCode2], ['split', 'Split', Layers]] as const).map(([m, label, Icon]) => (
            <button key={m} onClick={() => setMain(m)} style={tabBtn(main === m)}><Icon size={13} /><span>{label}</span></button>
          ))}
        </div>
        <button onClick={onClose} title="Fermer le studio (Échap)" style={{ ...tabBtn(false), background: 'rgba(239,68,68,0.14)', color: '#fca5a5' }}><X size={14} /><span>Fermer</span></button>
      </header>

      {/* Corps: arbre | principal | inspecteur */}
      <div style={{ flex: 1, minHeight: 0, display: 'grid', gridTemplateColumns: '15rem minmax(0,1fr) 20rem' }}>
        {/* Arborescence projet */}
        <aside style={{ borderRight: `1px solid ${c}`, overflow: 'auto', background: '#0c1017' }}>
          <div style={sectionLabel}><FileCode2 size={12} /> Arborescence ({files.length})</div>
          {files.length === 0 ? (
            <div style={{ padding: 14, fontSize: 11.5, color: '#6b7688' }}>Lance une génération : les fichiers du projet apparaîtront ici.</div>
          ) : (
            // Meme composant que le panneau de livraison et le viewer plein ecran:
            // une seule arborescence dans tout le module, avec vrais dossiers.
            <div style={{ padding: '0 6px 10px' }}>
              <CodeFileTree files={files} activeFile={activeFile} onSelectFile={setActiveFile} showSize />
            </div>
          )}
        </aside>

        {/* Zone principale */}
        <main style={{ minWidth: 0, display: 'grid', gridTemplateColumns: main === 'split' ? '1fr 1fr' : '1fr', background: '#0a0d12' }}>
          {(main === 'preview' || main === 'split') && (
            <div style={{ minWidth: 0, borderRight: main === 'split' ? `1px solid ${c}` : undefined, display: 'flex', flexDirection: 'column' }}>
              <BigLivePreviewFrame files={files} streamContent={streamPreview} isGenerating={isGenerating} iframeRef={iframeRef} viewport={viewport} onViewportChange={setViewport} />
            </div>
          )}
          {(main === 'code' || main === 'split') && (
            <div style={{ minWidth: 0, overflow: 'auto', background: '#0d1117' }}>
              {active ? (
                <CodeMirrorViewer code={active.content} language={active.language} showLineNumbers />
              ) : (
                <div style={{ padding: 24, color: '#6b7688', fontSize: 12 }}>Aucun fichier sélectionné.</div>
              )}
            </div>
          )}
        </main>

        {/* Inspecteur: logs / erreurs / runtime */}
        <aside style={{ borderLeft: `1px solid ${c}`, display: 'flex', flexDirection: 'column', minHeight: 0, background: '#0c1017' }}>
          <div style={{ display: 'flex', gap: 2, padding: 6, borderBottom: `1px solid ${c}` }}>
            {([['runtime', 'États', Gauge], ['logs', 'Logs', Terminal], ['erreurs', `Erreurs${(failingSteps.length || error) ? ' •' : ''}`, AlertTriangle]] as const).map(([t, label, Icon]) => (
              <button key={t} onClick={() => setTab(t)} style={{ ...tabBtn(tab === t), flex: 1, justifyContent: 'center' }}><Icon size={12} /><span>{label}</span></button>
            ))}
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: 12, fontSize: 11.5, lineHeight: 1.55 }}>
            {tab === 'runtime' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <Row icon={<Server size={12} />} label="Dev-server" value={devServerState.running ? `en ligne · ${devServerState.url || `:${devServerState.port}`}` : (devServerState.error || 'arrêté')} good={devServerState.running} />
                <Row icon={<Layers size={12} />} label="Type de projet" value={intent ? `${intent.projectType} · ${intent.complexity}` : '—'} />
                <Row icon={<Code2 size={12} />} label="Langages" value={intent?.languages?.join(', ') || '—'} />
                <Row icon={<Gauge size={12} />} label="Sandbox" value={validationResult ? (validationResult.ok ? 'validée' : `${failingSteps.length} étape(s) en échec`) : 'non exécutée'} good={validationResult?.ok} />
                {notes && <div><div style={{ ...sectionLabel, padding: '0 0 4px' }}><ScrollText size={12} /> Notes</div><div style={{ color: '#aeb9c9', whiteSpace: 'pre-wrap' }}>{notes.slice(0, 1200)}</div></div>}
              </div>
            )}
            {tab === 'logs' && (
              <pre style={preStyle}>{consoleOutput?.trim() || 'Aucun log console pour l’instant.'}</pre>
            )}
            {tab === 'erreurs' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {error && <div style={{ padding: 10, borderRadius: 8, background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.35)', color: '#fca5a5', whiteSpace: 'pre-wrap' }}>{error}</div>}
                {failingSteps.map((s, i) => (
                  <div key={i} style={{ padding: 10, borderRadius: 8, background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.28)' }}>
                    <div style={{ color: '#fbbf24', fontWeight: 600, marginBottom: 4 }}>{s.command}</div>
                    <pre style={{ ...preStyle, margin: 0, color: '#d6c08a' }}>{(s.output || '').slice(-800)}</pre>
                  </div>
                ))}
                {!error && failingSteps.length === 0 && <div style={{ color: '#6b7688' }}>Aucune erreur détectée.</div>}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}

function Row({ icon, label, value, good }: { icon: React.ReactNode; label: string; value: string; good?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
      <span style={{ color: '#6b7688', marginTop: 1 }}>{icon}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 9.5, textTransform: 'uppercase', letterSpacing: '.1em', color: '#6b7688' }}>{label}</div>
        <div style={{ color: good === true ? '#86efac' : good === false ? '#fca5a5' : '#c9d3e0', wordBreak: 'break-word' }}>{value}</div>
      </div>
    </div>
  )
}

const tabBtn = (active: boolean): React.CSSProperties => ({
  display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 8, border: 'none', cursor: 'pointer',
  fontSize: 11.5, fontWeight: 600, background: active ? 'rgba(59,130,246,0.22)' : 'transparent', color: active ? '#dbeafe' : '#8b98a9',
})
const sectionLabel: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 6, padding: '10px 14px', fontSize: 10, textTransform: 'uppercase', letterSpacing: '.12em', color: '#6b7688' }
const preStyle: React.CSSProperties = { margin: 0, fontFamily: 'ui-monospace, monospace', fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: '#aeb9c9' }
