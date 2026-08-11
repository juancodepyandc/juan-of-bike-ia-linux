import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildCodeFileTree,
  collectDirectoryPaths,
  countTreeFiles,
  fileExtensionOf,
  formatCodeFileSize,
  splitProjectPath,
  type CodeFileTreeNode,
} from '../services/codeFileTreeModel.ts'

// Forme EXACTE d'un projet reellement genere par le module (run960, 33 fichiers):
// chemins et tailles releves sur le dossier extrait. Le contenu est du
// remplissage de la bonne longueur — c'est la STRUCTURE qui est sous test.
const RUN960: Array<[string, number]> = [
  ['assets/aurora-asset-bundle.json', 2204],
  ['index.html', 223],
  ['package.json', 728],
  ['postcss.config.js', 79],
  ['README.md', 2710],
  ['src/App.tsx', 316],
  ['src/components/AnimatedSection.tsx', 534],
  ['src/components/CoffeeCard.tsx', 2142],
  ['src/components/ContactForm.tsx', 4045],
  ['src/components/Footer.tsx', 3620],
  ['src/components/Header.tsx', 2924],
  ['src/components/Layout.tsx', 429],
  ['src/components/MarketCalendar.tsx', 2789],
  ['src/components/OrderList.tsx', 5067],
  ['src/components/OrderSummary.tsx', 2398],
  ['src/components/StorySection.tsx', 3483],
  ['src/components/SubscriptionForm.tsx', 6802],
  ['src/main.tsx', 203],
  ['src/pages/AboutPage.tsx', 4017],
  ['src/pages/AdminDashboard.tsx', 3354],
  ['src/pages/ContactPage.tsx', 17837],
  ['src/pages/HomePage.tsx', 5629],
  ['src/pages/MarketPage.tsx', 2635],
  ['src/pages/SubscriptionsPage.tsx', 3549],
  ['src/routes/AppRoutes.tsx', 815],
  ['src/styles/index.css', 4578],
  ['src/types/index.ts', 227],
  ['src/utils/data.ts', 4683],
  ['src/utils/types.ts', 860],
  ['src/vite-env.d.ts', 84],
  ['start.sh', 213],
  ['tsconfig.json', 892],
  ['vite.config.ts', 188],
]

function run960Files() {
  return RUN960.map(([name, size]) => ({ name, content: 'x'.repeat(size) }))
}

function childNamed(nodes: readonly CodeFileTreeNode[], name: string): CodeFileTreeNode {
  const found = nodes.find((node) => node.name === name)
  assert.ok(found, `noeud "${name}" absent de [${nodes.map((n) => n.name).join(', ')}]`)
  return found
}

describe('codeFileTreeModel — decoupage de chemin', () => {
  test('normalise separateurs, segments vides et remontees', () => {
    assert.deepEqual(splitProjectPath('src/components/Footer.tsx', 0), ['src', 'components', 'Footer.tsx'])
    assert.deepEqual(splitProjectPath('src\\pages\\HomePage.tsx', 0), ['src', 'pages', 'HomePage.tsx'])
    assert.deepEqual(splitProjectPath('/src//utils/./data.ts', 0), ['src', 'utils', 'data.ts'])
    assert.deepEqual(splitProjectPath('src/lib/../main.tsx', 0), ['src', 'main.tsx'])
    assert.deepEqual(splitProjectPath('../../escape.ts', 0), ['escape.ts'])
  })

  test('un chemin vide reste visible sous un nom de repli (jamais d echec silencieux)', () => {
    assert.deepEqual(splitProjectPath('', 0), ['fichier-1'])
    assert.deepEqual(splitProjectPath('   ', 4), ['fichier-5'])
  })

  test('extension: minuscules, sans point, vide pour les cas limites', () => {
    assert.equal(fileExtensionOf('Footer.tsx'), 'tsx')
    assert.equal(fileExtensionOf('README.MD'), 'md')
    assert.equal(fileExtensionOf('vite.config.ts'), 'ts')
    assert.equal(fileExtensionOf('Dockerfile'), '')
    assert.equal(fileExtensionOf('.gitignore'), '')
    assert.equal(fileExtensionOf('archive.'), '')
  })
})

