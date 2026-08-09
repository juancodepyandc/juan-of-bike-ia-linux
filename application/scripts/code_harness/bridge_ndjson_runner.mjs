// Bridge NDJSON runner — makes the tunnel/CLI channel run the REAL pipeline.
//
// Before this runner, POST /api/code/generate/stream spawned
// python-services/aurora_code/bridge_agentic_stream.py: a standalone 394-line
// planner-executor with NONE of the quality gates the UI enjoys — no intent
// classification, no blocking architecture plan, no inter-module assets, no
// sandbox validation, no auto-correction loop, no design polish report. Any
// request arriving through /api/aurora/code/generate (cowork, tunnel, external
// callers) was therefore silently served by a degraded engine while the Tauri
// UI ran the full one. That is the hidden degraded path.
//
// This runner replaces that engine with the production `orchestrateCodeGeneration`
// — the exact function CodeView and the CLI harness call — and streams its
// progress as NDJSON using the SHARED event builders in
// src/services/codeStreamEvents.ts, so the schema (`aurora.code.stream/1`) and
// the consumer contract in bridge_server.py stay byte-identical.
//
// Protocol (unchanged from the Python engine it replaces):
//   stdin  : {"prompt": str, "model": str, "planningModel": str?, "runId": int?}
//   stdout : one JSON event per line, schema aurora.code.stream/1
//   stderr : human logs (never parsed)

import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { installHeadlessCodeEnv, routeConsoleToStderr } from './harness_env.mjs'

// Order matters: shims + resolve hook first, console rerouted before any
// pipeline module can log a single line onto stdout.
installHeadlessCodeEnv()
routeConsoleToStderr()

// ---------------------------------------------------------------------------
// 1. Read the JSON payload from stdin.
// ---------------------------------------------------------------------------
async function readStdin() {
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  return Buffer.concat(chunks).toString('utf8')
}

const raw = await readStdin()
let payload
try {
  payload = JSON.parse(raw || '{}')
} catch (err) {
  process.stdout.write(
    JSON.stringify({
      schema: 'aurora.code.stream/1',
      kind: 'error',
      runId: 0,
      sequence: 0,
      timestamp: Date.now(),
      message: `payload JSON invalide: ${err?.message ?? err}`,
      recoverable: false,
    }) + '\n',
  )
  process.exit(1)
}

const prompt = String(payload.prompt || '').trim()
const runId = Number(payload.runId) || Date.now()
if (!prompt) {
  process.stdout.write(
    JSON.stringify({
      schema: 'aurora.code.stream/1',
      kind: 'error',
      runId,
      sequence: 0,
      timestamp: Date.now(),
      message: 'prompt requis',
      recoverable: false,
    }) + '\n',
  )
  process.exit(1)
}

// ---------------------------------------------------------------------------
// 2. Load the real pipeline + the shared event builders.
// ---------------------------------------------------------------------------
const resolveSrc = (rel) => pathToFileURL(path.resolve(rel)).href

const { orchestrateCodeGeneration } = await import(resolveSrc('src/services/codeOrchestrator.ts'))
const { useAppStore } = await import(resolveSrc('src/stores/appStore.ts'))
const models = await import(resolveSrc('src/config/models.ts'))
const events = await import(resolveSrc('src/services/codeStreamEvents.ts'))

const {
  buildCodeStreamPhaseEvent,
  buildCodeStreamFileWrittenEvents,
  buildCodeStreamTestResultEvent,
  buildCodeStreamCorrectionEvent,
  buildCodeStreamVisualScoreEvent,
  buildCodeStreamDoneEvent,
  buildCodeStreamErrorEvent,
  serializeCodeStreamEvent,
} = events

// Same hardware profile the CLI harness declares, so the resilience layer makes
// the same num_ctx / memory-guard decisions on every channel.
useAppStore.setState({
  hardware: {
    os: 'Linux', cpu: 'bridge', cores: 16, ram_gb: 32,
    gpu: 'NVIDIA 16GB', vram_gb: 16, vram_free_gb: 15,
  },
})

const configuredCodeModel = String(payload.model || useAppStore.getState().codeModel || 'qwen3-coder:30b').trim()
const visionModel = useAppStore.getState().visionModel || models.DEFAULT_VISION_MODEL

// ---------------------------------------------------------------------------
// 3. NDJSON emitter.
// ---------------------------------------------------------------------------
let sequence = 0
const nextMeta = () => ({ runId, sequence: sequence++, timestamp: Date.now() })
const emit = (event) => {
  try {
    process.stdout.write(serializeCodeStreamEvent(event))
  } catch {
    /* a broken pipe must not crash the pipeline */
  }
}
const log = (...a) => process.stderr.write(a.join(' ') + '\n')

