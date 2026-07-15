import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { accessibilityCritic, compositeStaticCritic, securityCritic } from '../services/codeStaticCritics.ts'
import { deterministicPatcher, patchWithLog } from '../services/codeDeterministicPatcher.ts'
import { runCritiqueLoop } from '../services/codeMultiPassCritique.ts'
import type { CodeProject } from '../services/codeMultiPassCritique.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

const fakeIntent = {} as CodeIntent

const project = (files: Array<{ name: string; language: string; content: string }>): CodeProject => ({
  generationId: 'test', files,
})

const INACCESSIBLE_TSX = `
export function Bad() {
  return (
    <div>
      <img src="/logo.png" />
      <a onClick={() => alert('clicked')}>cliquez ici</a>
      <input type="text" />
      <button><svg width="12" /></button>
    </div>
  )
}
`.trim()

describe('boucle réelle critic+patcher — convergence', () => {
  test('a11y issues fixées en 1 passe', async () => {
    const broken = project([{ name: 'bad.tsx', language: 'tsx', content: INACCESSIBLE_TSX }])
    const beforeReport = await accessibilityCritic(broken, fakeIntent)
    const before = beforeReport.scores.accessibility

    const { project: patched, outcomes } = await patchWithLog(broken, fakeIntent, beforeReport)
    const afterReport = await accessibilityCritic(patched, fakeIntent)
    const after = afterReport.scores.accessibility

    assert.ok(after > before, `pas d'amélioration: avant ${before}, après ${after}`)
    assert.ok(outcomes['bad.tsx'].fixesApplied.length >= 2, `seulement ${outcomes['bad.tsx'].fixesApplied.length} fix(es)`)
  })

  test('shell=True + verify=False patchés en 1 passe', async () => {
    const py = `
import subprocess
import requests

subprocess.run(['ls'], shell=True)
requests.get('https://api.example.com', verify=False)
`.trim()
    const broken = project([{ name: 'bad.py', language: 'py', content: py }])
    const { project: patched } = await patchWithLog(broken, fakeIntent, await securityCritic(broken, fakeIntent))
    assert.ok(!/shell=True/.test(patched.files[0].content))
    assert.ok(!/verify=False/.test(patched.files[0].content))
    const after = await securityCritic(patched, fakeIntent)
    assert.ok(after.scores.security > 0.7, `security après patch ${after.scores.security}`)
  })

  test('runCritiqueLoop avec critics statiques converge vers threshold', async () => {
    const py = `
import subprocess
subprocess.run(cmd, shell=True)
`.trim()
    const broken = project([{ name: 'bad.py', language: 'py', content: py }])
    const result = await runCritiqueLoop(broken, fakeIntent, compositeStaticCritic, deterministicPatcher, {
      maxPasses: 3,
      thresholds: { required: { security: 0.8 }, overall: 0.85 },
    })
    assert.ok(result.thresholdMet, `stopReason ${result.stopReason}, passes ${result.passesUsed}, final ${JSON.stringify(result.finalReport.scores)}`)
    assert.ok(result.passesUsed <= 3)
  })

  test('code irréparable s\'arrête sur max-passes sans crasher', async () => {
    // Erreur de syntaxe (bracket mismatch) que le patcher ne sait PAS fixer.
    const broken = project([{ name: 'x.ts', language: 'ts', content: 'function f() { return (1 + 2' }])
    const result = await runCritiqueLoop(broken, fakeIntent, compositeStaticCritic, deterministicPatcher, { maxPasses: 3 })
    // On veut soit max-passes soit no-improvement, pas threshold-met.
    assert.notEqual(result.stopReason, 'threshold-met')
    assert.ok(result.passesUsed > 0)
  })

  test('multi-issues : ≥ 60 % des issues fixables sont corrigées par le patcher', async () => {
    // Génère un projet avec 6 issues fixables par le patcher déterministe :
    //   - img sans alt          → alt=""
    //   - <a>+onClick sans href → role/tabIndex
    //   - document.write        → console.warn
    //   - shell=True            → False
    //   - verify=False          → True
    //   - hashlib.md5           → sha256
    const tsx = `
export function Bad() {
  return (
    <div>
      <img src="/x" />
      <a onClick={() => alert('x')}>cliquez ici</a>
    </div>
  )
}
document.write('hello')
`.trim()
    const py = `
import subprocess
import requests
import hashlib
subprocess.run(['ls'], shell=True)
requests.get('https://x', verify=False)
hashlib.md5(b'pwd').hexdigest()
`.trim()
    const broken = project([
      { name: 'bad.tsx', language: 'tsx', content: tsx },
      { name: 'bad.py', language: 'py', content: py },
    ])
    const before = await compositeStaticCritic(broken, fakeIntent)
    const beforeIssues = before.issues.length
    assert.ok(beforeIssues >= 5, `attendu ≥ 5 issues, eu ${beforeIssues}`)

    // 1 passe du patcher
    const { project: patched } = await patchWithLog(broken, fakeIntent, before)
    const after = await compositeStaticCritic(patched, fakeIntent)
    const fixed = beforeIssues - after.issues.length
    const ratio = fixed / beforeIssues
    assert.ok(ratio >= 0.6, `seulement ${(ratio * 100).toFixed(0)}% des issues fixées (${fixed}/${beforeIssues})`)
  })

  test('runCritiqueLoop sur multi-issues converge : security passe de < 0.6 à 1.0', async () => {
    const py = `
import subprocess
import requests
import hashlib
subprocess.run(['ls'], shell=True)
requests.get('https://x', verify=False)
hashlib.md5(b'pwd').hexdigest()
`.trim()
    const broken = project([{ name: 'bad.py', language: 'py', content: py }])
    const beforeReport = await compositeStaticCritic(broken, fakeIntent)
    assert.ok(beforeReport.scores.security < 0.6, `security avant devrait être < 0.6, obtenu ${beforeReport.scores.security}`)

    const result = await runCritiqueLoop(broken, fakeIntent, compositeStaticCritic, deterministicPatcher, {
      maxPasses: 3,
      thresholds: { required: { security: 0.95 }, overall: 0.95 },
    })
    assert.equal(result.thresholdMet, true, `stopReason ${result.stopReason}, scores ${JSON.stringify(result.finalReport.scores)}`)
    assert.ok(result.finalReport.scores.security >= 0.95, `security après ${result.finalReport.scores.security}`)
    // L'overall doit aussi avoir monté (au moins 5 % d'amélioration).
    const overallGain = result.finalReport.overallScore - beforeReport.overallScore
    assert.ok(overallGain >= 0.05, `overall gain insuffisant Δ${overallGain.toFixed(3)}`)
  })

  test('blocker plafonne l\'overall à 0.5 (eval bloque l\'export)', async () => {
    const ts = `eval(userInput)`
    const r = await compositeStaticCritic(project([{ name: 'evil.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.equal(r.hasBlocker, true)
    assert.ok(r.overallScore <= 0.5, `blocker mais overall ${r.overallScore}`)
  })

  test('complexity critic : fonction CC > 60 → blocker', async () => {
    // Génère 70 if pour dépasser le seuil "ingérable".
    let body = ''
    for (let i = 0; i < 70; i += 1) body += `  if (x === ${i}) return ${i}\n`
    const code = `function bigSwitch(x: number) {\n${body}  return -1\n}`
    const { complexityCritic } = await import('../services/codeStaticCritics.ts')
    const r = await complexityCritic(project([{ name: 'big.ts', language: 'ts', content: code }]), fakeIntent)
    assert.equal(r.hasBlocker, true)
  })

  test('complexity critic : fonction simple → pas d\'issue', async () => {
    const code = `function add(a: number, b: number) { return a + b }`
    const { complexityCritic } = await import('../services/codeStaticCritics.ts')
    const r = await complexityCritic(project([{ name: 'simple.ts', language: 'ts', content: code }]), fakeIntent)
    assert.equal(r.issues.length, 0)
  })
})
