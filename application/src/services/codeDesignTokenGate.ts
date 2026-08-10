// ---------------------------------------------------------------------------
// codeDesignTokenGate — une variable CSS utilisee doit etre DEFINIE dans une
// feuille REELLEMENT CHARGEE.
//
// Cas reel qui motive cette porte (run `runId=940`, SaaS analytics Vue, 32
// fichiers livres, build vert): le rendu sortait entierement plat — police
// serif par defaut, un seul fond, une seule couleur de texte, zero ombre.
//
// Le modele avait pourtant bien fait son travail: `src/assets/styles/
// variables.css` definissait tous les tokens, et les composants les
// utilisaient (`var(--accent)`, `var(--bg)`, `var(--card-bg)`...). Mais
// `main.ts` n importait AUCUN CSS. La feuille de tokens existait sur le disque
// et n etait jamais chargee: chaque `var()` etait donc invalide, et le
// navigateur JETAIT silencieusement la declaration entiere.
//
// Une definition presente sur le disque mais jamais importee doit donc compter
// comme ABSENTE — c est tout l objet de cette porte. Elle raisonne sur le
// GRAPHE DE CHARGEMENT, pas sur la presence des fichiers.
// ---------------------------------------------------------------------------

export type TokenGateFile = { name: string; content: string }

export type DesignTokenReport = {
  /** true si aucune variable utilisee n est orpheline. */
  ok: boolean
  /** Variables employees sans definition atteignable. */
  orphanTokens: string[]
  /** Feuilles definissant des tokens mais jamais chargees. */
  unreachableStylesheets: string[]
  /** Feuilles effectivement atteintes depuis l entree. */
  loadedStylesheets: string[]
  /** Consigne de correction, vide si tout va bien. */
  critique: string
}

