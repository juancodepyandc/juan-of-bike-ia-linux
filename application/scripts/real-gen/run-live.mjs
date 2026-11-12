#!/usr/bin/env node
// Pilote l'écran de génération d'Aurora avec de VRAIES générations faites à partir
// de demandes (real_reference_views.py) et mesure sur ces runs réels :
//  - la latence entre l'événement réel du générateur et son affichage ;
//  - l'accord de l'hologramme avec les vues réellement générées (IoU face/profil) ;
//  - la justesse du temps d'attente affiché (prédiction lue à l'écran chaque seconde,
//    comparée au temps qui restait vraiment), l'historique venant des runs réels
//    précédents de la même session.
// Producteur (AURORA_REAL_GEN_BACKEND) :
//   comfy-flux2  (défaut) le producteur réel du module 3D : FLUX.2-dev via ComfyUI
//                (flux_reference_synth.synth_multiview : 4 vues, audit, essais) ;
//                à lancer sur le PC où ComfyUI et les poids FLUX.2 sont installés.
//   sd-turbo     remplaçant CPU pour une machine sans GPU ni poids FLUX.2 (conteneur de
//                développement) : de vraies images depuis la demande, pas le modèle d'Aurora.
//   AURORA_COMFY_BASE=http://127.0.0.1:8188   (comfy-flux2)
//   AURORA_REAL_GEN_STEPS / AURORA_REAL_GEN_SIZE (défauts du producteur sinon)
//   AURORA_REAL_GEN_PYTHON=/chemin/python   (torch + diffusers pour sd-turbo ; Pillow pour comfy-flux2)
//   AURORA_CHROMIUM=/chemin/chrome          (si la révision Playwright n'est pas installée)
//   AURORA_REAL_GEN_OUT=/dossier            (preuves JSON et captures)
//   AURORA_REAL_GEN_REQUESTS="demande 1|demande 2|…"
//   AURORA_REAL_GEN_SHOTS=all capture l'hologramme de chaque demande (sinon la dernière)
//   AURORA_REAL_GEN_REUSE=1   réévalue seulement l'hologramme sur les vues déjà générées
//                             (real-generation-evidence.json du dossier de sortie), avec le code actuel
//   ComfyUI doit être libre pendant la mesure : ses messages de progression sont diffusés à tous.
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { chromium } from 'playwright'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..', '..')
const python = process.env.AURORA_REAL_GEN_PYTHON || 'python3'
const backend = process.env.AURORA_REAL_GEN_BACKEND === 'sd-turbo' ? 'sd-turbo' : 'comfy-flux2'
const comfyBase = process.env.AURORA_COMFY_BASE || 'http://127.0.0.1:8188'
const out = path.resolve(process.env.AURORA_REAL_GEN_OUT || path.join(root, 'output', 'real-gen'))
fs.mkdirSync(out, { recursive: true })
// « demande::type » : le type de sujet (character, creature, product…) est transmis au producteur
// FLUX.2 (audit et essais propres aux personnages) et à l'hologramme (règles de profil des personnages)
const parseRequest = (raw) => {
  const [text, kind] = raw.split('::').map((x) => x.trim())
  return { text, kind: kind || null }
}
const requests = (process.env.AURORA_REAL_GEN_REQUESTS || '').split('|').map((s) => s.trim()).filter(Boolean).map(parseRequest)
if (!requests.length) {
  requests.push(...[
    'un robot jouet jaune et bleu::character',
    'une chaise en bois de style scandinave::product',
    'un dragon vert stylisé::creature',
    'une lampe de bureau articulée rouge::product',
    'un astronaute en combinaison blanche::character',
    'une théière en céramique bleue::product',
    'un casque de moto noir et orange::product',
  ].map(parseRequest))
}

