#!/usr/bin/env node
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { basename, dirname, extname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'
import { inflateSync } from 'node:zlib'

import { buildNegativePrompt, parseImageIntent, resolveReferenceDenoise } from '../src/utils/imagePromptParser.ts'
import { createFluxWorkflow } from '../src/utils/fluxWorkflow.ts'
import {
  assembleKontextInstruction,
  buildStagedKontextEditPlan,
  createFluxKontextWorkflow,
  resolveKontextModel,
  shouldUseStagedKontextEditPlan,
} from '../src/utils/fluxKontextWorkflow.ts'
import { looksFrench, applyEditLexicon, translateEditInstructionToEnglish } from '../src/utils/kontextInstructionTranslator.ts'
import { buildPrompt, parseBrief } from '../src/services/imagePromptBuilder.ts'
import {
  detectSubjectToResearch,
  resolveSubjectReference,
  buildAppearanceClause,
} from '../src/services/selfInformedReference.ts'

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url))
const REF_SEARCH_PY = resolve(SCRIPT_DIR, '..', 'python-services', 'reference_visual_search.py')

const DEFAULT_COMFY = process.env.COMFY_URL || 'http://127.0.0.1:8188'
const DEFAULT_OLLAMA = process.env.OLLAMA_URL || 'http://127.0.0.1:11434'

function usage() {
  console.log(`Usage:
  node --experimental-strip-types application/scripts/image_cli.mjs --prompt "un robot dans une serre" [options]
  node --experimental-strip-types application/scripts/image_cli.mjs --ref C:/photo.jpg --prompt "change la tenue en tee shirt rouge" [options]

Options:
  --prompt <text>       Prompt image ou instruction de retouche. Obligatoire.
  --ref <path>          Image de reference a modifier (BASE/destination). Si absent: creation pure.
  --ref2 <path>         Seconde image SOURCE: extrait un element (personne, objet,
                        decor, pose) de cette image et l'injecte dans --ref. Kontext requis.
  --stitch-direction <right|down|left|up>
                        Sens d'accolage des deux images pour l'injection. Defaut: right.
  --out <dir>           Dossier de sortie. Defaut: output/image-cli
  --tag <name>          Nom de fichier/prefixe ComfyUI, pas un style. Defaut: cli_<timestamp>
  --style <style>       Style creation/img2img; en Kontext, mets le style dans --prompt. Defaut: none
  --negative <text>     Negative prompt additionnel pour FLUX dev/img2img.
  --width <px>          Largeur canvas; en retouche, garde le ratio de la reference. Defaut: 1024
  --height <px>         Hauteur canvas; en retouche, garde le ratio de la reference. Defaut: 1024
  --steps <n>           Steps FLUX dev/Kontext. Defaut: 28
  --seed <n>            Seed fixe. Defaut: random
  --denoise <0..1>      Force img2img fallback si reference sans Kontext; ignore par Kontext. Defaut: auto
  --comfy <url>         URL ComfyUI. Defaut: ${DEFAULT_COMFY}
  --ollama <url>        URL Ollama pour traduction Kontext. Defaut: ${DEFAULT_OLLAMA}
  --translate-model <m> Modele Ollama traduction. Defaut: qwen3:14b
  --entity-description <text>
                      Apparence concrete du personnage/objet nomme a injecter (force, court-circuite la recherche).
  --vision-model <m>    Modele vision pour la recherche/verif de reference. Defaut: qwen3-vl:8b.
  --no-research         Desactive l'auto-information (pas de recherche web de reference).
`)
}

const BOOLEAN_FLAGS = new Set(['help', 'no-research'])

function parseArgs(argv) {
  const out = {}
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--help' || arg === '-h') {
      out.help = true
      continue
    }
    if (!arg.startsWith('--')) throw new Error(`Argument inattendu: ${arg}`)
    const key = arg.slice(2)
    if (BOOLEAN_FLAGS.has(key)) {
      out[key] = true
      continue
    }
    const next = argv[i + 1]
    if (!next || next.startsWith('--')) throw new Error(`Valeur manquante pour --${key}`)
    out[key] = next
    i += 1
  }
  return out
}

function numberOpt(value, fallback) {
  if (value === undefined) return fallback
  const n = Number(value)
  if (!Number.isFinite(n)) throw new Error(`Nombre invalide: ${value}`)
  return n
}

