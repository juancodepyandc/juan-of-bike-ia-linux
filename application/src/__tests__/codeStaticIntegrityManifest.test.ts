import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { projectIntegrityCritic } from '../services/codeStaticProjectIntegrity.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

// BALAYAGE des portes: une porte qui ne peut pas LIRE ne doit pas condamner.
//
// `hasTailwindSetup` rendait `false` quand `package.json` n etait pas parsable —
// donc « pas de Tailwind » — et la porte accusait « Classes Tailwind detectees
// sans configuration Tailwind ». Elle n avait rien mesure: elle n avait pas pu
// lire. Le conseil joint (« ajouter tailwindcss + config/postcss ») etait de
// surcroit irrealisable, puisque npm ne peut pas ouvrir un manifeste invalide.
// Et le VRAI defaut — JSON invalide, qui bloque toute installation — n etait
// signale nulle part.

const TAILWIND_PAGE = `
export default function App() {
  return (
    <div className="flex items-center justify-between gap-4 px-6 py-4">
      <h1 className="text-2xl font-bold text-slate-900">Brulerie</h1>
      <span className="rounded-lg bg-amber-600 shadow-md">Commander</span>
    </div>
  )
}
`

function project(packageJson: string) {
  return {
    generationId: 'test',
    files: [
      { name: 'package.json', language: 'json', content: packageJson },
      { name: 'index.html', language: 'html', content: '<!doctype html><html><body><div id="root"></div></body></html>' },
      { name: 'src/App.tsx', language: 'tsx', content: TAILWIND_PAGE },
    ],
  }
}

const intent = classifyCodeIntent('un site vitrine react pour une brulerie de cafe')

describe('portes: un manifeste illisible ne condamne pas Tailwind', () => {
  test('package.json invalide: le VRAI defaut est nomme, et il est reparable', async () => {
    const report = await projectIntegrityCritic(project('{ "name": "x", "dependencies": { "react": "^18", } }'), intent)
    const manifestIssue = report.issues.find((issue) => /JSON invalide/i.test(issue.message))
    assert.ok(manifestIssue, 'un package.json invalide doit etre signale')
    assert.equal(manifestIssue?.severity, 'block')
    assert.match(manifestIssue?.suggestion ?? '', /syntaxe JSON/i)
  })

  test('package.json invalide: la porte Tailwind se TAIT au lieu d accuser', async () => {
    const report = await projectIntegrityCritic(project('{ "name": "x", "dependencies": { "react": "^18", } }'), intent)
    assert.equal(
      report.issues.filter((issue) => /sans configuration Tailwind/i.test(issue.message)).length,
      0,
      'elle n a pas pu lire le manifeste: elle ne sait pas si Tailwind est configure',
    )
  })

  test('package.json valide SANS tailwind: la porte accuse, et elle a raison', async () => {
    const report = await projectIntegrityCritic(project('{"name":"x","dependencies":{"react":"^18.2.0"}}'), intent)
    assert.ok(
      report.issues.some((issue) => /sans configuration Tailwind/i.test(issue.message)),
      'ici la mesure a bien eu lieu: manifeste lu, tailwindcss absent',
    )
    assert.equal(report.issues.filter((issue) => /JSON invalide/i.test(issue.message)).length, 0)
  })

  test('package.json valide AVEC tailwind: aucune accusation', async () => {
    const report = await projectIntegrityCritic(
      project('{"name":"x","dependencies":{"react":"^18.2.0"},"devDependencies":{"tailwindcss":"^3.4.0"}}'),
      intent,
    )
    assert.equal(report.issues.filter((issue) => /sans configuration Tailwind/i.test(issue.message)).length, 0)
  })
})
