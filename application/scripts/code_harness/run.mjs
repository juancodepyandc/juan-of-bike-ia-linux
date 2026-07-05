// Headless harness for the REAL AuroraIA code pipeline.
//
// Runs the production `orchestrateCodeGeneration` (codeOrchestrator.ts) against
// the live local Ollama (127.0.0.1:11434), exactly as the app would, then writes
// the generated project to disk and prints a JSON quality summary.
//
// Usage:
//   cd application
//   node scripts/code_harness/run.mjs --out output/code-tests/<name> --prompt "..."
//   (or pass the prompt as trailing args, with the model via AURORA_CODE_MODEL)
//
// Why headless: the app routes ollamaChatStream through the bridge first, then
// falls back to direct Ollama — so this works even when the bridge is down.

import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'

// ---------------------------------------------------------------------------
// 1. Browser-ish globals so the (UI-flavoured) modules load under Node.
// ---------------------------------------------------------------------------
const mem = new Map()
const localStorageShim = {
  getItem: (k) => (mem.has(k) ? mem.get(k) : null),
  setItem: (k, v) => mem.set(k, String(v)),
  removeItem: (k) => mem.delete(k),
  clear: () => mem.clear(),
  key: (i) => Array.from(mem.keys())[i] ?? null,
  get length() {
    return mem.size
  },
}
const noop = () => {}
globalThis.localStorage = localStorageShim
globalThis.window = {
  location: { hostname: 'localhost', href: 'http://localhost/', origin: 'http://localhost' },
  localStorage: localStorageShim,
  addEventListener: noop,
  removeEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop, removeEventListener: noop }),
}
globalThis.document = {
  documentElement: { setAttribute: noop, classList: { add: noop, remove: noop, toggle: noop } },
  body: { setAttribute: noop },
  addEventListener: noop,
  createElement: () => ({ setAttribute: noop, style: {}, appendChild: noop }),
  querySelector: () => null,
}

// ---------------------------------------------------------------------------
// 2. Register the resolve hook for extensionless TS imports.
// ---------------------------------------------------------------------------
register('./hooks.mjs', import.meta.url)

// ---------------------------------------------------------------------------
// 3. Parse args.
// ---------------------------------------------------------------------------
const argv = process.argv.slice(2)
let outDir = null
let modelOverride = process.env.AURORA_CODE_MODEL || null
const promptParts = []
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--out') outDir = argv[++i]
  else if (argv[i] === '--model') modelOverride = argv[++i]
  else if (argv[i] === '--prompt') promptParts.push(argv[++i])
  else promptParts.push(argv[i])
}
const prompt = promptParts.join(' ').trim()
if (!prompt) {
  process.stderr.write('usage: run.mjs --out <dir> [--model <m>] --prompt "<prompt>"\n')
  process.exit(2)
}
if (!outDir) outDir = path.resolve('output/code-tests/harness_run')

// ---------------------------------------------------------------------------
// 4. Load the real pipeline.
// ---------------------------------------------------------------------------
const orchUrl = pathToFileURL(path.resolve('src/services/codeOrchestrator.ts')).href
const storeUrl = pathToFileURL(path.resolve('src/stores/appStore.ts')).href
const modelsUrl = pathToFileURL(path.resolve('src/config/models.ts')).href

const { orchestrateCodeGeneration } = await import(orchUrl)
const { useAppStore } = await import(storeUrl)
const models = await import(modelsUrl)

// Make the resilience layer (which reads hardware.vram_gb for num_ctx / memory
// guard decisions) behave like a real 16 GB GPU box instead of vram=0.
useAppStore.setState({
  hardware: {
    os: 'Windows 11', cpu: 'harness', cores: 16, ram_gb: 32,
    gpu: 'NVIDIA 16GB', vram_gb: 16, vram_free_gb: 15,
  },
})

const appCodeModel = useAppStore.getState().codeModel
const configuredCodeModel = modelOverride || appCodeModel
const visionModel = useAppStore.getState().visionModel || models.DEFAULT_VISION_MODEL

// Swap safety (16 GB VRAM): never let two big models sit in VRAM together — that
// concurrency crashed the box. Before generating, unload any resident model that
// is not the one we're about to use.
try {
  const ps = await fetch('http://127.0.0.1:11434/api/ps').then((r) => r.json()).catch(() => ({ models: [] }))
  for (const m of ps.models || []) {
    if (m.name !== configuredCodeModel) {
      process.stderr.write(`[swap] déchargement ${m.name} (≠ cible ${configuredCodeModel})\n`)
      await fetch('http://127.0.0.1:11434/api/generate', {
        method: 'POST',
        body: JSON.stringify({ model: m.name, keep_alive: 0 }),
      }).catch(() => {})
    }
  }
} catch {
  /* best effort — never block generation on this */
}