function contentType(path) {
  const ext = extname(path).toLowerCase()
  if (ext === '.jpg' || ext === '.jpeg') return 'image/jpeg'
  if (ext === '.webp') return 'image/webp'
  return 'image/png'
}

async function comfy(base, path, opts) {
  const r = await fetch(`${base}${path}`, opts)
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}: ${(await r.text()).slice(0, 500)}`)
  return r
}

async function queueAndWait(comfyUrl, workflow, timeoutMs = 30 * 60 * 1000) {
  const queued = await (await comfy(comfyUrl, '/prompt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: workflow }),
  })).json()
  if (!queued.prompt_id) throw new Error(`ComfyUI n'a pas retourne de prompt_id: ${JSON.stringify(queued).slice(0, 500)}`)

  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 3000))
    const history = await fetch(`${comfyUrl}/history/${queued.prompt_id}`).then((r) => r.json()).catch(() => null)
    const payload = history?.[queued.prompt_id]
    if (payload?.status?.status_str === 'error') {
      throw new Error(`ComfyUI error: ${JSON.stringify(payload.status.messages ?? []).slice(0, 1200)}`)
    }
    for (const node of Object.values(payload?.outputs ?? {})) {
      for (const image of node?.images ?? []) {
        if (image?.filename) return image.filename
      }
    }
  }
  throw new Error('Timeout ComfyUI')
}

async function uploadReference(comfyUrl, refPath) {
  const bytes = readFileSync(refPath)
  const form = new FormData()
  form.append('image', new Blob([bytes], { type: contentType(refPath) }), basename(refPath))
  form.append('overwrite', 'true')
  return comfy(comfyUrl, '/upload/image', { method: 'POST', body: form }).then((r) => r.json())
}

async function uploadBufferAsReference(comfyUrl, buffer, filename) {
  const form = new FormData()
  form.append('image', new Blob([buffer], { type: 'image/png' }), filename)
  form.append('overwrite', 'true')
  return comfy(comfyUrl, '/upload/image', { method: 'POST', body: form }).then((r) => r.json())
}

async function detectKontext(comfyUrl) {
  const info = await comfy(comfyUrl, '/object_info/UNETLoader').then((r) => r.json())
  const unets = info?.UNETLoader?.input?.required?.unet_name?.[0] ?? []
  return resolveKontextModel(Array.isArray(unets) ? unets : [])
}

async function freeComfyVram(comfyUrl) {
  await fetch(`${comfyUrl}/free`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unload_models: true, free_memory: true }),
  }).catch(() => {})
}

async function ollamaGenerate(ollamaUrl, model, p) {
  const r = await fetch(`${ollamaUrl}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, prompt: p, stream: false }),
  })
  return r.json()
}

async function unloadAllOllamaModels(ollamaUrl) {
  try {
    const ps = await fetch(`${ollamaUrl}/api/ps`).then((r) => r.json()).catch(() => null)
    if (Array.isArray(ps?.models)) {
      for (const m of ps.models) {
        const modelName = m?.name || m?.model
        if (modelName) {
          await fetch(`${ollamaUrl}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelName, messages: [], keep_alive: 0 }),
          }).catch(() => {})
          await fetch(`${ollamaUrl}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelName, prompt: '', stream: false, keep_alive: 0 }),
          }).catch(() => {})
        }
      }
    }
    await new Promise((r) => setTimeout(r, 1200))
  } catch {}
}

async function unloadOllamaModel(ollamaUrl, model) {
  await unloadAllOllamaModels(ollamaUrl)
}

function extractJsonLoose(text) {
  const m = (text || '').match(/\{[\s\S]*\}/)
  if (!m) return null
  try { return JSON.parse(m[0]) } catch { return null }
}

// Backend de recherche d'images de reference (meme script que l'UI) : DuckDuckGo
// + crawl4ai, sans cle API. Echoue silencieusement -> renvoie {ok:true,candidates:[]}.
function getPythonBin() {
  if (process.env.PYTHON) return process.env.PYTHON
  return process.platform === 'win32' ? 'python' : 'python3'
}

function runRefSearchPy(args) {
  try {
    const out = execFileSync(getPythonBin(), [REF_SEARCH_PY, ...args], {
      encoding: 'utf-8', timeout: 90000, maxBuffer: 48 * 1024 * 1024,
    })
    const line = (out || '').trim().split('\n').filter(Boolean).pop() || '{}'
    return JSON.parse(line)
  } catch {
    return null
  }
}

async function resolveOllamaTextModel(ollamaUrl, userSpecified) {
  if (userSpecified) return userSpecified
  try {
    const tags = await fetch(`${ollamaUrl}/api/tags`).then((r) => r.json())
    const names = (tags?.models || []).map((m) => m.name)
    const priority = ['qwen3.6:27b', 'qwen3:30b-a3b-instruct-2507-q4_K_M', 'qwen3:14b', 'qwen3-coder:30b', 'devstral:latest']
    for (const p of priority) {
      if (names.includes(p)) return p
    }
    if (names.length > 0) return names[0]
  } catch {}
  return 'qwen3.6:27b'
}

async function resolveOllamaVisionModel(ollamaUrl, userSpecified) {
  if (userSpecified) return userSpecified
  try {
    const tags = await fetch(`${ollamaUrl}/api/tags`).then((r) => r.json())
    const names = (tags?.models || []).map((m) => m.name)
    const priority = ['qwen3-vl:8b', 'qwen3-vl:30b']
    for (const p of priority) {
      if (names.includes(p)) return p
    }
    if (names.length > 0) return names[0]
  } catch {}
  return 'qwen3-vl:8b'
}

async function downloadRefBytes(url) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(8000) })
    if (r.ok) return Buffer.from(await r.arrayBuffer())
  } catch {}
  const res = runRefSearchPy(['--download-url', url])
  if (res?.ok && res.base64) return Buffer.from(res.base64, 'base64')
  return null
}

async function ollamaVision(ollamaUrl, model, text, base64) {
  const r = await fetch(`${ollamaUrl}/api/chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages: [{ role: 'user', content: text, images: [base64] }], stream: false, options: { temperature: 0.1 } }),
  })
  const j = await r.json()
  return j?.message?.content || ''
}