/** Durée lue dans le libellé affiché (formatWait), en secondes. */
function parseWait(text) {
  if (!text) return null
  if (/quelques secondes/.test(text)) return 5
  let m = text.match(/(\d+) h (\d+)/)
  if (m) return Number(m[1]) * 3600 + Number(m[2]) * 60
  m = text.match(/(\d+) h\b/)
  if (m) return Number(m[1]) * 3600
  m = text.match(/(\d+) min (\d+) s/)
  if (m) return Number(m[1]) * 60 + Number(m[2])
  m = text.match(/(\d+) min/)
  if (m) return Number(m[1]) * 60
  m = text.match(/(\d+) s/)
  if (m) return Number(m[1])
  return null
}

function prediction(eta, basis) {
  const head = (eta || '').split(' · ').slice(1).join(' · ')
  const approx = head.match(/≈\s*([^(]+)/)
  const lower = head.match(/≥\s*([^(]+)/)
  const interval = (basis || '').match(/intervalle (.+?) – (.+?) ·/)
  return {
    head,
    kind: approx ? 'approx' : lower ? 'lower' : 'none',
    seconds: approx ? parseWait(approx[1]) : lower ? parseWait(lower[1]) : null,
    low: interval ? parseWait(interval[1]) : null,
    high: interval ? parseWait(interval[2]) : null,
  }
}

const quantile = (values, q) => {
  const s = values.filter(Number.isFinite).sort((a, b) => a - b)
  return s.length ? s[Math.min(s.length - 1, Math.floor(q * (s.length - 1)))] : null
}

// Serveur de banc sans websocket HMR : le client Vite recharge la page quand sa connexion tombe
// (observé ici sous forte charge CPU), ce qui effaçait la session FX et l'historique en cours de
// mesure. La surveillance des fichiers est neutralisée par `ignored` (Vite ignore `watch: null`
// à la fusion avec vite.config.ts).
const server = await createServer({
  root,
  configFile: path.join(root, 'vite.config.ts'),
  server: { host: '127.0.0.1', port: 0, ws: false, watch: { ignored: ['**/*'] } },
  logLevel: 'warn',
})
await server.listen()
const base = new URL('scripts/fx-harness/index.html?mode=live', server.resolvedUrls.local[0]).href
const browser = await chromium.launch({
  executablePath: process.env.AURORA_CHROMIUM || undefined,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
})
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const pageErrors = []
const navigations = []
let loaded = false
page.on('pageerror', (e) => pageErrors.push(String(e)))
page.on('framenavigated', (frame) => {
  if (frame !== page.mainFrame() || !loaded) return
  navigations.push({ t: Date.now(), url: frame.url() })
  console.error(`[banc] navigation inattendue de la page à ${new Date().toISOString()}`)
})
await page.goto(base, { waitUntil: 'load' })
await page.waitForFunction(() => window.__liveReady === true, null, { timeout: 60000 })
loaded = true
const fx = (patch) => page.evaluate((p) => window.__fx(p), patch)
const dataUrl = (file) => 'data:image/png;base64,' + fs.readFileSync(file).toString('base64')

/** Accord hologramme / vues générées pour chaque run, puis capture de l'hologramme du dernier. */
async function evaluateHolograms(list) {
  const holo = []
  for (const r of list) {
    const pick = (role) => r.refs.find((x) => x.role === role)?.url
    const urls = [pick('face'), pick('droite') ?? pick('gauche'), pick('dos')]
    holo.push({ id: r.id, kind: r.kind ?? null, ...(await page.evaluate(([f, s, b, k]) => window.__holoCheck(f, s, b, k), [...urls, r.kind ?? null])) })
  }
  // capture de l'hologramme de chaque demande (AURORA_REAL_GEN_SHOTS=all) ou de la dernière
  const shots = process.env.AURORA_REAL_GEN_SHOTS === 'all' ? list : list.slice(-1)
  let holoNote = null
  for (const r of shots) {
    await fx({ active: true, phaseIndex: 2, phase: `Sculpture 3D — hologramme reconstruit depuis les vues générées (${r.id})`, refs: r.refs.map(({ url, role }) => ({ url, role })), subjectKind: r.kind ?? undefined })
    // capture déterministe : attendre la note de reconstruction (ou de refus), puis la fin de la convergence du nuage
    const noteLocator = page.locator('text=/Reconstruit depuis|Relief reconstruit|sujet non séparable/').first()
    await noteLocator.waitFor({ timeout: 20000 }).catch(() => {})
    await page.waitForTimeout(3500)
    const note = await noteLocator.textContent().catch(() => null)
    const entry = holo.find((h) => h.id === r.id)
    if (entry) entry.screenNote = note
    holoNote = note
    await page.screenshot({ path: path.join(out, r === list[list.length - 1] ? 'live-hologram.png' : `hologram-${r.id}.png`) })
    await fx({ active: false })
    await page.waitForTimeout(3200)
  }
  return { holo, holoNote }
}

if (process.env.AURORA_REAL_GEN_REUSE === '1') {
  const file = path.join(out, 'real-generation-evidence.json')
  const evidence = JSON.parse(fs.readFileSync(file, 'utf8'))
  const list = evidence.runs.map((r) => ({
    id: r.id,
    kind: r.kind ?? null,
    refs: r.refs.map((ref) => typeof ref === 'string'
      ? { role: ref.replace(/^.*_(face|droite|gauche|dos)\.png$/, '$1'), url: dataUrl(path.join(out, ref)) }
      : { role: ref.role, url: dataUrl(path.join(out, ref.file)) }),
  }))
  const { holo, holoNote } = await evaluateHolograms(list)
  evidence.hologram = holo
  evidence.hologramNote = holoNote
  evidence.hologramEvaluatedAt = new Date().toISOString()
  evidence.pageErrors = [...(evidence.pageErrors ?? []), ...pageErrors]
  fs.writeFileSync(file, JSON.stringify(evidence, null, 2))
  console.log(JSON.stringify(holo, null, 2))
  await browser.close()
  await server.close()
  process.exit(0)
}

const genArgs = [path.join(here, 'real_reference_views.py'), '--backend', backend, '--output-dir', out, '--comfy-base', comfyBase]
if (process.env.AURORA_REAL_GEN_STEPS) genArgs.push('--steps', process.env.AURORA_REAL_GEN_STEPS)
if (process.env.AURORA_REAL_GEN_SIZE) genArgs.push('--size', process.env.AURORA_REAL_GEN_SIZE)
const gen = spawn(python, genArgs, { stdio: ['pipe', 'pipe', 'inherit'] })
let backendInfo = null
const queue = []
let wake = null
readline.createInterface({ input: gen.stdout }).on('line', (line) => {
  try {
    queue.push(JSON.parse(line))
    wake?.()
  } catch { /* ligne de bibliothèque non JSON */ }
})
gen.on('exit', (code) => { queue.push({ ev: 'exit', code }); wake?.() })
const next = async () => {
  while (!queue.length) await new Promise((r) => { wake = r })
  wake = null
  return queue.shift()
}

const runs = []
const failed = []
try {
  for (let i = 0; i < requests.length; i++) {
    const id = `run${i + 1}`
    const { text: request, kind } = requests[i]
    gen.stdin.write(JSON.stringify({ id, request, seed: 11 + i, subject_kind: kind }) + '\n')
    const samples = []
    const latencies = []
    const refs = []
    let sampler = null
    let fraction = 0
    let attempts = 1
    const sample = async () => {
      const eta = await page.locator('[data-testid=fx-eta]').textContent({ timeout: 300 }).catch(() => null)
      const basis = await page.locator('[data-testid=fx-eta-basis]').textContent({ timeout: 300 }).catch(() => null)
      const phase = await page.locator('[data-testid=fx-phase]').textContent({ timeout: 300 }).catch(() => null)
      if (eta) samples.push({ t: Date.now(), eta, basis, phase })
    }
    for (;;) {
      const ev = await next()
      if (ev.ev === 'exit') throw new Error(`générateur arrêté (code ${ev.code})`)
      if (ev.ev === 'error') throw new Error(`producteur indisponible : ${ev.message}`)
      if (ev.ev === 'backend_ready') {
        backendInfo = ev
        continue
      }
      if (ev.ev === 'start') {
        await fx({ active: true, phaseIndex: 0, phase: `Analyse de la demande « ${request} »`, logLine: `demande reçue : ${request}` })
        sampler = setInterval(() => { void sample() }, 1000)
      } else if (ev.ev === 'model_load_start') {
        await fx({ active: true, logLine: `chargement du modèle ${ev.model}` })
      } else if (ev.ev === 'model_loaded') {
        await fx({ active: true, logLine: 'modèle de diffusion chargé' })
      } else if (ev.ev === 'attempt') {
        attempts = ev.attempt
        await fx({ active: true, phaseIndex: 1, logLine: `audit de turnaround refusé : nouvel essai ${ev.attempt}` })
      } else if (ev.ev === 'view_start') {
        await fx({ active: true, phaseIndex: 1, phase: `Référence photo — vue ${ev.view} (${ev.index + 1}/${ev.total})${attempts > 1 ? ` · essai ${attempts}` : ''}`, logLine: `génération de la vue ${ev.view}` })
      } else if (ev.ev === 'step') {
        // un nouvel essai ne fait pas reculer l'écran : la fraction reste monotone
        fraction = Math.max(fraction, (ev.index + ev.step / ev.steps) / ev.total)
        await fx({ active: true, phaseIndex: 1, phaseFraction: fraction, logLine: ev.step === ev.steps ? `vue ${ev.view} : ${ev.steps} pas de diffusion calculés` : undefined })
      } else if (ev.ev === 'view_failed') {
        await fx({ active: true, logLine: `vue ${ev.view} en échec : ${ev.error}` })
      } else if (ev.ev === 'view_done') {
        const ref = { url: dataUrl(ev.path), role: ev.view, path: ev.path }
        const at = refs.findIndex((x) => x.role === ev.view)
        if (at >= 0) refs[at] = ref
        else refs.push(ref)
        await fx({ active: true, phaseIndex: 1, refs: refs.map(({ url, role }) => ({ url, role })), subjectKind: kind ?? undefined, logLine: `vue ${ev.view} prête en ${ev.seconds} s` })
        await page.waitForFunction((n) => document.querySelectorAll('img[alt="face"], img[alt="droite"], img[alt="gauche"], img[alt="dos"]').length >= n, refs.length, { timeout: 10000 }).catch(() => {})
        latencies.push(Date.now() - ev.t * 1000)
        if (i === requests.length - 1 && ev.view === 'droite') await page.screenshot({ path: path.join(out, 'live-during-run.png') })
      } else if (ev.ev === 'done') {
        clearInterval(sampler)
        await sample()
        const tEnd = ev.t * 1000
        await fx({ active: false, outcome: ev.ok === false ? 'error' : 'success' })
        if (ev.ok === false) {
          // refus d'audit ou vue manquante : run réel mais sans livraison, exclu de la justesse
          failed.push({ id, request: request, seconds: ev.seconds, attempts: ev.attempts, error: ev.error, audit: ev.audit_failures })
          console.log(`${id} « ${request} » : refusé après ${ev.seconds} s (${ev.error})`)
          break
        }
        if (ev.websocket && (ev.websocket.reconnects > 0 || ev.websocket.last_error)) {
          console.error(`[banc] ${id} : websocket ComfyUI interrompu ${ev.websocket.reconnects} fois (${ev.websocket.last_error ?? 'sans message'}) — pas de diffusion partiellement absents`)
        }
        runs.push({
          id,
          request,
          kind,
          seconds: ev.seconds,
          websocket: ev.websocket ?? null,
          views: ev.views.map((v) => ({ role: v.role, seconds: v.seconds })),
          attempts: ev.attempts ?? 1,
          auditFailures: ev.audit_failures ?? [],
          samples: samples.map((s) => ({ ...s, actualRemaining: Math.max(0, (tEnd - s.t) / 1000), ...prediction(s.eta, s.basis) })),
          latencies,
          refs,
        })
        console.log(`${id} « ${request} » : ${ev.seconds} s réelles (vues ${ev.views.map((v) => `${v.role} ${v.seconds} s`).join(', ')})`)
        break
      }
    }
    // laisse finir la révélation (REVEAL_MS 2600) avant la demande suivante
    await page.waitForTimeout(3200)
  }

  if (!runs.length) throw new Error(`aucun run livré (${failed.length} refusé(s))`)
  // Accord hologramme / vues générées pour chaque run, capture de l'hologramme de la dernière demande
  const { holo, holoNote } = await evaluateHolograms(runs)

  const accuracy = await page.evaluate(() => window.__accuracy())
  // Justesse lue à l'écran, sur les runs qui disposaient déjà d'un historique réel (≥ 3 runs)
  const measured = runs.slice(3).flatMap((r) => r.samples.filter((s) => s.kind === 'approx' && s.seconds != null && s.actualRemaining >= 2))
  const errors = measured.map((s) => Math.abs(s.seconds - s.actualRemaining) / Math.max(s.actualRemaining, 10))
  const absErr = measured.map((s) => Math.abs(s.seconds - s.actualRemaining))
  const withInterval = measured.filter((s) => s.low != null && s.high != null)
  const covered = withInterval.filter((s) => s.actualRemaining >= s.low - 1 && s.actualRemaining <= s.high + 1)
  const evidence = {
    generator: backend === 'comfy-flux2'
      ? `FLUX.2-dev via ComfyUI (${backendInfo?.unet ?? '?'}, producteur flux_reference_synth du module 3D), vues face/dos/gauche/droite`
      : 'SD-Turbo (stabilityai/sd-turbo), CPU, 4 pas, 512 px, vues face/droite/dos — remplaçant sans GPU, pas le modèle d’Aurora',
    backend: backendInfo,
    failedRuns: failed,
    date: new Date().toISOString(),
    runs: runs.map(({ refs, samples, ...r }) => ({
      ...r,
      refs: refs.map((x) => ({ role: x.role, file: path.basename(x.path) })),
      etaSamples: samples.map((s) => ({ t: s.t, phase: s.phase, shown: s.head, predicted: s.seconds, kind: s.kind, low: s.low, high: s.high, actualRemaining: Math.round(s.actualRemaining * 10) / 10 })),
    })),
    syncLatencyMs: { p50: quantile(runs.flatMap((r) => r.latencies), 0.5), p90: quantile(runs.flatMap((r) => r.latencies), 0.9) },
    hologram: holo,
    hologramNote: holoNote,
    etaOnScreen: {
      runsWithHistory: Math.max(0, runs.length - 3),
      predictions: measured.length,
      medianRelativeError: quantile(errors, 0.5),
      p90RelativeError: quantile(errors, 0.9),
      medianAbsoluteErrorSeconds: quantile(absErr, 0.5),
      intervalCoverage: withInterval.length ? covered.length / withInterval.length : null,
    },
    calibrationInApp: accuracy,
    pageErrors,
    navigations,
  }
  fs.writeFileSync(path.join(out, 'real-generation-evidence.json'), JSON.stringify(evidence, null, 2))
  console.log(JSON.stringify({ syncLatencyMs: evidence.syncLatencyMs, hologram: holo.map((h) => ({ id: h.id, hull: h.hull, relief: h.relief })), etaOnScreen: evidence.etaOnScreen, calibrationInApp: accuracy, pageErrors, navigations }, null, 2))
} finally {
  gen.stdin.end()
  gen.kill()
  await browser.close()
  await server.close()
}
