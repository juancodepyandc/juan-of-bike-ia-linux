/**
 * Tests pour services/codeSystemPrompts — system prompts par rôle agent.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildArchitecteSystemPrompt,
  buildAuditeurSystemPrompt,
  buildAuditeurDiagnosticPrompt,
} from '../services/codeSystemPrompts.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

describe('buildArchitecteSystemPrompt', () => {
  test('renvoie un prompt non vide', () => {
    const intent = classifyCodeIntent('app react simple')
    const p = buildArchitecteSystemPrompt(intent)
    assert.ok(p.length > 100)
  })

  test('mentionne le projectType', () => {
    const intent = classifyCodeIntent('app react avec router')
    const p = buildArchitecteSystemPrompt(intent)
    assert.ok(p.includes('spa_react') || p.toLowerCase().includes('react'))
  })

  test('différent par projectType', () => {
    const a = buildArchitecteSystemPrompt(classifyCodeIntent('react'))
    const b = buildArchitecteSystemPrompt(classifyCodeIntent('python cli script'))
    assert.notEqual(a, b)
  })
})


describe('buildAuditeurSystemPrompt', () => {
  test('renvoie un prompt non vide', () => {
    const p = buildAuditeurSystemPrompt()
    assert.ok(p.length > 100)
  })

  test('mentionne audit / verdict', () => {
    const p = buildAuditeurSystemPrompt()
    assert.ok(/audit|verdict|score|critique/i.test(p))
  })

  test('appel sans args → succès', () => {
    assert.doesNotThrow(() => buildAuditeurSystemPrompt())
  })

  test('déterministe', () => {
    assert.equal(buildAuditeurSystemPrompt(), buildAuditeurSystemPrompt())
  })
})

describe('buildAuditeurDiagnosticPrompt', () => {
  test('renvoie un prompt non vide', () => {
    const p = buildAuditeurDiagnosticPrompt()
    assert.ok(p.length > 100)
  })

  test('mentionne diagnostic / erreurs / cause', () => {
    const p = buildAuditeurDiagnosticPrompt()
    assert.ok(/diagnostic|erreur|cause|sandbox|echec/i.test(p))
  })

  test('différent de l auditeur classique', () => {
    assert.notEqual(buildAuditeurDiagnosticPrompt(), buildAuditeurSystemPrompt())
  })
})


describe('Cohérence prompts', () => {
  // `getSystemPromptForRole` et `buildCodeurSystemPrompt` ont ete supprimes:
  // orphelins depuis que WS3 genere fichier par fichier. Le contrat qualite
  // envoye au codeur vit desormais dans `codeExecutorQualityContract`, verrouille
  // par son propre test. Restent ici les deux roles reellement appeles en
  // production: l architecte (phase de planification) et l auditeur (correction).
  test('chaque prompt de role encore utilise est substantiel', () => {
    const intent = classifyCodeIntent('react app')
    for (const p of [buildArchitecteSystemPrompt(intent), buildAuditeurSystemPrompt(), buildAuditeurDiagnosticPrompt()]) {
      assert.ok(p.length > 100, 'prompt trop court')
    }
  })
})