function candidateMatchesProfile(candidate, profile) {
  const searchable = `${candidate?.title || ''} ${candidate?.pageUrl || ''} ${candidate?.imageUrl || ''}`.toLowerCase()
  const identityTerms = Array.isArray(profile?.identityTerms) ? profile.identityTerms : []
  if (identityTerms.length > 0 && !identityTerms.some((term) => searchable.includes(String(term).toLowerCase()))) return false
  const requiredPageTerms = Array.isArray(profile?.requiredPageTerms) ? profile.requiredPageTerms : []
  if (requiredPageTerms.length > 0 && !requiredPageTerms.some((term) => searchable.includes(String(term).toLowerCase()))) return false
  const forbiddenPageTerms = Array.isArray(profile?.forbiddenPageTerms) ? profile.forbiddenPageTerms : []
  if (forbiddenPageTerms.some((term) => searchable.includes(String(term).toLowerCase()))) return false
  return true
}

function candidateLooksStrongTextReference(candidate, profile) {
  const searchable = `${candidate?.title || ''} ${candidate?.pageUrl || ''} ${candidate?.imageUrl || ''}`.toLowerCase()
  const imageUrl = String(candidate?.imageUrl || '').toLowerCase()
  const title = String(candidate?.title || '').toLowerCase()
  const identityTerms = Array.isArray(profile?.identityTerms) ? profile.identityTerms.map((term) => String(term).toLowerCase()) : []
  const requiredPageTerms = Array.isArray(profile?.requiredPageTerms) ? profile.requiredPageTerms.map((term) => String(term).toLowerCase()) : []
  if (!profile?.strictIdentity || identityTerms.length === 0 || requiredPageTerms.length === 0) return false
  if (!requiredPageTerms.some((term) => searchable.includes(term))) return false
  return identityTerms.some((term) => imageUrl.includes(term) || title.includes(term))
}

