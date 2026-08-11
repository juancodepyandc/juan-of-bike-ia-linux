// ---------------------------------------------------------------------------
// codeProjectReadme — assembles the README the user actually reads.
// Real project title (brand or manifest name), a per-file inventory of what
// each file DOES, prerequisites derived from the manifest, the ACTUAL scripts
// declared, a one-liner, exposed URLs, and the dependency block from the plan.
// Pure and deterministic — no I/O, no network, no LLM. Runs on all channels.
// ---------------------------------------------------------------------------

import { formatArchitecturePlanDependenciesForMarkdown } from './codeArchitecturePlan.ts'
import type { CodeIntent } from './codeIntent.ts'
import type { CodeFile } from './codeOrchestratorTypes.ts'
import { buildInventory, extractDeclaredRoutes } from './codeProjectReadmeInventory.ts'
import { buildProjectRunbook } from './codeProjectReadmeRunbook.ts'

function safeParseJson(text: string): unknown {
  try { return JSON.parse(text) } catch { return null }
}

// --------------------------------------------------------------------------
// Title resolution — cascade: subject → package.json name → prompt → fallback.
// --------------------------------------------------------------------------

/**
 * "brulerie-nomade" → "Brulerie Nomade".
 * "@aurora/brulerie" → "Brulerie".
 * "myAppLanding" → "My App Landing".
 */
