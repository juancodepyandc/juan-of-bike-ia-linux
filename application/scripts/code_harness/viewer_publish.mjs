// Publication des viewers de projets sur disque + reconstruction du HUB.
//
// Rien de nouveau cote stockage: on ecrit sous `output/code_assets/viewers/`,
// que la route GET `/api/code/assets/file/<path>` du pont sert deja. Le hub est
// donc joignable par le tunnel sans qu une seule ligne de `bridge_server.py`
// n ait a bouger — ce fichier porte du travail non commite de l utilisateur.
//
// Usage CLI (import des runs passes):
//   node --experimental-strip-types scripts/code_harness/viewer_publish.mjs --import

import path from 'node:path'
import fs from 'node:fs'
import { pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'

export const VIEWERS_ROOT = path.resolve('output/code_assets/viewers')
const resolveSrc = (rel) => pathToFileURL(path.resolve(rel)).href

async function services() {
  const redaction = await import(resolveSrc('src/services/codeArtifactRedaction.ts'))
  const viewer = await import(resolveSrc('src/services/codeViewerHtml.ts'))
  const index = await import(resolveSrc('src/services/codeViewerIndex.ts'))
  const preview = await import(resolveSrc('src/components/codeProjectPreviewHtml.ts'))
  return { ...viewer, ...index, ...redaction, buildLivePreviewHtml: preview.buildLivePreviewHtml }
}

/**
 * Ecrit un projet: page autonome (lien direct, hors ligne) + charge utile JSON
 * (chargee a la demande par le hub) + metadonnees.
 */
export async function publishCodeViewerProject({ id, title, brief, files: rawFiles, projectType, score, platforms, createdAt, withApk = false }) {
  const { buildCodeViewerHtml, buildCodeViewerProjectPayload, buildLivePreviewHtml, redactSecretsForPublication } = await services()
  // Le hub part sur une URL PUBLIQUE: aucune valeur de secret ne doit y monter.
  const { files, hits: redactions } = redactSecretsForPublication(rawFiles)
  const dir = path.join(VIEWERS_ROOT, id)
  fs.mkdirSync(dir, { recursive: true })

  // Un projet a bundler ne se rend pas en servant ses sources: son index.html
  // pointe `/src/main.tsx`. Afficher un cadre blanc serait mentir sur l etat du
  // livrable — on affiche la raison.
  const entry = files.find((f) => /(^|\/)index\.html?$/i.test(f.name || ''))
  const needsBuild = /<script[^>]+src=["'][^"']*\/?src\/[^"']+\.(ts|tsx|jsx|vue|svelte)["']/i.test(entry?.content ?? '')
    || files.some((f) => /\.(vue|svelte)$/i.test(f.name || ''))
  // Un projet a bundler est CONSTRUIT pour de vrai avant d etre montre: c est
  // le seul moyen d en voir le rendu, et c est la commande que le README
  // promet. Le code source reste celui qu on affiche a gauche; seul le rendu
  // vient du dist/.
  let previewFiles = files
  let notice = null
  let buildErrors = []
  if (needsBuild) {
    const { buildGeneratedProject } = await import('./project_build.mjs')
    const build = buildGeneratedProject(files)
    if (build.built) {
      previewFiles = build.files.filter((f) => f.content)
    } else {
      buildErrors = build.errors ?? []
      notice = [
        `Ce projet ne se construit pas en l etat (${build.reason}).`,
        '',
        ...buildErrors.slice(0, 8).map((line) => `  ${line}`),
        '',
        'Le code reste consultable fichier par fichier a gauche.',
      ].join('\n')
    }
  }
  let previewHtml = null
  if (!notice) {
    try {
      previewHtml = buildLivePreviewHtml(previewFiles)
    } catch {
      previewHtml = null
    }
  }

  const meta = {
    id,
    title: String(title || id).slice(0, 120),
    brief: String(brief || '').replace(/\s+/g, ' ').trim().slice(0, 220),
    createdAt: createdAt || Date.now(),
    fileCount: files.length,
    bytes: files.reduce((sum, file) => sum + (file.content?.length ?? 0), 0),
    projectType: projectType || undefined,
    score: typeof score === 'number' ? score : null,
    platforms: Array.isArray(platforms) ? platforms : [],
    needsBuild,
    buildOk: needsBuild ? buildErrors.length === 0 : null,
    buildErrors: buildErrors.slice(0, 8),
    redactions: redactions.length,
  }

  fs.writeFileSync(
    path.join(dir, 'index.html'),
    buildCodeViewerHtml({ files, title: meta.title, subtitle: id, previewHtml }),
    'utf8',
  )
  fs.writeFileSync(
    path.join(dir, 'project.json'),
    JSON.stringify({ ...buildCodeViewerProjectPayload({ files, previewHtml }), notice }),
    'utf8',
  )
  if (withApk) {
    const apk = buildProjectApk({
      id,
      files: needsBuild ? previewFiles : files,
      label: meta.title,
      needsBuild: needsBuild && Boolean(notice),
    })
    if (apk) {
      meta.apk = apk
      meta.platforms = [
        ...meta.platforms.filter((p) => p.family !== 'mobile_real'),
        { family: 'mobile_real', label: 'Mobile', status: 'executed', realExecution: true, detail: 'APK signe' },
      ]
    }
  }
  fs.writeFileSync(path.join(dir, 'meta.json'), JSON.stringify(meta, null, 2), 'utf8')
  return meta
}

/**
 * Empaquette le projet dans un VRAI APK signe, quand c est possible.
 *
 * Possible = un projet web deja servable (index.html + assets) ET le SDK
 * Android present. Un projet a bundler ou une demande React Native sortent du
 * cadre: on ne fabrique pas un APK qui ne contiendrait pas l application.
 * Retourne null sans bruit quand le cas ne s y prete pas — un APK absent est
 * un fait, pas une erreur.
 */
export function buildProjectApk({ id, files, label, needsBuild }) {
  if (needsBuild) return null
  if (!files.some((f) => /(^|\/)index\.html?$/i.test(f.name || ''))) return null

  const dir = path.join(VIEWERS_ROOT, id)
  const projectDir = path.join(dir, 'project')
  fs.rmSync(projectDir, { recursive: true, force: true })
  for (const file of files) {
    const dest = path.join(projectDir, file.name)
    fs.mkdirSync(path.dirname(dest), { recursive: true })
    fs.writeFileSync(dest, file.content ?? '', 'utf8')
  }

  const script = path.resolve('python-services/aurora_code/code_apk_package.py')
  const buildDir = path.join(dir, 'apk-build')
  const proc = spawnSync('python3', [script, projectDir, buildDir, label || 'Aurora App'], {
    encoding: 'utf8', timeout: 300_000,
  })
  const produced = path.join(buildDir, 'aurora-app.apk')
  if (proc.status !== 0 || !fs.existsSync(produced)) return null

  const apkPath = path.join(dir, 'app.apk')
  fs.copyFileSync(produced, apkPath)
  return { file: 'app.apk', bytes: fs.statSync(apkPath).size }
}

/** Reconstruit le hub a partir des `meta.json` presents sur disque. */
export async function rebuildCodeViewerIndex() {
  const { buildCodeViewerIndex, buildCodeViewerIndexHtml } = await services()
  fs.mkdirSync(VIEWERS_ROOT, { recursive: true })
  const entries = []
  for (const name of fs.readdirSync(VIEWERS_ROOT)) {
    const metaPath = path.join(VIEWERS_ROOT, name, 'meta.json')
    if (!fs.existsSync(metaPath)) continue
    try {
      entries.push(JSON.parse(fs.readFileSync(metaPath, 'utf8')))
    } catch {
      /* un projet illisible ne doit pas emporter le hub */
    }
  }
  const index = buildCodeViewerIndex(entries)
  fs.writeFileSync(path.join(VIEWERS_ROOT, 'index.json'), JSON.stringify(index), 'utf8')
  fs.writeFileSync(path.join(VIEWERS_ROOT, 'index.html'), buildCodeViewerIndexHtml(index), 'utf8')
  return index
}

// ---------------------------------------------------------------------------
// Import des runs PASSES: le hub doit montrer tout ce qui a deja ete produit,
// pas seulement ce qui sera genere apres cette fonctionnalite. Les flux NDJSON
// archives contiennent les fichiers livres — c est deja du stockage, on le lit.
// ---------------------------------------------------------------------------

const LANG_BY_EXT = {
  html: 'html', htm: 'html', css: 'css', js: 'javascript', mjs: 'javascript',
  json: 'json', md: 'markdown', sh: 'bash', ts: 'typescript', tsx: 'typescript',
  jsx: 'javascript', py: 'python', vue: 'vue', svelte: 'svelte',
}

/**
 * Plateformes reellement eprouvees, DEDUITES des preuves du flux — jamais
 * declarees d avance. Un audit de rendu qui a tourne prouve un navigateur;
 * l acceptation comportementale prouve une execution. Rien d autre n est
 * affirme: une pastille qui ment ne vaut pas mieux qu aucune pastille.
 */
function platformsFromStream(events) {
  const platforms = []
  const rendered = events.some((e) => e.kind === 'visual.score' && e.source === 'render_audit')
  const behaved = events.some((e) => e.kind === 'test.result' && /Acceptation comportementale/.test(e.summary || ''))
  if (rendered || behaved) {
    platforms.push({
      family: 'web',
      label: 'Web',
      status: 'executed',
      realExecution: true,
      detail: [rendered ? 'rendu Chromium' : '', behaved ? 'acceptation comportementale' : ''].filter(Boolean).join(' + '),
    })
  }
  return platforms
}

export function readRunFromStream(streamPath) {
  const files = new Map()
  const events = []
  let runId = null
  let score = null
  let createdAt = null
  for (const line of fs.readFileSync(streamPath, 'utf8').split('\n')) {
    if (!line.trim()) continue
    let event
    try {
      event = JSON.parse(line)
    } catch {
      continue
    }
    events.push(event)
    runId ??= event.runId ?? null
    createdAt ??= event.timestamp ?? null
    if (event.kind === 'file.written' && typeof event.content === 'string') {
      const ext = String(event.path || '').split('.').pop()?.toLowerCase() ?? ''
      files.set(event.path, {
        name: event.path,
        language: event.language || LANG_BY_EXT[ext] || 'text',
        content: event.content,
      })
    }
    if (event.kind === 'done' && typeof event.finalScore === 'number') score = event.finalScore
  }
  return { runId, score, createdAt, files: [...files.values()], platforms: platformsFromStream(events) }
}

async function importPastRuns(withApk = false) {
  const auditRoot = path.resolve('output/code')
  if (!fs.existsSync(auditRoot)) return []
  const imported = []
  for (const dir of fs.readdirSync(auditRoot).sort()) {
    const streamPath = path.join(auditRoot, dir, 'stream.ndjson')
    if (!fs.existsSync(streamPath)) continue
    const run = readRunFromStream(streamPath)
    // Un flux sans fichier ecrit n est pas un projet: on ne fabrique pas
    // d entree vide juste pour remplir le hub.
    if (run.files.length === 0) continue
    let brief = ''
    const payloadPath = path.join(auditRoot, dir, 'payload.json')
    if (fs.existsSync(payloadPath)) {
      try {
        brief = JSON.parse(fs.readFileSync(payloadPath, 'utf8')).prompt ?? ''
      } catch { /* brief facultatif */ }
    }
    const html = run.files.find((f) => /(^|\/)index\.html?$/i.test(f.name))
    const title = html?.content.match(/<title[^>]*>([^<]{2,80})<\/title>/i)?.[1]?.trim()
      || brief.slice(0, 60)
      || `run ${run.runId ?? dir}`
    const meta = await publishCodeViewerProject({
      id: `run-${run.runId ?? dir}`,
      title,
      brief,
      files: run.files,
      score: run.score,
      platforms: run.platforms,
      withApk,
      createdAt: run.createdAt ?? fs.statSync(streamPath).mtimeMs,
    })
    imported.push(meta)
  }
  return imported
}

if (process.argv.includes('--import')) {
  const { installHeadlessCodeEnv } = await import('./harness_env.mjs')
  installHeadlessCodeEnv()
  const imported = await importPastRuns(process.argv.includes('--apk'))
  const index = await rebuildCodeViewerIndex()
  process.stdout.write(`${imported.length} run(s) importe(s), ${index.projects.length} projet(s) au hub\n`)
  for (const meta of index.projects) {
    process.stdout.write(`  ${meta.id.padEnd(12)} ${String(meta.fileCount).padStart(3)} fichiers  ${meta.title}\n`)
  }
}
