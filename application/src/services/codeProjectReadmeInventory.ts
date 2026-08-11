// ---------------------------------------------------------------------------
// codeProjectReadmeInventory — per-file role derivation for the README.
// Each entry says WHAT the file does, from convention + measured content
// (routes declared, exports counted, scripts listed…). Pure functions only.
// ---------------------------------------------------------------------------

import type { CodeFile } from './codeOrchestratorTypes.ts'

export type InventoryEntry = {
  path: string
  role: string
}

export type InventoryGroup = {
  label: string
  entries: InventoryEntry[]
}

export type RouteInfo = {
  path: string
  element: string
}

function normalize(p: string): string {
  return p.replace(/\\/g, '/')
}

function baseName(p: string): string {
  return normalize(p).split('/').pop() || p
}

function parentDir(p: string): string {
  const n = normalize(p)
  const i = n.lastIndexOf('/')
  return i >= 0 ? n.slice(0, i) : ''
}

function stem(p: string): string {
  const b = baseName(p)
  const i = b.lastIndexOf('.')
  return i > 0 ? b.slice(0, i) : b
}

function extOf(name: string): string {
  const m = name.match(/\.[^.]+$/)
  return m ? m[0].toLowerCase() : ''
}

function safeParseJson(text: string): unknown {
  try { return JSON.parse(text) } catch { return null }
}

function isReadmish(p: string): boolean {
  return /^readme\.md$/i.test(baseName(p))
}

// --------------------------------------------------------------------------
// Content probes — extract measurable facts from a file's source text.
// --------------------------------------------------------------------------