function humanizePackageName(raw: string): string {
  const noScope = raw.replace(/^@[^/]+\//, '')
  const spaced = noScope
    .replace(/[-_.]+/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
  if (!spaced) return raw
  return spaced.replace(/\S+/g, (w) => w.charAt(0).toUpperCase() + w.slice(1))
}

const GENERIC_PACKAGE_NAMES = new Set([
  'app', 'apps', 'site', 'website', 'web', 'project', 'my-app', 'my-project',
  'vite-project', 'vite-app', 'react-app', 'react-project', 'my-vue-app',
  'nextjs-app', 'nuxt-app', 'svelte-app', 'starter', 'template', 'demo',
  'test-app', 'example', 'aurora-code', 'code',
])

function isGenericPackageName(name: string): boolean {
  const key = name.toLowerCase().replace(/^@[^/]+\//, '')
  return GENERIC_PACKAGE_NAMES.has(key)
}

/** Proper-name shape: starts with an uppercase letter (Unicode-aware), no verb prefix. */
function looksLikeProperName(candidate: string): boolean {
  return /^\p{Lu}[\p{L}\p{N}\s'’&·.-]{1,60}$/u.test(candidate.trim())
}

function resolveProjectTitle(files: CodeFile[], intent: CodeIntent, prompt: string): string {
  const subject = intent.assetPlan?.subject

  // 1) Brand dictionary hit or inferred brand — highest confidence signal.
  if (subject && subject.canonical && (subject.source === 'brand' || subject.source === 'inferred_brand')) {
    const canonical = subject.canonical.trim()
    if (canonical) return canonical
  }

  // 2) Quoted subject — accept ONLY if it looks like a proper name. The classifier's
  //    quoted heuristic can misfire on French elisions (`s'appelle "X"` captures
  //    `appelle`), so we reject shapes that don't start with an uppercase letter.
  if (subject && subject.canonical && subject.source === 'quoted') {
    const canonical = subject.canonical.trim()
    if (canonical && looksLikeProperName(canonical)) return canonical
  }

  const pkg = files.find((f) => f.name.replace(/\\/g, '/').toLowerCase() === 'package.json')
  const parsed = pkg ? safeParseJson(pkg.content) as { name?: unknown } | null : null
  const rawName = parsed && typeof parsed.name === 'string' ? parsed.name.trim() : ''

  // 3) Package.json name — semantic identity chosen by the LLM. Skip generic placeholders.
  if (rawName && !isGenericPackageName(rawName)) {
    return humanizePackageName(rawName)
  }

  // 4) Prompt-level quoted phrase, same shape check.
  const quoted = prompt.match(/[«"“]([\p{L}\p{N}][\p{L}\p{N}\s'’&·.-]{1,60}?)[»"”]/u)?.[1]?.trim()
  if (quoted && looksLikeProperName(quoted)) return quoted

  // 5) Fall back to the raw package name even if generic, then the project type.
  if (rawName) return humanizePackageName(rawName)
  return intent.projectType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function summarizePrompt(prompt: string): string {
  const trimmed = prompt.replace(/\s+/g, ' ').trim()
  if (!trimmed) return ''
  // A greeting ("Salut !") is a sentence too — don't stop there. Keep expanding
  // to the next boundary until we have at least ~80 chars of substance, capped
  // at 220 so the blockquote stays one paragraph.
  const MIN = 80
  const MAX = 220
  const re = /[.!?…]+(?:\s|$)/g
  let cursor = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(trimmed))) {
    const end = m.index + m[0].length
    cursor = end
    if (end >= MIN) break
  }
  if (cursor === 0) cursor = trimmed.length
  const slice = trimmed.slice(0, cursor).trim()
  return slice.length > MAX ? slice.slice(0, MAX - 1).trimEnd() + '…' : slice
}

// --------------------------------------------------------------------------
// README assembly.
// --------------------------------------------------------------------------

export function generateProjectReadme(
  files: CodeFile[],
  intent: CodeIntent,
  prompt: string,
  architecturePlan: string | null,
): CodeFile {
  const title = resolveProjectTitle(files, intent, prompt)
  const summary = summarizePrompt(prompt)
  const runbook = buildProjectRunbook(files, intent)
  const inventory = buildInventory(files)
  const routes = extractDeclaredRoutes(files)
  const hasStartSh = files.some((f) => f.name.replace(/\\/g, '/').toLowerCase() === 'start.sh')

  const parts: string[] = []
  parts.push(`# ${title}`, '')
  if (summary) parts.push(`> ${summary}`, '')

  parts.push('## Prérequis', '')
  for (const line of runbook.prerequisites) parts.push(`- ${line}`)
  parts.push('')

  if (runbook.oneLiner) {
    parts.push('## Démarrage rapide', '', '```bash', runbook.oneLiner, '```', '')
  }

  if (runbook.installBlock.length) {
    parts.push('## Installation', '', ...runbook.installBlock, '')
  }
  parts.push('## Lancement', '', ...runbook.runBlock, '')

  if (runbook.scriptDocs.length) {
    parts.push('## Scripts npm disponibles', '', ...runbook.scriptDocs, '')
  }

  if (routes.length && runbook.runUrl) {
    parts.push('## URLs exposées', '')
    parts.push(`Serveur local: \`${runbook.runUrl}\``, '')
    for (const route of routes) {
      const base = runbook.runUrl.replace(/\/$/, '')
      parts.push(`- \`${base}${route.path}\` — ${route.element}`)
    }
    parts.push('')
  }

  if (hasStartSh) {
    parts.push('## Raccourci Linux/macOS', '',
      'Le fichier `start.sh` installe les dépendances si nécessaire puis lance le projet:',
      '',
      '```bash',
      './start.sh',
      '```',
      '')
  }

  if (architecturePlan) {
    const deps = formatArchitecturePlanDependenciesForMarkdown(architecturePlan)
    if (deps) parts.push('## Dépendances', '', deps, '')
  }

  parts.push('## Structure du projet', '')
  for (const group of inventory) {
    parts.push(`### ${group.label}`, '')
    for (const entry of group.entries) {
      parts.push(`- \`${entry.path}\` — ${entry.role}`)
    }
    parts.push('')
  }

  parts.push('---', '*Généré par Aurora IA — Module Code*')

  return { name: 'README.md', language: 'markdown', content: parts.join('\n') }
}
