// Anti-orphan scanner for the Code module (recommendation #10 of the July audit).
//
// A "flagship deliverable" that is implemented + tested but never reached from
// the real pipeline is the exact `aurora_code_loop.py` anti-pattern the refonte
// had to eradicate: green tests create an illusion of completeness while the
// capability is inert in production.
//
// Method: build the real import graph from the PRODUCTION entry points and mark
// every module reachable from them. A `code*.ts` service that is not reachable
// is dead capability, no matter how many tests cover it.
//
// Two verdicts per unreachable module:
//   ORPHAN — has tests but no production reachability (green tests, inert code)
//   DEAD   — no production reachability and no tests at all
//
// Usage:
//   node scripts/code_harness/orphan_scan.mjs [--json <path>]

import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const SRC = path.resolve('src')
const SERVICES = path.join(SRC, 'services')

// Real production entry points of the Code module, all three channels.
const ENTRY_POINTS = [
  path.join(SRC, 'stores', 'codeStreamStore.ts'),
  path.join(SRC, 'services', 'codeOrchestrator.ts'),
  path.join(SRC, 'views', 'CodeView.tsx'),
  path.join(SRC, 'views', 'MangaCodeView.tsx'),
].filter((f) => existsSync(f))

// The headless runners are production too: the bridge route spawns the NDJSON
// runner, so anything it calls is genuinely reachable from the tunnel channel.
// Ignoring them would report a symbol as orphan while a live channel uses it.
const HARNESS_DIR = path.resolve('scripts', 'code_harness')
const HARNESS_FILES = existsSync(HARNESS_DIR)
  ? readdirSync(HARNESS_DIR)
      .filter((n) => /\.mjs$/.test(n))
      .map((n) => path.join(HARNESS_DIR, n))
  : []

function walk(dir, acc = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules') continue
      walk(full, acc)
    } else if (/\.(ts|tsx)$/.test(entry.name)) {
      acc.push(full)
    }
  }
  return acc
}

const allFiles = [...walk(SRC), ...HARNESS_FILES]
const isTest = (f) => f.includes('__tests__') || /\.test\.tsx?$/.test(f)
const contents = new Map()
for (const f of allFiles) contents.set(f, readFileSync(f, 'utf8'))

/**
 * Removes comments before counting symbol references.
 *
 * Without this the scanner lies in the most dangerous direction: a symbol merely
 * NAMED in a doc comment (for instance a comment explaining that it is dead)
 * counts as a caller, so a real orphan is reported as wired. A tool meant to
 * catch orphans must never manufacture false "wired" verdicts.
 *
 * Conservative on purpose: whole-line comments and block comments only, so an
 * inline `//` inside a string (e.g. "https://…") is never mangled.
 */
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((line) => {
      const t = line.trim()
      return !t.startsWith('//') && !t.startsWith('*')
    })
    .join('\n')
}

const codeOnly = new Map()
for (const f of allFiles) codeOnly.set(f, stripComments(contents.get(f)))

// ---------------------------------------------------------------------------
// Resolve a relative specifier the way Vite / the harness hook does.
// ---------------------------------------------------------------------------
function resolveSpecifier(spec, fromFile) {
  if (!spec.startsWith('.')) return null
  const base = path.resolve(path.dirname(fromFile), spec)
  const candidates = [
    base,
    base + '.ts',
    base + '.tsx',
    base + '.js',
    base + '.mjs',
  ]
  try {
    if (existsSync(base) && statSync(base).isDirectory()) {
      candidates.push(path.join(base, 'index.ts'), path.join(base, 'index.tsx'))
    }
  } catch {
    /* ignore */
  }
  for (const c of candidates) {
    try {
      if (existsSync(c) && statSync(c).isFile()) return c
    } catch {
      /* ignore */
    }
  }
  return null
}

// Every static import/export-from plus dynamic import() and bare side-effect
// import. Multi-line import blocks are common in this codebase, so match the
// `from '<spec>'` tail directly instead of trying to span the whole statement.
const SPEC_RE =
  /\bfrom\s*['"]([^'"]+)['"]|\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)|^\s*import\s+['"]([^'"]+)['"]/gm

// Import dynamique par URL absolue: `import(pathToFileURL(path.resolve('src/...')))`.
// Les runners headless chargent le graphe TS ainsi; sans cette reconnaissance,
// un module reellement utilise par le canal tunnel serait declare orphelin.
const RESOLVE_RE = /path\.resolve\(\s*['"]((?:src|application\/src)\/[^'"]+)['"]\s*\)/g

