import type { CodeFile } from './codeOrchestrator.ts'

export const CODE_REGRESSION_SNAPSHOT_SCHEMA = 'aurora.code.regression-snapshot/1'

export type CodeCapabilitySnapshot = {
  schemaVersion: typeof CODE_REGRESSION_SNAPSHOT_SCHEMA
  files: string[]
  nonEmptyFiles: string[]
  testFiles: string[]
  fileSizes: Record<string, number>
  packageScripts: Record<string, string>
  exportsByFile: Record<string, string[]>
  endpointsByFile: Record<string, string[]>
  /** Fichiers .html qui sont de VRAIS documents (doctype ou balise <html>). */
  htmlDocuments: string[]
  sourceFileCount: number
  sourceBytes: number
}

export type CodeRegressionViolationKind =
  | 'removed_file'
  | 'emptied_file'
  | 'removed_test'
  | 'removed_script'
  | 'removed_export'
  | 'removed_endpoint'
  | 'source_file_drop'
  | 'source_size_drop'
  | 'broken_html_document'

export type CodeRegressionViolation = {
  kind: CodeRegressionViolationKind
  detail: string
}

export type CodeRegressionGuardReport = {
  ok: boolean
  violations: CodeRegressionViolation[]
  before: CodeCapabilitySnapshot
  after: CodeCapabilitySnapshot
}

const SOURCE_FILE_RE = /\.(?:[cm]?[jt]sx?|vue|svelte|py|rs|go|java|kt|kts|swift|c|cc|cpp|h|hpp|cs|php|rb|dart|lua|ex|exs|scala|hs|zig)$/i
const TEST_FILE_RE = /(^|\/)(?:test|tests|__tests__|spec)\//i
const TEST_NAME_RE = /\.(?:test|spec)\.[cm]?[jt]sx?$/i

function normalizePath(path: string): string {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').trim().toLowerCase()
}

function uniq(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b))
}

function isSourceFile(path: string): boolean {
  return SOURCE_FILE_RE.test(path)
}

function isTestFile(path: string): boolean {
  return TEST_FILE_RE.test(path) || TEST_NAME_RE.test(path)
}

/**
 * Un `.html` qui cesse d etre un DOCUMENT.
 *
 * Mesure reelle (run 960): pendant une passe de correction, l `index.html` d un
 * projet Vite est passe de 569 octets de document a 223 octets contenant un
 * simple fragment JSX `<img className=... />`. Le point d entree du site etait
 * detruit; le garde n a rien vu, parce que `.html` n est ni un fichier source
 * (SOURCE_FILE_RE), ni un test, ni un fichier vide. Perdre le doctype/`<html>`
 * n est pas une question de taille: c est une capacite qui disparait.
 */
function isHtmlDocument(file: CodeFile): boolean {
  if (!/\.html?$/i.test(file.name)) return false
  return /<!doctype\s+html|<html[\s>]/i.test(file.content)
}

function parseJsonObject(content: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(content)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : null
  } catch {
    return null
  }
}

function extractPackageScripts(file: CodeFile): Record<string, string> {
  const path = normalizePath(file.name)
  if (!path.endsWith('package.json')) return {}

  const manifest = parseJsonObject(file.content)
  const scripts = manifest?.scripts
  if (!scripts || typeof scripts !== 'object' || Array.isArray(scripts)) return {}

  const out: Record<string, string> = {}
  for (const [name, command] of Object.entries(scripts as Record<string, unknown>)) {
    if (typeof command === 'string' && command.trim()) {
      out[`${path}#${name}`] = command.trim()
    }
  }
  return out
}