// Dependances Node du resolveur auto-informant — MEME logique que l'UI (recherche
// web -> verif vision "bon sujet" -> description vision -> upload ComfyUI), avec
// HTTP/python natif au lieu des hooks Tauri. Garantit la parite UI/CLI.
function makeSelfInformDeps({ comfyUrl, ollamaUrl, visionModel, textModel }) {
  // Identite = on FAIT CONFIANCE au classement de recherche (les top resultats
  // d'une requete precise "Jax The Amazing Digital Circus" SONT Jax) + au filtre
  // URL (candidateMatchesProfile exige l'identite dans l'URL/titre). On NE
  // demande PAS au modele vision "est-ce X ?" : un 8B ne connait pas un perso de
  // niche et accepterait n'importe quel personnage de la meme franchise (Pomni au
  // lieu de Jax). On garde juste un filtre vision LEGER (un seul perso net, pas un
  // collage/wallpaper/UI/photo de vraies personnes), et c'est le CONSENSUS des
  // descriptions (cote resolver) qui demote un intrus minoritaire.
  const fetchReferenceImages = async (queries, profile) => {
    const refs = []
    const seen = new Set()
    let scanned = 0
    for (const q of queries.slice(0, 3)) {
      if (refs.length >= 4 || scanned >= 12) break
      const res = runRefSearchPy(['--query', q, '--limit', '8'])
      const cands = (res?.candidates || []).filter((c) => c?.imageUrl && candidateMatchesProfile(c, profile))
      for (const c of cands.slice(0, 8)) {
        if (refs.length >= 4 || scanned >= 12) break
        const key = `${c.pageUrl || ''}::${c.imageUrl || ''}`
        if (seen.has(key)) continue
        seen.add(key)
        scanned += 1

        const buf = await downloadRefBytes(c.imageUrl)
        if (!buf || buf.length < 2048) continue
        const base64 = buf.toString('base64')
        // Filtre LEGER, identite-agnostique : on ne garde qu'une image centree sur
        // UN personnage/creature illustre ou rendu (pas un collage/wallpaper charge,
        // pas une photo de vraies personnes, pas une UI/meme/texte).
        const gate = extractJsonLoose(await ollamaVision(
          ollamaUrl, visionModel,
          'Does this image show ONE single illustrated or 3D-rendered character/creature as the clear main subject itself, occupying most of the frame? Reject photos of merchandise/products such as watches, clocks, shirts, boxes, posters or packaging where the character is merely printed on an object. Also reject busy collages, wallpapers, real humans, UI screenshots, memes, and mostly text/logo. Reply ONLY JSON {"single":true|false}.',
          base64,
        ))
        if (gate && gate.single === false) continue

        let comfyFilename = null
        try {
          const form = new FormData()
          form.append('image', new Blob([buf]), `autoref_${Date.now()}_${refs.length}.png`)
          form.append('overwrite', 'true')
          const up = await comfy(comfyUrl, '/upload/image', { method: 'POST', body: form }).then((r) => r.json())
          comfyFilename = up?.name ?? null
        } catch {}
        // score = rang de recherche (les premiers resultats sont les plus pertinents)
        refs.push({ comfyFilename, blob: new Blob([buf]), base64, sourceUrl: c.imageUrl, score: 100 - refs.length })
        console.error(`[research] ref+ ${(c.imageUrl || '').slice(0, 90)}`)
      }
    }
    return refs
  }

  return {
    textModel,
    generate: (model, p) => ollamaGenerate(ollamaUrl, model, p),
    fetchReferenceImages,
    fetchReferenceImage: async (queries, profile) => (await fetchReferenceImages(queries, profile))[0] ?? null,
    describeReferenceImage: async (ref, target) => {
      if (!ref?.base64) return ''
      return ollamaVision(
        ollamaUrl, visionModel,
        `Describe the EXACT visual appearance of "${target.searchLabel || target.subject}" for an image editor: ${target.role === 'become_scene'
          ? 'layout, dominant colors, ground/sky, signature structures and props of this exact place/environment'
          : 'species/type, exact colors, face/eyes, outfit, accessories, distinctive marks'}. One dense English line, max 45 words. Appearance ONLY, no preamble, no quotes.`,
        ref.base64,
      )
    },
  }
}

function paethPredictor(a, b, c) {
  const p = a + b - c
  const pa = Math.abs(p - a)
  const pb = Math.abs(p - b)
  const pc = Math.abs(p - c)
  if (pa <= pb && pa <= pc) return a
  if (pb <= pc) return b
  return c
}

