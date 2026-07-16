import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  accessibilityCritic,
  complexityCritic,
  compositeStaticCritic,
  securityCritic,
  syntaxCritic,
} from '../services/codeStaticCritics.ts'
import type { CodeProject } from '../services/codeMultiPassCritique.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

const fakeIntent = {} as CodeIntent

function project(files: Array<{ name: string; language: string; content: string }>): CodeProject {
  return { generationId: 'static-audit', files }
}

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

describe('critics statiques actifs', () => {
  test('detecte plusieurs defauts accessibilite dans un fichier', async () => {
    const report = await accessibilityCritic(project([
      { name: 'bad.tsx', language: 'tsx', content: INACCESSIBLE_TSX },
    ]), fakeIntent)
    assert.ok(report.scores.accessibility < 1)
    assert.ok(report.issues.length >= 2)
  })

  test('detecte shell=True et verify=False sans les modifier', async () => {
    const content = [
      'import subprocess',
      'import requests',
      "subprocess.run(['ls'], shell=True)",
      "requests.get('https://api.example.com', verify=False)",
    ].join('\n')
    const report = await securityCritic(project([{ name: 'bad.py', language: 'py', content }]), fakeIntent)
    assert.ok(report.scores.security < 0.8)
    assert.ok(report.issues.length >= 2)
  })

  test('le critic composite relaie un incident de securite', async () => {
    const report = await compositeStaticCritic(project([
      { name: 'bad.py', language: 'py', content: 'subprocess.run(cmd, shell=True)' },
    ]), fakeIntent)
    assert.ok(report.scores.security < 1)
    assert.ok(report.issues.some((issue) => issue.axis === 'security'))
  })

  test('une syntaxe non fermee reste un echec explicite', async () => {
    const report = await syntaxCritic(project([
      { name: 'x.ts', language: 'ts', content: 'function f() { return (1 + 2' },
    ]), fakeIntent)
    assert.ok(report.scores.compile < 1)
    assert.ok(report.issues.length > 0)
  })

  test('rapporte un ensemble multi-fichiers de defauts', async () => {
    const tsx = `${INACCESSIBLE_TSX}\ndocument.write('hello')`
    const py = [
      'import hashlib',
      "subprocess.run(['ls'], shell=True)",
      "requests.get('https://x', verify=False)",
      "hashlib.md5(b'pwd').hexdigest()",
    ].join('\n')
    const report = await compositeStaticCritic(project([
      { name: 'bad.tsx', language: 'tsx', content: tsx },
      { name: 'bad.py', language: 'py', content: py },
    ]), fakeIntent)
    assert.ok(report.issues.length >= 5)
  })

  test('un groupe de primitives Python dangereuses abaisse fortement la securite', async () => {
    const content = [
      "subprocess.run(['ls'], shell=True)",
      "requests.get('https://x', verify=False)",
      "hashlib.md5(b'pwd').hexdigest()",
    ].join('\n')
    const report = await compositeStaticCritic(project([{ name: 'bad.py', language: 'py', content }]), fakeIntent)
    assert.ok(report.scores.security < 0.6)
  })

  test('eval bloque l export et plafonne le score', async () => {
    const report = await compositeStaticCritic(project([
      { name: 'evil.ts', language: 'ts', content: 'eval(userInput)' },
    ]), fakeIntent)
    assert.equal(report.hasBlocker, true)
    assert.ok(report.overallScore <= 0.5)
  })

  test('une God-function de complexite elevee devient bloquante', async () => {
    let body = ''
    for (let index = 0; index < 70; index += 1) body += `  if (x === ${index}) return ${index}\n`
    const content = `function bigSwitch(x: number) {\n${body}  return -1\n}`
    const report = await complexityCritic(project([{ name: 'big.ts', language: 'ts', content }]), fakeIntent)
    assert.equal(report.hasBlocker, true)
  })

  test('une fonction simple ne produit pas de faux positif de complexite', async () => {
    const report = await complexityCritic(project([
      { name: 'simple.ts', language: 'ts', content: 'function add(a: number, b: number) { return a + b }' },
    ]), fakeIntent)
    assert.equal(report.issues.length, 0)
  })

  test('un fragment accessible conserve le score maximal', async () => {
    const content = '<main><h1>Produit</h1><img src="/product.avif" alt="Produit"></main>'
    const report = await accessibilityCritic(project([{ name: 'good.html', language: 'html', content }]), fakeIntent)
    assert.equal(report.scores.accessibility, 1)
  })

  test('rapporte les occurrences dangereuses dans plusieurs fichiers', async () => {
    const report = await securityCritic(project([
      { name: 'a.ts', language: 'ts', content: 'eval(first)' },
      { name: 'b.ts', language: 'ts', content: 'eval(second)' },
    ]), fakeIntent)
    assert.ok(report.issues.filter((issue) => issue.severity === 'block').length >= 2)
  })
})
