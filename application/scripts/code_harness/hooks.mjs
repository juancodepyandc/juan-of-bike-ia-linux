// Resolve hook: lets Node import the AuroraIA src/ TS graph without a bundler.
// Node v24 strips types natively for *.ts, but it does NOT resolve extensionless
// relative imports (e.g. `import x from './codeIntent'`). This hook appends the
// right extension / index file so the whole orchestrator graph loads as-is.
import { existsSync, statSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'

const KNOWN_EXT = /\.(ts|tsx|js|mjs|cjs|json|css|node)$/

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith('.') && !KNOWN_EXT.test(specifier)) {
    let base
    try {
      base = fileURLToPath(new URL(specifier, context.parentURL))
    } catch {
      return nextResolve(specifier, context)
    }
    const candidates = [
      base + '.ts',
      base + '.tsx',
      base + '.js',
      base + '.mjs',
    ]
    // directory → index
    try {
      if (existsSync(base) && statSync(base).isDirectory()) {
        candidates.push(base + '/index.ts', base + '/index.tsx', base + '/index.js')
      }
    } catch {
      /* ignore */
    }
    for (const cand of candidates) {
      if (existsSync(cand)) {
        return { url: pathToFileURL(cand).href, shortCircuit: true }
      }
    }
  }
  // CSS imports inside components — never executed by the orchestrator, but the
  // module graph may touch one. Stub them to an empty module.
  if (specifier.endsWith('.css')) {
    return { url: 'data:text/javascript,export default {}', shortCircuit: true }
  }
  return nextResolve(specifier, context)
}