function pngLooksBlack(buffer) {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
  if (buffer.length < 33 || !buffer.subarray(0, 8).equals(sig)) return false

  let offset = 8
  let width = 0
  let height = 0
  let bitDepth = 0
  let colorType = 0
  const idat = []
  while (offset + 12 <= buffer.length) {
    const length = buffer.readUInt32BE(offset)
    const type = buffer.toString('ascii', offset + 4, offset + 8)
    const start = offset + 8
    const end = start + length
    if (end + 4 > buffer.length) return false
    if (type === 'IHDR') {
      width = buffer.readUInt32BE(start)
      height = buffer.readUInt32BE(start + 4)
      bitDepth = buffer[start + 8]
      colorType = buffer[start + 9]
    } else if (type === 'IDAT') {
      idat.push(buffer.subarray(start, end))
    } else if (type === 'IEND') {
      break
    }
    offset = end + 4
  }

  if (!width || !height || bitDepth !== 8 || idat.length === 0) return false
  const channels = colorType === 6 ? 4 : colorType === 2 ? 3 : colorType === 0 ? 1 : 0
  if (!channels) return false

  let raw
  try {
    raw = inflateSync(Buffer.concat(idat))
  } catch {
    return false
  }

  const stride = width * channels
  const bpp = channels
  let inOffset = 0
  let previous = Buffer.alloc(stride)
  let count = 0
  let sumLuma = 0
  let maxRgb = 0

  for (let y = 0; y < height; y += 1) {
    if (inOffset >= raw.length) return false
    const filter = raw[inOffset]
    inOffset += 1
    if (inOffset + stride > raw.length) return false
    const row = Buffer.from(raw.subarray(inOffset, inOffset + stride))
    inOffset += stride

    for (let x = 0; x < stride; x += 1) {
      const left = x >= bpp ? row[x - bpp] : 0
      const up = previous[x]
      const upLeft = x >= bpp ? previous[x - bpp] : 0
      if (filter === 1) row[x] = (row[x] + left) & 255
      else if (filter === 2) row[x] = (row[x] + up) & 255
      else if (filter === 3) row[x] = (row[x] + Math.floor((left + up) / 2)) & 255
      else if (filter === 4) row[x] = (row[x] + paethPredictor(left, up, upLeft)) & 255
      else if (filter !== 0) return false
    }

    for (let x = 0; x < stride; x += channels) {
      let r
      let g
      let b
      let a = 255
      if (channels === 1) {
        r = g = b = row[x]
      } else {
        r = row[x]
        g = row[x + 1]
        b = row[x + 2]
        if (channels === 4) a = row[x + 3]
      }
      if (a < 4) continue
      count += 1
      sumLuma += 0.2126 * r + 0.7152 * g + 0.0722 * b
      maxRgb = Math.max(maxRgb, r, g, b)
    }
    previous = row
  }

  if (count === 0) return false
  return sumLuma / count < 2 && maxRgb < 8
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  if (args.help) return usage()
  const prompt = String(args.prompt || '').trim()
  if (!prompt) {
    usage()
    throw new Error('--prompt est obligatoire')
  }

  const comfyUrl = args.comfy || DEFAULT_COMFY
  const ollamaUrl = args.ollama || DEFAULT_OLLAMA
  const outDir = resolve(args.out || (process.cwd().endsWith('application') ? join('output', 'image', 'cli') : join('application', 'output', 'image', 'cli')))
  const width = numberOpt(args.width, 1024)
  const height = numberOpt(args.height, 1024)
  const steps = numberOpt(args.steps, 28)
  const seed = args.seed === undefined ? null : numberOpt(args.seed, null)
  const style = args.style || 'none'
  const negative = args.negative || ''
  const refPath = args.ref ? resolve(args.ref) : null
  const ref2Path = args.ref2 ? resolve(args.ref2) : null
  const stitchDirection = args['stitch-direction'] || 'right'
  if (!['right', 'down', 'left', 'up'].includes(stitchDirection)) {
    throw new Error(`--stitch-direction invalide: ${stitchDirection} (right|down|left|up)`)
  }
  if (ref2Path && !refPath) throw new Error('--ref2 (source) requiert --ref (image de base/destination)')
  const refDenoise = args.denoise === undefined ? 0.7 : numberOpt(args.denoise, 0.7)

  mkdirSync(outDir, { recursive: true })
  await comfy(comfyUrl, '/system_stats').catch(() => {
    throw new Error(`ComfyUI indisponible sur ${comfyUrl}`)
  })

  const intent = parseImageIntent(prompt, { hasReference: Boolean(refPath) })
  const modeSlug = (intent?.editMode || 'creation').toLowerCase().replace(/[^a-z0-9]+/g, '_')
  const promptSlug = prompt
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 32) || 'image'
  const tag = (args.tag || `${modeSlug}_${promptSlug}_${Date.now()}`).replace(/[^a-z0-9_.-]+/gi, '_')
  let workflow
  let stagedReplacementPlan = null
  let stagedReferenceFilename = null
  let stagedKontextModel = null
  let engine = 'flux-dev'
  let entityTarget = null
  let entityDescription = ''
  let entityReferenceCount = 0
  let helperModelUsed = ''
  let visionModelUsed = ''
  let entityClause = ''
  const targetToResearch = detectSubjectToResearch(prompt, intent)

  if (refPath) {
    const upload = await uploadReference(comfyUrl, refPath)
    const referenceFilename = upload.name
    const wantsKontext = intent.isEditIntent || Boolean(ref2Path)
    const kontextModel = wantsKontext ? await detectKontext(comfyUrl).catch(() => null) : null

    if (kontextModel && wantsKontext) {
      const helperModel = await resolveOllamaTextModel(ollamaUrl, args['translate-model'] || process.env.TRANSLATE_MODEL)
      const visionModel = await resolveOllamaVisionModel(ollamaUrl, args['vision-model'] || process.env.VISION_MODEL)
      helperModelUsed = helperModel

      // Libere la VRAM ComfyUI avant les passes Ollama (traduction + vision) pour
      // ne pas faire cohabiter FLUX + LLM/vision sur une carte 16 Go.
      await freeComfyVram(comfyUrl)

      // 1) Traduction FR->EN de l'instruction.
      let englishCore
      try {
        englishCore = await translateEditInstructionToEnglish(prompt, {
          model: helperModel,
          timeoutMs: 30000,
          generate: (model, p) => ollamaGenerate(ollamaUrl, model, p),
        })
      } catch {
        englishCore = undefined
      }

      // 2) AUTO-INFORMATION : pour un sujet specifique (personnage/objet nomme a
      // ajouter, ou environnement/lieu nomme), Aurora recherche une VRAIE reference
      // (image verifiee bon-sujet par vision + description vision precise) au lieu
      // d'inventer. L'image trouvee d'un sujet a AJOUTER sert de 2e reference Kontext.
      let autoSecondReference = null
      const forced = String(args['entity-description'] || '').trim()
      const target = targetToResearch
      if (target && forced) {
        entityClause = buildAppearanceClause(target, forced)
        entityTarget = target.subject
        entityDescription = forced
        entityReferenceCount = 0
      } else if (target && !args['no-research']) {
        const resolved = await resolveSubjectReference(target, {
          ...makeSelfInformDeps({ comfyUrl, ollamaUrl, visionModel, textModel: helperModel }),
          onProgress: (m) => console.error(`[research] ${m}`),
        })
        if (resolved.appearanceDescription) entityClause = buildAppearanceClause(target, resolved.appearanceDescription)
        // NB: on n'AUTO-stitch PAS l'image trouvee (un sujet isole sur fond neutre
        // fait "collapser" Kontext, qui recrache la reference au lieu d'editer la
        // base). La description consensus, tres precise, suffit en mono-image et
        // PRESERVE la scene de base. Le stitch reste reserve a --ref2 (explicite).
        void autoSecondReference
        if (resolved.advisory) console.error(`warning: ${resolved.advisory}`)
        entityTarget = resolved.subject
        entityDescription = resolved.appearanceDescription
        entityReferenceCount = resolved.referenceComfyFilename ? 1 : 0
        visionModelUsed = visionModel
      }

      // 3) Reference manuelle (--ref2) OU image auto-recherchee du sujet a ajouter.
      let secondReferenceFilename = null
      if (ref2Path) {
        const upload2 = await uploadReference(comfyUrl, ref2Path)
        secondReferenceFilename = upload2.name
      } else if (autoSecondReference) {
        secondReferenceFilename = autoSecondReference
      }
      const injection = Boolean(secondReferenceFilename)
      engine = injection ? 'kontext-inject' : 'kontext'
      stagedReferenceFilename = referenceFilename
      stagedKontextModel = kontextModel

      if (shouldUseStagedKontextEditPlan(intent, { rawPrompt: prompt, injection })) {
        let removeEnglishCore
        let addEnglishCore
        try {
          removeEnglishCore = await translateEditInstructionToEnglish(`suppression complete de ${intent.removals.join(' et ')}`, {
            model: helperModel,
            timeoutMs: 30000,
            generate: (model, p) => ollamaGenerate(ollamaUrl, model, p),
          })
        } catch {
          removeEnglishCore = undefined
        }
        try {
          addEnglishCore = await translateEditInstructionToEnglish(`ajoute ${intent.additions.join(' et ')}`, {
            model: helperModel,
            timeoutMs: 30000,
            generate: (model, p) => ollamaGenerate(ollamaUrl, model, p),
          })
        } catch {
          addEnglishCore = undefined
        }
        stagedReplacementPlan = buildStagedKontextEditPlan({
          rawPrompt: prompt,
          intent,
          englishCore,
          removeEnglishCore,
          addEnglishCore,
          entityClause,
        })
        engine = 'kontext-staged'
      }

      // Source UNIQUE de l'instruction Kontext (identique a l'UI useImageViewLogic) :
      // coeur traduit + apparence, AUCUN contrat d'orchestrateur (qui deviendrait
      // du guidage positif faute de canal negatif dans le graphe Kontext).
      workflow = stagedReplacementPlan ? null : createFluxKontextWorkflow({
        instruction: assembleKontextInstruction({
          rawPrompt: prompt,
          intent,
          englishCore,
          entityClause,
          injection,
        }),
        referenceFilename,
        secondReferenceFilename,
        stitchDirection,
        unetName: kontextModel,
        filenamePrefix: tag,
        seed,
        steps,
        width,
        height,
      })
    } else {
      const englishPrompt = looksFrench(intent.cleanedPrompt) ? applyEditLexicon(intent.cleanedPrompt) : intent.cleanedPrompt
      const denoise = refDenoise ?? (intent.isEditIntent ? resolveReferenceDenoise(intent, 0.58, style) : 0.58)
      workflow = createFluxWorkflow({
        prompt: [englishPrompt || intent.cleanedPrompt, entityClause].filter(Boolean).join('\n\n'),
        negativePrompt: buildNegativePrompt(negative, intent.removals),
        style,
        width,
        height,
        steps,
        filenamePrefix: tag,
        seed,
        referenceImage: { filename: referenceFilename, denoise },
        editIntent: intent,
      })
    }
  } else {
    const forced = String(args['entity-description'] || '').trim()
    if (targetToResearch && forced) {
      entityClause = buildAppearanceClause(targetToResearch, forced)
      entityTarget = targetToResearch.subject
      entityDescription = forced
      entityReferenceCount = 0
    } else if (targetToResearch && !args['no-research']) {
      const helperModel = await resolveOllamaTextModel(ollamaUrl, args['translate-model'] || process.env.TRANSLATE_MODEL)
      const visionModel = await resolveOllamaVisionModel(ollamaUrl, args['vision-model'] || process.env.VISION_MODEL)
      helperModelUsed = helperModel
      visionModelUsed = visionModel
      await freeComfyVram(comfyUrl)
      const resolved = await resolveSubjectReference(targetToResearch, {
        ...makeSelfInformDeps({ comfyUrl, ollamaUrl, visionModel, textModel: helperModel }),
        onProgress: (m) => console.error(`[research] ${m}`),
      })
      if (resolved.appearanceDescription) entityClause = buildAppearanceClause(targetToResearch, resolved.appearanceDescription)
      if (resolved.advisory) console.error(`warning: ${resolved.advisory}`)
      entityTarget = resolved.subject
      entityDescription = resolved.appearanceDescription
      entityReferenceCount = resolved.referenceCount
    }

    const englishPrompt = looksFrench(intent.cleanedPrompt) ? applyEditLexicon(intent.cleanedPrompt) : intent.cleanedPrompt

    const brief = parseBrief(englishPrompt || intent.cleanedPrompt)
    const builtPrompt = buildPrompt({
      ...brief,
      subject: englishPrompt || intent.cleanedPrompt,
      context: entityClause || brief.context,
      negativeHints: [negative, ...intent.removals].filter(Boolean),
    })

    workflow = createFluxWorkflow({
      prompt: [builtPrompt.positive, entityClause].filter(Boolean).join('\n\n'),
      negativePrompt: builtPrompt.negative,
      style,
      width,
      height,
      steps,
      filenamePrefix: tag,
      seed,
      editIntent: intent,
    })
  }

  if (helperModelUsed) await unloadOllamaModel(ollamaUrl, helperModelUsed)
  if (visionModelUsed) await unloadOllamaModel(ollamaUrl, visionModelUsed)
  await freeComfyVram(comfyUrl)

  console.log(JSON.stringify({
    prompt,
    mode: intent.editMode,
    engine,
    stages: stagedReplacementPlan ? stagedReplacementPlan.stages.map((stage) => stage.id) : undefined,
    style,
    ref: refPath,
    ref2: ref2Path || undefined,
    stitchDirection: ref2Path ? stitchDirection : undefined,
    seed,
    entity: entityTarget,
    entityDescription: entityDescription || undefined,
    entityReferenceCount: entityReferenceCount || undefined,
    helperModel: helperModelUsed || undefined,
    visionModel: visionModelUsed || undefined,
  }, null, 2))

  await unloadAllOllamaModels(ollamaUrl)
  await freeComfyVram(comfyUrl)
  await new Promise((r) => setTimeout(r, 2500))
  await freeComfyVram(comfyUrl)

  try {
    let imageBuffer
    if (stagedReplacementPlan) {
      let activeReferenceFilename = stagedReferenceFilename
      if (!activeReferenceFilename) throw new Error('Reference de depart manquante pour le workflow multi-etage')
      if (!stagedKontextModel) throw new Error('Modele Kontext introuvable pour le workflow multi-etage')
      for (let i = 0; i < stagedReplacementPlan.stages.length; i += 1) {
        const stage = stagedReplacementPlan.stages[i]
        console.error(`[kontext-staged] ${stage.progressLabel}`)
        const stageWorkflow = createFluxKontextWorkflow({
          instruction: stage.instruction,
          referenceFilename: activeReferenceFilename,
          secondReferenceFilename: null,
          stitchDirection,
          unetName: stagedKontextModel,
          filenamePrefix: `${tag}_stage${i + 1}`,
          seed: seed === null ? null : seed + i,
          steps,
          width,
          height,
        })
        const filename = await queueAndWait(comfyUrl, stageWorkflow)
        imageBuffer = Buffer.from(await fetch(`${comfyUrl}/view?filename=${encodeURIComponent(filename)}&type=output`).then((r) => r.arrayBuffer()))
        if (pngLooksBlack(imageBuffer)) {
          throw new Error(`Rendu noir detecte pendant la passe multi-etage ${i + 1}`)
        }
        if (i < stagedReplacementPlan.stages.length - 1) {
          const upload = await uploadBufferAsReference(comfyUrl, imageBuffer, `${tag}_stage${i + 1}.png`)
          activeReferenceFilename = upload.name
        }
      }
    } else {
      const filename = await queueAndWait(comfyUrl, workflow)
      imageBuffer = Buffer.from(await fetch(`${comfyUrl}/view?filename=${encodeURIComponent(filename)}&type=output`).then((r) => r.arrayBuffer()))
    }
    if (!imageBuffer) throw new Error('Aucune image produite par ComfyUI')
    const targetSubdir = join(outDir, tag)
    mkdirSync(targetSubdir, { recursive: true })
    const destImage = join(targetSubdir, 'image.png')
    const destPrompt = join(targetSubdir, 'prompt.txt')
    const destMeta = join(targetSubdir, 'metadata.json')

    writeFileSync(destImage, imageBuffer)
    
    const promptTextContent = [
      `PROMPT: ${prompt}`,
      `INTENTION: ${intent.editMode}`,
      `STYLE: ${style}`,
      `STEPS: ${steps}`,
      `SEED: ${seed}`,
      `ENGINE: ${engine}`,
      `REFERENCE_BASE: ${refPath || 'aucune'}`,
      `REFERENCE_SOURCE: ${ref2Path || 'aucune'}`,
      `ENTITE_DETECTEE: ${entityTarget || 'aucune'}`,
      `DESCRIPTION_ENTITE: ${entityDescription || 'aucune'}`,
      `DATE: ${new Date().toISOString()}`,
    ].join('\n')
    writeFileSync(destPrompt, promptTextContent)

    const metaContent = {
      prompt,
      mode: intent.editMode,
      engine,
      style,
      steps,
      seed,
      ref: refPath,
      ref2: ref2Path || undefined,
      entity: entityTarget,
      entityDescription: entityDescription || undefined,
      timestamp: new Date().toISOString(),
    }
    writeFileSync(destMeta, JSON.stringify(metaContent, null, 2))

    console.log(`saved ${destImage}`)
    console.log(`saved ${destPrompt}`)
  } finally {
    await freeComfyVram(comfyUrl)
    if (helperModelUsed) await unloadOllamaModel(ollamaUrl, helperModelUsed)
    if (visionModelUsed) await unloadOllamaModel(ollamaUrl, visionModelUsed)
  }
}

main().catch((err) => {
  console.error(err?.message || err)
  process.exit(1)
})
