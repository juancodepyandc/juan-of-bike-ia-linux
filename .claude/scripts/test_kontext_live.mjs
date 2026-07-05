// Test live du pipeline edition image v83 :
//   1. txt2img FLUX dev (createFluxWorkflow reel)
//   2. upload du resultat comme reference
//   3. edition Kontext (parseImageIntent + buildKontextInstruction +
//      createFluxKontextWorkflow reels) — "ajoute un chapeau rouge"
//   4. sauvegarde base.png / edited.png pour verification vision
// Lancer depuis la racine repo :
//   node --experimental-strip-types .claude/scripts/test_kontext_live.mjs
import { createFluxWorkflow } from '../../application/src/utils/fluxWorkflow.ts'
import { parseImageIntent } from '../../application/src/utils/imagePromptParser.ts'
import { buildKontextInstruction, createFluxKontextWorkflow } from '../../application/src/utils/fluxKontextWorkflow.ts'
import { writeFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const COMFY = 'http://127.0.0.1:8188'
const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'test-outputs', 'image_kontext')
mkdirSync(OUT_DIR, { recursive: true })

async function queueAndWait(workflow, label, timeoutMs = 10 * 60 * 1000) {
  const queueResp = await fetch(`${COMFY}/prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: workflow }),
  })
  const queued = await queueResp.json()
  if (!queued.prompt_id) throw new Error(`${label}: pas de prompt_id — ${JSON.stringify(queued).slice(0, 400)}`)
  console.log(`[${label}] queued ${queued.prompt_id}`)

  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    await new Promise((r) => setTimeout(r, 3000))
    const hist = await fetch(`${COMFY}/history/${queued.prompt_id}`).then((r) => r.json()).catch(() => null)
    const payload = hist?.[queued.prompt_id]
    if (payload?.status?.status_str === 'error') {
      throw new Error(`${label}: erreur ComfyUI — ${JSON.stringify(payload.status.messages ?? []).slice(0, 600)}`)
    }
    const outputs = payload?.outputs
    if (outputs) {
      for (const node of Object.values(outputs)) {
        for (const img of node?.images ?? []) {
          if (img?.filename) {
            console.log(`[${label}] done in ${Math.round((Date.now() - started) / 1000)}s → ${img.filename}`)
            return img.filename
          }
        }
      }
    }
  }
  throw new Error(`${label}: timeout`)
}

async function download(filename, dest) {
  const buf = await fetch(`${COMFY}/view?filename=${encodeURIComponent(filename)}&type=output`)
    .then((r) => r.arrayBuffer())
  writeFileSync(dest, Buffer.from(buf))
  console.log(`saved ${dest} (${Math.round(buf.byteLength / 1024)} KB)`)
}

// ---------- 1. base txt2img ----------
const basePrompt = 'un chat roux assis sur un tabouret en bois, photo simple, fond gris uni, le chat ne porte rien sur la tete'
const baseWorkflow = createFluxWorkflow({
  prompt: basePrompt,
  width: 768,
  height: 768,
  steps: 20,
  filenamePrefix: 'v83_kontext_base',
  style: 'none',
  seed: 12345,
})
const baseFile = await queueAndWait(baseWorkflow, 'base')
const basePath = join(OUT_DIR, 'base.png')
await download(baseFile, basePath)

// ---------- 2. upload comme reference ----------
const baseBytes = await fetch(`${COMFY}/view?filename=${encodeURIComponent(baseFile)}&type=output`).then((r) => r.arrayBuffer())
const form = new FormData()
form.append('image', new Blob([baseBytes], { type: 'image/png' }), 'v83_kontext_ref.png')
form.append('overwrite', 'true')
const up = await fetch(`${COMFY}/upload/image`, { method: 'POST', body: form }).then((r) => r.json())
console.log(`[upload] ${up.name}`)

// ---------- 3. edition Kontext via le VRAI chemin de code ----------
const editPrompt = 'ajoute un chapeau rouge sur la tete du chat'
const intent = parseImageIntent(editPrompt, { hasReference: true })
console.log(`[intent] mode=${intent.editMode} isEdit=${intent.isEditIntent} additions=${JSON.stringify(intent.additions)}`)
if (!intent.isEditIntent) throw new Error('le parser n a pas detecte l intention d edition')

const instruction = buildKontextInstruction(editPrompt, intent)
console.log(`[instruction] ${instruction}`)

// Comme le hook v83 : /free avant le swap dev → kontext (sinon CPU OOM,
// les deux UNET 16+11 GB coexistent en RAM pendant le chargement).
await fetch(`${COMFY}/free`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ unload_models: true, free_memory: true }),
})
console.log('[free] modeles dev decharges avant swap kontext')

const kontextWorkflow = createFluxKontextWorkflow({
  instruction,
  referenceFilename: up.name,
  unetName: 'flux1-dev-kontext_fp8_scaled.safetensors',
  filenamePrefix: 'v83_kontext_edit',
  seed: 777,
})
const editFile = await queueAndWait(kontextWorkflow, 'kontext-edit')
const editPath = join(OUT_DIR, 'edited.png')
await download(editFile, editPath)

console.log('\nLIVE TEST OK')
console.log(`base   : ${basePath}`)
console.log(`edited : ${editPath}`)
