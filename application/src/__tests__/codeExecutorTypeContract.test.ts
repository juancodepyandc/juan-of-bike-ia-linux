import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { buildExecutorQualityContract } from '../services/codeExecutorQualityContract.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

// MESURE: les regles de typage existaient dans le contrat INGENIEUR et
// n atteignaient jamais l executor. WS3 appelle le modele une fois par fichier
// via `buildExecutorQualityContract`; le contrat ingenieur ne transite que par
// `codeSystemPrompts`. Les consignes etaient ecrites, testees... et jamais
// delivrees a ce qui ecrit le code.

const intent = classifyCodeIntent('site vitrine react pour une brulerie de cafe')
const contractFor = (path: string, language: string) => buildExecutorQualityContract({
  intent,
  prompt: 'site vitrine react pour une brulerie de cafe',
  target: { path, language, role: 'component' },
})

describe('le contrat de typage atteint enfin le fichier qu il concerne', () => {
  test('un composant .tsx recoit les regles de typage', () => {
    const contract = contractFor('src/components/OrderList.tsx', 'tsx')
    assert.match(contract, /CONTRAT DE TYPAGE/)
    assert.match(contract, /Aucun parametre implicitement `any`/)
    assert.match(contract, /aucune requise omise, aucune non declaree ajoutee/)
    assert.match(contract, /s ecrivent ENSEMBLE/)
    assert.match(contract, /jamais a un libelle affiche/)
  })

  test('un module .ts les recoit aussi', () => {
    assert.match(contractFor('src/data/coffees.ts', 'typescript'), /CONTRAT DE TYPAGE/)
  })

  test('un fichier NON type ne porte pas de contrat de typage', () => {
    // Le budget par fichier est borne: on ne depense pas de contexte pour rien.
    assert.doesNotMatch(contractFor('src/styles/global.css', 'css'), /CONTRAT DE TYPAGE/)
    assert.doesNotMatch(contractFor('index.html', 'html'), /CONTRAT DE TYPAGE/)
  })

  test('le contrat de typage precede les blocs esthetiques, donc survit au budget', () => {
    // Regression connue: les seuils typographiques etaient tronques parce que
    // places en fin de liste. Le typage ne doit pas subir le meme sort.
    const contract = contractFor('src/components/HeroSection.tsx', 'tsx')
    const typing = contract.indexOf('CONTRAT DE TYPAGE')
    const archetype = contract.indexOf('ARCHETYPE RETENU')
    assert.ok(typing >= 0)
    if (archetype >= 0) assert.ok(typing < archetype, 'le typage doit venir avant l archetype')
  })
})
