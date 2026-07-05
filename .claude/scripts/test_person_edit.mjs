// Test live edition d'image sur une VRAIE photo de personne (libre de droit).
// Passe par le VRAI chemin de code du module image :
//   parseImageIntent -> buildKontextInstruction -> createFluxKontextWorkflow
// puis soumet a ComfyUI (Kontext) et telecharge le resultat pour verification.
//
// Usage :
//   node --experimental-strip-types .claude/scripts/test_person_edit.mjs "ajoute des lunettes de soleil" [tag]
//
// L'image source (person_src.jpg) est FIGEE sur disque : aucune regeneration,
// pour que chaque retest compare bien le meme point de depart.
import { parseImageIntent } from '../../application/src/utils/imagePromptParser.ts'
import { buildKontextInstruction, createFluxKontextWorkflow, resolveKontextModel } from '../../application/src/utils/fluxKontextWorkflow.ts'
import { translateEditInstructionToEnglish } from '../../application/src/utils/kontextInstructionTranslator.ts'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const COMFY = 'http://127.0.0.1:8188'
const HERE = dirname(fileURLToPath(import.meta.url))
// OUT_DIR / source configurables : SRC_IMG (chemin photo source), OUT_DIR (sortie).
const OUT_DIR = process.env.OUT_DIR
  ? process.env.OUT_DIR
  : join(HERE, '..', 'test-outputs', 'image_person_test')
mkdirSync(OUT_DIR, { recursive: true })

const editPrompt = process.argv[2] || 'ajoute des lunettes de soleil'
const tag = process.argv[3] || 'edit'
const SRC = process.env.SRC_IMG ? process.env.SRC_IMG : join(OUT_DIR, 'person_src.jpg')

function log(...a) { console.log(...a) }

async function comfy(path, opts) {
  const r = await fetch(`${COMFY}${path}`, opts)
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`)
  return r
}

async function queueAndWait(workflow, label, timeoutMs = 12 * 60 * 1000) {
  const queued = await (await comfy('/prompt', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: workflow }),
  })).json()
  if (!queued.prompt_id) throw new Error(`${label}: pas de prompt_id — ${JSON.stringify(queued).slice(0, 600)}`)
  log(`[${label}] queued ${queued.prompt_id}`)
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    await new Promise((r) => setTimeout(r, 3000))
    const hist = await fetch(`${COMFY}/history/${queued.prompt_id}`).then((r) => r.json()).catch(() => null)
    const payload = hist?.[queued.prompt_id]
    if (payload?.status?.status_str === 'error') {
      throw new Error(`${label}: erreur ComfyUI — ${JSON.stringify(payload.status.messages ?? []).slice(0, 1200)}`)
    }
    const outputs = payload?.outputs
    if (outputs) {
      for (const node of Object.values(outputs)) {
        for (const img of node?.images ?? []) {
          if (img?.filename) {
            log(`[${label}] done in ${Math.round((Date.now() - started) / 1000)}s → ${img.filename}`)
            return img.filename
          }
        }
      }
    }
  }
  throw new Error(`${label}: timeout`)
}

async function download(filename, dest) {
  const buf = await fetch(`${COMFY}/view?filename=${encodeURIComponent(filename)}&type=output`).then((r) => r.arrayBuffer())
  writeFileSync(dest, Buffer.from(buf))
  log(`saved ${dest} (${Math.round(buf.byteLength / 1024)} KB)`)
}

// ---------- 0. resolution du modele kontext (comme l'app) ----------
const info = await comfy('/object_info/UNETLoader').then((r) => r.json())
const unetNames = info?.UNETLoader?.input?.required?.unet_name?.[0] ?? []
const kontextModel = resolveKontextModel(Array.isArray(unetNames) ? unetNames : [])
if (!kontextModel) throw new Error('Aucun UNET kontext installe')
log(`[model] kontext = ${kontextModel}`)

// ---------- 1. upload de la photo source comme reference ----------
const srcBytes = readFileSync(SRC)
const form = new FormData()
form.append('image', new Blob([srcBytes], { type: 'image/jpeg' }), 'person_ref.jpg')
form.append('overwrite', 'true')
const up = await comfy('/upload/image', { method: 'POST', body: form }).then((r) => r.json())
log(`[upload] ${up.name}`)

// ---------- 2. intention + instruction (VRAI chemin de code) ----------
const intent = parseImageIntent(editPrompt, { hasReference: true })
log(`\n[PROMPT] "${editPrompt}"`)
log(`[intent] mode=${intent.editMode} isEdit=${intent.isEditIntent}`)
log(`[intent] additions=${JSON.stringify(intent.additions)} removals=${JSON.stringify(intent.removals)} replacements=${JSON.stringify(intent.replacements)}`)
if (!intent.isEditIntent) throw new Error('le parser n a pas detecte l intention d edition')

// VRAI nouveau chemin : traduction FR->EN (lexique + LLM Ollama reel) puis
// buildKontextInstruction avec le cœur anglais.
const OLLAMA = 'http://127.0.0.1:11434'
const ollamaGen = async (model, p) => {
  const r = await fetch(`${OLLAMA}/api/generate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, prompt: p, stream: false }),
  })
  return r.json()
}
const englishCore = await translateEditInstructionToEnglish(editPrompt, {
  generate: ollamaGen, model: process.env.TRANSLATE_MODEL || 'qwen3:14b', timeoutMs: 30000,
})
log(`[ENGLISH CORE] ${englishCore}`)
const instruction = buildKontextInstruction(editPrompt, intent, { englishCore })
log(`[INSTRUCTION envoyee a Kontext]\n  ${instruction}\n`)

// ---------- 3. /free avant le swap (comme le hook v83) ----------
await fetch(`${COMFY}/free`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ unload_models: true, free_memory: true }),
}).catch(() => {})
log('[free] VRAM liberee avant chargement kontext')

// ---------- 4. workflow Kontext reel ----------
const workflow = createFluxKontextWorkflow({
  instruction,
  referenceFilename: up.name,
  unetName: kontextModel,
  filenamePrefix: `person_${tag}`,
  seed: 777,
})
const editFile = await queueAndWait(workflow, `kontext-${tag}`)
const editPath = join(OUT_DIR, `edited_${tag}.png`)
await download(editFile, editPath)

log('\nLIVE TEST OK')
log(`source : ${SRC}`)
log(`edited : ${editPath}`)
