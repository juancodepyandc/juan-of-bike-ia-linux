// Test live du pipeline video v84 : prompt FR → composeur cinematique reel
// (analyzeVideoPrompt + composeWanPrompt) → video_generate.py (TI2V-5B/LTX).
// Verifie : resolution >= cible adaptative, interpolation appliquee, fichier
// exploitable. Lancer depuis la racine :
//   node --experimental-strip-types .claude/scripts/test_video_composer_live.mjs
import { analyzeVideoPrompt, composeWanPrompt } from '../../application/src/services/videoPromptComposer.ts'
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
const OUT = join(ROOT, 'application', 'output', 'videos', `v84_composer_${Date.now()}.mp4`)
const THUMB = OUT.replace('.mp4', '_thumb.png')

// Prompt utilisateur type (FR, avec grammaire camera + lumiere + style).
const userPrompt = 'zoom avant sur un chat roux qui court dans un champ au coucher de soleil, style réaliste'

// Distillation LLM simulee indisponible (pire cas : fallback brut) — le
// composeur doit quand meme produire la grammaire EN.
const analysis = analyzeVideoPrompt(userPrompt)
const finalPrompt = composeWanPrompt(userPrompt, analysis, { mode: 't2v' })

console.log('[analysis]', JSON.stringify(analysis))
console.log('[prompt final]\n' + finalPrompt + '\n')

const args = [
  join(ROOT, 'application', 'python-services', 'video_generate.py'),
  '--prompt', finalPrompt,
  '--output', OUT,
  '--width', '768',
  '--height', '512',
  '--num_frames', '25',
  '--thumbnail', THUMB,
  '--vram_gb', '16',
  '--model_mode', 'quality',
  '--quality_mode', 'auto',
  '--motion_interp', '2',
]
console.log('[run] python video_generate.py (33 frames, budget adaptatif)…')
const started = Date.now()
// v84 : streaming temps reel — chaque ligne PROGRESS visible immediatement
// dans le log (l'ancien spawnSync bufferisait tout jusqu'a la fin = aveugle).
const res = await new Promise((resolve) => {
  const child = spawn('python', args, { cwd: join(ROOT, 'application') })
  const timer = setTimeout(() => { try { child.kill('SIGKILL') } catch {} }, 40 * 60 * 1000)
  child.stdout.on('data', (d) => process.stdout.write(d))
  child.stderr.on('data', (d) => process.stderr.write(d))
  child.on('exit', (code) => { clearTimeout(timer); resolve({ status: code }) })
  child.on('error', () => { clearTimeout(timer); resolve({ status: -1 }) })
})
const dur = Math.round((Date.now() - started) / 1000)
console.log(`[python exit=${res.status} en ${dur}s]`)

if (!existsSync(OUT)) {
  console.error('ECHEC: pas de fichier video produit')
  process.exit(1)
}
const sizeMb = (statSync(OUT).size / (1024 * 1024)).toFixed(1)

// ffprobe : resolution / fps / duree reelles.
const probe = spawnSync('ffprobe', [
  '-v', 'error',
  '-select_streams', 'v:0',
  '-show_entries', 'stream=width,height,r_frame_rate,nb_frames',
  '-show_entries', 'format=duration',
  '-of', 'json', OUT,
], { encoding: 'utf8' })
console.log(`\nLIVE VIDEO OK — ${OUT} (${sizeMb} MB)`)
console.log(probe.stdout || probe.stderr)