describe('codeFileTreeModel — arbre du projet reel run960 (33 fichiers)', () => {
  test('la racine trie les dossiers avant les fichiers, chacun alphabetiquement', () => {
    const tree = buildCodeFileTree(run960Files())
    assert.deepEqual(tree.map((node) => node.name), [
      'assets',
      'src',
      'index.html',
      'package.json',
      'postcss.config.js',
      'README.md',
      'start.sh',
      'tsconfig.json',
      'vite.config.ts',
    ])
    assert.deepEqual(tree.map((node) => node.isDirectory), [
      true, true, false, false, false, false, false, false, false,
    ])
  })

  test('imbrication reelle: src contient 6 sous-dossiers et ses 2 fichiers racine', () => {
    const tree = buildCodeFileTree(run960Files())
    const src = childNamed(tree, 'src')
    assert.equal(src.isDirectory, true)
    assert.equal(src.path, 'src')
    assert.deepEqual(src.children.map((node) => node.name), [
      'components', 'pages', 'routes', 'styles', 'types', 'utils',
      'App.tsx', 'main.tsx', 'vite-env.d.ts',
    ])

    const pages = childNamed(src.children, 'pages')
    assert.deepEqual(pages.children.map((node) => node.path), [
      'src/pages/AboutPage.tsx',
      'src/pages/AdminDashboard.tsx',
      'src/pages/ContactPage.tsx',
      'src/pages/HomePage.tsx',
      'src/pages/MarketPage.tsx',
      'src/pages/SubscriptionsPage.tsx',
    ])
    assert.equal(pages.children.every((node) => !node.isDirectory), true)
  })

  test('chaque feuille pointe sur son index d origine et porte son extension', () => {
    const files = run960Files()
    const tree = buildCodeFileTree(files)
    const src = childNamed(tree, 'src')
    const footer = childNamed(childNamed(src.children, 'components').children, 'Footer.tsx')
    assert.equal(footer.extension, 'tsx')
    assert.equal(footer.size, 3620)
    assert.equal(files[footer.fileIndex!].name, 'src/components/Footer.tsx')

    const css = childNamed(childNamed(src.children, 'styles').children, 'index.css')
    assert.equal(css.extension, 'css')
    assert.equal(files[css.fileIndex!].name, 'src/styles/index.css')
  })

  test('la taille d un dossier est la somme de ses descendants', () => {
    const tree = buildCodeFileTree(run960Files())
    const total = RUN960.reduce((sum, [, size]) => sum + size, 0)
    assert.equal(tree.reduce((sum, node) => sum + node.size, 0), total)

    const src = childNamed(tree, 'src')
    const srcTotal = RUN960
      .filter(([name]) => name.startsWith('src/'))
      .reduce((sum, [, size]) => sum + size, 0)
    assert.equal(src.size, srcTotal)

    const components = childNamed(src.children, 'components')
    assert.equal(components.size, 34233)
    assert.equal(components.children.length, 11)
  })

  test('les dossiers listes couvrent toute la profondeur du projet', () => {
    const tree = buildCodeFileTree(run960Files())
    assert.deepEqual(collectDirectoryPaths(tree), [
      'assets',
      'src',
      'src/components',
      'src/pages',
      'src/routes',
      'src/styles',
      'src/types',
      'src/utils',
    ])
    assert.equal(countTreeFiles(tree), 33)
  })
})

describe('codeFileTreeModel — deduplication et cas limites', () => {
  test('un chemin livre deux fois ne produit qu un noeud, sur la premiere occurrence', () => {
    const tree = buildCodeFileTree([
      { name: 'src/App.tsx', content: 'premier' },
      { name: 'src/App.tsx', content: 'second-plus-long' },
      { name: 'src\\App.tsx', content: 'variante-windows' },
    ])
    const src = childNamed(tree, 'src')
    assert.equal(src.children.length, 1)
    const app = src.children[0]
    assert.equal(app.fileIndex, 0)
    assert.equal(app.size, 'premier'.length)
    assert.equal(src.size, 'premier'.length)
    assert.equal(countTreeFiles(tree), 1)
  })

  test('un fichier et un dossier homonymes cohabitent sans s ecraser', () => {
    const tree = buildCodeFileTree([
      { name: 'docs', content: 'note libre' },
      { name: 'docs/guide.md', content: '# guide' },
    ])
    assert.deepEqual(tree.map((node) => [node.name, node.isDirectory]), [
      ['docs', true],
      ['docs', false],
    ])
    assert.equal(childNamed(tree.filter((n) => n.isDirectory), 'docs').children.length, 1)
    assert.equal(countTreeFiles(tree), 2)
  })

  test('le tri est numerique-aware et insensible a l ordre d arrivee', () => {
    const shuffled = buildCodeFileTree([
      { name: 'step10.ts', content: '' },
      { name: 'zeta/z.ts', content: '' },
      { name: 'step2.ts', content: '' },
      { name: 'alpha/a.ts', content: '' },
    ])
    assert.deepEqual(shuffled.map((node) => node.name), ['alpha', 'zeta', 'step2.ts', 'step10.ts'])
  })

  test('une liste vide donne un arbre vide', () => {
    assert.deepEqual(buildCodeFileTree([]), [])
    assert.equal(countTreeFiles([]), 0)
    assert.deepEqual(collectDirectoryPaths([]), [])
  })
})

describe('codeFileTreeModel — taille lisible', () => {
  test('octets, kilo-octets, mega-octets en francais', () => {
    assert.equal(formatCodeFileSize(0), '0 o')
    assert.equal(formatCodeFileSize(223), '223 o')
    assert.equal(formatCodeFileSize(1023), '1023 o')
    assert.equal(formatCodeFileSize(4578), '4,5 Ko')
    assert.equal(formatCodeFileSize(17837), '17,4 Ko')
    assert.equal(formatCodeFileSize(3_500_000), '3,3 Mo')
    assert.equal(formatCodeFileSize(Number.NaN), '0 o')
  })
})
