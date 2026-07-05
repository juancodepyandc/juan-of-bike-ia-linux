// E2E "comme le site" : tout passe par le BRIDGE (port 3001), exactement les
// endpoints que l'app web (mode navigateur / tunnel) utilise — pas ComfyUI en
// direct. Verifie : upload, generation via le vrai code de prod, recuperation
// de l'image (affichable/telechargeable) et conformite.
//
// Usage : node --experimental-strip-types .claude/scripts/bridge_e2e.mjs "ajoute des cheveux" hair <src.jpg>
import { parseImageIntent } from '../../application/src/utils/imagePromptParser.ts'
import { buildKontextInstruction, createFluxKontextWorkflow, resolveKontextModel } from '../../application/src/utils/fluxKontextWorkflow.ts'
import { translateEditInstructionToEnglish } from '../../application/src/utils/kontextInstructionTranslator.ts'
import { readFileSync, writeFileSync } from 'node:fs'

const BRIDGE = process.env.BRIDGE_BASE || 'http://127.0.0.1:3001'
const OLLAMA = 'http://127.0.0.1:11434'
const editPrompt = process.argv[2] || 'ajoute des cheveux'
const tag = process.argv[3] || 'site'
const SRC = process.argv[4] || '.claude/test-outputs/bald_test/bald_src.jpg'
const OUT = `.claude/test-outputs/bald_test/site_${tag}.png`

const log = (...a) => console.log(...a)
const ollamaGen = async (model, p) => {
  const r = await fetch(`${OLLAMA}/api/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model, prompt: p, stream: false }) })
  return r.json()
}

// 1. modele kontext (via proxy bridge, comme l'app)
const info = await fetch(`${BRIDGE}/proxy/comfy/object_info/UNETLoader`).then((r) => r.json())
const kontextModel = resolveKontextModel(info?.UNETLoader?.input?.required?.unet_name?.[0] ?? [])
log('[1/7] kontext model =', kontextModel)

// 2. upload image source via le bridge (endpoint web)
const bytes = readFileSync(SRC)
const form = new FormData()
form.append('image', new Blob([bytes], { type: 'image/jpeg' }), 'site_ref.jpg')
form.append('overwrite', 'true')
let upName = null
for (const url of [`${BRIDGE}/api/comfyui/upload`, `${BRIDGE}/proxy/comfy/upload/image`]) {
  try {
    const r = await fetch(url, { method: 'POST', body: form })
    if (r.ok) { const d = await r.json().catch(() => ({})); upName = d.name || 'site_ref.jpg'; log('[2/7] upload OK via', url.replace(BRIDGE, ''), '->', upName); break }
  } catch { /* try next */ }
}
if (!upName) throw new Error('upload bridge a echoue')

// 3. intent + traduction + instruction (VRAI code de prod)
const intent = parseImageIntent(editPrompt, { hasReference: true })
const englishCore = await translateEditInstructionToEnglish(editPrompt, { generate: ollamaGen, model: 'qwen3:14b', timeoutMs: 30000 })
const instruction = buildKontextInstruction(editPrompt, intent, { englishCore })
log(`[3/7] prompt="${editPrompt}" -> EN="${englishCore}"`)
log('       instruction =', instruction)

// 4. /free (comme le hook avant le swap kontext)
await fetch(`${BRIDGE}/proxy/comfy/free`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ unload_models: true, free_memory: true }) }).catch(() => {})
log('[4/7] /free OK')

// 5. queue via proxy bridge
const workflow = createFluxKontextWorkflow({ instruction, referenceFilename: upName, unetName: kontextModel, filenamePrefix: `site_${tag}`, seed: 777 })
const q = await fetch(`${BRIDGE}/proxy/comfy/prompt`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt: workflow }) }).then((r) => r.json())
if (!q.prompt_id) throw new Error('pas de prompt_id: ' + JSON.stringify(q).slice(0, 300))
log('[5/7] queued', q.prompt_id)

// 6. poll history via proxy bridge
let filename = null
const started = Date.now()
while (Date.now() - started < 10 * 60 * 1000) {
  await new Promise((r) => setTimeout(r, 3000))
  const hist = await fetch(`${BRIDGE}/proxy/comfy/history/${q.prompt_id}`).then((r) => r.json()).catch(() => null)
  const payload = hist?.[q.prompt_id]
  if (payload?.status?.status_str === 'error') throw new Error('erreur ComfyUI: ' + JSON.stringify(payload.status.messages).slice(0, 400))
  for (const node of Object.values(payload?.outputs ?? {})) for (const img of node?.images ?? []) if (img?.filename) filename = img.filename
  if (filename) break
}
if (!filename) throw new Error('timeout rendu')
log(`[6/7] rendu OK in ${Math.round((Date.now() - started) / 1000)}s -> ${filename}`)

// 7. recuperation de l'image via le bridge (chemin d'affichage/telechargement du site)
const viewUrl = `${BRIDGE}/proxy/comfy/view?filename=${encodeURIComponent(filename)}&type=output`
const resp = await fetch(viewUrl)
const ct = resp.headers.get('content-type')
const buf = Buffer.from(await resp.arrayBuffer())
writeFileSync(OUT, buf)
const isPng = buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47
log(`[7/7] view ${resp.status} content-type=${ct} bytes=${buf.length} validPNG=${isPng}`)
log('SAVED', OUT)
log(JSON.stringify({ ok: resp.ok && isPng, http: resp.status, contentType: ct, bytes: buf.length, viewUrl }, null, 0))
process.exit(0)
