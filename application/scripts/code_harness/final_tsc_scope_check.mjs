import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'

const inputPath = process.argv[2]
const outputPath = process.argv[3]
const tscExitCode = Number(process.argv[4] || 0)

if (!inputPath || !outputPath) {
  throw new Error('usage: final_tsc_scope_check.mjs <tsc-log> <report> <exit-code>')
}

const allowedOutsideCode = new Set([
  'AuroraCoworkView.tsx',
  'CoworkOverlay.tsx',
  'coworkPlanner.ts',
  'coworkProjectThread.ts',
  'fluxKontextWorkflow.ts',
  'pixelArtEnforcer.ts',
  'sessionTempStorage.ts',
])
const raw = await readFile(inputPath, 'utf8')
const diagnostics = raw.split(/\r?\n/).flatMap((line) => {
  const match = line.match(/^(.+?)\((\d+),(\d+)\): error (TS\d+):\s*(.*)$/)
  if (!match) return []
  return [{
    path: match[1],
    line: Number(match[2]),
    column: Number(match[3]),
    code: match[4],
    message: match[5],
  }]
})
const unexpected = diagnostics.filter((diagnostic) => {
  return !allowedOutsideCode.has(path.basename(diagnostic.path))
})
const ok = tscExitCode === 0 || (diagnostics.length > 0 && unexpected.length === 0)
const report = {
  schemaVersion: 'aurora.code.final-tsc-scope/1',
  tscExitCode,
  diagnostics: diagnostics.length,
  files: [...new Set(diagnostics.map((diagnostic) => diagnostic.path))].sort(),
  allowedOutsideCode: [...allowedOutsideCode].sort(),
  unexpected,
  codeDiagnostics: unexpected.filter((diagnostic) => /code/i.test(diagnostic.path)),
  classification: tscExitCode === 0 ? 'clean' : 'known-outside-code-debt',
  ok,
}

await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
if (!ok) process.exitCode = 1
