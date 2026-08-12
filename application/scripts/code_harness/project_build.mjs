// Construction REELLE d un projet genere, avant tout jugement.
//
// Le verrou identifie au tour precedent: un projet a bundler (React/Vue/Svelte)
// ne peut pas etre juge en servant ses sources — son `index.html` pointe
// `/src/main.tsx`, que seul un build resout. Le juge de rendu et l acceptation
// comportementale se declaraient donc « non applicables », et tout le haut du
// spectre restait non mesure: pas de rendu, pas d acceptation, pas d APK.
//
// On construit donc pour de vrai, avec la commande que le README promet
// (`npm install && npm run build`). Le build est la VERITE TERRAIN: il ne
// devine pas comme une heuristique, il compile. Sur le premier essai reel il a
// sorti deux defauts que rien d autre n avait nommes aussi precisement — une
// chaine non terminee dans un SVG et un import non resolu.
//
// node_modules est mutualise par empreinte de dependances: un projet qui
// reutilise la meme pile ne reinstalle rien.

import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const BUILD_ROOT = path.join(os.tmpdir(), 'aurora-code-builds')
const MODULES_CACHE = path.join(BUILD_ROOT, '_modules')

/** Un projet a-t-il besoin d etre construit avant d etre servi ? */
export function projectNeedsBuild(files) {
  const entry = files.find((f) => /(^|\/)index\.html?$/i.test(f.name || ''))
  const html = entry?.content ?? ''
  return /<script[^>]+src=["'][^"']*\/?src\/[^"']+\.(ts|tsx|jsx|vue|svelte)["']/i.test(html)
    || files.some((f) => /\.(vue|svelte)$/i.test(f.name || ''))
}

function readManifest(files) {
  const pkg = files.find((f) => /(^|\/)package\.json$/i.test(f.name || ''))
  if (!pkg) return null
  try {
    return JSON.parse(pkg.content)
  } catch {
    return null
  }
}

/**
 * Repare le trou le plus courant, et purement mecanique: un `vite.config`
 * importe un plugin que le manifeste ne declare pas. Mesure reelle (run 940):
 * `Cannot find package '@vitejs/plugin-react'` — le projet etait juste, sa
 * liste de dependances incomplete. C est verifiable sans deviner: on lit les
 * imports du fichier de config.
 */
// Un plugin doit parler la meme version majeure que son bundler: installer le
// dernier @vitejs/plugin-react a cote d un vite 5 donne
// `ERR_PACKAGE_PATH_NOT_EXPORTED` (mesure reelle). On aligne donc sur le vite
// DECLARE plutot que de prendre la derniere version.
const PLUGIN_SPEC_BY_VITE_MAJOR = {
  4: { '@vitejs/plugin-react': '^4', '@vitejs/plugin-vue': '^4' },
  5: { '@vitejs/plugin-react': '^4', '@vitejs/plugin-vue': '^5' },
  6: { '@vitejs/plugin-react': '^4', '@vitejs/plugin-vue': '^5' },
  7: { '@vitejs/plugin-react': '^5', '@vitejs/plugin-vue': '^6' },
  8: { '@vitejs/plugin-react': '^6', '@vitejs/plugin-vue': '^6' },
}

export function specForConfigPlugin(pkg, manifest, fallback) {
  const declared = manifest.devDependencies?.vite ?? manifest.dependencies?.vite ?? ''
  const major = Number(String(declared).match(/(\d+)/)?.[1])
  const table = PLUGIN_SPEC_BY_VITE_MAJOR[major]
  return table?.[pkg] ?? fallback(pkg)
}

export function completeMissingConfigDeps(manifest, files, specFor) {
  const config = files.find((f) => /(^|\/)vite\.config\.[cm]?[jt]s$/i.test(f.name || ''))
  if (!config) return { manifest, added: [] }
  const declared = new Set([
    ...Object.keys(manifest.dependencies ?? {}),
    ...Object.keys(manifest.devDependencies ?? {}),
  ])
  const added = []
  for (const match of String(config.content).matchAll(/\bfrom\s+['"]([^'".][^'"]*)['"]/g)) {
    const pkg = match[1].startsWith('@')
      ? match[1].split('/').slice(0, 2).join('/')
      : match[1].split('/')[0]
    if (pkg === 'vite' || declared.has(pkg) || pkg.startsWith('node:')) continue
    declared.add(pkg)
    added.push(pkg)
  }
  if (added.length === 0) return { manifest, added }
  const next = { ...manifest, devDependencies: { ...(manifest.devDependencies ?? {}) } }
  for (const pkg of added) next.devDependencies[pkg] = specForConfigPlugin(pkg, manifest, specFor)
  return { manifest: next, added }
}

function run(cmd, args, cwd, timeoutMs) {
  const proc = spawnSync(cmd, args, {
    cwd, encoding: 'utf8', timeout: timeoutMs,
    env: { ...process.env, CI: '1', npm_config_fund: 'false', npm_config_audit: 'false' },
  })
  const out = `${proc.stdout ?? ''}${proc.stderr ?? ''}`
  return { ok: proc.status === 0, out, status: proc.status }
}

/** Les erreurs utiles, pas 60 ko de journal npm. */
export function extractBuildErrors(log, max = 12) {
  const lines = String(log)
    // Les couleurs ANSI rendent le journal illisible pour un modele.
    .replace(/\[[0-9;]*m/g, '')
    .split('\n')
  const errors = []
  for (const line of lines) {
    const clean = line.trim()
    if (!clean || clean.length > 400) continue
    if (/^(error|✘|×)|error TS\d+|Module not found|Unterminated|Unexpected token|Cannot find|Could not resolve|is not exported/i.test(clean)) {
      if (!errors.includes(clean)) errors.push(clean)
    }
    if (errors.length >= max) break
  }
  return errors
}

function collectDist(distDir, prefix = '') {
  const out = []
  if (!fs.existsSync(distDir)) return out
  for (const entry of fs.readdirSync(distDir, { withFileTypes: true })) {
    const full = path.join(distDir, entry.name)
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name
    if (entry.isDirectory()) {
      out.push(...collectDist(full, rel))
      continue
    }
    // Les binaires restent sur disque: seul le texte sert au rendu.
    const isText = /\.(html?|css|js|mjs|json|svg|txt|map)$/i.test(entry.name)
    out.push({
      name: rel,
      language: path.extname(entry.name).slice(1) || 'text',
      content: isText ? fs.readFileSync(full, 'utf8') : '',
      binaryPath: isText ? undefined : full,
    })
  }
  return out
}

/**
 * Construit le projet et renvoie les fichiers de `dist/`.
 *
 * Ne leve jamais: un build impossible doit degrader proprement, jamais faire
 * tomber une livraison.
 */
export function buildGeneratedProject(files, { timeoutMs = 240_000, specFor = () => 'latest' } = {}) {
  const rawManifest = readManifest(files)
  if (!rawManifest) return { built: false, reason: 'aucun package.json exploitable' }
  const { manifest, added: addedDeps } = completeMissingConfigDeps(rawManifest, files, specFor)
  const buildScript = manifest.scripts?.build
  if (!buildScript) return { built: false, reason: 'aucun script build declare' }

  const deps = JSON.stringify({ d: manifest.dependencies ?? {}, v: manifest.devDependencies ?? {} })
  const fingerprint = createHash('sha1').update(deps).digest('hex').slice(0, 12)
  const dir = path.join(BUILD_ROOT, `build-${createHash('sha1').update(JSON.stringify(files.map((f) => f.name))).digest('hex').slice(0, 10)}-${fingerprint}`)
  fs.rmSync(dir, { recursive: true, force: true })
  fs.mkdirSync(dir, { recursive: true })

  const effectiveFiles = addedDeps.length === 0 ? files : files.map((file) => (
    /(^|\/)package\.json$/i.test(file.name || '')
      ? { ...file, content: `${JSON.stringify(manifest, null, 2)}\n` }
      : file
  ))
  for (const file of effectiveFiles) {
    const dest = path.join(dir, file.name)
    if (!path.resolve(dest).startsWith(path.resolve(dir))) continue
    fs.mkdirSync(path.dirname(dest), { recursive: true })
    fs.writeFileSync(dest, file.content ?? '', 'utf8')
  }

  // node_modules mutualise par pile de dependances: le 2e projet React ne
  // repaie pas l installation.
  const cache = path.join(MODULES_CACHE, fingerprint)
  const modules = path.join(dir, 'node_modules')
  let install = { ok: true, out: 'node_modules reutilise depuis le cache\n' }
  if (fs.existsSync(path.join(cache, '.ok'))) {
    fs.cpSync(cache, modules, { recursive: true, dereference: false })
  } else {
    const npmArgs = ['install', '--prefer-offline', '--no-audit', '--no-fund', '--loglevel=error']
    install = run('npm', npmArgs, dir, timeoutMs)
    // Conflit de pairs: un projet genere melange souvent des versions qui ne se
    // parlent pas (mesure reelle run 940: un `vite.config` Vue qui importe le
    // plugin React, plugin dont la derniere version exige un vite plus recent
    // que celui declare). C est exactement ce que `--legacy-peer-deps` existe
    // pour absorber; refuser d installer ne dirait rien de plus au modele.
    if (!install.ok && /Could not resolve dependency|ERESOLVE|peer dep/i.test(install.out)) {
      const relaxed = run('npm', [...npmArgs, '--legacy-peer-deps'], dir, timeoutMs)
      if (relaxed.ok) install = { ...relaxed, out: `${install.out}\n[reprise avec --legacy-peer-deps]\n${relaxed.out}` }
    }
    if (install.ok && fs.existsSync(modules)) {
      try {
        fs.mkdirSync(path.dirname(cache), { recursive: true })
        fs.rmSync(cache, { recursive: true, force: true })
        fs.cpSync(modules, cache, { recursive: true, dereference: false })
        fs.writeFileSync(path.join(cache, '.ok'), '1', 'utf8')
      } catch {
        /* le cache est un confort, jamais une condition */
      }
    }
  }
  if (!install.ok) {
    return { built: false, reason: 'npm install a echoue', errors: extractBuildErrors(install.out), log: install.out.slice(-4000), dir }
  }

  // `tsc && vite build` echoue sur le moindre type; le rendu, lui, n a besoin
  // que du bundle. On tente le script declare, puis on retombe sur le bundler
  // seul — un projet qui S AFFICHE vaut mieux qu un projet invisible parce
  // qu une annotation de type manquait.
  let build = run('npm', ['run', 'build'], dir, timeoutMs)
  let relaxedTypes = false
  if (!build.ok && /vite build/.test(String(buildScript))) {
    const fallback = run('npx', ['vite', 'build'], dir, timeoutMs)
    if (fallback.ok) {
      relaxedTypes = true
      build = fallback
    }
  }

  const dist = path.join(dir, manifest.aurora?.distDir || 'dist')
  const distFiles = collectDist(dist)
  if (!build.ok || distFiles.length === 0) {
    return {
      built: false,
      reason: build.ok ? 'build sans sortie dist/' : 'build en echec',
      errors: extractBuildErrors(build.out),
      log: build.out.slice(-4000),
      dir,
    }
  }

  return { built: true, dir, distDir: dist, files: distFiles, relaxedTypes, addedDeps, log: build.out.slice(-2000) }
}
