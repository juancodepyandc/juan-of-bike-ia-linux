// Verrouille le garde-fou du classifieur semantique.
//
// Regression reelle: le prompt « landing page premium pour la marque
// Mercedes-Benz, hero anime, section specs, formulaire de contact, responsive »
// a ete classe `ide` par le modele, avec une confiance au-dessus du seuil, et
// `runIntentPhase` a remplace l heuristique sans controle. Le projectType
// pilotant l archetype, le contrat de livraison et les commandes, la livraison
// partait en design d editeur de code sans page d entree.
//
// Et c etait non deterministe: le meme prompt gardait `static_web` sur un run
// (classifieur en timeout) et basculait sur `ide` au suivant.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  codeProjectFamily,
  decideSemanticIntentOverride,
} from '../services/codeSemanticIntentGuard.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

const intentOf = (type: string) => ({ projectType: type } as never)

const MERCEDES =
  'landing page premium pour la marque Mercedes-Benz, hero anime, section specs, formulaire de contact, responsive'

describe('codeSemanticIntentGuard', () => {
  test('rejette le basculement `static_web` -> `ide` non corrobore (cas reel)', () => {
    const heuristic = classifyCodeIntent(MERCEDES)
    assert.equal(heuristic.projectType, 'static_web')
    const decision = decideSemanticIntentOverride({
      prompt: MERCEDES,
      heuristic,
      semantic: intentOf('ide'),
    })
    assert.equal(decision.accept, false)
    assert.equal(decision.reason, 'cross_family_unsupported')
  })

  test('accepte `ide` quand le prompt parle vraiment d un editeur de code', () => {
    const prompt = 'un IDE web avec file tree, coloration syntaxique et terminal integre'
    const decision = decideSemanticIntentOverride({
      prompt,
      heuristic: classifyCodeIntent(prompt),
      semantic: intentOf('ide'),
    })
    assert.equal(decision.accept, true)
  })

  test('accepte un affinage dans la meme famille (static_web -> spa_react)', () => {
    const decision = decideSemanticIntentOverride({
      prompt: 'un site avec des composants dynamiques',
      heuristic: intentOf('static_web'),
      semantic: intentOf('spa_react'),
    })
    assert.equal(decision.accept, true)
    assert.equal(decision.reason, 'same_family')
  })

  test('laisse la main au modele quand l heuristique n a rien reconnu', () => {
    const decision = decideSemanticIntentOverride({
      prompt: 'quelque chose de tres exotique',
      heuristic: intentOf('unknown'),
      semantic: intentOf('compiler'),
    })
    assert.equal(decision.accept, true)
    assert.equal(decision.reason, 'heuristic_low_information')
  })

  test('laisse passer les types exotiques corrobores (raison d etre du classifieur)', () => {
    const cases: Array<[string, string]> = [
      ['ecris un compilateur avec lexer, parser et AST', 'compiler'],
      ['un noyau bare metal qui boote et affiche un message', 'os_kernel'],
      ['firmware embarque pour esp32 qui lit un capteur', 'embedded_esp32'],
    ]
    for (const [prompt, type] of cases) {
      const decision = decideSemanticIntentOverride({
        prompt,
        heuristic: intentOf('cli_python'),
        semantic: intentOf(type),
      })
      assert.equal(decision.accept, true, `${type} devrait etre accepte pour: ${prompt}`)
    }
  })

  test('type identique: decision triviale, aucun rejet', () => {
    const decision = decideSemanticIntentOverride({
      prompt: 'peu importe',
      heuristic: intentOf('static_web'),
      semantic: intentOf('static_web'),
    })
    assert.equal(decision.accept, true)
    assert.equal(decision.reason, 'same_type')
  })

  test('familles connues pour les types structurants', () => {
    assert.equal(codeProjectFamily('static_web'), 'web')
    assert.equal(codeProjectFamily('ide'), 'tool')
    assert.equal(codeProjectFamily('os_kernel'), 'system')
    assert.equal(codeProjectFamily('mobile_rn'), 'mobile')
  })

  test('un jeu ne bascule pas en systeme sans indice', () => {
    const prompt = 'jeu pong arcade canvas avec score'
    const decision = decideSemanticIntentOverride({
      prompt,
      heuristic: classifyCodeIntent(prompt),
      semantic: intentOf('os_kernel'),
    })
    assert.equal(decision.accept, false)
  })
})