// ---------------------------------------------------------------------------
// 5. Run, capturing phases / tokens / files.
// ---------------------------------------------------------------------------
const t0 = Date.now()
const phases = []
let tokenChars = 0
let lastFiles = []
let lastNotes = ''
const corrections = []
const recoveries = []

const log = (...a) => process.stderr.write(a.join(' ') + '\n')
log(`[harness] model=${configuredCodeModel} (app default=${appCodeModel}) vision=${visionModel}`)
log(`[harness] prompt: ${prompt.slice(0, 120)}${prompt.length > 120 ? '…' : ''}`)

let result
try {
  result = await orchestrateCodeGeneration({
    prompt,
    enrichedPrompt: prompt,
    conversationHistory: [],
    existingFiles: [],
    contextImages: [],
    userFileDataUrls: {},
    configuredCodeModel,
    visionModel,
    setPhase: (detail, progress) => {
      const line = `${Math.round((progress ?? 0))}% ${detail}`
      phases.push({ t: Math.round((Date.now() - t0) / 1000), line })
      log(`[phase] ${line}`)
    },
    onToken: (tok) => {
      tokenChars += tok.length
    },
    onFilesUpdate: (files, notes) => {
      lastFiles = files
      lastNotes = notes
      log(`[files] ${files.length} file(s), notes=${(notes || '').length}c`)
    },
    onValidationUpdate: (r) => log(`[validation] ok=${r?.ok} steps=${r?.steps?.length ?? 0}`),
    onCorrectionLogUpdate: (logArr, attempt, score) => {
      corrections.push({ attempt, score, passes: logArr?.length ?? 0 })
      log(`[correction] attempt=${attempt} score=${score}`)
    },
    onRecoveryEvent: (ev) => {
      recoveries.push(ev)
      log(`[recovery] ${JSON.stringify(ev).slice(0, 160)}`)
    },
    onFollowUpAnalysis: (a) => log(`[followup] ${JSON.stringify(a).slice(0, 160)}`),
  })
} catch (err) {
  log(`[harness] FATAL: ${err && err.stack ? err.stack : err}`)
  process.exit(1)
}

const elapsed = Math.round((Date.now() - t0) / 1000)
const files = result.files && result.files.length ? result.files : lastFiles
const succeeded = result.phase === 'done'
  && files.length > 0
  && (typeof result.finalScore !== 'number' || result.finalScore > 0)
  && !/^Erreur fatale du pipeline:/i.test(String(result.notes || lastNotes || ''))

// ---------------------------------------------------------------------------
// 6. Write files to disk.
// ---------------------------------------------------------------------------
mkdirSync(outDir, { recursive: true })
const fileReport = []
for (const f of files) {
  const rel = f.path || f.name || 'unnamed.txt'
  const dest = path.join(outDir, rel)
  mkdirSync(path.dirname(dest), { recursive: true })
  const content = typeof f.content === 'string' ? f.content : String(f.content ?? '')
  writeFileSync(dest, content, 'utf8')
  fileReport.push({ path: rel, bytes: Buffer.byteLength(content, 'utf8'), lines: content.split('\n').length })
}

// ---------------------------------------------------------------------------
// 7. Summary.
// ---------------------------------------------------------------------------
const summary = {
  ok: succeeded,
  elapsedSec: elapsed,
  model: configuredCodeModel,
  phaseFinal: result.phase,
  intent: result.intent
    ? {
        projectType: result.intent.projectType,
        language: result.intent.language,
        framework: result.intent.framework,
        title: result.intent.title,
      }
    : null,
  finalScore: result.finalScore,
  totalAttempts: result.totalAttempts,
  designReport: result.designReport
    ? { score: result.designReport.score, issues: result.designReport.issues }
    : null,
  sandbox: result.sandboxResult ? { ok: result.sandboxResult.ok } : null,
  tokenChars,
  totalBytes: fileReport.reduce((s, f) => s + f.bytes, 0),
  fileCount: fileReport.length,
  files: fileReport,
  notes: (result.notes || lastNotes || '').slice(0, 600),
  corrections,
  recoveries: recoveries.length,
  outDir,
}
writeFileSync(path.join(outDir, '_harness_summary.json'), JSON.stringify(summary, null, 2), 'utf8')
process.stdout.write(JSON.stringify(summary, null, 2) + '\n')
process.exit(succeeded ? 0 : 1)
