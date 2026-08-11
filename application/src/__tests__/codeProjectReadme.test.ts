import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import type { CodeIntent } from '../services/codeIntent.ts'
import { generateProjectReadme } from '../services/codeProjectReadme.ts'
import { upsertProjectSupportFilesForTest } from '../services/codeProjectSupportFiles.ts'

const REACT_PKG = JSON.stringify({
  name: 'brulerie-nomade',
  private: true,
  scripts: { dev: 'vite', build: 'tsc && vite build', preview: 'vite preview', test: 'vitest' },
  dependencies: { react: '^18.3.1', 'react-dom': '^18.3.1', 'react-router-dom': '^6.26.0' },
  devDependencies: { vite: '^8', '@vitejs/plugin-react': '^6', typescript: '^5.4.5' },
}, null, 2)

const ROUTES_TSX = `import { Routes, Route } from 'react-router-dom'
import HomePage from '../pages/HomePage'
import AboutPage from '../pages/AboutPage'
import AdminDashboard from '../pages/AdminDashboard'

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/admin" element={<AdminDashboard />} />
    </Routes>
  )
}
`

const MAIN_TSX = `import { createRoot } from 'react-dom/client'
import App from './App'
createRoot(document.getElementById('root')!).render(<App />)
`

const APP_TSX = `import { BrowserRouter } from 'react-router-dom'
import AppRoutes from './routes/AppRoutes'
export default function App() { return <BrowserRouter><AppRoutes /></BrowserRouter> }
`

const CARD_TSX = `import React from 'react'
interface CoffeeCardProps { name: string; origin: string; price: number }
const CoffeeCard: React.FC<CoffeeCardProps> = ({ name, origin, price }) => <div>{name}</div>
export default CoffeeCard
`

const staticIntent = (): CodeIntent => ({
  ...reactIntent(),
  // Pas de marque: c est justement le cas ou le titre manquait.
  assetPlan: { ...reactIntent().assetPlan, subject: undefined },
  projectType: 'static_web',
  frameworks: [],
  needsDevServer: false,
  needsBundling: false,
  devCommand: '',
  buildCommand: '',
})

const reactIntent = (): CodeIntent => ({
  projectType: 'spa_react',
  complexity: 'moderate',
  languages: ['typescript'],
  frameworks: ['react', 'vite'],
  features: [],
  needsDevServer: true,
  needsBundling: true,
  previewType: 'dev_server',
  devCommand: 'npm run dev',
  buildCommand: 'npm run build',
  testCommand: 'npm test',
  primaryModelRole: 'code',
  needsArchitecturePlanning: true,
  estimatedFileCount: 8,
  assetPlan: {
    styleHints: [], objectMentions: [], effectMentions: [], paletteHints: [],
    wantsPremiumLook: false, wantsImages: false, wants3D: false, wantsResearch: false,
    researchQueries: [],
    subject: { canonical: 'Brûlerie Nomade', domain: 'coffee', source: 'quoted', raw: '"Brûlerie Nomade"' },
    language: 'fr',
  },
}) as unknown as CodeIntent