function extractExports(content: string): string[] {
  const exports: string[] = []

  for (const match of content.matchAll(/\bexport\s+(?:async\s+)?(?:function|class|const|let|var|type|interface|enum)\s+([A-Za-z_$][\w$]*)/g)) {
    exports.push(match[1])
  }
  if (/\bexport\s+default\b/.test(content)) exports.push('default')

  for (const match of content.matchAll(/\bexport\s*\{([^}]+)\}/g)) {
    for (const rawName of match[1].split(',')) {
      const cleaned = rawName
        .replace(/\btype\s+/g, '')
        .trim()
      if (!cleaned) continue
      const alias = cleaned.match(/\bas\s+([A-Za-z_$][\w$]*)$/)
      const direct = cleaned.match(/^([A-Za-z_$][\w$]*)/)
      exports.push(alias?.[1] ?? direct?.[1] ?? '')
    }
  }

  for (const match of content.matchAll(/\bexports\.([A-Za-z_$][\w$]*)\s*=/g)) {
    exports.push(match[1])
  }
  for (const match of content.matchAll(/\bmodule\.exports\.([A-Za-z_$][\w$]*)\s*=/g)) {
    exports.push(match[1])
  }
  for (const match of content.matchAll(/\bmodule\.exports\s*=\s*\{([^}]+)\}/g)) {
    for (const rawName of match[1].split(',')) {
      const direct = rawName.trim().match(/^([A-Za-z_$][\w$]*)/)
      if (direct) exports.push(direct[1])
    }
  }

  return uniq(exports)
}

function routePathFromNextFile(path: string): string | null {
  const normalized = normalizePath(path)
  const match = normalized.match(/^app\/api\/(.+)\/route\.[cm]?[jt]s$/)
  if (!match) return null
  return `/api/${match[1].replace(/\[(.+?)\]/g, ':$1')}`
}

