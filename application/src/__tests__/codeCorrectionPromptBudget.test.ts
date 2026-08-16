import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  CHARS_PER_TOKEN,
  RESERVED_OUTPUT_TOKENS,
  correctionFileBudgetChars,
  describeOmittedFiles,
  filesNamedByFailures,
  selectFilesForCorrectionPrompt,
} from '../services/codeCorrectionPromptBudget.ts'
import type { CodeFile } from '../services/codeOrchestratorTypes.ts'

/** Silhouette du projet reel du run 1141: 35 fichiers, ~87 000 octets. */
const PROJECT: CodeFile[] = [
  { name: 'src/components/SubscriptionForm.tsx', language: 'tsx', content: 'S'.repeat(9475) },
  { name: 'src/pages/AboutPage.tsx', language: 'tsx', content: 'A'.repeat(6339) },
  { name: 'src/pages/HomePage.tsx', language: 'tsx', content: 'H'.repeat(5491) },
  { name: 'src/components/ContactForm.tsx', language: 'tsx', content: 'C'.repeat(5394) },
  { name: 'src/App.tsx', language: 'tsx', content: 'P'.repeat(1062) },
  { name: 'package.json', language: 'json', content: '{}'.padEnd(734, ' ') },
]

describe('budget de prompt de correction — laisser la place de repondre', () => {
  // Mesure run 1141, prompt reellement construit sur les 35 fichiers livres:
  // 24 542 jetons dans une fenetre de 24 576 -> 34 jetons pour la reponse.
  test('la sortie est reservee AVANT de remplir', () => {
    const budget = correctionFileBudgetChars({ contextTokens: 24_576, otherPromptChars: 6_000 })
    const promptTokens = 6_000 / CHARS_PER_TOKEN + budget / CHARS_PER_TOKEN
    assert.ok(promptTokens <= 24_576 - RESERVED_OUTPUT_TOKENS + 1)
    assert.ok(RESERVED_OUTPUT_TOKENS >= 4_000, 'trop peu pour reecrire des fichiers entiers')
  })

  test('le budget ne tombe jamais a zero, meme avec un en-tete enorme', () => {
    assert.ok(correctionFileBudgetChars({ contextTokens: 24_576, otherPromptChars: 500_000 }) >= 4_000)
  })

  test('les fichiers NOMMES par les erreurs sont retenus, meme les plus gros', () => {
    const failing = [
      "src/components/SubscriptionForm.tsx(12,3): error TS2339: Property 'x' does not exist.",
      "src/pages/AboutPage.tsx(4,1): error TS2307: Cannot find module './Logo'.",
    ]
    const named = filesNamedByFailures(PROJECT, failing)
    assert.equal(named.has('src/components/subscriptionform.tsx'), true)
    assert.equal(named.has('src/pages/aboutpage.tsx'), true)
    assert.equal(named.has('src/pages/homepage.tsx'), false)

    // Budget volontairement etroit: sans priorite, le plus gros fichier (9 475)
    // serait le premier ecarte — or c est celui que l erreur designe.
    const selection = selectFilesForCorrectionPrompt({
      files: PROJECT, failingOutputs: failing, budgetChars: 17_000,
    })
    const kept = selection.included.map((f) => f.name)
    assert.ok(kept.includes('src/components/SubscriptionForm.tsx'))
    assert.ok(kept.includes('src/pages/AboutPage.tsx'))
    assert.ok(selection.omitted.length > 0)
  })

  test('aucun fichier n est coupe en deux', () => {
    const selection = selectFilesForCorrectionPrompt({
      files: PROJECT, failingOutputs: [], budgetChars: 12_000,
    })
    for (const file of selection.included) {
      const original = PROJECT.find((f) => f.name === file.name)!
      assert.equal(file.content, original.content, `${file.name} tronque`)
    }
  })

  test('au moins un fichier passe toujours, meme si le budget est minuscule', () => {
    const selection = selectFilesForCorrectionPrompt({
      files: PROJECT, failingOutputs: [], budgetChars: 10,
    })
    assert.equal(selection.included.length, 1)
    assert.equal(selection.omitted.length, PROJECT.length - 1)
  })

  test('tout tient: rien n est omis', () => {
    const selection = selectFilesForCorrectionPrompt({
      files: PROJECT, failingOutputs: [], budgetChars: 1_000_000,
    })
    assert.equal(selection.included.length, PROJECT.length)
    assert.deepEqual(selection.omitted, [])
    assert.equal(describeOmittedFiles(selection.omitted), '')
  })

  test('les fichiers omis sont NOMMES et declares intouchables', () => {
    // Sans cela le modele croit qu ils n existent pas et les recree — c est
    // exactement la regression que le garde anti-regression passait son temps
    // a refuser.
    const text = describeOmittedFiles(['src/utils/animations.ts', 'README.md'])
    assert.match(text, /2 FICHIER\(S\) DU PROJET NON JOINTS/)
    assert.match(text, /Ils EXISTENT et sont corrects/)
    assert.match(text, /Ne les recree pas/)
    assert.match(text, /src\/utils\/animations\.ts/)
  })
})
