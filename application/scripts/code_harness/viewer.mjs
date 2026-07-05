// Build the EXACT preview HTML the app's CodePreviewFrame would render, by
// running the real `extractWebPreview` (codeOutputFiles.ts) over a generated
// project on disk. Writes <dir>/_preview.html. This is how we "use the
// integrated visualizer" headlessly + verify it doesn't mangle the output.
//
// Usage: node scripts/code_harness/viewer.mjs <projectDir>
import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const noop = () => {}
const mem = new Map()
globalThis.localStorage = { getItem:(k)=>mem.has(k)?mem.get(k):null, setItem:(k,v)=>mem.set(k,String(v)), removeItem:(k)=>mem.delete(k), clear:()=>mem.clear(), key:(i)=>Array.from(mem.keys())[i]??null, get length(){return mem.size} }
globalThis.window = { location:{hostname:'localhost',href:'http://localhost/'}, addEventListener:noop, removeEventListener:noop, matchMedia:()=>({matches:false,addEventListener:noop}) }
globalThis.document = { documentElement:{setAttribute:noop,classList:{add:noop,remove:noop}}, body:{setAttribute:noop}, addEventListener:noop, createElement:()=>({setAttribute:noop,style:{}}), querySelector:()=>null }
register('./hooks.mjs', import.meta.url)

const dir = path.resolve(process.argv[2] || 'output/code-tests/harness_run')
const EXT_LANG = { html:'markup', htm:'markup', css:'css', js:'javascript', mjs:'javascript', jsx:'jsx', ts:'typescript', tsx:'tsx', json:'json', md:'markdown' }
const SKIP_DIRS = new Set(['node_modules', 'dist', 'build', '.git', '.vite', '.next', 'coverage'])
const SKIP_FILES = new Set(['package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'bun.lockb', '_preview.html'])

function walk(base, rel = '') {
  const out = []
  for (const name of readdirSync(path.join(base, rel))) {
    const r = rel ? `${rel}/${name}` : name
    const full = path.join(base, r)
    if (statSync(full).isDirectory()) {
      if (!SKIP_DIRS.has(name)) out.push(...walk(base, r))
    } else if (!SKIP_FILES.has(name) && !name.startsWith('_')) {
      out.push(r)
    }
  }
  return out
}

const files = walk(dir)
  .filter((r) => !r.endsWith('.bat'))
  .map((r) => {
    const ext = r.split('.').pop().toLowerCase()
    return { path: r.replace(/\\/g, '/'), content: readFileSync(path.join(dir, r), 'utf8'), language: EXT_LANG[ext] ?? 'text' }
  })

const { extractWebPreview } = await import(pathToFileURL(path.resolve('src/services/codeOutputFiles.ts')).href)
const preview = extractWebPreview(files)
if (!preview) {
  console.error('extractWebPreview returned null — no renderable web entry found. Files:', files.map(f=>f.path).join(', '))
  process.exit(1)
}
const dest = path.join(dir, '_preview.html')
writeFileSync(dest, preview.html, 'utf8')
console.log(JSON.stringify({
  ok: true, kind: preview.kind, entry: preview.entry.path,
  previewBytes: Buffer.byteLength(preview.html, 'utf8'),
  inlinedJs: /data-aurora-inline/.test(preview.html),
  dest,
  inputFiles: files.map((f) => f.path),
}, null, 2))