function extractEndpoints(file: CodeFile): string[] {
  const endpoints: string[] = []
  const path = normalizePath(file.name)
  const content = file.content

  for (const match of content.matchAll(/\b(?:app|router|server|api)\.(get|post|put|patch|delete|options|head|all)\s*\(\s*['"`]([^'"`]+)['"`]/gi)) {
    endpoints.push(`${match[1].toUpperCase()} ${match[2]}`)
  }
  for (const match of content.matchAll(/@\w+\.(get|post|put|patch|delete|options|head|route)\s*\(\s*['"`]([^'"`]+)['"`]/gi)) {
    endpoints.push(`${match[1].toUpperCase()} ${match[2]}`)
  }
  for (const match of content.matchAll(/\bpath\s*\(\s*['"`]([^'"`]+)['"`]/gi)) {
    endpoints.push(`DJANGO ${match[1]}`)
  }

  const nextRoute = routePathFromNextFile(path)
  if (nextRoute) {
    const methods = extractExports(content).filter((name) => /^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)$/i.test(name))
    for (const method of methods.length ? methods : ['ALL']) {
      endpoints.push(`${method.toUpperCase()} ${nextRoute}`)
    }
  }

  return uniq(endpoints)
}

export function snapshotCodeCapabilities(files: CodeFile[]): CodeCapabilitySnapshot {
  const normalizedFiles = files.map((file) => ({
    ...file,
    normalizedName: normalizePath(file.name),
  })).sort((a, b) => a.normalizedName.localeCompare(b.normalizedName))

  const fileSizes: Record<string, number> = {}
  const packageScripts: Record<string, string> = {}
  const exportsByFile: Record<string, string[]> = {}
  const endpointsByFile: Record<string, string[]> = {}

  for (const file of normalizedFiles) {
    fileSizes[file.normalizedName] = file.content.trim().length
    Object.assign(packageScripts, extractPackageScripts(file))

    const fileExports = extractExports(file.content)
    if (fileExports.length > 0) exportsByFile[file.normalizedName] = fileExports

    const endpoints = extractEndpoints(file)
    if (endpoints.length > 0) endpointsByFile[file.normalizedName] = endpoints
  }

  const sourceFiles = normalizedFiles.filter((file) => isSourceFile(file.normalizedName))
  return {
    schemaVersion: CODE_REGRESSION_SNAPSHOT_SCHEMA,
    files: normalizedFiles.map((file) => file.normalizedName),
    nonEmptyFiles: normalizedFiles
      .filter((file) => file.content.trim().length > 0)
      .map((file) => file.normalizedName),
    testFiles: normalizedFiles
      .filter((file) => isTestFile(file.normalizedName))
      .map((file) => file.normalizedName),
    htmlDocuments: normalizedFiles
      .filter((file) => isHtmlDocument(file))
      .map((file) => file.normalizedName),
    fileSizes,
    packageScripts,
    exportsByFile,
    endpointsByFile,
    sourceFileCount: sourceFiles.length,
    sourceBytes: sourceFiles.reduce((sum, file) => sum + file.content.trim().length, 0),
  }
}

function missingFrom(before: string[], after: string[]): string[] {
  const afterSet = new Set(after)
  return before.filter((item) => !afterSet.has(item))
}

function pushMissingMapEntries(
  violations: CodeRegressionViolation[],
  kind: CodeRegressionViolationKind,
  before: Record<string, string[] | string>,
  after: Record<string, string[] | string>,
): void {
  for (const [key, beforeValue] of Object.entries(before)) {
    const beforeValues = Array.isArray(beforeValue) ? beforeValue : [beforeValue]
    const afterValue = after[key]
    const afterValues = Array.isArray(afterValue) ? afterValue : afterValue ? [afterValue] : []
    for (const value of beforeValues) {
      if (!afterValues.includes(value)) {
        violations.push({ kind, detail: `${key}:${value}` })
      }
    }
  }
}

export function compareCodeCapabilities(
  before: CodeCapabilitySnapshot,
  after: CodeCapabilitySnapshot,
): CodeRegressionGuardReport {
  const violations: CodeRegressionViolation[] = []

  for (const path of missingFrom(before.nonEmptyFiles, after.files)) {
    violations.push({ kind: 'removed_file', detail: path })
  }
  for (const path of before.nonEmptyFiles) {
    if (after.files.includes(path) && (after.fileSizes[path] ?? 0) === 0) {
      violations.push({ kind: 'emptied_file', detail: path })
    }
  }
  for (const path of missingFrom(before.testFiles, after.testFiles)) {
    violations.push({ kind: 'removed_test', detail: path })
  }
  // Un point d entree HTML qui cesse d etre un document est une capacite
  // perdue, pas un detail de mise en forme: la page ne s ouvre plus.
  for (const path of missingFrom(before.htmlDocuments, after.htmlDocuments)) {
    if (after.files.includes(path)) {
      violations.push({ kind: 'broken_html_document', detail: path })
    }
  }

  pushMissingMapEntries(violations, 'removed_script', before.packageScripts, after.packageScripts)
  pushMissingMapEntries(violations, 'removed_export', before.exportsByFile, after.exportsByFile)
  pushMissingMapEntries(violations, 'removed_endpoint', before.endpointsByFile, after.endpointsByFile)

  if (before.sourceFileCount >= 3 && after.sourceFileCount < Math.ceil(before.sourceFileCount * 0.7)) {
    violations.push({
      kind: 'source_file_drop',
      detail: `${before.sourceFileCount}->${after.sourceFileCount}`,
    })
  }
  if (before.sourceBytes >= 1000 && after.sourceBytes < Math.floor(before.sourceBytes * 0.65)) {
    violations.push({
      kind: 'source_size_drop',
      detail: `${before.sourceBytes}->${after.sourceBytes}`,
    })
  }

  return { ok: violations.length === 0, violations, before, after }
}

export function inspectCodePatchRegression(beforeFiles: CodeFile[], afterFiles: CodeFile[]): CodeRegressionGuardReport {
  return compareCodeCapabilities(
    snapshotCodeCapabilities(beforeFiles),
    snapshotCodeCapabilities(afterFiles),
  )
}

export function formatCodeRegressionGuardReport(report: CodeRegressionGuardReport): string {
  if (report.ok) return 'Aucune regression comportementale detectee.'
  const preview = report.violations
    .slice(0, 8)
    .map((violation) => `- ${violation.kind}: ${violation.detail}`)
  const suffix = report.violations.length > preview.length
    ? `\n- ... ${report.violations.length - preview.length} autre(s) regression(s)`
    : ''
  return `Regression refusee par le harnais anti-regression:\n${preview.join('\n')}${suffix}`
}
