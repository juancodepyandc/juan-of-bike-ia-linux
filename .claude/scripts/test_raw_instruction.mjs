// A/B : envoie une instruction Kontext BRUTE (arg) sans passer par
// buildKontextInstruction, pour isoler l'effet de la langue de l'instruction.
import { createFluxKontextWorkflow, resolveKontextModel } from '../../application/src/utils/fluxKontextWorkflow.ts'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const COMFY = 'http://127.0.0.1:8188'
const HERE = dirname(fileURLToPath(import.meta.url))
const OUT_DIR = join(HERE, '..', 'test-outputs', 'image_person_test')
mkdirSync(OUT_DIR, { recursive: true })
const instruction = process.argv[2]
const tag = process.argv[3] || 'raw'
if (!instruction) throw new Error('usage: node test_raw_instruction.mjs "<instruction>" <tag>')

async function queueAndWait(workflow, label, timeoutMs = 10 * 60 * 1000) {
  const queued = await fetch(`${COMFY}/prompt`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: workflow }) }).then((r) => r.json())
  if (!queued.prompt_id) throw new Error(`${label}: ${JSON.stringify(queued).slice(0, 400)}`)
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    await new Promise((r) => setTimeout(r, 3000))
    const hist = await fetch(`${COMFY}/history/${queued.prompt_id}`).then((r) => r.json()).catch(() => null)
    const payload = hist?.[queued.prompt_id]
    if (payload?.status?.status_str === 'error') throw new Error(`${label}: ${JSON.stringify(payload.status.messages ?? []).slice(0, 800)}`)
    for (const node of Object.values(payload?.outputs ?? {})) for (const img of node?.images ?? []) if (img?.filename) { console.log(`[${label}] ${Math.round((Date.now()-started)/1000)}s -> ${img.filename}`); return img.filename }
  }
  throw new Error(`${label}: timeout`)
}

const info = await fetch(`${COMFY}/object_info/UNETLoader`).then((r) => r.json())
const kontextModel = resolveKontextModel(info?.UNETLoader?.input?.required?.unet_name?.[0] ?? [])
const srcBytes = readFileSync(join(OUT_DIR, 'person_src.jpg'))
const form = new FormData()
form.append('image', new Blob([srcBytes], { type: 'image/jpeg' }), 'person_ref.jpg')
form.append('overwrite', 'true')
const up = await fetch(`${COMFY}/upload/image`, { method: 'POST', body: form }).then((r) => r.json())
console.log(`[INSTRUCTION] ${instruction}`)
const workflow = createFluxKontextWorkflow({ instruction, referenceFilename: up.name, unetName: kontextModel, filenamePrefix: `person_${tag}`, seed: 777 })
const f = await queueAndWait(workflow, tag)
const buf = await fetch(`${COMFY}/view?filename=${encodeURIComponent(f)}&type=output`).then((r) => r.arrayBuffer())
const dest = join(OUT_DIR, `edited_${tag}.png`)
writeFileSync(dest, Buffer.from(buf))
console.log(`saved ${dest}`)
