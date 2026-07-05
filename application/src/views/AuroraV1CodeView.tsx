/**
 * AuroraV1CodeView — Editorial diff entry for the Code module.
 *
 * Visual chrome from _design/aurora_design_screens_v1/modules.jsx
 * (CodeScreen): three columns — file tree on the left with active model
 * panel below, "before" code pane in the centre, "after · streaming"
 * pane on the right with diff hunks (red insertion / green
 * application), bottom Accepter ⌘↵ / Réviser / Annuler bar.
 *
 * Real wiring: CodeView (2398 LOC of intent classification, architecture
 * planning, sandbox execution loop, dev-server preview, 22-language
 * support, design tokens, R3F + GLSL playground, Aurora-Connect
 * extension lookup) lazy-mounts as soon as the user clicks "Ouvrir
 * l'orchestrateur" — full feature parity guaranteed.
 */
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Send, StopCircle, Sparkles, Copy, X, Download, FolderGit2, Globe, Plus, Clock, FolderOpen, Save } from 'lucide-react'
import { useCodeViewLogic } from '../hooks/useCodeViewLogic'
import { useModuleStreak } from '../hooks/useModuleStreak'
import { useFileDrop } from '../hooks/useFileDrop'
import { getDailyTip } from '../utils/dailyTip'
import FavoriteButton from '../components/FavoriteButton'
import { extractGeneratedFiles, extractWebPreview, type ParsedFile } from '../services/codeOutputFiles'
import { intelligentlyElevateFiles } from '../services/codeOutputIntelligent'
import { useCodeStreamStore } from '../stores/codeStreamStore'
import { downloadProjectZip, formatEta } from '../utils/codeDownload'
import MachineConnectionsPanel from '../components/MachineConnectionsPanel'
import SessionSwitcher from '../components/SessionSwitcher'
import { useModuleHistoryStore } from '../stores/moduleHistoryStore'

const FOLLOWUP_LABELS: Record<string, string> = {
  increment: 'Modification du projet en cours',
  pivot_platform: 'Changement de stack (même concept)',
  pivot_feature: 'Évolution majeure du projet',
  fresh_start: 'Nouveau projet',
  clarify_only: 'Clarification',
}

// v82k7 : delegate `<CodeView />` (manga loader) retiré. Le mode live
// rend désormais une salle de code editorial native qui consume la
// même useCodeViewLogic avec un rendu CodeBlock pleine largeur.
// v82bh : CodeBlock lazy-imported aussi pour ne pas tirer le bundle
// Prism (621KB) sur le V1 Code preview tant que l'user n'a pas
// envoyé un prompt. Suspense fallback = plain pre pendant que Prism
// charge.
const CodeBlock = lazy(() => import('../components/CodeBlock'))

// Heuristique simple pour deviner le langage du streamOutput
// avant de le passer à Prism. Le system prompt cadre TS/React par
// défaut, donc 'typescript' est le bon fallback.
function detectStreamLanguage(prompt: string, output: string): string {
  const p = prompt.toLowerCase()
  if (/\bpython\b|\.py\b|django|flask|pytorch/.test(p)) return 'python'
  if (/\brust\b|\.rs\b|cargo/.test(p)) return 'rust'
  if (/\bgo(lang)?\b|\.go\b/.test(p)) return 'go'
  if (/\bjava\b|\.java\b|spring/.test(p)) return 'java'
  if (/\bc\+\+\b|cpp|\.cpp\b/.test(p)) return 'cpp'
  if (/\bjavascript\b|\.js\b/.test(p) && !/typescript|\.ts/.test(p)) return 'javascript'
  if (/\bsql\b|select.*from/.test(p)) return 'sql'
  if (/\bbash\b|shell|\.sh\b/.test(p)) return 'bash'
  if (/\bcss\b|\.css\b|tailwind/.test(p)) return 'css'
  if (/\bhtml\b|\.html\b/.test(p)) return 'markup'
  if (/\byaml\b|\.ya?ml\b/.test(p)) return 'yaml'
  if (/\bjson\b|\.json\b/.test(p)) return 'json'
  // Fallback : si l'output commence par <html> ou contient <script> → markup
  if (/^\s*<(html|!DOCTYPE)/i.test(output)) return 'markup'
  return 'typescript'
}

const GREEN = 'oklch(0.72 0.12 145)'
const RED = 'oklch(0.55 0.18 25)'

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

// v82n6 : DEMO_FILES kept as idle placeholder only. Once user submits and
// streamOutput is non-empty, the file tree is replaced with a REAL parsed
// list from extractGeneratedFiles() in the component body. The user
// reported "j'ai toujours la même arborescence donc des choses aucun
// rapport" — that was because this list never got updated. Now it does.
const DEMO_FILES = ['App.tsx', 'router.ts', 'auth/', 'api/diffusion.ts', 'lib/utils.ts', 'theme.css', 'README.md']
const MODELS: Array<[string, string]> = [
  ['qwen3:14b', 'plan'],
  ['deepseek-coder:33b', 'edit'],
  ['llama3.2:3b', 'fix'],
]

const BEFORE = `export async function diffuse(
  prompt: string,
  steps = 28,
  // TODO: validate guidance range
  guidance: number,
) {
  const res = await fetch('/api/flux', {
    method: 'POST',
    body: JSON.stringify({ prompt, steps }),
  });
  return res.json();
}`

const AFTER_PRE = `export async function diffuse(
  prompt: string,
  steps = 28,
`
const AFTER_HIGHLIGHT = `  guidance: number = 4.5,
) {
  if (guidance < 1 || guidance > 20) {
    throw new RangeError('guidance ∈ [1, 20]');
  }`
const AFTER_POST = `
  const res = await fetch('/api/flux', {
    method: 'POST',
    body: JSON.stringify({ prompt, steps, guidance }),
  });
  return res.json();
}`

