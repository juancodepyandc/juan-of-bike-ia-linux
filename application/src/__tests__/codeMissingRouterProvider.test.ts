/**
 * Run 1181 — des routes montees hors de tout routeur.
 *
 * Acceptation comportementale 0/2, rendu 10/100, page vide:
 *   TypeError: Cannot destructure property 'basename' of 'y.useContext(...)'
 *   FAIL renders-content: 0 caracteres, 0 controles, 0 surfaces.
 *
 * Verifie fichier par fichier sur le livrable reel: AUCUN des 36 fichiers ne
 * contient BrowserRouter, HashRouter, MemoryRouter ni RouterProvider. Le
 * fournisseur n etait pas mal place — il etait absent.
 *
 * Les extraits ci-dessous sont ceux du livrable
 * (output/code_assets/viewers/run-1181/project.json).
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectMissingRouterProvider,
  repairMissingRouterProvider,
} from '../services/codeMissingRouterProvider.ts'

const MAIN = `import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)`

const ROUTES = `import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
const AppRoutes: React.FC = () => <Routes><Route path="/" element={<Home />} /></Routes>;
export default AppRoutes;`

const FILES = [
  { name: 'src/main.tsx', language: 'tsx', content: MAIN },
  { name: 'src/routes/AppRoutes.tsx', language: 'tsx', content: ROUTES },
]

describe('un routeur absent se pose sans modele', () => {
  test('le cas reel du run 1181: aucun fournisseur dans tout le projet', () => {
    const d = detectMissingRouterProvider(FILES)
    assert.equal(d.hasProvider, false)
    assert.deepEqual(d.consumers, ['src/routes/AppRoutes.tsx'])
  })

  test('l arbre monte est enveloppe dans le POINT D ENTREE, pas dans le fichier qui plante', () => {
    const r = repairMissingRouterProvider(FILES)
    assert.equal(r.entry, 'src/main.tsx')
    const main = r.files.find((f) => f.name === 'src/main.tsx')!
    assert.match(main.content, /import \{ BrowserRouter \} from 'react-router-dom'/)
    assert.match(main.content, /<BrowserRouter>[\s\S]*<App \/>[\s\S]*<\/BrowserRouter>/)
    // La virgule finale de l appel est preservee: on enveloppe, on ne reformate pas.
    assert.match(main.content, /<\/BrowserRouter>,\n\)/)
    // Le fichier qui portait la trace n est pas touche.
    assert.equal(r.files.find((f) => f.name === 'src/routes/AppRoutes.tsx')!.content, ROUTES)
  })

  test('un projet qui a DEJA un routeur n est pas touche', () => {
    const withRouter = [
      { name: 'src/main.tsx', language: 'tsx', content: `import { BrowserRouter } from 'react-router-dom'\n${MAIN}` },
      { name: 'src/routes/AppRoutes.tsx', language: 'tsx', content: ROUTES },
    ]
    assert.equal(repairMissingRouterProvider(withRouter).entry, null)
  })

  test('un projet sans routes n est pas touche', () => {
    const plain = [{ name: 'src/main.tsx', language: 'tsx', content: MAIN }]
    const r = repairMissingRouterProvider(plain)
    assert.equal(r.entry, null)
    assert.equal(r.files, plain)
  })

  test('un point d entree non reconnaissable ne declenche rien', () => {
    const odd = [{ name: 'src/routes/AppRoutes.tsx', language: 'tsx', content: ROUTES }]
    assert.equal(repairMissingRouterProvider(odd).entry, null)
  })

  test('une parenthese imbriquee dans createRoot ne fait pas rater l appel', () => {
    // `createRoot(document.getElementById('root')!)` a fait echouer le premier
    // jet de ce module: un `[^)]*` s arretait a la parenthese interne.
    const r = repairMissingRouterProvider(FILES)
    assert.notEqual(r.entry, null)
  })

  test('un import react-router-dom existant recoit BrowserRouter au lieu d un doublon', () => {
    const withImport = [
      { name: 'src/main.tsx', language: 'tsx', content: MAIN.replace("import App from './App'", "import App from './App'\nimport { Link } from 'react-router-dom'") },
      { name: 'src/routes/AppRoutes.tsx', language: 'tsx', content: ROUTES },
    ]
    const main = repairMissingRouterProvider(withImport).files.find((f) => f.name === 'src/main.tsx')!
    assert.match(main.content, /import \{ Link, BrowserRouter \} from 'react-router-dom'/)
    assert.equal((main.content.match(/from 'react-router-dom'/g) ?? []).length, 1)
  })
})