log(`[bridge-runner] model=${configuredCodeModel} runId=${runId}`)
log(`[bridge-runner] prompt: ${prompt.slice(0, 140)}`)

emit(buildCodeStreamPhaseEvent({ ...nextMeta(), message: 'Demarrage du pipeline expert...', progress: 1 }))

// ---------------------------------------------------------------------------
// 4. Run the production orchestrator.
// ---------------------------------------------------------------------------
let lastFiles = []
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
      emit(buildCodeStreamPhaseEvent({ ...nextMeta(), message: String(detail ?? ''), progress: Number(progress) || 0 }))
    },
    // Token deltas are not forwarded: the NDJSON channel is an event stream for
    // machine consumers, not a character-by-character mirror. Keeps the stream
    // small and the memory profile O(n) on the consumer side.
    onToken: () => {},
    onFilesUpdate: (files) => {
      // Progress signal only — no content. The authoritative payload is emitted
      // once at the end, so consumers never have to de-duplicate file bodies.
      const evts = buildCodeStreamFileWrittenEvents({
        files: files ?? [],
        previousFiles: lastFiles,
        nextMeta,
        includeContent: false,
      })
      for (const e of evts) emit(e)
      lastFiles = files ?? []
    },
    onValidationUpdate: (sandboxResult) => {
      if (!sandboxResult) return
      emit(buildCodeStreamTestResultEvent(sandboxResult, nextMeta()))
    },
    onCorrectionLogUpdate: (logArr, attempt, score) => {
      const pass = Array.isArray(logArr) && logArr.length ? logArr[logArr.length - 1] : null
      emit(buildCodeStreamCorrectionEvent({ ...nextMeta(), pass, attempt: Number(attempt) || 0, score: Number(score) || 0 }))
    },
  })
} catch (err) {
  const message = err?.stack || String(err)
  log(`[bridge-runner] FATAL: ${message}`)
  emit(buildCodeStreamErrorEvent({ ...nextMeta(), message: String(err?.message ?? err), recoverable: true }))
  process.exit(1)
}

// ---------------------------------------------------------------------------
// 5. Final authoritative delivery: every file, with content.
// ---------------------------------------------------------------------------
const files = result?.files?.length ? result.files : lastFiles
if (!files.length) {
  emit(
    buildCodeStreamErrorEvent({
      ...nextMeta(),
      message: (result?.notes || 'Le pipeline n a produit aucun fichier exploitable.').slice(0, 2000),
      recoverable: true,
    }),
  )
  process.exit(1)
}

for (const e of buildCodeStreamFileWrittenEvents({
  files,
  previousFiles: [],
  nextMeta,
  includeContent: true,
})) {
  emit(e)
}

// WS9 sur le canal tunnel: la porte visuelle source-statique est evaluee par le
// pipeline pour les trois canaux, donc son verdict doit aussi etre OBSERVABLE
// ici, pas seulement dans l UI Tauri.
const visual = result?.visualFidelity
if (visual && Array.isArray(visual.checks) && visual.checks.length > 0) {
  emit(
    buildCodeStreamVisualScoreEvent({
      ...nextMeta(),
      score: Number(visual.score) || 0,
      viewport: 'source',
      summary: String(visual.summary ?? ''),
      source: visual.source === 'render_audit' ? 'render_audit' : 'source_static',
      failedChecks: Array.isArray(visual.failedChecks) ? visual.failedChecks : [],
    }),
  )
}

// Un pipeline en erreur qui a tout de meme produit des fichiers partiels ne doit
// PAS etre annonce `done`: les consommateurs (bridge `_aurora_code`, cowork)
// lisent `done` comme une livraison valide. Emettre `done` ici transformerait un
// echec en succes silencieux — exactement l anti-pattern que ce module paie
// depuis le debut. Les fichiers partiels restent emis pour inspection, puis on
// clot par un `error` explicite.
const pipelineFailed =
  result?.phase === 'error' || /^Erreur fatale du pipeline:/i.test(String(result?.notes ?? ''))

if (pipelineFailed) {
  emit(
    buildCodeStreamErrorEvent({
      ...nextMeta(),
      message: String(result?.notes ?? 'pipeline en erreur').slice(0, 2000),
      recoverable: true,
    }),
  )
  log(`[bridge-runner] FAILED phase=${result?.phase} files=${files.length} (fichiers partiels emis)`)
  process.exit(1)
}

emit(
  buildCodeStreamDoneEvent({
    ...nextMeta(),
    files,
    finalScore: Number(result?.finalScore) || 0,
    totalAttempts: Number(result?.totalAttempts) || 0,
    notes: String(result?.notes ?? ''),
  }),
)

log(`[bridge-runner] done files=${files.length} score=${result?.finalScore} attempts=${result?.totalAttempts}`)
process.exit(0)