describe('codeProjectReadme', () => {
  test('titre = nom de la MARQUE quand assetPlan.subject expose un canonique', () => {
    const files = [
      { name: 'package.json', language: 'json', content: REACT_PKG },
      { name: 'src/main.tsx', language: 'tsx', content: MAIN_TSX },
    ]
    const readme = generateProjectReadme(files, reactIntent(), 'salut, un site pour "Brûlerie Nomade"', null)
    assert.ok(readme.content.startsWith('# Brûlerie Nomade'), `titre attendu, obtenu: ${readme.content.slice(0, 60)}`)
    assert.equal(readme.content.startsWith('# Spa React'), false, 'plus jamais le type au lieu du sujet')
  })

  test('titre secours = nom humanisé du package.json quand aucun sujet', () => {
    const intent = reactIntent()
    intent.assetPlan.subject = { canonical: null, domain: null, source: 'none', raw: '' } as CodeIntent['assetPlan']['subject']
    const files = [
      { name: 'package.json', language: 'json', content: REACT_PKG },
      { name: 'src/main.tsx', language: 'tsx', content: MAIN_TSX },
    ]
    const readme = generateProjectReadme(files, intent, 'crée un site', null)
    assert.ok(readme.content.startsWith('# Brulerie Nomade'), `titre attendu, obtenu: ${readme.content.slice(0, 60)}`)
  })

  test('une entrée de routes déclare le nombre et les chemins réels du fichier', () => {
    const files = [
      { name: 'package.json', language: 'json', content: REACT_PKG },
      { name: 'src/main.tsx', language: 'tsx', content: MAIN_TSX },
      { name: 'src/App.tsx', language: 'tsx', content: APP_TSX },
      { name: 'src/routes/AppRoutes.tsx', language: 'tsx', content: ROUTES_TSX },
    ]
    const readme = generateProjectReadme(files, reactIntent(), 'ma marque de café', null)
    assert.match(readme.content, /src\/routes\/AppRoutes\.tsx.*3 routes.*\/.*\/about.*\/admin/s)
  })

  test('une entrée composant décrit le composant et compte ses props', () => {
    const files = [
      { name: 'package.json', language: 'json', content: REACT_PKG },
      { name: 'src/main.tsx', language: 'tsx', content: MAIN_TSX },
      { name: 'src/components/CoffeeCard.tsx', language: 'tsx', content: CARD_TSX },
    ]
    const readme = generateProjectReadme(files, reactIntent(), 'café', null)
    assert.match(readme.content, /CoffeeCard\.tsx.*Composant.*`CoffeeCard`.*3 props/)
  })

  test('démarrage rapide = one-liner conforme aux scripts réels du package.json', () => {
    const files = [
      { name: 'package.json', language: 'json', content: REACT_PKG },
      { name: 'src/main.tsx', language: 'tsx', content: MAIN_TSX },
    ]
    const readme = generateProjectReadme(files, reactIntent(), 'café', null)
    assert.match(readme.content, /## Démarrage rapide[\s\S]*?```bash[\s\S]*?npm install && npm run dev[\s\S]*?```/)
    assert.match(readme.content, /`npm run dev` \(`vite`\)/)
    assert.match(readme.content, /`npm run build` \(`tsc && vite build`\)/)
    assert.match(readme.content, /`npm run preview` \(`vite preview`\)/)
  })

  test('la version Node requise est déduite de la version majeure de Vite', () => {
    const files = [
      { name: 'package.json', language: 'json', content: REACT_PKG },
      { name: 'src/main.tsx', language: 'tsx', content: MAIN_TSX },
    ]
    const readme = generateProjectReadme(files, reactIntent(), 'café', null)
    assert.match(readme.content, /Node\.js >= 20/)
  })

  test('les URLs exposées reprennent les chemins déclarés dans le routeur', () => {
    const files = [
      { name: 'package.json', language: 'json', content: REACT_PKG },
      { name: 'src/main.tsx', language: 'tsx', content: MAIN_TSX },
      { name: 'src/routes/AppRoutes.tsx', language: 'tsx', content: ROUTES_TSX },
    ]
    const readme = generateProjectReadme(files, reactIntent(), 'café', null)
    assert.match(readme.content, /## URLs exposées/)
    assert.match(readme.content, /http:\/\/localhost:5173\/`\s*$/m)
    assert.match(readme.content, /http:\/\/localhost:5173\/about/)
    assert.match(readme.content, /http:\/\/localhost:5173\/admin/)
  })

  test('start.sh évoqué SEULEMENT quand le fichier existe réellement', () => {
    const filesWithout = [
      { name: 'package.json', language: 'json', content: REACT_PKG },
      { name: 'src/main.tsx', language: 'tsx', content: MAIN_TSX },
    ]
    const readmeWithout = generateProjectReadme(filesWithout, reactIntent(), 'café', null)
    assert.equal(readmeWithout.content.includes('start.sh'), false, 'plus de mensonge quand le script n\'existe pas')

    const filesWith = [...filesWithout, { name: 'start.sh', language: 'bash', content: '#!/usr/bin/env bash\nvite' }]
    const readmeWith = generateProjectReadme(filesWith, reactIntent(), 'café', null)
    assert.match(readmeWith.content, /## Raccourci Linux\/macOS/)
    assert.match(readmeWith.content, /\.\/start\.sh/)
  })

  test('projet trivial static_web reste court et n\'invente pas de sections', () => {
    const intent = { projectType: 'static_web', assetPlan: { subject: { source: 'none' } } } as unknown as CodeIntent
    const files = [
      { name: 'index.html', language: 'html', content: '<!doctype html><html><body>hi</body></html>' },
      { name: 'style.css', language: 'css', content: 'body{margin:0}' },
      { name: 'script.js', language: 'javascript', content: 'console.log("hi")' },
    ]
    const readme = generateProjectReadme(files, intent, 'une petite page HTML', null)
    assert.equal(readme.content.includes('## Scripts npm'), false, 'un site statique n\'a pas de scripts npm')
    assert.equal(readme.content.includes('## URLs exposées'), false, 'un site statique n\'a pas de routes React Router')
    assert.equal(readme.content.includes('## Démarrage rapide'), false, 'un site statique n\'a pas de one-liner')
    assert.match(readme.content, /Aucun \(le projet est statique/)
    assert.match(readme.content, /## Structure du projet/)
    // Under 2 KB is fine for a 3-file project — no bloat.
    assert.ok(readme.content.length < 2000, `trop verbeux pour 3 fichiers: ${readme.content.length} caracteres`)
  })

  test('les scripts sont ceux réellement déclarés (pas un `npm run dev` deviné)', () => {
    // A CLI Node with only a `start` script must not be documented with `dev`.
    const intent = {
      projectType: 'cli_node',
      needsDevServer: false,
      devCommand: null, buildCommand: null, testCommand: null,
      assetPlan: { subject: { source: 'none' } },
    } as unknown as CodeIntent
    const cliPkg = JSON.stringify({ name: 'aurora-cli', scripts: { start: 'node dist/index.js' }, dependencies: {} })
    const files = [
      { name: 'package.json', language: 'json', content: cliPkg },
      { name: 'src/index.ts', language: 'typescript', content: 'export const run = () => 0' },
    ]
    const readme = generateProjectReadme(files, intent, 'un CLI', null)
    assert.match(readme.content, /npm install && npm start/)
    assert.equal(readme.content.includes('npm run dev'), false, 'aucun script inventé')
  })
})

describe('codeProjectReadme through the support pipeline', () => {
  test('upsertProjectSupportFiles génère le README APRÈS start.sh et l\'y référence', () => {
    const intent = reactIntent()
    const files = upsertProjectSupportFilesForTest([
      { name: 'package.json', language: 'json', content: REACT_PKG },
      { name: 'src/main.tsx', language: 'tsx', content: MAIN_TSX },
    ], intent, 'salut, "Brûlerie Nomade" une SPA React', null)
    const names = files.map((f) => f.name)
    assert.ok(names.includes('README.md'))
    assert.ok(names.includes('start.sh'))
    const readme = files.find((f) => f.name === 'README.md')!
    assert.match(readme.content, /## Raccourci Linux\/macOS/)
    assert.ok(readme.content.startsWith('# Brûlerie Nomade'))
  })
})

describe('codeProjectReadme — titre d un projet statique', () => {
  // Mesure reelle (run 971): sans package.json ni marque, le README s intitulait
  // « Static Web » — le TYPE, pas le projet. Le modele avait pourtant deja choisi
  // un nom: il est dans le <title> de la page livree.
  const CONVERTER = [
    {
      name: 'index.html',
      language: 'html',
      content: '<!DOCTYPE html><html lang="fr"><head><title>Convertisseur de Température</title></head><body><h1>x</h1></body></html>',
    },
    { name: 'script.js', language: 'javascript', content: 'console.log(1)' },
  ]

  test('le <title> du document sert de nom quand il n y a rien d autre', () => {
    const readme = generateProjectReadme(CONVERTER, staticIntent(), 'une page pour convertir des temperatures', null)
    assert.ok(readme.content.startsWith('# Convertisseur de Température'), readme.content.slice(0, 60))
  })

  test('un <title> de gabarit ne devient pas un nom de projet', () => {
    const templated = [{ ...CONVERTER[0], content: '<!DOCTYPE html><html><head><title>Vite</title></head><body></body></html>' }]
    const readme = generateProjectReadme(templated, staticIntent(), 'une page', null)
    assert.equal(readme.content.startsWith('# Vite'), false)
  })
})