const CSS_RE = /\.(css|scss|sass|less)$/i
const norm = (p: string) => p.replace(/\\/g, '/').replace(/^\.\//, '').toLowerCase()

function findFile(files: TokenGateFile[], target: string): TokenGateFile | undefined {
  const t = norm(target)
  return files.find((f) => norm(f.name) === t)
    // Un import relatif (`../assets/x.css`) se resout par suffixe: on ne
    // reconstruit pas un resolveur complet pour un controle de coherence.
    || files.find((f) => norm(f.name).endsWith(t.replace(/^(\.\.\/)+/, '')))
}

/** Feuilles chargees par un HTML: <link rel=stylesheet> et <style> inline. */
function stylesheetsFromHtml(html: string): string[] {
  const links: string[] = []
  for (const m of html.matchAll(/<link[^>]+href=["']([^"']+\.(?:css|scss|sass|less))["'][^>]*>/gi)) {
    if (/rel=["']?stylesheet/i.test(m[0])) links.push(m[1])
  }
  return links
}

/** Imports CSS d un module JS/TS: `import './x.css'`. */
function cssImportsFromScript(src: string): string[] {
  const out: string[] = []
  for (const m of src.matchAll(/import\s+["']([^"']+\.(?:css|scss|sass|less))["']/g)) out.push(m[1])
  for (const m of src.matchAll(/import\s+[^;\n]*from\s+["']([^"']+\.(?:css|scss|sass|less))["']/g)) out.push(m[1])
  return out
}

/** Modules JS/TS importes par un module (pour suivre l entree). */
function scriptImportsFromScript(src: string): string[] {
  const out: string[] = []
  for (const m of src.matchAll(/from\s+["'](\.[^"']+)["']/g)) out.push(m[1])
  for (const m of src.matchAll(/import\s+["'](\.[^"']+)["']/g)) out.push(m[1])
  return out.filter((p) => !CSS_RE.test(p))
}

const ENTRY_HTML = /(^|\/)index\.html?$/i
const ENTRY_SCRIPT = /(^|\/)(main|index|app)\.[jt]sx?$/i

/**
 * Construit le CSS effectivement charge depuis l entree du projet.
 *
 * - HTML statique: les `<link>` et les `<style>` de la page.
 * - Projet a bundler: le CSS importe par le point d entree JS (transitivement),
 *   PLUS les blocs `<style>` des composants monofichiers, qui sont compiles
 *   avec le composant et donc toujours charges quand il est rendu.
 */
export function collectLoadedCss(files: TokenGateFile[]): {
  css: string
  loaded: string[]
} {
  const loaded: string[] = []
  let css = ''
  const seen = new Set<string>()

  const addSheet = (ref: string) => {
    const file = findFile(files, ref)
    if (!file || seen.has(norm(file.name))) return
    seen.add(norm(file.name))
    loaded.push(file.name)
    css += `\n${file.content}`
    for (const nested of cssImportsFromScript(file.content)) addSheet(nested)
    for (const m of file.content.matchAll(/@import\s+(?:url\()?["']?([^"')]+)["']?\)?/g)) addSheet(m[1])
  }

  const walkScript = (ref: string, depth = 0) => {
    if (depth > 12) return
    const file = findFile(files, ref) || findFile(files, `${ref}.ts`) || findFile(files, `${ref}.js`)
    if (!file || seen.has(`js:${norm(file.name)}`)) return
    seen.add(`js:${norm(file.name)}`)
    for (const sheet of cssImportsFromScript(file.content)) addSheet(sheet)
    for (const next of scriptImportsFromScript(file.content)) walkScript(next, depth + 1)
  }

  for (const file of files) {
    if (ENTRY_HTML.test(file.name)) {
      for (const sheet of stylesheetsFromHtml(file.content)) addSheet(sheet)
      for (const m of file.content.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)) css += `\n${m[1]}`
      for (const m of file.content.matchAll(/<script[^>]+src=["'](\.?\/?[^"']+\.[jt]sx?)["']/gi)) walkScript(m[1])
    }
    if (ENTRY_SCRIPT.test(file.name)) walkScript(file.name)
    // Composants monofichiers: leur <style> est compile avec eux.
    if (/\.(vue|svelte)$/i.test(file.name)) {
      for (const m of file.content.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)) css += `\n${m[1]}`
    }
  }
  return { css, loaded }
}

/** Tokens definis dynamiquement en JS: `setProperty('--x', ...)`. */
function tokensSetByScript(files: TokenGateFile[]): string[] {
  const out: string[] = []
  for (const file of files) {
    if (CSS_RE.test(file.name)) continue
    for (const m of file.content.matchAll(/setProperty\(\s*["'`](--[A-Za-z0-9_-]+)["'`]/g)) out.push(m[1])
  }
  return out
}

/**
 * Verifie que chaque `var(--x)` employe dans le CSS charge a une definition
 * atteignable. Ne s applique qu aux projets porteurs de CSS.
 */
export function checkDesignTokens(files: TokenGateFile[]): DesignTokenReport {
  const { css, loaded } = collectLoadedCss(files)
  const used = new Set<string>()
  for (const m of css.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)/g)) used.add(m[1])
  const defined = new Set<string>()
  for (const m of css.matchAll(/(--[A-Za-z0-9_-]+)\s*:/g)) defined.add(m[1])
  for (const token of tokensSetByScript(files)) defined.add(token)

  const orphanTokens = [...used].filter((t) => !defined.has(t)).sort()

  // Feuilles qui definissent des tokens sans jamais etre chargees: c est
  // presque toujours l import manquant qui explique les orphelins.
  const loadedSet = new Set(loaded.map(norm))
  const unreachableStylesheets = files
    .filter((f) => CSS_RE.test(f.name) && !loadedSet.has(norm(f.name)) && /--[A-Za-z0-9_-]+\s*:/.test(f.content))
    .map((f) => f.name)

  return {
    ok: orphanTokens.length === 0,
    orphanTokens,
    unreachableStylesheets,
    loadedStylesheets: loaded,
    critique: buildDesignTokenCritique(orphanTokens, unreachableStylesheets, files),
  }
}

/** Consigne de correction ciblee, nommant les variables et l import a ajouter. */
export function buildDesignTokenCritique(
  orphanTokens: string[],
  unreachableStylesheets: string[],
  files: TokenGateFile[],
): string {
  if (orphanTokens.length === 0) return ''
  const entry = files.find((f) => ENTRY_SCRIPT.test(f.name))?.name
    ?? files.find((f) => ENTRY_HTML.test(f.name))?.name
    ?? 'le point d entree'
  const lines = [
    '## TOKENS DE DESIGN NON CHARGES — CORRECTION OBLIGATOIRE',
    `${orphanTokens.length} variable(s) CSS sont utilisees sans definition ATTEIGNABLE: ${orphanTokens.slice(0, 12).join(', ')}.`,
    'Le navigateur jette silencieusement toute declaration dont la variable est inconnue: la page sort donc sans couleurs, sans polices et sans ombres, meme si le CSS semble correct a la lecture.',
  ]
  if (unreachableStylesheets.length > 0) {
    lines.push(
      `Ces feuilles DEFINISSENT des tokens mais ne sont jamais chargees: ${unreachableStylesheets.join(', ')}.`,
      `CORRECTIF: importe-les depuis \`${entry}\` (par exemple \`import './assets/styles/variables.css'\`) ou reference-les par un <link rel="stylesheet"> dans la page d entree.`,
    )
  } else {
    lines.push('CORRECTIF: definis ces variables dans un bloc `:root { ... }` d une feuille reellement chargee par l entree.')
  }
  return lines.join('\n')
}
