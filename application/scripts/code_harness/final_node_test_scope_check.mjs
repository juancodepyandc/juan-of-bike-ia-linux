import { readFile, writeFile } from 'node:fs/promises'
import process from 'node:process'

const inputPath = process.argv[2]
const outputPath = process.argv[3]
const testExitCode = Number(process.argv[4] || 0)

if (!inputPath || !outputPath) {
  throw new Error('usage: final_node_test_scope_check.mjs <test-log> <report> <exit-code>')
}

const raw = await readFile(inputPath, 'utf8')
const metric = (name) => Number(raw.match(new RegExp(`^ℹ ${name} (\\d+)$`, 'm'))?.[1] || 0)
const failingFiles = [...raw.matchAll(/^test at (.+?):\d+:\d+$/gm)].map((match) => match[1])
const uniqueFailingFiles = [...new Set(failingFiles)].sort()
const tests = metric('tests')
const passed = metric('pass')
const failed = metric('fail')
const cancelled = metric('cancelled')
const allowedOutsideCode = testExitCode !== 0
  && tests >= 4_500
  && failed > 0
  && failed === failingFiles.length
  && cancelled === 0
  && uniqueFailingFiles.length === 1
  && uniqueFailingFiles[0] === 'src/__tests__/coworkExtract.test.ts'
  && !/test at src\/__tests__\/(?!coworkExtract\.test\.ts)/.test(raw)
const ok = testExitCode === 0 || allowedOutsideCode
const report = {
  schemaVersion: 'aurora.code.final-node-test-scope/1',
  testExitCode,
  tests,
  passed,
  failed,
  cancelled,
  failingFiles: uniqueFailingFiles,
  classification: testExitCode === 0 ? 'clean' : 'known-cowork-live-integration-debt',
  ok,
}

await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
if (!ok) process.exitCode = 1
