import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  RENDER_ROOT_FAILURE,
  buildRenderRootCauseCritique,
  dependsOnMountedPage,
  extractSourcePathsFromErrors,
  splitRenderFailures,
} from '../services/codeRenderCausalOrder.ts'
import { buildTargetedRepairScope } from '../services/codeTargetedRepairScope.ts'
import type { CodeFile } from '../services/codeOrchestratorTypes.ts'

/** Les SEPT echecs reellement remontes au run 1101, dans l ordre. */
const RUN_1101_FAILED = [
  'runtime_clean', 'display_typography', 'type_scale', 'real_typeface',
  'visual_content', 'depth', 'interactivity',
]

describe('ordre causal — un juge dont la page n a jamais monte ne mesure rien', () => {
  test('un crash reduit les sept echecs a la seule cause', () => {
    const { causes, symptoms } = splitRenderFailures(RUN_1101_FAILED)
    assert.deepEqual(causes, [RENDER_ROOT_FAILURE])
    assert.deepEqual(symptoms, [
      'display_typography', 'type_scale', 'real_typeface', 'visual_content', 'depth', 'interactivity',
    ])
  })

  test('sans crash, tout echec reste une cause a part entiere', () => {
    const { causes, symptoms } = splitRenderFailures(['display_typography', 'depth'])
    assert.deepEqual(causes, ['display_typography', 'depth'])
    assert.deepEqual(symptoms, [])
  })

  test('seul runtime_clean ne depend pas d une page montee', () => {
    assert.equal(dependsOnMountedPage(RENDER_ROOT_FAILURE), false)
    for (const id of ['display_typography', 'depth', 'heading_order', 'first_paint', 'real_iconography']) {
      assert.equal(dependsOnMountedPage(id), true, id)
    }
  })

  test('la consigne interdit explicitement de retoucher les styles', () => {
    const critique = buildRenderRootCauseCritique({
      consoleErrors: ["TypeError: Cannot read properties of undefined (reading 'map')\n    at hd (src/pages/Markets.tsx:42:18)"],
      symptoms: ['display_typography', 'depth'],
    })
    assert.match(critique, /CORRIGE CE CRASH, ET RIEN D AUTRE/)
    assert.match(critique, /src\/pages\/Markets\.tsx:42:18/)
    assert.match(critique, /Ne retouche AUCUN fichier de style/)
    assert.match(critique, /NON CONCLUANTS/)
    assert.match(critique, /display_typography, depth/)
    // Le conseil doit viser la SOURCE de la donnee, pas un `?.` cosmetique.
    assert.match(critique, /pas par un `\?\.` pose au hasard/)
  })
})

describe('la trace resolue devient la portee du patch', () => {
  test('extrait les chemins source, ignore les positions de bundle', () => {
    const resolved = [
      "TypeError: Cannot read properties of undefined (reading 'map')\n    at hd (src/pages/Markets.tsx:42:18)\n    at Bo (src/App.tsx:7:3)",
    ]
    assert.deepEqual(extractSourcePathsFromErrors(resolved), ['src/pages/Markets.tsx', 'src/App.tsx'])

    // Forme NON resolue (run 1101 avant correctif): aucun fichier reparable.
    const minified = ['TypeError: x\n    at hd (http://127.0.0.1:34141/assets/index-C-nmfp7n.js:8:193411)']
    assert.deepEqual(extractSourcePathsFromErrors(minified), [])
  })

  test('les fichiers nommes par la trace passent devant l heuristique', () => {
    const files: CodeFile[] = [
      { name: 'src/pages/Markets.tsx', language: 'tsx', content: 'export default function M(){ return <div>{markets.map(x => x)}</div> }' },
      { name: 'src/App.css', language: 'css', content: '.a{color:red}' },
      { name: 'src/components/Header.tsx', language: 'tsx', content: '<header><button>x</button></header>' },
      { name: 'src/styles/variables.css', language: 'css', content: ':root{--x:1}' },
    ]
    const scope = buildTargetedRepairScope({
      files,
      failedChecks: [RENDER_ROOT_FAILURE],
      evidencePaths: ['src/pages/Markets.tsx'],
      maxTargets: 1,
    })
    assert.deepEqual(scope.targets.map((f) => f.name), ['src/pages/Markets.tsx'])
    assert.deepEqual(scope.reasonsByPath['src/pages/Markets.tsx'], ['trace runtime', RENDER_ROOT_FAILURE])
    // Les CSS que la passe du run 1101 avait repeints sont hors portee.
    assert.ok(scope.protectedPaths.includes('src/App.css'))
    assert.ok(scope.protectedPaths.includes('src/styles/variables.css'))
  })

  test('sans trace exploitable, la portee reste celle du critere', () => {
    const files: CodeFile[] = [
      { name: 'index.html', language: 'html', content: '<html><body><div id="root"></div></body></html>' },
      { name: 'package.json', language: 'json', content: '{}' },
    ]
    const scope = buildTargetedRepairScope({ files, failedChecks: [RENDER_ROOT_FAILURE], evidencePaths: [] })
    assert.deepEqual(scope.targets.map((f) => f.name), ['index.html'])
  })
})