export function extractRoutes(source: string): RouteInfo[] {
  const out: RouteInfo[] = []
  const routeRe = /<Route\s+[^>]*path\s*=\s*["']([^"']+)["'][^>]*element\s*=\s*\{\s*<\s*(\w+)/g
  let m: RegExpExecArray | null
  while ((m = routeRe.exec(source))) {
    out.push({ path: m[1], element: m[2] })
  }
  return out
}

function defaultExportName(source: string): string | null {
  const m1 = source.match(/export\s+default\s+function\s+(\w+)/)
  if (m1) return m1[1]
  const m2 = source.match(/export\s+default\s+(\w+)\s*;?\s*$/m)
  if (m2 && /^[A-Za-z_]/.test(m2[1])) return m2[1]
  const m3 = source.match(/const\s+(\w+)\s*(?::\s*[^=]+)?=\s*(?:React\.FC|\([^)]*\)\s*(?::\s*[^=]+)?=>)/)
  if (m3) return m3[1]
  const m4 = source.match(/function\s+(\w+)\s*\(/)
  return m4?.[1] ?? null
}

function countPropsLines(source: string): number {
  const propsBlock = source.match(/interface\s+\w+Props\s*\{([\s\S]*?)\}/)?.[1]
    ?? source.match(/type\s+\w+Props\s*=\s*\{([\s\S]*?)\}/)?.[1]
  if (!propsBlock) return 0
  // Split on both newlines and semicolons/commas so both multi-line and single-line
  // prop declarations are counted correctly (`{ a: A; b: B; c: C }` = 3 props).
  return propsBlock
    .split(/[\n;,]/)
    .map((segment) => segment.replace(/^\s*\/\/.*/, '').trim())
    .filter((segment) => /^[\w$][\w$]*\s*\??\s*:\s*/.test(segment))
    .length
}

function countExports(source: string): number {
  return (source.match(/^\s*export\s+(?:const|function|type|interface|class|default)\b/gm) || []).length
}

// --------------------------------------------------------------------------
// describeFile — deterministic sentence for each file.
// --------------------------------------------------------------------------

export function describeFile(file: CodeFile): string {
  const path = normalize(file.name)
  const name = baseName(path)
  const parent = parentDir(path)
  const ext = extOf(name)
  const content = file.content

  // Root configuration
  if (/^package\.json$/i.test(name) && parent === '') {
    const pkg = safeParseJson(content) as { scripts?: Record<string, unknown>; dependencies?: Record<string, unknown>; devDependencies?: Record<string, unknown> } | null
    const scripts = pkg?.scripts && typeof pkg.scripts === 'object' ? Object.keys(pkg.scripts) : []
    const deps = pkg?.dependencies ? Object.keys(pkg.dependencies).length : 0
    const dev = pkg?.devDependencies ? Object.keys(pkg.devDependencies).length : 0
    const parts = ['Manifeste npm']
    if (scripts.length) parts.push(`${scripts.length} script${scripts.length > 1 ? 's' : ''} (${scripts.slice(0, 4).join(', ')}${scripts.length > 4 ? '…' : ''})`)
    if (deps || dev) parts.push(`${deps} deps + ${dev} devDeps`)
    return parts.join(' — ') + '.'
  }
  if (/^tsconfig(\..+)?\.json$/i.test(name)) return 'Configuration TypeScript (cibles, chemins, options du compilateur).'
  if (/^vite\.config\.(t|j|m|c)s$/i.test(name)) return 'Configuration Vite (serveur de dev, plugins framework, build).'
  if (/^tailwind\.config\.(t|j|m|c)s$/i.test(name)) return 'Configuration Tailwind (thème étendu, contenu scanné, plugins).'
  if (/^postcss\.config\.(t|j|m|c)s$/i.test(name)) return 'Configuration PostCSS (Tailwind + Autoprefixer).'
  if (/^\.env(\..+)?$/i.test(name)) return 'Variables d\'environnement.'
  if (/^requirements\.txt$/i.test(name)) return 'Dépendances Python (une par ligne).'
  if (/^cargo\.toml$/i.test(name)) return 'Manifeste Cargo (crates + profil de build Rust).'
  if (/^go\.mod$/i.test(name)) return 'Manifeste Go modules.'
  if (/^dockerfile$/i.test(name)) return 'Image Docker de l\'application.'
  if (/^index\.html$/i.test(name) && parent === '') {
    // Vite entry (imports a module script under /src/) vs plain static HTML page.
    if (/<script[^>]*\btype\s*=\s*["']module["'][^>]*src\s*=\s*["']\/src\//i.test(content)) {
      return 'Point d\'entrée HTML — chargé par Vite, monte le module JS racine dans `#root`.'
    }
    return 'Page HTML — point d\'entrée statique du site.'
  }

  // CSS
  if (ext === '.css') {
    if (/@tailwind\b/.test(content)) return 'Feuille de style globale (imports Tailwind base/components/utilities).'
    if (/^index$|^main$|^global(s)?$|^app$|^styles?$/i.test(stem(path))) return 'Feuille de style globale du projet.'
    return `Feuille de style (\`${stem(path)}\`).`
  }

  // JS/TS family
  if (ext === '.tsx' || ext === '.jsx' || ext === '.ts' || ext === '.js') {
    if (/from ['"]react-router/.test(content) && /<Routes?\b/.test(content)) {
      const routes = extractRoutes(content)
      if (routes.length) {
        const preview = routes.slice(0, 4).map((r) => `\`${r.path}\``).join(', ')
        const suffix = routes.length > 4 ? '…' : ''
        return `Table de routage — ${routes.length} route${routes.length > 1 ? 's' : ''} (${preview}${suffix}).`
      }
      return 'Table de routage React Router.'
    }
    if (/createRoot\s*\(/.test(content) || /ReactDOM\.render\b/.test(content)) {
      return 'Bootstrap React — monte le composant racine dans le DOM (`#root`).'
    }
    if (/(?:BrowserRouter|HashRouter|MemoryRouter)\b/.test(content) && /^App$/i.test(stem(path))) {
      return 'Coquille applicative — Router + layout global.'
    }
    if (/from ['"]zustand/.test(content)) {
      const store = defaultExportName(content) || stem(path)
      return `Store Zustand — état global exposé par \`${store}\`.`
    }
    if (parent.endsWith('/pages') || parent === 'pages') {
      const named = defaultExportName(content) || stem(path)
      return `Page — vue rendue par la route correspondante (\`${named}\`).`
    }
    if (parent.endsWith('/components') || parent === 'components') {
      const named = defaultExportName(content) || stem(path)
      const props = countPropsLines(content)
      return props
        ? `Composant — \`${named}\`, ${props} prop${props > 1 ? 's' : ''}.`
        : `Composant — \`${named}\`.`
    }
    if (stem(path) === 'index' && (parent.endsWith('/types') || parent === 'types')) {
      const types = (content.match(/\bexport\s+(?:type|interface)\s+\w+/g) || []).length
      return types
        ? `Types partagés — ${types} définition${types > 1 ? 's' : ''} exportée${types > 1 ? 's' : ''}.`
        : 'Types partagés du projet.'
    }
    if (parent.endsWith('/types') || parent === 'types') {
      const types = (content.match(/\bexport\s+(?:type|interface)\s+\w+/g) || []).length
      return types
        ? `Types partagés — ${types} définition${types > 1 ? 's' : ''} exportée${types > 1 ? 's' : ''}.`
        : `Types partagés (${stem(path)}).`
    }
    if (parent.endsWith('/utils') || parent === 'utils' || parent.endsWith('/lib') || parent === 'lib' || parent.endsWith('/helpers') || parent === 'helpers') {
      const fns = countExports(content)
      return fns ? `Utilitaires — ${fns} export${fns > 1 ? 's' : ''}.` : `Utilitaires (${stem(path)}).`
    }
    if (parent.endsWith('/data') || parent === 'data') {
      const items = countExports(content)
      return items ? `Données statiques — ${items} export${items > 1 ? 's' : ''}.` : 'Données statiques.'
    }
    if (parent.endsWith('/hooks') || parent === 'hooks') {
      const named = defaultExportName(content) || stem(path)
      return `Hook React — \`${named}\`.`
    }
    if (parent.endsWith('/services') || parent === 'services') {
      const fns = countExports(content)
      return fns ? `Service — ${fns} export${fns > 1 ? 's' : ''}.` : `Service (${stem(path)}).`
    }
    if (stem(path) === 'vite-env') return 'Types d\'ambiance Vite (`import.meta.env`).'
    const fns = countExports(content)
    return fns ? `Module \`${stem(path)}\` — ${fns} export${fns > 1 ? 's' : ''}.` : `Module \`${stem(path)}\`.`
  }

  // Python
  if (ext === '.py') {
    if (/if\s+__name__\s*==\s*['"]__main__/.test(content)) return 'Script Python — point d\'entrée exécutable.'
    if (/^(app|main)\.py$/i.test(name)) return 'Point d\'entrée Python.'
    return `Module Python (${stem(path)}).`
  }

  // Shell / bash
  if (ext === '.sh') {
    if (/^start\.sh$/i.test(name)) return 'Script de lancement Linux/macOS — installe les dépendances si nécessaire puis démarre.'
    return `Script shell (${stem(path)}).`
  }

  // Rust / Go
  if (ext === '.rs') return `Module Rust (${stem(path)}).`
  if (ext === '.go') return `Module Go (${stem(path)}).`

  return `Fichier ${ext.slice(1) || file.language || 'texte'}.`
}

// --------------------------------------------------------------------------
// Grouping — collapse dozens of files into readable directory buckets.
// --------------------------------------------------------------------------

const GROUP_RULES: Array<{ label: string; test: (path: string) => boolean }> = [
  { label: 'Configuration', test: (p) => /^(package\.json|tsconfig[^/]*\.json|vite\.config\.[^/]+|tailwind\.config\.[^/]+|postcss\.config\.[^/]+|requirements\.txt|cargo\.toml|go\.mod|dockerfile|\.env(?:\..+)?)$/i.test(p) },
  { label: 'Point d\'entrée', test: (p) => /^(index\.html|src\/(main|index)\.(tsx|jsx|ts|js)|main\.(py|rs|go)|app\.py)$/i.test(p) },
  { label: 'Coquille applicative', test: (p) => /^src\/App\.(tsx|jsx|ts|js)$/i.test(p) },
  { label: 'Routes', test: (p) => /^src\/routes\//i.test(p) },
  { label: 'Pages', test: (p) => /^src\/pages\//i.test(p) },
  { label: 'Composants', test: (p) => /^src\/components\//i.test(p) },
  { label: 'Hooks', test: (p) => /^src\/hooks\//i.test(p) },
  { label: 'Services', test: (p) => /^src\/services\//i.test(p) },
  { label: 'Types', test: (p) => /^src\/types\//i.test(p) || /\.d\.ts$/i.test(p) },
  { label: 'Utilitaires', test: (p) => /^src\/(utils|lib|helpers)\//i.test(p) },
  { label: 'Données', test: (p) => /^src\/data\//i.test(p) },
  { label: 'Styles', test: (p) => /^src\/styles\//i.test(p) || /\.css$/i.test(p) },
  { label: 'Assets', test: (p) => /^(assets|public)\//i.test(p) || /^src\/assets\//i.test(p) },
  { label: 'Tests', test: (p) => /(^|\/)__tests__\//i.test(p) || /\.test\.(t|j)sx?$/i.test(p) },
  { label: 'Scripts', test: (p) => /^(start|launch|lancement)\.(sh|bat)$/i.test(p) },
  // Root-level JS/TS files that aren't config (e.g. plain-HTML site's `script.js`,
  // a small CLI's `main.ts`) end up in the "Modules" bucket instead of "Autre".
  { label: 'Modules', test: (p) => /^[^/]+\.(js|mjs|cjs|ts|jsx|tsx)$/i.test(p) },
]

function classifyPath(path: string): string {
  const n = normalize(path)
  for (const rule of GROUP_RULES) {
    if (rule.test(n)) return rule.label
  }
  const parts = n.split('/')
  if (parts.length > 1) return `Autre — ${parts[0]}/`
  return 'Autre'
}

export function buildInventory(files: CodeFile[]): InventoryGroup[] {
  const kept = files.filter((f) => !isReadmish(f.name))
  const groups = new Map<string, InventoryEntry[]>()
  for (const file of kept) {
    const label = classifyPath(file.name)
    const role = describeFile(file)
    const list = groups.get(label) || []
    list.push({ path: normalize(file.name), role })
    groups.set(label, list)
  }
  const preferred = [
    'Configuration', 'Point d\'entrée', 'Coquille applicative', 'Routes', 'Pages',
    'Composants', 'Hooks', 'Services', 'Types', 'Utilitaires', 'Données',
    'Modules', 'Styles', 'Assets', 'Tests', 'Scripts',
  ]
  const result: InventoryGroup[] = []
  for (const label of preferred) {
    if (groups.has(label)) {
      result.push({ label, entries: groups.get(label)!.sort((a, b) => a.path.localeCompare(b.path)) })
      groups.delete(label)
    }
  }
  for (const [label, entries] of [...groups.entries()].sort()) {
    result.push({ label, entries: entries.sort((a, b) => a.path.localeCompare(b.path)) })
  }
  return result
}

export function extractDeclaredRoutes(files: CodeFile[]): RouteInfo[] {
  for (const f of files) {
    if (!/\.(t|j)sx?$/i.test(f.name)) continue
    if (!/from ['"]react-router/.test(f.content)) continue
    if (!/<Routes?\b/.test(f.content)) continue
    const routes = extractRoutes(f.content)
    if (routes.length) return routes
  }
  return []
}
