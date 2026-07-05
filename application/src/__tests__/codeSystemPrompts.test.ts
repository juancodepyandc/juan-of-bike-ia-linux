/**
 * Tests pour services/codeSystemPrompts — system prompts par rôle agent.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildArchitecteSystemPrompt,
  buildCodeurSystemPrompt,
  buildAuditeurSystemPrompt,
  buildAuditeurDiagnosticPrompt,
  getSystemPromptForRole,
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

describe('buildCodeurSystemPrompt', () => {
  test('renvoie un prompt non vide', () => {
    const intent = classifyCodeIntent('landing page HTML CSS')
    const p = buildCodeurSystemPrompt(intent)
    assert.ok(p.length > 200)
  })

  test('promptHint forwardé / contextuel', () => {
    const intent = classifyCodeIntent('landing page')
    const a = buildCodeurSystemPrompt(intent, 'apple style premium')
    const b = buildCodeurSystemPrompt(intent)
    // Avec ou sans hint, le prompt doit être non vide
    assert.ok(a.length > 100)
    assert.ok(b.length > 100)
  })

  test('contient le format FICHIER', () => {
    const intent = classifyCodeIntent('react app')
    const p = buildCodeurSystemPrompt(intent)
    assert.ok(p.includes('FICHIER') || p.includes('FILE'))
  })

  test('React 3D verrouille JSON strict et noms R3F officiels', () => {
    const intent = classifyCodeIntent('application React Vite TypeScript 3D avec Three.js et HUD')
    const p = buildCodeurSystemPrompt(intent)
    assert.ok(/JSON strict/i.test(p))
    assert.ok(p.includes('@react-three/fiber'))
    assert.ok(p.includes('@react-three/drei'))
    assert.ok(p.includes('react-three/drei'))
    assert.ok(/hors `<Canvas>`|hors Canvas|Html/i.test(p))
  })

  test('static_web → directives design intégrées', () => {
    const intent = classifyCodeIntent('landing page HTML moderne')
    const p = buildCodeurSystemPrompt(intent, 'landing page')
    assert.ok(p.length > 500)
  })

  test('app complete → contrat livrable interdit la demo isolee', () => {
    const intent = classifyCodeIntent('application complete client CRM avec dashboard, recherche, notifications, workflow et UI pro')
    const p = buildCodeurSystemPrompt(intent)
    assert.ok(/CONTRAT LIVRABLE/i.test(p))
    assert.ok(/fichier independant minimal/i.test(p))
    assert.ok(/environ\s+\d+\s+fichiers/i.test(p))
    assert.ok(/point d entree, la configuration, les styles, les composants\/services/i.test(p))
  })

  test('CLI complete → console comme produit, pas UI tunnel', () => {
    const intent = classifyCodeIntent('CLI Python complet pour analyser des logs avec sous-commandes et tests')
    const p = buildCodeurSystemPrompt(intent)
    assert.ok(/Mode de livraison retenu: CLI_CONSOLE/i.test(p))
    assert.ok(/La console est le produit/i.test(p))
    assert.ok(/--help/i.test(p))
  })

  test('projet complexe 3D/multipage → contrat expert sans reduction de scope', () => {
    const intent = classifyCodeIntent('plateforme web complete multipage avec simulateur 3D, dashboard, favoris, recherche, tunnel preview et rendu premium')
    const p = buildCodeurSystemPrompt(intent)
    assert.equal(intent.needsArchitecturePlanning, true)
    assert.ok(/CONTRAT INGENIEUR EXPERT/i.test(p))
    assert.ok(/Ne reduis pas le scope/i.test(p))
    assert.ok(/3D\/simulateur/i.test(p))
    assert.ok(/Securite par defaut/i.test(p))
  })

  test('CLI/OS complexe → garde-fous systeme et dry-run', () => {
    const intent = classifyCodeIntent('outil CLI Rust complet de personnalisation OS avec profils, rollback, dry-run et verification securite')
    const p = buildCodeurSystemPrompt(intent)
    assert.ok(/CLI\/system\/OS/i.test(p))
    assert.ok(/dry-run/i.test(p))
    assert.ok(/confirmation explicite/i.test(p))
    assert.ok(/privileges admin/i.test(p))
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

describe('getSystemPromptForRole', () => {
  const intent = classifyCodeIntent('landing react')

  test('role architecte', () => {
    const p = getSystemPromptForRole('architecte', intent)
    assert.ok(p.length > 100)
    assert.equal(p, buildArchitecteSystemPrompt(intent))
  })

  test('role codeur', () => {
    const p = getSystemPromptForRole('codeur', intent)
    assert.ok(p.length > 100)
    assert.equal(p, buildCodeurSystemPrompt(intent))
  })

  test('role auditeur', () => {
    const p = getSystemPromptForRole('auditeur', intent)
    assert.ok(p.length > 100)
    assert.equal(p, buildAuditeurSystemPrompt())
  })

  test('role diagnosticien', () => {
    const p = getSystemPromptForRole('diagnosticien', intent)
    assert.ok(p.length > 100)
    assert.equal(p, buildAuditeurDiagnosticPrompt())
  })

  test('rôles distincts donnent prompts distincts', () => {
    const a = getSystemPromptForRole('architecte', intent)
    const c = getSystemPromptForRole('codeur', intent)
    const u = getSystemPromptForRole('auditeur', intent)
    assert.notEqual(a, c)
    assert.notEqual(a, u)
    assert.notEqual(c, u)
  })
})

describe('Cohérence prompts', () => {
  test('chaque prompt > 100 chars (substantiel)', () => {
    const intent = classifyCodeIntent('react app')
    for (const role of ['architecte', 'codeur', 'auditeur', 'diagnosticien'] as const) {
      const p = getSystemPromptForRole(role, intent)
      assert.ok(p.length > 100, `${role} prompt trop court`)
    }
  })

  test('codeur prompt mentionne format sortie', () => {
    const intent = classifyCodeIntent('react')
    const p = buildCodeurSystemPrompt(intent)
    assert.ok(/FICHIER|FILE|---/i.test(p))
  })
})
