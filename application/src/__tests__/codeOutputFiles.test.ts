/**
 * Tests pour services/codeOutputFiles — parser multi-file output LLM.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  extractGeneratedFiles,
  extractWebPreview,
} from '../services/codeOutputFiles.ts'

describe('extractGeneratedFiles — edge cases', () => {
  test('stream vide → []', () => {
    assert.deepEqual(extractGeneratedFiles(''), [])
  })

  test('stream whitespace only → []', () => {
    assert.deepEqual(extractGeneratedFiles('   \n\t  '), [])
  })

  test('texte sans fence → fichier sniffé (markdown ou txt)', () => {
    const r = extractGeneratedFiles('Juste du texte simple.')
    assert.equal(r.length, 1)
    assert.ok(r[0].path)
    assert.equal(r[0].content, 'Juste du texte simple.')
  })
})

describe('extractGeneratedFiles — fenced blocks', () => {
  test('fence avec lang + path inline → fichier nommé', () => {
    const stream = '```tsx src/App.tsx\nexport default function App() { return null }\n```'
    const r = extractGeneratedFiles(stream)
    assert.equal(r.length, 1)
    assert.equal(r[0].path, 'src/App.tsx')
    assert.equal(r[0].language, 'tsx')
  })

  test('fence sans path → contenu sniffé (HTML)', () => {
    const stream = '```html\n<!DOCTYPE html><html><body>hi</body></html>\n```'
    const r = extractGeneratedFiles(stream)
    assert.equal(r.length, 1)
    assert.equal(r[0].path, 'index.html')
  })

  test('fence sans path → contenu sniffé (React)', () => {
    const stream = '```tsx\nimport React from "react"\nexport default function App() {\n  return <div>hi</div>\n}\n```'
    const r = extractGeneratedFiles(stream)
    assert.equal(r.length, 1)
    assert.equal(r[0].path, 'App.tsx')
  })

  test('fence sans path → contenu sniffé (Python)', () => {
    const stream = '```python\nimport os\ndef hello():\n    print("hi")\n```'
    const r = extractGeneratedFiles(stream)
    assert.equal(r.length, 1)
    assert.equal(r[0].path, 'script.py')
  })

  test('plusieurs fenced blocks → plusieurs fichiers', () => {
    const stream = `\`\`\`ts src/a.ts
const a = 1
\`\`\`

\`\`\`ts src/b.ts
const b = 2
\`\`\``
    const r = extractGeneratedFiles(stream)
    assert.equal(r.length, 2)
    assert.equal(r[0].path, 'src/a.ts')
    assert.equal(r[1].path, 'src/b.ts')
  })
})

describe('extractGeneratedFiles — file header formats', () => {
  test('comment style "// File: x.ts" → fichier nommé', () => {
    const stream = '// File: src/x.ts\n```ts\nconst x = 1\n```'
    const r = extractGeneratedFiles(stream)
    assert.equal(r[0].path, 'src/x.ts')
  })

  test('comment style "# Fichier: x.py" → fichier nommé', () => {
    const stream = '# Fichier: a.py\n```py\nprint(1)\n```'
    const r = extractGeneratedFiles(stream)
    assert.equal(r[0].path, 'a.py')
  })

  test('expert header "--- FICHIER: a.ts ---" → fichier nommé', () => {
    const stream = '--- FICHIER: a.ts ---\n```ts\nconst a = 1\n```'
    const r = extractGeneratedFiles(stream)
    assert.equal(r[0].path, 'a.ts')
  })

  test('standalone path "src/utils.js"', () => {
    const stream = '`src/utils.js`\n```js\nfunction u(){}\n```'
    const r = extractGeneratedFiles(stream)
    assert.equal(r[0].path, 'src/utils.js')
  })
})

describe('extractGeneratedFiles — language inference', () => {
  test('.tsx → tsx', () => {
    const r = extractGeneratedFiles('```tsx src/x.tsx\nconst x = 1\n```')
    assert.equal(r[0].language, 'tsx')
  })

  test('.css → css', () => {
    const r = extractGeneratedFiles('```css style.css\n.a { color: red }\n```')
    assert.equal(r[0].language, 'css')
  })

  test('extension inconnue → text', () => {
    const r = extractGeneratedFiles('```\nrandom content\n```')
    assert.ok(typeof r[0].language === 'string')
  })
})

describe('extractGeneratedFiles — degenerate closing fences', () => {
  test('closing "---" en milieu de fence → traité comme close', () => {
    const stream = '--- FICHIER: a.ts ---\n```ts\nconst a = 1\n---\n--- FICHIER: b.ts ---\n```ts\nconst b = 2\n```'
    const r = extractGeneratedFiles(stream)
    assert.ok(r.length >= 1)
    assert.equal(r[0].path, 'a.ts')
  })
})

describe('extractWebPreview', () => {
  test('files vide → null', () => {
    assert.equal(extractWebPreview([]), null)
  })

  test('index.html → kind html', () => {
    const r = extractWebPreview([
      { path: 'index.html', content: '<!DOCTYPE html><html><body>hi</body></html>', language: 'markup' },
    ])
    assert.equal(r?.kind, 'html')
  })

  test('CSS sibling injectée dans head', () => {
    const r = extractWebPreview([
      { path: 'index.html', content: '<html><head></head><body></body></html>', language: 'markup' },
      { path: 'style.css', content: '.a { color: red }', language: 'css' },
    ])
    assert.ok(r?.html.includes('color: red'))
  })

  test('JS sibling injecté avant </body>', () => {
    const r = extractWebPreview([
      { path: 'index.html', content: '<html><body></body></html>', language: 'markup' },
      { path: 'app.js', content: 'console.log("hi")', language: 'javascript' },
    ])
    assert.ok(r?.html.includes('console.log'))
  })

  test('App.tsx React entry → kind react avec Babel CDN', () => {
    const r = extractWebPreview([
      { path: 'App.tsx', content: 'export default function App() { return (<div>hi</div>) }', language: 'tsx' },
    ])
    assert.equal(r?.kind, 'react')
    assert.ok(r?.html.includes('@babel/standalone'))
    assert.ok(r?.html.includes('ReactDOM'))
  })

  test('Pure CSS → kind css avec preview stage', () => {
    const r = extractWebPreview([
      { path: 'style.css', content: 'h1 { color: blue }', language: 'css' },
    ])
    assert.equal(r?.kind, 'css')
    assert.ok(r?.html.includes('preview-stage'))
  })

  test('Python seul → null (pas de preview web)', () => {
    const r = extractWebPreview([
      { path: 'main.py', content: 'print("hi")', language: 'python' },
    ])
    assert.equal(r, null)
  })
})
