// Non-regression du bug capstone « Brulerie Nomade » (run 960).
//
// Chaine complete du defaut, telle que mesuree sur le flux reel:
//   1. le harnais headless declarait `window` sans `window.document`;
//   2. web-tree-sitter levait a l import -> AST reel MORT sur CLI/tunnel;
//   3. repli lexical -> les apostrophes francaises du texte JSX comptaient
//      comme des delimiteurs de chaine -> « parens non equilibres » sur des
//      composants React VALIDES;
//   4. 9 passes de correction contre un bug inexistant, plateau, boucle;
//   5. la passe esthetique de secours remplacait le livrable SANS comparer;
//   6. la porte visuelle jugeait un SPA React sur son index.html de 223 octets.

import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { describe, test } from 'node:test'
import { bracketBalanceIgnoringLiterals } from '../services/codeLexicalAnalysis.ts'
import { resolveTreeSitterLanguage } from '../services/codeTreeSitterAst.ts'
import { syntaxCritic } from '../services/codeStaticSyntax.ts'
import { inspectCodePatchRegression } from '../services/codeRegressionGuard.ts'
import { pickBestDelivery } from '../services/codeBestDeliverySelection.ts'
import {
  buildRegressionFeedbackBlock,
  filesImplicatedByFailures,
} from '../services/codeCorrectionRegressionFeedback.ts'
import { evaluateVisualFidelity } from '../services/codeVisualFidelity.ts'
import type { CodeIntent } from '../services/codeIntent.ts'

// Composant reellement livre par le run 960 (Footer.tsx), reduit a l essentiel:
// il est VALIDE, et sa seule particularite est l apostrophe de « l'Atelier ».
const FRENCH_JSX = `import React from 'react'

const Footer: React.FC = () => {
  return (
    <footer className="bg-[#0f172a]">
      <p>Torrefie cette semaine, pas l'an dernier</p>
      <p className="mt-2">123 Rue de l'Atelier, 69000 Lyon</p>
      <p>Notre page d'accueil et l'histoire de l'atelier</p>
    </footer>
  )
}

export default Footer
`

const BROKEN_JSX = `export default function Casse() {
  return (
    <div>
      <span>{items.map((item) => (<b>{item}</b>)}</span>
    </div>
  )
}
`

function file(name: string, content: string, language = 'typescript') {
  return { name, language, content }
}

const WEB_INTENT = { projectType: 'spa_react' } as unknown as CodeIntent
// Barre VITRINE: ces deux tests mesurent la richesse editoriale, pas un outil.
const SHOWCASE_BRIEF = 'site vitrine pour promouvoir notre marque de cafe'

describe('capstone Brulerie Nomade — AST reel sur les canaux headless', () => {
  test('le shim headless ne tue plus web-tree-sitter (cause racine)', () => {
    // Sous-processus: installHeadlessCodeEnv() enregistre un resolve hook
    // global, on ne le fait donc pas dans le processus de test.
    const script = [
      "const { installHeadlessCodeEnv } = await import('./scripts/code_harness/harness_env.mjs');",
      'installHeadlessCodeEnv();',
      "const m = await import('./src/services/codeTreeSitterAst.ts');",
      "const r = await m.parseCodeWithTreeSitter('const a = (1 + 2)\\n', 'tsx');",
      'process.stdout.write(r.ok ? `OK:${r.hasError}` : `FAIL:${r.reason}`);',
    ].join('\n')
    const out = execFileSync(
      process.execPath,
      ['--experimental-strip-types', '--input-type=module', '--eval', script],
      { cwd: process.cwd(), encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] },
    )
    assert.equal(out, 'OK:false', `AST indisponible sous le harnais headless: ${out}`)
  })

  test('la grammaire suit l EXTENSION, pas le libelle de langage', () => {
    // detectLanguage() etiquette un .tsx « typescript », grammaire qui refuse le JSX.
    assert.equal(resolveTreeSitterLanguage('src/pages/Home.tsx', 'typescript'), 'tsx')
    assert.equal(resolveTreeSitterLanguage('src/App.jsx', 'javascript'), 'jsx')
    assert.equal(resolveTreeSitterLanguage('src/util.ts', 'typescript'), 'ts')
    assert.equal(resolveTreeSitterLanguage('notes.txt', 'text'), null)
  })
})

