/**
 * Tests "barre expert" pour les critics statiques.
 *
 * Règle : pour chaque critic, je définis 1 bon échantillon et 1 mauvais.
 * Le critic est validé SEULEMENT si :
 *   - le bon code reçoit score ≥ 0.9 ET aucun blocker
 *   - le mauvais code reçoit score ≤ 0.5 OU au moins un blocker
 *
 * Si le seuil n'est pas atteint, c'est le critic qui est mauvais, pas le test.
 * J'itère jusqu'à ce que la barre soit franchie.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  accessibilityCritic,
  compositeStaticCritic,
  deliverableCompletenessCritic,
  projectIntegrityCritic,
  securityCritic,
  structureCritic,
  syntaxCritic,
} from '../services/codeStaticCritics.ts'
import type { CodeProject } from '../services/codeMultiPassCritique.ts'
import { classifyCodeIntent, type CodeIntent } from '../services/codeIntent.ts'

const fakeIntent = {} as CodeIntent

const project = (files: Array<{ name: string; language: string; content: string }>): CodeProject => ({
  generationId: 'test', files,
})

// --- Bonnes pratiques ------------------------------------------------------
const GOOD_TS = `
import { useState } from 'react'

export function Counter() {
  const [count, setCount] = useState(0)
  return (
    <button aria-label="incrementer" onClick={() => setCount(c => c + 1)}>
      compteur: {count}
    </button>
  )
}
`.trim()

const GOOD_PY = `
import json
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    args = parser.parse_args()
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
`.trim()

// --- Mauvaises pratiques ---------------------------------------------------
const BROKEN_SYNTAX_TS = `
function hello() {
  const x = (1 + 2
  return x
}
`.trim()

const INSECURE_TS = `
const userInput = location.hash
document.querySelector('#out').innerHTML = '<p>' + userInput + '</p>'
eval(userInput)
const apiKey = "sk-prod-abcdef123456ghijkl"
`.trim()

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

const HUGE_FILE_TS = (() => {
  const body = 'const a' + 'a'.repeat(5) + ' = 1\n'
  return body.repeat(1700)
})()

describe('syntaxCritic — barre expert', () => {
  test('bon code TypeScript ≥ 0.9, pas de blocker', async () => {
    const r = await syntaxCritic(project([{ name: 'a.tsx', language: 'tsx', content: GOOD_TS }]), fakeIntent)
    assert.ok(r.scores.compile >= 0.9, `score ${r.scores.compile}`)
    assert.equal(r.hasBlocker, false)
  })

  test('bon code Python ≥ 0.9', async () => {
    const r = await syntaxCritic(project([{ name: 'main.py', language: 'py', content: GOOD_PY }]), fakeIntent)
    assert.ok(r.scores.compile >= 0.9)
  })

  test('parens non équilibrés ↦ blocker + score 0', async () => {
    const r = await syntaxCritic(project([{ name: 'broken.ts', language: 'ts', content: BROKEN_SYNTAX_TS }]), fakeIntent)
    assert.equal(r.hasBlocker, true)
    assert.equal(r.scores.compile, 0)
  })

  test('fichier vide ↦ score < 1', async () => {
    const r = await syntaxCritic(project([{ name: 'empty.ts', language: 'ts', content: '' }]), fakeIntent)
    assert.ok(r.scores.compile < 1)
  })

  test('brackets dans strings, regex et templates ne déclenchent pas de blocker', async () => {
    const code = [
      'function ok() {',
      '  const a = "{[(])}"',
      '  const b = /[({})]/g',
      '  const c = `template } { [ )`',
      '  return a + String(b) + c',
      '}',
    ].join('\n')
    const r = await syntaxCritic(project([{ name: 'literals.ts', language: 'ts', content: code }]), fakeIntent)
    assert.equal(r.hasBlocker, false, JSON.stringify(r.issues))
    assert.ok(!r.issues.some((i) => /non équilibrés/.test(i.message)), JSON.stringify(r.issues))
  })
})

describe('securityCritic — barre expert', () => {
  test('code propre ≥ 0.95', async () => {
    const r = await securityCritic(project([{ name: 'a.tsx', language: 'tsx', content: GOOD_TS }]), fakeIntent)
    assert.ok(r.scores.security >= 0.95, `score ${r.scores.security}, issues ${JSON.stringify(r.issues)}`)
  })

  test('code avec eval + innerHTML + secret ↦ score ≤ 0.5 ou blocker', async () => {
    const r = await securityCritic(project([{ name: 'bad.ts', language: 'ts', content: INSECURE_TS }]), fakeIntent)
    assert.ok(r.hasBlocker || r.scores.security <= 0.5, `score ${r.scores.security}, hasBlocker ${r.hasBlocker}`)
    // Doit avoir détecté au moins 3 issues distinctes (eval, innerHTML+concat, secret).
    assert.ok(r.issues.length >= 3, `issues count ${r.issues.length}`)
  })

  test('data-flow taint détecte les alias sans nom req/input', async () => {
    const ts = `
const params = new URLSearchParams(location.search)
const next = params.get('next')
fetch(next)
document.querySelector('#out')!.innerHTML = next
`.trim()
    const r = await securityCritic(project([{ name: 'taint.ts', language: 'ts', content: ts }]), fakeIntent)
    const taintIssues = r.issues.filter((i) => /Data-flow taint/i.test(i.message))
    assert.ok(taintIssues.some((i) => /network URL sink/i.test(i.message)), JSON.stringify(r.issues))
    assert.ok(taintIssues.some((i) => /DOM HTML sink/i.test(i.message)), JSON.stringify(r.issues))
  })

  test('toutes les occurrences eval sont rapportées', async () => {
    const ts = `eval('a')\neval('b')\n`
    const r = await securityCritic(project([{ name: 'multi.ts', language: 'ts', content: ts }]), fakeIntent)
    const evalIssues = r.issues.filter((i) => /Usage de eval/.test(i.message))
    assert.equal(evalIssues.length, 2, JSON.stringify(r.issues))
    assert.deepEqual(evalIssues.map((i) => i.location?.line), [1, 2])
  })

  test('shell=True python détecté', async () => {
    const py = `import subprocess\nsubprocess.run(cmd, shell=True)\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(r.scores.security < 1)
    assert.ok(r.issues.some((i) => i.message.includes('shell=True')))
  })

  test('TLS verify=False détecté', async () => {
    const py = `import requests\nrequests.get('https://x', verify=False)\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(r.issues.some((i) => i.message.toLowerCase().includes('verify')))
  })

  test('hashlib md5 password détecté', async () => {
    const py = `import hashlib\nhashlib.md5(password.encode()).hexdigest()\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(r.issues.some((i) => /md5|sha-1|sha1/i.test(i.message)))
  })

  test('new Function() détecté', async () => {
    const ts = `const f = new Function('return 1')\n`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /new Function/i.test(i.message)))
  })

  test('path traversal détecté', async () => {
    const ts = `import fs from 'fs'\nconst p = baseDir + '../etc/passwd'\nfs.readFile(p)\n`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /traversal/i.test(i.message)))
  })

  test('SSRF via fetch + req.params détecté', async () => {
    const ts = `fetch('https://internal.api/' + req.params.host)\n`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /SSRF/i.test(i.message)))
  })

  test('prototype pollution Object.assign({}, req.body) détecté', async () => {
    const ts = `const merged = Object.assign({}, req.body)\n`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /prototype pollution/i.test(i.message)))
  })

  test('ReDoS via RegExp + input détecté', async () => {
    const ts = `const re = new RegExp('^.*' + req.body.pattern + '$')\n`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /ReDoS/i.test(i.message)))
  })

  test('open redirect détecté', async () => {
    const ts = `window.location.href = req.query.next\n`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /redirect/i.test(i.message)))
  })

  test('document.cookie direct flaggé warn', async () => {
    const ts = `document.cookie = 'auth=' + token\n`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /cookie/i.test(i.message)))
  })

  test('JSON.parse(localStorage...) flaggé warn', async () => {
    const ts = `const data = JSON.parse(localStorage.getItem('cache'))\n`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /JSON\.parse/i.test(i.message)))
  })

  test('SQL injection par concaténation détectée (block)', async () => {
    const ts = `db.query('SELECT * FROM users WHERE id=' + userId)`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /SQL injection/i.test(i.message)))
    assert.equal(r.hasBlocker, true)
  })

  test('NoSQL $where + input détecté', async () => {
    const ts = `db.find({ $where: 'this.user==' + req.params.id })`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /NoSQL/i.test(i.message)))
  })

  test('IDOR route :userId flag warn', async () => {
    const ts = `app.get('/api/users/:userId/profile', handler)`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /IDOR/i.test(i.message)))
  })

  test('Header injection setHeader + req détecté', async () => {
    const ts = `res.setHeader('X-Redirect', req.query.url)`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /header injection|CRLF/i.test(i.message)))
  })

  test('CORS wildcard détecté', async () => {
    const ts = `res.setHeader('Access-Control-Allow-Origin', '*')`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /CORS/i.test(i.message)))
  })

  test('LDAP injection détecté', async () => {
    const ts = `const filter = 'cn=' + req.body.username + ')'`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /LDAP/i.test(i.message)))
  })

  test('http:// sur endpoint sensible détecté', async () => {
    const ts = `fetch('http://api.example.com/login', { method: 'POST' })`
    const r = await securityCritic(project([{ name: 'a.ts', language: 'ts', content: ts }]), fakeIntent)
    assert.ok(r.issues.some((i) => /TLS|http:/i.test(i.message)))
  })

  test('mutable default arg détecté (Python)', async () => {
    const py = `def add(item, items=[]):\n    items.append(item)\n    return items\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(r.issues.some((i) => /mutable/i.test(i.message)))
  })

  test('except: pass détecté', async () => {
    const py = `try:\n    x = 1\nexcept:\n    pass\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(r.issues.some((i) => /except: pass/i.test(i.message)))
  })

  test('os.system + concat → block', async () => {
    const py = `os.system('cat ' + filename)\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(r.issues.some((i) => /os\.system|injection de commande/i.test(i.message)))
    assert.equal(r.hasBlocker, true)
  })

  test('yaml.load sans Loader détecté', async () => {
    const py = `import yaml\ndata = yaml.load(stream)\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(r.issues.some((i) => /yaml/i.test(i.message)))
  })

  test('yaml.safe_load ne déclenche pas l\'alerte', async () => {
    const py = `import yaml\ndata = yaml.safe_load(stream)\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(!r.issues.some((i) => /yaml/i.test(i.message)))
  })

  test('execute("...%s..." % var) Python SQLi détecté', async () => {
    const py = `cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(r.issues.some((i) => /SQL injection|SQLi/i.test(i.message)))
    assert.equal(r.hasBlocker, true)
  })

  test('print debug oublié détecté', async () => {
    const py = `print("DEBUG: value =", x)\n`
    const r = await securityCritic(project([{ name: 'a.py', language: 'py', content: py }]), fakeIntent)
    assert.ok(r.issues.some((i) => /debug/i.test(i.message)))
  })

  test('NOMBRE total de règles ≥ 18 (couverture OWASP étendue)', async () => {
    // Test "à la barre" : si on retire une règle, ça doit casser ce test.
    // On compose un fichier avec 1 hit par règle.
    const combo = `
eval('x')
new Function('return 1')
document.write('hi')
const r = Math.random()
const apiKey = "sk-prod-abcdef123456"
const p = baseDir + '../etc/passwd'
fetch('https://x.com/' + req.params.id)
const m = Object.assign({}, req.body)
const re = new RegExp('a' + req.body.p)
const d = JSON.parse(localStorage.getItem('k'))
window.location.href = req.query.next
document.cookie = 'a=' + 'b'
`.trim()
    const r = await securityCritic(project([{ name: 'all.ts', language: 'ts', content: combo }]), fakeIntent)
    assert.ok(r.issues.length >= 8, `seulement ${r.issues.length} issues détectées dans le combo (${r.issues.map((i) => i.message).join(' | ')})`)
  })
})

describe('deliverableCompletenessCritic — anti sortie pauvre', () => {
  test('app client complete livree en un seul fichier est bloquee', async () => {
    const intent = classifyCodeIntent(
      'application complete client CRM avec dashboard, recherche, notifications, workflow, UI pro, tunnel et pas de fichier independant',
    )
    const poor = project([{
      name: 'src/App.tsx',
      language: 'tsx',
      content: GOOD_TS,
    }])
    const r = await deliverableCompletenessCritic(poor, intent)
    assert.equal(r.hasBlocker, true)
    assert.ok(r.scores.fidelity <= 0.5, `fidelity ${r.scores.fidelity}`)
    assert.ok(r.issues.some((i) => /Livrable trop petit|package\.json|Tauri incomplete/i.test(i.message)))
  })

  test('CLI complet sans parser ni verification est refuse', async () => {
    const intent = classifyCodeIntent('outil CLI Python complet pour analyser des logs avec sous-commandes, export CSV, config et tests')
    const poor = project([
      { name: 'main.py', language: 'py', content: 'print("analyse logs")\n' },
      { name: 'README.md', language: 'md', content: 'Usage rapide\n' },
      { name: 'config.json', language: 'json', content: '{"level":"info"}\n' },
    ])
    const r = await deliverableCompletenessCritic(poor, intent)
    assert.ok(r.issues.some((i) => /Livrable trop petit|parser d arguments/i.test(i.message)), JSON.stringify(r.issues))
    assert.ok(r.scores.fidelity < 1)
  })

  test('SPA structuree avec package, src et styles passe le critic de completude', async () => {
    const intent = classifyCodeIntent('dashboard React admin analytics avec filtres, CRUD utilisateurs, responsive et dev-server')
    const good = project([
      { name: 'package.json', language: 'json', content: '{"scripts":{"dev":"vite","build":"vite build"},"dependencies":{"@vitejs/plugin-react":"latest","vite":"latest","react":"latest","react-dom":"latest"}}' },
      { name: 'index.html', language: 'html', content: '<div id="root"></div><script type="module" src="/src/main.tsx"></script>' },
      { name: 'src/main.tsx', language: 'tsx', content: 'import React from "react"; import { createRoot } from "react-dom/client"; import { App } from "./App"; createRoot(document.getElementById("root")!).render(<App />)' },
      { name: 'src/App.tsx', language: 'tsx', content: GOOD_TS },
      { name: 'src/styles.css', language: 'css', content: 'body{font-family:sans-serif}' },
      { name: 'src/data/users.ts', language: 'ts', content: 'export const users = []' },
      { name: 'src/services/api.ts', language: 'ts', content: 'export async function listUsers(){ return [] }' },
      { name: 'README.md', language: 'md', content: 'npm run dev' },
    ])
    const r = await deliverableCompletenessCritic(good, intent)
    assert.equal(r.hasBlocker, false)
    assert.equal(r.issues.length, 0)
  })
})

describe('projectIntegrityCritic - recevabilite client web', () => {
  test('SPA avec imports locaux absents est bloquee avant export', async () => {
    const intent = classifyCodeIntent('vraie web app React dashboard avec recherche, routing et favoris persistants')
    const broken = project([
      { name: 'package.json', language: 'json', content: '{"scripts":{"build":"tsc && vite build"},"dependencies":{"@vitejs/plugin-react":"latest","vite":"latest","react":"latest","react-dom":"latest","react-router-dom":"latest"}}' },
      { name: 'src/App.tsx', language: 'tsx', content: `
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import './index.css'

export default function App() {
  return <><Home /><Dashboard /></>
}
`.trim() },
      { name: 'src/index.css', language: 'css', content: 'body { margin: 0; }' },
    ])
    const r = await projectIntegrityCritic(broken, intent)
    assert.equal(r.hasBlocker, true)
    assert.ok(r.issues.some((i) => /import local introuvable.*\.\/pages\/Home/i.test(i.message)), JSON.stringify(r.issues))
    assert.equal(r.scores.compile, 0)
  })

  test('dependance npm importee mais absente du package.json est bloquee', async () => {
    const intent = classifyCodeIntent('web app React dashboard avec editeur de regles et icones')
    const broken = project([
      { name: 'package.json', language: 'json', content: '{"scripts":{"build":"tsc && vite build"},"dependencies":{"react":"latest","react-dom":"latest"},"devDependencies":{"vite":"latest"}}' },
      { name: 'src/RulesEditorPage.tsx', language: 'tsx', content: `
import React from 'react'
import { FiPlus } from 'react-icons/fi'

export default function RulesEditorPage() {
  return <button><FiPlus />Ajouter</button>
}
`.trim() },
    ])
    const r = await projectIntegrityCritic(broken, intent)
    assert.equal(r.hasBlocker, true)
    assert.ok(r.issues.some((i) => /dependance npm.*react-icons/i.test(i.message)), JSON.stringify(r.issues))
    assert.equal(r.scores.compile, 0)
  })

  test('classes Tailwind sans Tailwind ni CSS correspondant sont refusees', async () => {
    const intent = classifyCodeIntent('web app React premium responsive avec dashboard')
    const broken = project([
      { name: 'package.json', language: 'json', content: '{"dependencies":{"react":"latest","react-dom":"latest"},"devDependencies":{"vite":"latest"}}' },
      { name: 'src/App.tsx', language: 'tsx', content: `
export default function App() {
  return <main className="min-h-screen flex flex-col bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 px-4 py-8 mx-auto max-w-6xl gap-6 rounded-xl shadow-lg">
    <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <button className="inline-flex items-center justify-center rounded-full bg-blue-600 text-white px-4 py-2 hover:bg-blue-700 transition">OK</button>
    </section>
  </main>
}
`.trim() },
    ])
    const r = await projectIntegrityCritic(broken, intent)
    assert.equal(r.hasBlocker, false)
    assert.ok(r.issues.some((i) => /Tailwind/i.test(i.message)), JSON.stringify(r.issues))
    assert.ok(r.scores.preview < 1)
  })

  test('Tailwind configure ne declenche pas le rejet utilitaire', async () => {
    const intent = classifyCodeIntent('web app React premium responsive avec dashboard')
    const good = project([
      { name: 'package.json', language: 'json', content: '{"dependencies":{"react":"latest","react-dom":"latest"},"devDependencies":{"vite":"latest","tailwindcss":"latest"}}' },
      { name: 'src/App.tsx', language: 'tsx', content: '<main className="min-h-screen flex bg-white text-gray-900 px-4 py-8">OK</main>' },
      { name: 'src/index.css', language: 'css', content: '@tailwind base; @tailwind components; @tailwind utilities;' },
    ])
    const r = await projectIntegrityCritic(good, intent)
    assert.ok(!r.issues.some((i) => /Tailwind/i.test(i.message)), JSON.stringify(r.issues))
  })
})

describe('structureCritic — barre expert', () => {
  test('fichier raisonnable score ≥ 0.9', async () => {
    const r = await structureCritic(project([{ name: 'a.ts', language: 'ts', content: GOOD_TS }]), fakeIntent)
    assert.ok(r.scores.lint >= 0.9)
  })

  test('fichier 1700 lignes ↦ score < 1 + issue error', async () => {
    const r = await structureCritic(project([{ name: 'huge.ts', language: 'ts', content: HUGE_FILE_TS }]), fakeIntent)
    assert.ok(r.scores.lint < 1)
    assert.ok(r.issues.some((i) => i.severity === 'error' && /enorme|énorme/i.test(i.message)))
  })

  test('God-function de plus de 200 lignes détectée', async () => {
    const body = Array.from({ length: 210 }, (_, i) => `  total += ${i}`).join('\n')
    const code = `function god() {\n  let total = 0\n${body}\n  return total\n}\n`
    const r = await structureCritic(project([{ name: 'god.ts', language: 'ts', content: code }]), fakeIntent)
    assert.ok(r.issues.some((i) => /fonction de plus de 200 lignes/i.test(i.message)), JSON.stringify(r.issues))
  })
})

describe('accessibilityCritic — barre expert', () => {
  test('TSX propre score ≥ 0.95', async () => {
    const r = await accessibilityCritic(project([{ name: 'good.tsx', language: 'tsx', content: GOOD_TS }]), fakeIntent)
    assert.ok(r.scores.accessibility >= 0.95, `score ${r.scores.accessibility}`)
  })

  test('img sans alt + a onClick + input sans label ↦ score < 0.7', async () => {
    const r = await accessibilityCritic(project([{ name: 'bad.tsx', language: 'tsx', content: INACCESSIBLE_TSX }]), fakeIntent)
    assert.ok(r.scores.accessibility < 0.7, `score ${r.scores.accessibility}`)
    assert.ok(r.issues.length >= 3)
  })
})

describe('compositeStaticCritic — barre expert', () => {
  test('bon code global ≥ 0.85', async () => {
    const r = await compositeStaticCritic(project([{ name: 'a.tsx', language: 'tsx', content: GOOD_TS }]), fakeIntent)
    assert.ok(r.overallScore >= 0.85, `overall ${r.overallScore}`)
    assert.equal(r.hasBlocker, false)
  })

  test('code horrible ↦ overall < 0.5 OU blocker', async () => {
    const horrible = project([
      { name: 'bad.tsx', language: 'tsx', content: INACCESSIBLE_TSX },
      { name: 'insecure.ts', language: 'ts', content: INSECURE_TS },
    ])
    const r = await compositeStaticCritic(horrible, fakeIntent)
    assert.ok(r.hasBlocker || r.overallScore < 0.5, `overall ${r.overallScore}, blocker ${r.hasBlocker}`)
  })
})