function edgesOf(file) {
  const src = contents.get(file) ?? ''
  const out = []
  for (const m of src.matchAll(RESOLVE_RE)) {
    const abs = path.resolve(m[1].replace(/^application\//, ''))
    try {
      if (existsSync(abs) && statSync(abs).isFile()) out.push(abs)
    } catch { /* ignore */ }
  }
  for (const m of src.matchAll(SPEC_RE)) {
    const spec = m[1] || m[2] || m[3]
    if (!spec) continue
    const resolved = resolveSpecifier(spec, file)
    if (resolved) out.push(resolved)
  }
  return out
}

// ---------------------------------------------------------------------------
// BFS from the production entry points.
// ---------------------------------------------------------------------------
const reachable = new Set()
// Les runners headless sont eux aussi des points d entree de production: la
// route bridge en spawn un, donc tout ce qu ils importent est reellement
// atteint depuis le canal tunnel.
const ALL_ENTRY_POINTS = [...ENTRY_POINTS, ...HARNESS_FILES]
const queue = [...ALL_ENTRY_POINTS]
for (const e of ALL_ENTRY_POINTS) reachable.add(e)
while (queue.length) {
  const cur = queue.shift()
  for (const next of edgesOf(cur)) {
    if (reachable.has(next)) continue
    reachable.add(next)
    queue.push(next)
  }
}

// ---------------------------------------------------------------------------
// Verdict per code*.ts service module.
// ---------------------------------------------------------------------------
const codeServiceFiles = readdirSync(SERVICES)
  .filter((n) => /^code.*\.ts$/.test(n))
  .map((n) => path.join(SERVICES, n))

const testFiles = allFiles.filter(isTest)
function testsTouching(file) {
  const rel = path.basename(file)
  const modName = rel.replace(/\.ts$/, '')
  return testFiles
    .filter((t) => new RegExp(`services/${modName}(\\.ts)?['"]`).test(contents.get(t) ?? ''))
    .map((t) => path.relative(SRC, t))
}

const orphans = []
const dead = []
const wired = []
for (const file of codeServiceFiles) {
  const rel = path.relative(SRC, file)
  if (reachable.has(file)) {
    wired.push(rel)
    continue
  }
  const tests = testsTouching(file)
  if (tests.length > 0) orphans.push({ module: rel, tests })
  else dead.push({ module: rel })
}

// ---------------------------------------------------------------------------
// Symbol level. A module can be reachable while one of its exported functions
// is never called by anyone (buildDesignDirectives was exactly that case).
// Strict definition, so every hit is unambiguous: an exported symbol with ZERO
// production reference anywhere outside its own definition line — neither in
// another module, nor inside its own module.
// ---------------------------------------------------------------------------
const EXPORT_RE =
  /^export\s+(?:async\s+)?(?:function|class)\s+([A-Za-z0-9_]+)|^export\s+const\s+([A-Za-z0-9_]+)\s*[:=]/gm

const productionFiles = allFiles.filter((f) => !isTest(f))
const symbolOrphans = []
for (const file of codeServiceFiles) {
  if (!reachable.has(file)) continue // already reported at module level
  const src = contents.get(file)
  for (const m of src.matchAll(EXPORT_RE)) {
    const name = m[1] || m[2]
    if (!name) continue
    // Deliberate test seams are not orphans: they exist to be called by tests.
    if (/ForTest$/.test(name)) continue

    const word = new RegExp(`\\b${name}\\b`, 'g')
    let refs = 0
    for (const other of productionFiles) {
      const osrc = codeOnly.get(other)
      if (other === file) {
        // Count references inside the defining module, minus the definition.
        const hits = (osrc.match(word) || []).length
        const defs = (osrc.match(new RegExp(`^export\\s+(?:async\\s+)?(?:function|class|const)\\s+${name}\\b`, 'gm')) || []).length
        refs += Math.max(0, hits - defs)
      } else {
        // Re-export blocks are plumbing, not usage — strip them first.
        const stripped = osrc.replace(/export\s*\{[^}]*\}(\s*from\s*['"][^'"]+['"])?/gs, '')
        refs += (stripped.match(word) || []).length
      }
    }
    if (refs === 0) {
      const tests = testFiles
        .filter((t) => new RegExp(`\\b${name}\\b`).test(codeOnly.get(t) ?? ''))
        .map((t) => path.relative(SRC, t))
      symbolOrphans.push({ symbol: name, module: path.relative(SRC, file), tests })
    }
  }
}

const out = {
  generatedAt: new Date().toISOString(),
  entryPoints: ENTRY_POINTS.map((f) => path.relative(SRC, f)),
  totalCodeServiceModules: codeServiceFiles.length,
  wiredCount: wired.length,
  orphanCount: orphans.length,
  deadCount: dead.length,
  symbolOrphanCount: symbolOrphans.length,
  orphans,
  dead,
  symbolOrphans,
  wired,
}

const jsonIdx = process.argv.indexOf('--json')
if (jsonIdx !== -1 && process.argv[jsonIdx + 1]) {
  writeFileSync(process.argv[jsonIdx + 1], JSON.stringify(out, null, 2), 'utf8')
}

process.stdout.write(
  `entry points: ${out.entryPoints.join(', ')}\n` +
    `code service modules: ${out.totalCodeServiceModules}  wired: ${out.wiredCount}  ` +
    `orphan: ${out.orphanCount}  dead: ${out.deadCount}\n`,
)
if (orphans.length) {
  process.stdout.write('\nORPHAN (tested but unreachable from production):\n')
  for (const o of orphans) process.stdout.write(`  - ${o.module}  (${o.tests.length} test file(s))\n`)
}
if (dead.length) {
  process.stdout.write('\nDEAD (unreachable, untested):\n')
  for (const d of dead) process.stdout.write(`  - ${d.module}\n`)
}
process.stdout.write(`\nSYMBOL ORPHANS (exported, zero production reference): ${symbolOrphans.length}\n`)
for (const s of symbolOrphans) {
  process.stdout.write(`  - ${s.symbol}  [${s.module}]  tests=${s.tests.length}\n`)
}