describe('capstone Brulerie Nomade — le repli lexical ne hallucine plus', () => {
  test("une apostrophe francaise dans du texte JSX n ouvre pas de chaine", () => {
    const balance = bracketBalanceIgnoringLiterals(FRENCH_JSX)
    assert.deepEqual(balance, { ok: true, diff: 0, kind: '' })
  })

  test('une vraie chaine JS reste masquee', () => {
    // Si l apostrophe cessait d etre un delimiteur, la parenthese de la chaine
    // serait comptee et le fichier deviendrait faussement desequilibre.
    const source = "const label = 'un ( non ferme'\nconst n = (1 + 2)\n"
    assert.equal(bracketBalanceIgnoringLiterals(source).ok, true)
  })

  test('un vrai desequilibre reste detecte', () => {
    assert.equal(bracketBalanceIgnoringLiterals('function f() { return (1 \n').ok, false)
  })

  test('le composant francais valide ne produit AUCUN bloqueur', async () => {
    const report = await syntaxCritic(
      { generationId: 't', files: [file('src/components/Footer.tsx', FRENCH_JSX)] },
      WEB_INTENT,
    )
    assert.deepEqual(report.issues.filter((issue) => issue.severity === 'block'), [])
  })

  test('un composant reellement casse produit un bloqueur', async () => {
    const report = await syntaxCritic(
      { generationId: 't', files: [file('src/pages/Casse.tsx', BROKEN_JSX)] },
      WEB_INTENT,
    )
    assert.equal(report.issues.some((issue) => issue.severity === 'block'), true)
  })
})

describe('capstone Brulerie Nomade — le garde voit le point d entree detruit', () => {
  test("un index.html reduit a un fragment JSX est refuse", () => {
    const before = [file('index.html', '<!doctype html><html><body><div id="root"></div></body></html>', 'html')]
    const after = [file('index.html', '<img src="http://127.0.0.1:3001/a.avif" className="w-full" />', 'html')]
    const report = inspectCodePatchRegression(before, after)
    assert.equal(report.ok, false)
    assert.equal(report.violations.some((violation) => violation.kind === 'broken_html_document'), true)
  })

  test('une simple retouche du document reste acceptee', () => {
    const before = [file('index.html', '<!doctype html><html><body><div id="root"></div></body></html>', 'html')]
    const after = [file('index.html', '<!doctype html><html lang="fr"><body><div id="root"></div></body></html>', 'html')]
    assert.equal(inspectCodePatchRegression(before, after).ok, true)
  })
})

describe('capstone Brulerie Nomade — le refus anti-regression parle au correcteur', () => {
  test('aucun refus => aucune consigne ajoutee', () => {
    assert.equal(buildRegressionFeedbackBlock({ guardReport: null, consecutiveRejections: 0, implicatedFiles: [] }), '')
  })

  test('un refus transmet le verdict exact du garde', () => {
    const block = buildRegressionFeedbackBlock({
      guardReport: 'Regression refusee:\n- removed_export: src/routes/approutes.tsx:AppRoutes',
      consecutiveRejections: 1,
      implicatedFiles: ['src/pages/ContactPage.tsx'],
    })
    assert.match(block, /REFUSEE ET ANNULEE/)
    assert.match(block, /removed_export: src\/routes\/approutes\.tsx:AppRoutes/)
    assert.doesNotMatch(block, /PORTEE RESSERREE/)
  })

  test('deux refus consecutifs resserrent la portee sur les fichiers fautifs', () => {
    const block = buildRegressionFeedbackBlock({
      guardReport: 'Regression refusee:\n- removed_file: src/components/footer.tsx',
      consecutiveRejections: 2,
      implicatedFiles: ['src/pages/ContactPage.tsx', 'src/components/MarketCalendar.tsx'],
    })
    assert.match(block, /PORTEE RESSERREE/)
    assert.match(block, /`src\/pages\/ContactPage\.tsx`, `src\/components\/MarketCalendar\.tsx`/)
  })

  test('les fichiers fautifs sont ceux NOMMES par les erreurs', () => {
    const files = [
      file('src/pages/ContactPage.tsx', 'x'),
      file('src/pages/HomePage.tsx', 'x'),
      file('src/types/index.ts', 'x'),
    ]
    const implicated = filesImplicatedByFailures(files, [
      '[block] src/pages/ContactPage.tsx: erreur de syntaxe (analyse AST tree-sitter tsx)',
    ])
    assert.deepEqual(implicated, ['src/pages/ContactPage.tsx'])
  })
})

describe('capstone Brulerie Nomade — la passe esthetique ne jette plus le meilleur etat', () => {
  const incumbent = {
    files: [file('index.html', '<!doctype html><html><body><section>a</section></body></html>', 'html')],
    visualScore: 44,
    compositionOk: true,
    pipelineFailed: false,
  }

  test('une regeneration moins bien notee est ecartee', () => {
    const selection = pickBestDelivery(incumbent, { ...incumbent, visualScore: 38 })
    assert.equal(selection.adopt, false)
    assert.match(selection.reason, /38\/100 contre 44\/100/)
  })

  test('une regeneration a egalite est ecartee', () => {
    assert.equal(pickBestDelivery(incumbent, { ...incumbent, visualScore: 44 }).adopt, false)
  })

  test('une regeneration strictement meilleure est adoptee', () => {
    assert.equal(pickBestDelivery(incumbent, { ...incumbent, visualScore: 71 }).adopt, true)
  })

  test('une regeneration vide est ecartee', () => {
    assert.equal(pickBestDelivery(incumbent, { ...incumbent, files: [], visualScore: 99 }).adopt, false)
  })

  test('une regeneration en erreur est ecartee', () => {
    const selection = pickBestDelivery(incumbent, { ...incumbent, visualScore: 90, pipelineFailed: true })
    assert.equal(selection.adopt, false)
    assert.match(selection.reason, /terminee en erreur/)
  })

  test('une regeneration plus belle mais amputee est ecartee', () => {
    const richer = {
      files: [
        file('index.html', '<!doctype html><html><body><section>a</section></body></html>', 'html'),
        file('src/pages/AdminDashboard.tsx', 'export default function AdminDashboard() { return null }'),
      ],
      visualScore: 40,
      compositionOk: true,
      pipelineFailed: false,
    }
    const selection = pickBestDelivery(richer, { ...incumbent, visualScore: 95 })
    assert.equal(selection.adopt, false)
    assert.match(selection.reason, /perd des capacites/)
  })

  test('un rendu non mesurable ne remplace pas un rendu mesure', () => {
    assert.equal(pickBestDelivery(incumbent, { ...incumbent, visualScore: null }).adopt, false)
  })
})

