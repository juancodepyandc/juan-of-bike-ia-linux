import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  buildBrowserWorkspacePreviewHtml,
  detectBrowserWorkspaceEntry,
  normalizeRuntimePath,
  supportsBrowserWorkspaceRuntime,
} from '../services/codeBrowserWorkspaceRuntime.ts'
import { shouldPauseLivePreviewDuringGeneration } from '../services/codeLivePreviewPolicy.ts'

describe('codeBrowserWorkspaceRuntime', () => {
  test('detecte et bundle un workspace React multi-fichiers sans dev-server', () => {
    const files = [
      {
        name: 'src/main.tsx',
        language: 'tsx',
        content: "import { createRoot } from 'react-dom/client'\nimport App from './App'\ncreateRoot(document.getElementById('root')!).render(<App />)",
      },
      {
        name: 'src/App.tsx',
        language: 'tsx',
        content: "import './style.css'\nexport default function App(){ return <button>OK</button> }",
      },
      { name: 'src/style.css', language: 'css', content: 'button{color:tomato}' },
    ]

    const entry = detectBrowserWorkspaceEntry(files)
    const html = buildBrowserWorkspacePreviewHtml(files)

    assert.deepEqual(entry, { path: 'src/main.tsx', synthetic: false, reason: 'main_entry' })
    assert.equal(supportsBrowserWorkspaceRuntime(files), true)
    assert.ok(html)
    assert.match(html, /esbuild-wasm@0\.28\.1/)
    assert.match(html, /importmap/)
    assert.match(html, /aurora-code-runtime/)
    assert.match(html, /react-dom\/client/)
    assert.match(html, /src\/App\.tsx/)
  })

  test('synthesise une entree quand seul App.tsx est present', () => {
    const files = [
      { name: 'src/App.tsx', language: 'tsx', content: 'export default function App(){ return <main>Aurora</main> }' },
    ]

    const entry = detectBrowserWorkspaceEntry(files)
    const html = buildBrowserWorkspacePreviewHtml(files)

    assert.equal(entry?.synthetic, true)
    assert.equal(entry?.path, 'aurora-entry.tsx')
    assert.match(entry?.content || '', /createRoot/)
    assert.match(html || '', /aurora-entry\.tsx/)
  })

  test('laisse les projets HTML statiques au preview historique', () => {
    const files = [
      { name: 'index.html', language: 'html', content: '<main>Hello</main>' },
      { name: 'src/App.tsx', language: 'tsx', content: 'export default function App(){ return null }' },
    ]

    assert.equal(supportsBrowserWorkspaceRuntime(files), false)
    assert.equal(buildBrowserWorkspacePreviewHtml(files), null)
  })

  test('normalise les chemins pieges et ne gele plus la preview legere pendant generation', () => {
    assert.equal(normalizeRuntimePath('./src/../src/App.tsx'), 'src/App.tsx')
    assert.equal(normalizeRuntimePath('src\\\\components\\\\Button.tsx'), 'src/components/Button.tsx')

    assert.equal(shouldPauseLivePreviewDuringGeneration({ isGenerating: true, totalBytes: 40_000, isHeavy: false }), false)
    assert.equal(shouldPauseLivePreviewDuringGeneration({ isGenerating: true, totalBytes: 190_000, isHeavy: false }), true)
    assert.equal(shouldPauseLivePreviewDuringGeneration({ isGenerating: true, totalBytes: 40_000, isHeavy: true }), true)
    assert.equal(shouldPauseLivePreviewDuringGeneration({ isGenerating: false, totalBytes: 300_000, isHeavy: true }), false)
  })

  test('atelier code isole: aucune reference aux vues du module 3D', () => {
    const delivery = readFileSync('src/views/codeViewDeliveryPanel.tsx', 'utf8')
    const atelier = readFileSync('src/views/codeViewWorkspaceAtelier.tsx', 'utf8')

    assert.doesNotMatch(`${delivery}\n${atelier}`, /AuroraV1(?:3D|ThreeD)|AuroraV3(?:3D|ThreeD)|ThreeDProgressOverlay|ModelView/)
  })
})