export default function AuroraV1CodeView() {
  const [live, setLive] = useState(false)
  const [streamLen, setStreamLen] = useState(0)
  const code = useCodeViewLogic()
  const activeCodeSessionId = useModuleHistoryStore((s) => s.activeSessionId.code ?? null)
  const createCodeSession = useModuleHistoryStore((s) => s.createSession)
  const codeStreak = useModuleStreak('code')
  // v82n8 : detect "completed while away" — store has lastCompletedAt,
  // we remember our own last-seen value when this view mounts. If the
  // store's lastCompletedAt advances past it while we're alive, no
  // banner needed (the user is here). If we mount and the store's
  // lastCompletedAt > our last-seen, AND we have streamOutput, show a
  // small "généré pendant ton absence" banner that auto-dismisses.
  const lastCompletedAt = useCodeStreamStore((s) => s.lastCompletedAt)
  const runId = useCodeStreamStore((s) => s.runId)
  const errorDialog = useCodeStreamStore((s) => s.errorDialog)
  const dismissErrorDialog = useCodeStreamStore((s) => s.dismissErrorDialog)
  const retryAfterError = useCodeStreamStore((s) => s.retryAfterError)
  // v82nd : detect installed code editor at mount so the button label
  // says e.g. "Ouvrir dans VSCode" or "Ouvrir dans Cursor".
  const [editorName, setEditorName] = useState<string>('VSCode')
  const [openingFolder, setOpeningFolder] = useState(false)
  useEffect(() => {
    if (activeCodeSessionId) {
      code.activateSession(activeCodeSessionId)
      return
    }
    const created = createCodeSession('code')
    code.activateSession(created)
  }, [activeCodeSessionId, code.activateSession, createCodeSession])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const bridge = (await import('../utils/runtime')).getBridgeUrl()
        const r = await fetch(`${bridge}/api/code/detect-editor`, {
          signal: AbortSignal.timeout(3000),
        })
        if (!r.ok) return
        const j = await r.json() as { ok?: boolean; editor?: { name?: string } }
        if (!cancelled && j?.ok && j.editor?.name) setEditorName(j.editor.name)
      } catch { /* keep default */ }
    })()
    return () => { cancelled = true }
  }, [])
  const handleOpenInEditor = async () => {
    if (parsedFiles.length === 0 || openingFolder) return
    setOpeningFolder(true)
    try {
      const bridge = (await import('../utils/runtime')).getBridgeUrl()
      const r = await fetch(`${bridge}/api/code/open-folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          files: parsedFiles.map((f) => ({ path: f.path, content: f.content })),
          project_name: `aurora-${Date.now().toString(36)}`,
        }),
        signal: AbortSignal.timeout(8000),
      })
      const j = await r.json() as { ok?: boolean; project_dir?: string; editor?: { name?: string }; error?: string }
      if (!j?.ok) {
        // Surface as a small inline alert (use the existing error
        // dialog plumbing for consistency).
        useCodeStreamStore.setState({
          errorDialog: {
            title: `Impossible d'ouvrir dans ${editorName}`,
            message: j?.error || 'Échec inconnu lors de l\'ouverture du dossier.',
            suggestion: `Vérifie que ${editorName} est dans le PATH (commande "code" / "cursor"). Sinon le dossier est quand même écrit sur le disque.`,
          },
        })
      }
    } catch (e) {
      useCodeStreamStore.setState({
        errorDialog: {
          title: 'Bridge non joignable',
          message: e instanceof Error ? e.message : String(e),
          suggestion: 'Relance Aurora puis réessaie.',
        },
      })
    } finally {
      setOpeningFolder(false)
    }
  }
  // v85 : ZIP export of the whole project (keeps "télécharger comme
  // actuellement" but bundles the full tree, not one file at a time).
  const [downloadingZip, setDownloadingZip] = useState(false)
  // v85f : preview-before-accept — download / repo-write open a confirm modal
  // (rendered preview + file list) instead of acting immediately.
  const [confirmAction, setConfirmAction] = useState<null | 'download' | 'repo'>(null)
  const handleDownloadZip = async () => {
    if (code.files.length === 0 || downloadingZip) return
    setDownloadingZip(true)
    try {
      await downloadProjectZip(code.files, code.repoLabel || code.draft || 'aurora-projet')
    } finally {
      setDownloadingZip(false)
    }
  }
  // v85 : local mirror of the repo path so the user can type/paste it.
  const [repoPathInput, setRepoPathInput] = useState('')
  useEffect(() => { setRepoPathInput(code.repoPath ?? '') }, [code.repoPath])
  // v85e : live elapsed-time ticker for the current task (1s cadence while
  // streaming) — gives a real-time chrono next to the ETA.
  const [nowTick, setNowTick] = useState(() => Date.now())
  useEffect(() => {
    if (!code.streaming) return
    setNowTick(Date.now())
    const id = window.setInterval(() => setNowTick(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [code.streaming])
  const elapsedSec = code.streaming && code.genStartedAt ? Math.max(0, (nowTick - code.genStartedAt) / 1000) : null
  const lastSeenCompletedRef = useRef<number | null>(null)
  const lastSeenRunRef = useRef<number>(0)
  const [completedWhileAwayAt, setCompletedWhileAwayAt] = useState<number | null>(null)
  useEffect(() => {
    // First mount in this session : capture the current values, no banner.
    if (lastSeenCompletedRef.current === null) {
      lastSeenCompletedRef.current = lastCompletedAt
      lastSeenRunRef.current = runId
      return
    }
    // Subsequent re-mounts : if completion advanced AND it's the same
    // run we kicked off (or a new completed run), surface the banner.
    if (
      lastCompletedAt !== null
      && lastCompletedAt !== lastSeenCompletedRef.current
      && !code.streaming
    ) {
      setCompletedWhileAwayAt(lastCompletedAt)
      lastSeenCompletedRef.current = lastCompletedAt
      lastSeenRunRef.current = runId
      const t = window.setTimeout(() => setCompletedWhileAwayAt(null), 6000)
      return () => window.clearTimeout(t)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastCompletedAt, runId])
  // v82n6 : real multi-file parsing. While streaming, every render
  // re-parses streamOutput so the user sees files appear progressively
  // in the left tree as fenced blocks land. Cheap (single string scan,
  // no DOM thrash beyond the tree).
  const parsedFiles = useMemo<ParsedFile[]>(() => {
    // v85 : the orchestrator now returns a STRUCTURED, validated, merged
    // file tree (code.files). Prefer it whenever we're not actively
    // streaming — it's the real project state (and survives navigation).
    // While tokens are still arriving we live-parse the stream so files
    // appear progressively in the tree.
    if (!code.streaming && code.files.length > 0) {
      return code.files.map((f) => ({ path: f.name, content: f.content, language: f.language }))
    }
    if (!code.streamOutput || code.streamOutput.length === 0) {
      return code.files.map((f) => ({ path: f.name, content: f.content, language: f.language }))
    }
    const raw = extractGeneratedFiles(code.streamOutput)
    // v82ni/v82nk : intelligent elevation via DOMParser. Passes the
    // user's prompt as a context fallback for image queries AND the
    // brand primary color (when brand-enrich detected one) so the
    // page is recolored to the brand's palette instead of the LLM's
    // training-default Tailwind violet/green.
    if (!code.streaming) {
      return intelligentlyElevateFiles(raw, code.draft, code.brandPrimary || '').files
    }
    return raw
  }, [code.streamOutput, code.streaming, code.draft, code.brandPrimary, code.files])
  const [activeFileIdx, setActiveFileIdx] = useState(0)
  // Auto-follow: when a new file appears, jump the cursor to it so the
  // user always sees the latest. If user manually clicked one earlier,
  // we keep their choice (clamp to bounds when files shrink/grow).
  const userPickedRef = useRef(false)
  useEffect(() => {
    if (parsedFiles.length === 0) {
      setActiveFileIdx(0)
      userPickedRef.current = false
      return
    }
    if (!userPickedRef.current) {
      setActiveFileIdx(parsedFiles.length - 1)
    } else {
      setActiveFileIdx((idx) => Math.min(idx, parsedFiles.length - 1))
    }
  }, [parsedFiles.length])
  const activeFile: ParsedFile | null = parsedFiles[activeFileIdx] ?? null
  // v82n6 : detect a runnable web preview (index.html or full <html>)
  // so the centre pane can show an iframe instead of the static BEFORE
  // demo. Only runs when stream completes (heavy regex) — during stream,
  // we keep the live code view to avoid reflow on every token.
  const webPreview = useMemo(
    () => (code.hasOutput && !code.streaming ? extractWebPreview(parsedFiles) : null),
    [code.hasOutput, code.streaming, parsedFiles],
  )
  // v82ir : tokens/s rolling window 3s pour speed indicator pendant stream.
  // v82it : tpsHistory cap 30 samples pour sparkline mini.
  // v82iv : finalStats persistant après le stream pour récap UX.
  const [tokensPerSec, setTokensPerSec] = useState<number | null>(null)
  const [tpsHistory, setTpsHistory] = useState<number[]>([])
  const [finalStats, setFinalStats] = useState<{
    avg: number; max: number; tokens: number; durationSec: number
  } | null>(null)
  const speedSamplesRef = useRef<Array<{ ts: number; len: number }>>([])
  const streamStartRef = useRef<number | null>(null)
  useEffect(() => {
    if (!code.streaming) {
      // v82iv : freeze final stats si on a un history non-vide avant reset.
      if (tpsHistory.length > 0 && streamStartRef.current !== null) {
        const avg = tpsHistory.reduce((a, b) => a + b, 0) / tpsHistory.length
        const max = Math.max(...tpsHistory)
        const tokens = Math.ceil(code.streamOutput.length / 4)
        const durationSec = (Date.now() - streamStartRef.current) / 1000
        setFinalStats({ avg, max, tokens, durationSec })
      }
      speedSamplesRef.current = []
      streamStartRef.current = null
      setTokensPerSec(null)
      setTpsHistory([])
      return
    }
    if (streamStartRef.current === null) {
      streamStartRef.current = Date.now()
      setFinalStats(null) // clear ancien recap au début du nouveau stream
    }
    const now = Date.now()
    const len = code.streamOutput.length
    speedSamplesRef.current.push({ ts: now, len })
    const cutoff = now - 3000
    speedSamplesRef.current = speedSamplesRef.current.filter((s) => s.ts >= cutoff)
    if (speedSamplesRef.current.length >= 2) {
      const first = speedSamplesRef.current[0]
      const last = speedSamplesRef.current[speedSamplesRef.current.length - 1]
      const dtSec = (last.ts - first.ts) / 1000
      const dCh = last.len - first.len
      if (dtSec > 0.2) {
        const tps = (dCh / 4) / dtSec
        setTokensPerSec(tps)
        setTpsHistory((h) => [...h, tps].slice(-30))
      }
    }
  }, [code.streamOutput, code.streaming])
  // v82fm : drop zone Code → injecte le contenu lu dans le prompt
  // courant (code.draft) entouré d'un fence. L'utilisateur tape ensuite
  // sa demande et envoie. Supporte text/PDF/DOCX (lazy via readTextFile).
  const drop = useFileDrop({
    onFiles: async (files) => {
      const { readTextFile } = await import('../utils/textFileExtract')
      const sections: string[] = []
      for (const f of files) {
        try {
          const text = await readTextFile(f)
          // Détection langue rapide pour fence
          const lang = (() => {
            const lower = f.name.toLowerCase()
            if (/\.tsx?$/.test(lower)) return 'typescript'
            if (/\.jsx?$/.test(lower)) return 'javascript'
            if (/\.py$/.test(lower)) return 'python'
            if (/\.rs$/.test(lower)) return 'rust'
            if (/\.go$/.test(lower)) return 'go'
            if (/\.java$/.test(lower)) return 'java'
            if (/\.cpp$|\.cc$|\.cxx$/.test(lower)) return 'cpp'
            if (/\.cs$/.test(lower)) return 'csharp'
            if (/\.rb$/.test(lower)) return 'ruby'
            if (/\.php$/.test(lower)) return 'php'
            if (/\.swift$/.test(lower)) return 'swift'
            if (/\.kt$/.test(lower)) return 'kotlin'
            if (/\.css$/.test(lower)) return 'css'
            if (/\.html?$/.test(lower)) return 'html'
            if (/\.sql$/.test(lower)) return 'sql'
            if (/\.json$/.test(lower)) return 'json'
            if (/\.ya?ml$/.test(lower)) return 'yaml'
            if (/\.md$/.test(lower)) return 'markdown'
            return ''
          })()
          // Clamp 30KB par fichier pour ne pas saturer le prompt
          const clamped = text.length > 30000
            ? text.slice(0, 30000) + '\n// ... [tronqué à 30KB] ...'
            : text
          sections.push(`### ${f.name}\n\`\`\`${lang}\n${clamped}\n\`\`\``)
        } catch {
          sections.push(`### ${f.name}\n(lecture impossible)`)
        }
      }
      const inject = sections.join('\n\n')
      code.setDraft(`${inject}\n\n${code.draft}`)
    },
    accept: ['txt', 'md', 'markdown', 'json', 'csv', 'log', 'py', 'js', 'ts', 'tsx', 'jsx', 'rs', 'go', 'java', 'cpp', 'cs', 'rb', 'php', 'swift', 'kt', 'html', 'css', 'sh', 'tex', 'xml', 'yaml', 'yml', 'sql', 'pdf', 'docx'],
    acceptMime: ['text/', 'application/pdf', 'application/json', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    disabled: code.streaming,
  })

  // v82bd : la "demo" animation reste comme idle state quand l'user
  // n'a pas encore tapé de prompt — fait vivre le pane editorial. Dès
  // que streamOutput a du contenu, on bascule sur le vrai streaming
  // en remplaçant AFTER_HIGHLIGHT.slice(0, streamLen) par
  // code.streamOutput dans le rendu plus bas.
  useEffect(() => {
    if (live || code.hasOutput || code.streaming) return
    const total = AFTER_HIGHLIGHT.length
    let i = 0
    const id = window.setInterval(() => {
      i = (i + 4) % (total + 40)
      setStreamLen(Math.min(i, total))
    }, 60)
    return () => window.clearInterval(id)
  }, [live, code.hasOutput, code.streaming])

  // v82k7 : salle de code editorial native — no manga delegate.
  if (live) {
    return (
      <div className="aurora-v1-live-fade" style={{
        height: '100%', display: 'flex', flexDirection: 'column',
        background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
        fontFamily: 'var(--font-sans, system-ui)', overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 24px', display: 'flex', alignItems: 'center', gap: 12,
          borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
          background: 'linear-gradient(180deg, oklch(0.72 0.12 145 / 0.10), transparent)',
        }}>
          <span style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            letterSpacing: '0.18em', textTransform: 'uppercase',
            color: 'oklch(0.78 0.16 145)',
          }}>● Orchestrateur Code · {code.model}</span>
          <span style={{ flex: 1 }} />
          {code.streaming && (
            <button type="button" onClick={code.abort}
              style={{
                padding: '6px 12px', fontSize: 11,
                background: 'oklch(0.55 0.18 25 / 0.15)',
                color: 'oklch(0.78 0.16 25)',
                border: '1px solid oklch(0.78 0.16 25 / 0.45)',
                cursor: 'pointer', borderRadius: 6,
                display: 'inline-flex', alignItems: 'center', gap: 6,
              }}><StopCircle size={12} /> Stop</button>
          )}
          {code.streamOutput && !code.streaming && (
            <button type="button" onClick={() => {
              void navigator.clipboard?.writeText(code.streamOutput).catch(() => {})
            }}
              style={{
                padding: '6px 12px', fontSize: 11,
                background: 'transparent', color: 'var(--fg-dim, #aaa)',
                border: '1px solid var(--line, rgba(255,255,255,0.18))',
                cursor: 'pointer', borderRadius: 6,
                display: 'inline-flex', alignItems: 'center', gap: 6,
              }}><Copy size={12} /> Copier</button>
          )}
          <button type="button" onClick={() => setLive(false)}
            style={{
              padding: '6px 12px', fontSize: 11,
              fontFamily: 'var(--font-mono, monospace)',
              background: 'transparent', color: 'var(--fg-dim, #aaa)',
              border: '1px solid var(--line, rgba(255,255,255,0.18))',
              cursor: 'pointer', borderRadius: 6,
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}><X size={12} /> Fermer</button>
        </div>

        <div style={{ flex: 1, overflow: 'auto', padding: 0, display: 'flex' }}>
          {!code.streamOutput && !code.streaming ? (
            <div style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--fg-mute, #888)',
              fontFamily: 'var(--font-display, serif)', fontStyle: 'italic', fontSize: 18,
            }}>
              Aucun code généré. Reviens à la chrome editorial pour saisir un brief.
            </div>
          ) : (
            <Suspense fallback={
              <pre style={{
                flex: 1, padding: 24, margin: 0, overflow: 'auto',
                fontFamily: 'var(--font-mono, monospace)', fontSize: 12,
                color: 'var(--fg, #f5f5f5)', whiteSpace: 'pre-wrap',
              }}>{code.streamOutput}</pre>
            }>
              <div style={{ flex: 1, padding: 24, overflow: 'auto' }}>
                <CodeBlock code={code.streamOutput} language={'typescript'} />
              </div>
            </Suspense>
          )}
        </div>
      </div>
    )
  }

  return (
    <div {...drop.bind} className="aurora-v1-cols" style={{
      height: '100%', display: 'grid',
      gridTemplateColumns: '260px 1fr 1fr',
      // v82n9 : explicit single-row cap = viewport height. Without this
      // the grid implicit-row was content-sized so right column grew
      // beyond viewport, hiding the prompt input under overflow:hidden.
      gridTemplateRows: '1fr',
      background: 'var(--bg, #0c0a09)', color: 'var(--fg, #f5f5f5)',
      fontFamily: 'var(--font-sans, system-ui)', overflow: 'hidden',
      position: 'relative',
      outline: drop.isDraggingOver ? '2px dashed oklch(0.74 0.13 60)' : 'none',
      outlineOffset: drop.isDraggingOver ? '-6px' : '0',
      transition: 'outline 120ms ease',
    }}>
      {/* v82nc : modal error dialog. Centred over the whole module,
          blocks interaction until user clicks OK (which auto-retries)
          or Annuler (which just dismisses). Shows the failure reason +
          a concrete suggestion (ollama pull X / start-aurora / etc). */}
      {errorDialog && (
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
      )}
      {/* v85f : APERÇU AVANT D'ACCEPTER — rien n'est téléchargé ni écrit dans le
          repo tant que l'utilisateur n'a pas vu le rendu + la liste de fichiers
          et cliqué Accepter. Règle le "ça met à jour automatiquement" + permet
          de voir l'écran noir AVANT de polluer le repo. */}
      {confirmAction && (
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
      )}
      {/* v82n8/v82nb : phase-aware banner. During pre-stream phases
          (research, brand) show the specific message from the store
          so the user knows we're searching the web for design
          inspiration / enriching the brand profile, NOT just frozen.
          During streaming, show the persistent "continue dans tous les
          modules" reassurance. After completion, show "généré pendant
          ton absence" if the user was away. */}
      {/* v85 : pipeline banner with live ETA + progress + phase. The
          orchestrator runs analyse→plan→génération→validation→correction;
          `code.streaming` stays true the whole time so this shows the real
          phase message, the elapsed-derived ETA, and a thin progress bar. */}
      {(code.streaming || completedWhileAwayAt) && (() => {
        const accent = !code.streaming
          ? '0.78 0.16 80'                                   // done · gold
          : code.phase === 'research' || code.phase === 'brand'
            ? '0.74 0.13 60'                                  // research · amber
            : code.phase === 'planning'
              ? '0.65 0.20 296'                               // planning · violet
              : code.phase === 'validation'
                ? '0.70 0.13 200'                             // validation · cyan
                : '0.72 0.12 145'                             // streaming · green
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
              {/* Row 1 — pulse + narration française (ce qu'il fait) + toggle voix */}
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
                {/* 🔊 énoncer à voix haute — OFF par défaut */}
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
              {/* Row 2 — chrono temps réel + ETA + progression */}
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
      })()}
      {/* v82fm : hint visuel pendant drag-over */}
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
          {'</> Déposer code ou doc ·'} ts / py / md / pdf / docx
        </div>
      )}
      {/* Left: file tree + models — v82n6 : DYNAMIC tree from parsedFiles
          when stream has output, else demo placeholder.
          v82n9 : minHeight:0 + height:100% so overflowY:auto kicks in
          when the file list is long. */}
      <div style={{
        padding: '24px 18px',
        borderRight: '1px solid var(--line, rgba(255,255,255,0.12))',
        display: 'flex', flexDirection: 'column', gap: 12,
        overflowY: 'auto', minHeight: 0, height: '100%',
      }}>
        {/* v85 : work mode — travailler EN LIGNE (génération in-app +
            téléchargement) ou sur MON REPO (lecture du projet réel comme
            contexte + écriture des changements sur le disque). */}
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
                  placeholder="C:\\chemin\\vers\\repo" spellCheck={false}
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
              {/* v85f : autonomie — installer les dépendances pour que ça tourne sur le PC */}
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
        {/* v85e : narration — bouton "énoncer à voix haute" (OFF par défaut) +
            journal de ce qu'Aurora fait, en français, première personne. */}
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
            DEMO_FILES.map((f, i) => (
              <div key={f} style={{
                padding: '6px 10px', borderRadius: 6,
                fontSize: 12, fontFamily: 'var(--font-mono, monospace)',
                color: i === 3 ? 'var(--fg, #f5f5f5)' : 'var(--fg-dim, #aaa)',
                background: i === 3 ? 'var(--ink-800, #1a1a1a)' : 'transparent',
                display: 'flex', gap: 8, opacity: 0.55,
              }}>
                <span style={{ color: 'var(--fg-mute, #777)' }}>{i === 3 ? '◆' : '·'}</span>{f}
              </div>
            ))
          )}
        </div>

        <div style={{ flex: 1 }} />

        <div style={{
          padding: 12,
          background: 'var(--bg-card, rgba(255,255,255,0.03))',
          border: '1px solid var(--line, rgba(255,255,255,0.12))',
          borderRadius: 8,
        }}>
          <Eyebrow style={{ marginBottom: 8 }}>Modèles actifs</Eyebrow>
          {MODELS.map(([m, r]) => (
            <div key={m} style={{
              display: 'flex', justifyContent: 'space-between',
              fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
              padding: '4px 0',
            }}>
              <span style={{ color: 'var(--fg-dim, #aaa)' }}>{m}</span>
              <span style={{ color: GREEN }}>{r}</span>
            </div>
          ))}
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

      {/* Centre: PREVIEW PANE — v82n7 :
          - while streaming → CONSTRUCTION indicator with file list,
            spinner, and "files appearing as fences land" hint, NEVER
            duplicate the right-pane code (user reported the pane was
            "remet simplement le code en directe").
          - else if webPreview detected (HTML / React / CSS) → iframe
            live render that REALLY emulates the page.
          - else if a file is active and stream done → show that file
            (click another file in left tree to switch).
          - else (idle, never submitted) → BEFORE demo placeholder. */}
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
                  : 'api/diffusion.ts · before'}
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
            // v82n6 : whiteSpace pre + overflow auto for horizontal scroll
            whiteSpace: 'pre',
            overflow: 'auto',
          }}>
            {activeFile.content}
          </pre>
        ) : (
          <pre style={{
            flex: 1, padding: '18px 22px', margin: 0,
            fontFamily: 'var(--font-mono, monospace)', fontSize: 12, lineHeight: 1.7,
            color: 'var(--fg-dim, #aaa)', overflow: 'auto',
            whiteSpace: 'pre-wrap',
          }}>
            {`export async function diffuse(\n  prompt: string,\n  steps = 28,\n`}
            <span style={{
              background: `${RED}33`, display: 'block',
              padding: '0 22px', margin: '0 -22px',
            }}>{`  // TODO: validate guidance range\n  guidance: number,`}</span>
            {BEFORE.slice(BEFORE.indexOf('  guidance: number,') + '  guidance: number,'.length)}
          </pre>
        )}
      </div>

      {/* Right: after streaming — v82bd : real LLM stream via
          useCodeViewLogic. v82n9 : minHeight:0 + height:100% so the
          flex column constrains its children inside the grid cell.
          Without this, the prompt input was pushed below the viewport
          and the streaming code couldn't be scrolled. */}
      <div style={{
        display: 'flex', flexDirection: 'column',
        minWidth: 0, minHeight: 0, height: '100%',
      }}>
        <div style={{
          padding: '14px 22px',
          borderBottom: '1px solid var(--line, rgba(255,255,255,0.12))',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <Eyebrow dot={GREEN}>
            {code.streaming ? 'stream · live' : code.hasOutput ? 'output · ready' : 'after · streaming'}
          </Eyebrow>
          {/* v82is : Stop button inline header pendant streaming */}
          {code.streaming && (
            <button type="button" onClick={code.abort}
              title="Arrêter le streaming (Esc dans le composer)"
              style={{
                marginRight: 8, padding: '3px 8px',
                background: 'oklch(0.55 0.18 25 / 0.10)',
                color: 'oklch(0.78 0.16 25)',
                border: '1px solid oklch(0.55 0.18 25 / 0.45)',
                fontSize: 10, fontWeight: 700,
                fontFamily: 'var(--font-mono, monospace)',
                cursor: 'pointer', borderRadius: 4,
                letterSpacing: '0.05em', textTransform: 'uppercase',
              }}>
              ✕ Stop
            </button>
          )}
          {/* v82iq : indicator enrichi avec token estimate live + dot
              animé pendant streaming */}
          <span style={{
            fontFamily: 'var(--font-mono, monospace)', fontSize: 11,
            color: 'var(--fg-dim, #aaa)',
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}>
            {code.streaming && (
              <span style={{
                display: 'inline-block', width: 6, height: 6,
                borderRadius: '50%', background: GREEN,
                animation: 'aurora-pulse-code 1.2s ease-in-out infinite',
              }} />
            )}
            <span>
              {code.hasOutput || code.streaming
                ? `${code.model} · ${code.streamOutput.length} c. · ~${Math.ceil(code.streamOutput.length / 4)}t${
                  code.streaming && tokensPerSec !== null && tokensPerSec > 0
                    ? ` · ${tokensPerSec.toFixed(1)}t/s`
                    : ''
                }${
                  !code.streaming && finalStats !== null
                    ? ` · avg ${finalStats.avg.toFixed(1)} · max ${finalStats.max.toFixed(1)} · ${finalStats.durationSec.toFixed(1)}s`
                    : ''
                }`
                : '+18 −4 · 0.4s'}
            </span>
            {/* v82it : sparkline mini 30 samples tps */}
            {code.streaming && tpsHistory.length >= 2 && (() => {
              const max = Math.max(1, ...tpsHistory)
              return (
                <div style={{
                  display: 'flex', alignItems: 'flex-end', gap: 1,
                  height: 12, width: 50,
                }} title={`tps history · last ${tpsHistory.length} samples · max ${max.toFixed(1)}t/s`}>
                  {tpsHistory.map((v, i) => (
                    <span key={i} style={{
                      flex: 1, height: Math.max(1, (v / max) * 12),
                      background: GREEN, borderRadius: 1, opacity: 0.85,
                    }} />
                  ))}
                </div>
              )
            })()}
            <style>{`
              @keyframes aurora-pulse-code {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.4; transform: scale(0.85); }
              }
            `}</style>
          </span>
        </div>

        {/* Stream pane — v82bh :
            - idle : demo animation static (faux streaming visual)
            - streaming : plain <pre> mono pour ne pas thrasher Prism
              au render à chaque token entrant
            - has-output (post-stream) : CodeBlock highlighted (Prism
              vscDarkPlus theme + line numbers + langue détectée)
            - error : block dédié */}
        {code.hasOutput && !code.streaming ? (
          <div style={{
            flex: '1 1 0', overflow: 'auto', minHeight: 0,
            // v82n9 : ensure horizontal scroll inside CodeBlock too —
            // Prism's <pre> defaults sometimes wrap on smaller widths.
            display: 'flex', flexDirection: 'column',
          }}>
            <Suspense fallback={
              <pre style={{
                padding: '18px 22px', margin: 0,
                fontFamily: 'var(--font-mono, monospace)', fontSize: 12, lineHeight: 1.7,
                color: 'var(--fg, #f5f5f5)',
                whiteSpace: 'pre', // h-scroll instead of wrap
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
        ) : (
          <pre style={{
            flex: '1 1 0', padding: '18px 22px', margin: 0,
            minHeight: 0, // v82n9 : critical for flex column shrink
            fontFamily: 'var(--font-mono, monospace)', fontSize: 12, lineHeight: 1.7,
            color: 'var(--fg, #f5f5f5)', overflow: 'auto',
            // v82n6 : pre + horizontal scroll for live streaming output too,
            // so long lines stay readable instead of wrapping into spaghetti.
            whiteSpace: code.streaming ? 'pre' : 'pre-wrap',
          }}>
            {code.streaming ? (
              <>
                {code.streamOutput}
                <span style={{
                  display: 'inline-block', width: 7, height: 14,
                  background: GREEN, verticalAlign: 'text-bottom',
                  animation: 'aurora-blink 1s steps(2) infinite',
                }} />
              </>
            ) : (
              <>
                {AFTER_PRE}
                <span style={{
                  background: `${GREEN}30`, display: 'block',
                  padding: '0 22px', margin: '0 -22px',
                }}>{AFTER_HIGHLIGHT.slice(0, streamLen)}<span style={{
                  display: 'inline-block', width: 7, height: 14,
                  background: GREEN, verticalAlign: 'text-bottom',
                  animation: 'aurora-blink 1s steps(2) infinite',
                }} /></span>
                {AFTER_POST}
              </>
            )}
            <style>{`@keyframes aurora-blink { 50% { opacity: 0 } }`}</style>
          </pre>
        )}

        {/* v82ft : daily tip Code (visible si pas de stream / output) */}
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

        {/* Real prompt input + submit — v82bd
            v82n9 : flexShrink:0 + maxHeight:40% so this area NEVER
            grows beyond 40% of column height. Plus the inner history
            list (which already has overflowY:auto + maxHeight:140) is
            preserved. User reported they couldn't reach this prompt
            input — root cause was the column not constraining its
            children's height. Now the stream pane shrinks to fit and
            the prompt is always visible at the bottom. */}
        <div style={{
          padding: 14, gap: 8,
          borderTop: '1px solid var(--line, rgba(255,255,255,0.12))',
          display: 'flex', flexDirection: 'column',
          flexShrink: 0,
          maxHeight: '40%',
          overflowY: 'auto',
          background: 'var(--bg, #0c0a09)',
        }}>
          {/* v85 : continuity badge — makes it explicit that the next
              prompt iterates the SAME project (the bug the user reported
              was every prompt spawning a brand new project). */}
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
            {/* v82fa : preset surprise (random idée code + auto-submit) */}
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
            {/* v82hc : ★ favori dans bibliothèque */}
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
            {/* v82nd : open in detected editor (VSCode / Cursor / etc).
                Visible only when stream done AND we have parsed files. */}
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
              {/* v82ng : show modelUsed (actual) when it differs from
                  code.model (configured) — auto-reroute happened. */}
              {code.modelUsed && code.modelUsed !== code.model && (
                <span style={{ color: 'oklch(0.74 0.13 60)', fontSize: 9 }}>↳</span>
              )}
              {code.modelUsed || code.model || 'no model'} · stream direct
            </span>
            {/* v82ia : streak créativité Code */}
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
          {/* v82gr : prompt history persistant cliquable pour recall */}
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
    </div>
  )
}

type PreviewRuntimeMessage = {
  source?: string
  type?: 'ready' | 'error' | 'console'
  level?: string
  message?: string
  filename?: string
  lineno?: number
  colno?: number
  bodyTextLen?: number
  nodeCount?: number
  canvasCount?: number
  imageCount?: number
}

function instrumentPreviewHtml(html: string): string {
  const script = `<script>
(function(){
  var send = function(payload) {
    try { window.parent.postMessage(Object.assign({ source: 'aurora-code-preview' }, payload), '*'); } catch (_) {}
  };
  var stringify = function(value) {
    try {
      if (value && value.stack) return String(value.stack);
      if (value && value.message) return String(value.message);
      if (typeof value === 'string') return value;
      return JSON.stringify(value);
    } catch (_) {
      return String(value);
    }
  };
  var reportReady = function() {
    try {
      var body = document.body;
      var text = body && body.innerText ? body.innerText.trim() : '';
      send({
        type: 'ready',
        bodyTextLen: text.length,
        nodeCount: body ? body.querySelectorAll('*').length : 0,
        canvasCount: body ? body.querySelectorAll('canvas').length : 0,
        imageCount: body ? body.querySelectorAll('img').length : 0
      });
    } catch (err) {
      send({ type: 'error', message: stringify(err) });
    }
  };
  window.addEventListener('error', function(event) {
    send({
      type: 'error',
      message: event.message || stringify(event.error) || 'Runtime error',
      filename: event.filename || '',
      lineno: event.lineno || 0,
      colno: event.colno || 0
    });
  });
  window.addEventListener('unhandledrejection', function(event) {
    send({ type: 'error', message: stringify(event.reason) || 'Unhandled promise rejection' });
  });
  var originalError = console.error;
  console.error = function() {
    send({ type: 'console', level: 'error', message: Array.prototype.map.call(arguments, stringify).join(' ') });
    return originalError.apply(console, arguments);
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ setTimeout(reportReady, 80); }, { once: true });
  } else {
    setTimeout(reportReady, 80);
  }
  window.addEventListener('load', function(){ setTimeout(reportReady, 160); }, { once: true });
})();
<\/script>`

  if (/<head[\s>]/i.test(html)) {
    return html.replace(/<head([^>]*)>/i, `<head$1>${script}`)
  }
  if (/<html[\s>]/i.test(html)) {
    return html.replace(/<html([^>]*)>/i, `<html$1>${script}`)
  }
  return `${script}${html}`
}

function CodePreviewFrame({ html, title }: { html: string; title: string }) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [ready, setReady] = useState(false)
  const [stalled, setStalled] = useState(false)
  const [runtimeMessages, setRuntimeMessages] = useState<PreviewRuntimeMessage[]>([])
  const [lastReadySignal, setLastReadySignal] = useState<PreviewRuntimeMessage | null>(null)
  const instrumentedHtml = useMemo(() => instrumentPreviewHtml(html), [html])

  useEffect(() => {
    setReady(false)
    setStalled(false)
    setRuntimeMessages([])
    setLastReadySignal(null)
    // v85h : longer grace window. External scripts (Tailwind CDN, Google Fonts)
    // can delay the iframe `load` past a couple seconds on a cold cache; the
    // native onLoad below clears `stalled` the instant the frame loads, so this
    // timer only fires for a genuinely stuck frame.
    const timer = window.setTimeout(() => setStalled(true), 9000)
    return () => window.clearTimeout(timer)
  }, [instrumentedHtml])

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      // v85h : a sandboxed/opaque-origin srcdoc iframe does NOT reliably make
      // `event.source === iframe.contentWindow`, so that check silently dropped
      // every 'ready' signal → false "PREVIEW SANS SIGNAL" even though the page
      // rendered. The unique `data.source` marker is enough to identify our own
      // instrumented preview messages.
      const data = event.data as PreviewRuntimeMessage
      if (!data || data.source !== 'aurora-code-preview') return
      if (data.type === 'ready') {
        setReady(true)
        setStalled(false)
        setLastReadySignal(data)
        return
      }
      if (data.type === 'error' || data.type === 'console') {
        setRuntimeMessages((messages) => [...messages, data].slice(-5))
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  const emptyRender = ready
    && (lastReadySignal?.bodyTextLen ?? 0) < 2
    && (lastReadySignal?.nodeCount ?? 0) <= 3
    && (lastReadySignal?.canvasCount ?? 0) === 0
    && (lastReadySignal?.imageCount ?? 0) === 0
  const topIssue = runtimeMessages[0]
  // v85h : once the frame has loaded (native onLoad OR 'ready' postMessage),
  // NEVER show the "sans signal" alarm — the 9s stall timer fires independently
  // and used to re-raise it even on a perfectly rendered page.
  const showStalled = stalled && !ready

  return (
    <div style={{ flex: 1, minHeight: 0, position: 'relative', background: '#fff' }}>
      <iframe
        ref={iframeRef}
        srcDoc={instrumentedHtml}
        title={title}
        // v85h : the native load event is the authoritative "the frame loaded"
        // signal — it always fires for srcdoc, unlike the postMessage which the
        // sandbox/source-check could drop. Clears the false "SANS SIGNAL" alarm.
        onLoad={() => { setStalled(false); setReady(true) }}
        // v82ns : keep srcdoc in an opaque origin. allow-scripts + forms are
        // enough for a runnable preview without letting generated links steer Aurora.
        sandbox="allow-scripts allow-forms allow-modals"
        style={{
          width: '100%',
          height: '100%',
          border: 'none',
          background: '#fff',
        }}
      />
      {(topIssue || showStalled || emptyRender) && (
        <div style={{
          position: 'absolute',
          left: 12,
          right: 12,
          bottom: 12,
          borderRadius: 8,
          padding: '10px 12px',
          background: topIssue ? 'oklch(0.20 0.05 25 / 0.96)' : 'oklch(0.20 0.04 70 / 0.94)',
          border: topIssue ? '1px solid oklch(0.62 0.18 25 / 0.65)' : '1px solid oklch(0.74 0.13 60 / 0.55)',
          color: topIssue ? 'oklch(0.86 0.12 25)' : 'oklch(0.88 0.12 70)',
          boxShadow: '0 12px 36px rgba(0,0,0,0.35)',
          fontFamily: 'var(--font-mono, monospace)',
          fontSize: 10.5,
          lineHeight: 1.45,
          pointerEvents: 'none',
        }}>
          <div style={{ textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 700, marginBottom: 4 }}>
            {topIssue ? 'Preview runtime error' : showStalled ? 'Preview sans signal' : 'Preview vide detectee'}
          </div>
          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {topIssue
              ? `${topIssue.message || 'Erreur runtime inconnue'}${topIssue.lineno ? ` (${topIssue.lineno}:${topIssue.colno ?? 0})` : ''}`
              : showStalled
                ? 'Le frame ne confirme pas son chargement. La generation continue d etre conservee, mais il faut corriger le runtime avant export.'
                : 'Le document charge mais ne peint quasiment rien. Aurora doit corriger le point d entree ou le contenu initial.'}
          </div>
        </div>
      )}
    </div>
  )
}

function MachinePanelSection() {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 16 }}>
      <button onClick={() => setOpen(o => !o)} style={{
        background: 'rgba(94,124,222,.2)', color: '#e6e8eb',
        border: '1px solid rgba(94,124,222,.4)', borderRadius: 6,
        padding: '6px 12px', fontSize: 12, cursor: 'pointer',
      }}>{open ? '▾' : '▸'} Connexions machines (SSH / Pi / VPS)</button>
      {open && <div style={{ marginTop: 8 }}><MachineConnectionsPanel embed /></div>}
    </div>
  )
}