describe('capstone Brulerie Nomade — la porte visuelle regarde le vrai markup', () => {
  const VITE_SHELL = '<!doctype html><html lang="fr"><head><title>x</title></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>'
  const PAGE = `export default function HomePage() {
  return (
    <div className="flex flex-col">
      <section className="bg-gradient-to-br from-amber-900 to-stone-800"><h1>Brulerie Nomade</h1><img src="/hero.avif" alt="cafe" /></section>
      <section><h2>Nos cafes</h2></section>
      <section><h2>Notre histoire</h2></section>
      <section><h2>Marches</h2></section>
      <section><h2>Abonnement</h2></section>
      <section><h2>Contact</h2><img src="/atelier.avif" alt="atelier" /></section>
    </div>
  )
}
`

  test('un SPA React n est plus juge sur sa coquille Vite de 223 octets', () => {
    const files = [file('index.html', VITE_SHELL, 'html'), file('src/pages/HomePage.tsx', PAGE)]
    const report = evaluateVisualFidelity(files, WEB_INTENT, null, SHOWCASE_BRIEF)
    // Les 6 <section> vivent dans le .tsx: avant, la porte en comptait 0.
    assert.equal(report.failedChecks.includes('min_sections'), false)
    assert.match(report.checks.find((check) => check.id === 'min_sections')!.label, /trouve: 6/)
    // Les 2 <img> aussi.
    assert.equal(report.failedChecks.includes('has_images'), false)
    // Tailwind: le degrade et le flex sont des CLASSES, jamais des declarations CSS.
    assert.equal(report.failedChecks.includes('has_gradient'), false)
    assert.equal(report.failedChecks.includes('has_modern_layout'), false)
  })

  test('un projet static_web sans composants garde le comportement d avant', () => {
    const files = [file('index.html', VITE_SHELL, 'html')]
    const report = evaluateVisualFidelity(files, { projectType: 'static_web' } as unknown as CodeIntent, null, SHOWCASE_BRIEF)
    assert.equal(report.failedChecks.includes('min_sections'), true)
    assert.match(report.checks.find((check) => check.id === 'min_sections')!.label, /trouve: 0/)
    assert.equal(report.failedChecks.includes('html_size'), true)
  })
})

describe('capstone — le parser dit OU, pas seulement QUE', () => {
  // Mesure reelle (run 1011): « AboutPage.tsx: erreur de syntaxe » a coute
  // quatre passes de correction. Le parser connaissait la position exacte
  // depuis le debut — il suffisait de la lire.
  test('une apostrophe non echappee est localisee a la ligne et au jeton', async () => {
    const source = [
      'const markets = [',
      '  { id: 1, day: "samedi" },',
      "  { id: 2, location: 'Presqu'ile' },",
      ']',
    ].join('\n')
    const report = await syntaxCritic(
      { generationId: 't', files: [file('src/data/markets.ts', source, 'ts')] },
      WEB_INTENT,
    )
    const blocker = report.issues.find((issue) => issue.severity === 'block')
    assert.ok(blocker, 'le fichier casse doit bloquer')
    assert.match(blocker!.message, /markets\.ts:3:/)
    assert.match(blocker!.message, /Presqu/)
  })

  test('un fichier sain ne porte aucune position', async () => {
    const report = await syntaxCritic(
      { generationId: 't', files: [file('src/ok.ts', 'export const a = 1\n', 'ts')] },
      WEB_INTENT,
    )
    assert.deepEqual(report.issues.filter((issue) => issue.severity === 'block'), [])
  })

  test('la suggestion invite a corriger A la position donnee', async () => {
    const report = await syntaxCritic(
      { generationId: 't', files: [file('src/bad.ts', 'const a = (1 + \n', 'ts')] },
      WEB_INTENT,
    )
    const blocker = report.issues.find((issue) => issue.severity === 'block')
    assert.match(blocker!.suggestion ?? '', /CETTE position/)
  })
})
