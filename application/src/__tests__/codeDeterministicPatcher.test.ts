/**
 * Tests pour services/codeDeterministicPatcher — fixes regex sans LLM.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  deterministicPatcher,
  patchWithLog,
} from '../services/codeDeterministicPatcher.ts'
import type { CodeProject, CritiqueReport } from '../services/codeMultiPassCritique.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

const intent = classifyCodeIntent('app react')
const emptyReport: CritiqueReport = {
  scores: { compile: 1, lint: 1, tests: 1, fidelity: 1, runtime: 1, preview: 1, security: 1, accessibility: 1, perf: 1 },
  overallScore: 1,
  issues: [],
  hasBlocker: false,
}

function project(files: { name: string; language: string; content: string }[]): CodeProject {
  return { files, generationId: 'test' }
}

describe('deterministicPatcher — img sans alt', () => {
  test('<img src="x"> → ajoute alt=""', async () => {
    const out = await deterministicPatcher(
      project([{ name: 'a.html', language: 'markup', content: '<img src="x.jpg">' }]),
      intent, emptyReport,
    )
    assert.ok(out.files[0].content.includes('alt=""'))
  })

  test('<img alt="déjà"> → inchangé', async () => {
    const original = '<img src="x.jpg" alt="déjà là">'
    const out = await deterministicPatcher(
      project([{ name: 'a.html', language: 'markup', content: original }]),
      intent, emptyReport,
    )
    assert.equal(out.files[0].content, original)
  })
})

describe('deterministicPatcher — <a> onClick sans href', () => {
  test('<a onClick=...> → ajoute role="button" + tabIndex=0', async () => {
    const out = await deterministicPatcher(
      project([{ name: 'App.jsx', language: 'jsx', content: '<a onClick={() => {}}>Cliquer</a>' }]),
      intent, emptyReport,
    )
    assert.ok(out.files[0].content.includes('role="button"'))
    assert.ok(out.files[0].content.includes('tabIndex={0}'))
  })

  test('<a href="x" onClick=...> → inchangé', async () => {
    const original = '<a href="x.html" onClick={() => {}}>Lien</a>'
    const out = await deterministicPatcher(
      project([{ name: 'App.jsx', language: 'jsx', content: original }]),
      intent, emptyReport,
    )
    assert.equal(out.files[0].content, original)
  })
})

describe('deterministicPatcher — document.write', () => {
  test('document.write(...) → commenté + console.warn', async () => {
    const out = await deterministicPatcher(
      project([{ name: 'app.js', language: 'javascript', content: 'document.write("hello")' }]),
      intent, emptyReport,
    )
    assert.ok(out.files[0].content.includes('console.warn'))
    assert.ok(!out.files[0].content.match(/^document\.write\s*\(/))
  })
})

describe('deterministicPatcher — shell=True', () => {
  test('subprocess shell=True → shell=False', async () => {
    const out = await deterministicPatcher(
      project([{ name: 'a.py', language: 'python', content: 'subprocess.run("ls", shell=True)' }]),
      intent, emptyReport,
    )
    assert.ok(out.files[0].content.includes('shell=False'))
  })
})

describe('deterministicPatcher — verify=False', () => {
  test('requests verify=False → verify=True', async () => {
    const out = await deterministicPatcher(
      project([{ name: 'a.py', language: 'python', content: 'requests.get(url, verify=False)' }]),
      intent, emptyReport,
    )
    assert.ok(out.files[0].content.includes('verify=True'))
  })
})

describe('deterministicPatcher — hashlib.md5', () => {
  test('hashlib.md5(...) → hashlib.sha256', async () => {
    const out = await deterministicPatcher(
      project([{ name: 'a.py', language: 'python', content: 'h = hashlib.md5(data)' }]),
      intent, emptyReport,
    )
    assert.ok(out.files[0].content.includes('sha256'))
    assert.ok(!out.files[0].content.includes('md5'))
  })
})

describe('deterministicPatcher — Math.random pour token', () => {
  test('Math.random près de "token" → crypto.getRandomValues', async () => {
    const code = 'const token = Math.random()'
    const out = await deterministicPatcher(
      project([{ name: 'a.js', language: 'javascript', content: code }]),
      intent, emptyReport,
    )
    assert.ok(out.files[0].content.includes('crypto.getRandomValues') || out.files[0].content.includes('Uint32Array'))
  })

  test('Math.random loin de "token" → inchangé', async () => {
    const code = 'const x = Math.random() * 100;'
    const out = await deterministicPatcher(
      project([{ name: 'a.js', language: 'javascript', content: code }]),
      intent, emptyReport,
    )
    assert.equal(out.files[0].content, code)
  })

  test('Math.random près de "secret"', async () => {
    const code = 'const mySecret = Math.random();'
    const out = await deterministicPatcher(
      project([{ name: 'a.js', language: 'javascript', content: code }]),
      intent, emptyReport,
    )
    assert.ok(out.files[0].content.includes('crypto.getRandomValues') || out.files[0].content.includes('Uint32Array'))
  })
})

describe('deterministicPatcher — pas de fix', () => {
  test('code propre → inchangé', async () => {
    const code = 'const x = 1;\nconsole.log(x);'
    const out = await deterministicPatcher(
      project([{ name: 'a.js', language: 'javascript', content: code }]),
      intent, emptyReport,
    )
    assert.equal(out.files[0].content, code)
  })

  test('fichiers vides → inchangé', async () => {
    const out = await deterministicPatcher(
      project([{ name: 'a.js', language: 'javascript', content: '' }]),
      intent, emptyReport,
    )
    assert.equal(out.files[0].content, '')
  })

  test('plusieurs fichiers → tous traités', async () => {
    const out = await deterministicPatcher(
      project([
        { name: 'a.js', language: 'javascript', content: 'const x = 1;' },
        { name: 'b.py', language: 'python', content: 'shell=True' },
      ]),
      intent, emptyReport,
    )
    assert.equal(out.files.length, 2)
    assert.ok(out.files[1].content.includes('shell=False'))
  })
})

describe('patchWithLog', () => {
  test('renvoie outcomes par fichier', async () => {
    const { project: p, outcomes } = await patchWithLog(
      project([
        { name: 'a.py', language: 'python', content: 'shell=True' },
        { name: 'b.js', language: 'javascript', content: 'const x = 1;' },
      ]),
      intent, emptyReport,
    )
    assert.ok(outcomes['a.py'].changed)
    assert.ok(outcomes['a.py'].fixesApplied.length > 0)
    assert.equal(outcomes['b.js'].changed, false)
    assert.equal(outcomes['b.js'].fixesApplied.length, 0)
    assert.equal(p.files.length, 2)
  })

  test('fixesApplied liste les corrections', async () => {
    const { outcomes } = await patchWithLog(
      project([{ name: 'a.py', language: 'python', content: 'hashlib.md5(data)\nshell=True' }]),
      intent, emptyReport,
    )
    assert.ok(outcomes['a.py'].fixesApplied.some((f) => f.includes('md5')))
    assert.ok(outcomes['a.py'].fixesApplied.some((f) => f.includes('shell')))
  })

  test('plusieurs fixes sur même fichier cumulés', async () => {
    const { outcomes } = await patchWithLog(
      project([{
        name: 'a.py', language: 'python',
        content: 'shell=True\nverify=False\nhashlib.md5(data)',
      }]),
      intent, emptyReport,
    )
    assert.ok(outcomes['a.py'].fixesApplied.length >= 3)
  })
})

describe('deterministicPatcher — generationId préservé', () => {
  test('generationId du project conservé', async () => {
    const p: CodeProject = { files: [{ name: 'a.js', language: 'js', content: 'const x = 1;' }], generationId: 'abc-123' }
    const out = await deterministicPatcher(p, intent, emptyReport)
    assert.equal(out.generationId, 'abc-123')
  })
})
