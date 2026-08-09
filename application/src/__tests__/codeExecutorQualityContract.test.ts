// Verrouille le contrat qualite envoye au CODEUR pendant la generation WS3.
//
// Contexte de la regression: quand WS3 est devenu le moteur de generation,
// `buildCodeurSystemPrompt` (contrat design, verrouillage marque, contrat de
// livraison, interactivite) est devenu orphelin — son seul appelant restant,
// `getSystemPromptForRole`, n avait plus aucun appelant de production. Le
// modele generait donc sans connaitre la barre de qualite, ce qui a produit un
// run reel de 14 fichiers SANS index.html sur un `static_web`.
//
// Ces tests garantissent que le contrat existe, qu il porte les regles dures du
// module (marque, livraison, archetype) et qu il reste borne en taille — WS3
// appelle le modele une fois par fichier, un prompt non borne se paierait a
// chaque appel.

import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  EXECUTOR_QUALITY_CONTRACT_CONFIG_MAX_CHARS,
  EXECUTOR_QUALITY_CONTRACT_MAX_CHARS,
  buildExecutorQualityContract,
} from '../services/codeExecutorQualityContract.ts'
import { buildCodeGenerationActionMessages } from '../services/codeGenerationActionProducer.ts'
import { classifyCodeIntent } from '../services/codeIntent.ts'

const BRAND_PROMPT = 'landing page premium pour la marque Mercedes-Benz, hero anime, section specs'

describe('codeExecutorQualityContract', () => {
  test('verrouille la marque sur un fichier visuel (regle dure fidelite marque)', () => {
    const intent = classifyCodeIntent(BRAND_PROMPT)
    const contract = buildExecutorQualityContract({
      intent,
      prompt: BRAND_PROMPT,
      target: { path: 'index.html' },
    })
    assert.match(contract, /Mercedes-Benz/, 'le nom de marque doit etre transmis au codeur')
    assert.match(contract, /VERROUILLAGE SUJET/, 'le bloc de verrouillage sujet doit etre present')
  })

  test('transmet le contrat de livraison: index.html obligatoire en static_web', () => {
    // C est exactement ce qui manquait au run reel qui a livre 14 fichiers sans
    // page d entree puis brule une passe de regeneration pour s en apercevoir.
    const intent = classifyCodeIntent(BRAND_PROMPT)
    assert.equal(intent.projectType, 'static_web')
    const contract = buildExecutorQualityContract({
      intent,
      prompt: BRAND_PROMPT,
      target: { path: 'src/main.ts' },
    })
    assert.match(contract, /index\.html/)
    assert.match(contract, /CONTRAT DE LIVRAISON/)
  })

  test('transmet l archetype design detecte sur un fichier visuel', () => {
    const intent = classifyCodeIntent(BRAND_PROMPT)
    const contract = buildExecutorQualityContract({
      intent,
      prompt: BRAND_PROMPT,
      target: { path: 'index.html' },
    })
    assert.match(contract, /ARCHETYPE RETENU/)
  })

  test('un fichier de configuration ne paie pas les directives esthetiques', () => {
    const intent = classifyCodeIntent(BRAND_PROMPT)
    const visual = buildExecutorQualityContract({ intent, prompt: BRAND_PROMPT, target: { path: 'index.html' } })
    const config = buildExecutorQualityContract({ intent, prompt: BRAND_PROMPT, target: { path: 'tsconfig.json' } })
    assert.ok(
      config.length <= EXECUTOR_QUALITY_CONTRACT_CONFIG_MAX_CHARS,
      `contrat config ${config.length} > budget ${EXECUTOR_QUALITY_CONTRACT_CONFIG_MAX_CHARS}`,
    )
    assert.ok(config.length < visual.length / 4, 'un fichier de config doit couter bien moins qu un fichier visuel')
    assert.doesNotMatch(config, /ARCHETYPE RETENU/)
  })

  test('vite.config.ts est traite comme de la configuration, pas comme de l UI', () => {
    const intent = classifyCodeIntent('dashboard fintech temps reel, graphique live, tableau triable')
    const contract = buildExecutorQualityContract({
      intent,
      prompt: 'dashboard fintech temps reel',
      target: { path: 'vite.config.ts' },
    })
    assert.ok(contract.length <= EXECUTOR_QUALITY_CONTRACT_CONFIG_MAX_CHARS)
  })

  test('respecte le budget de caracteres sur un fichier visuel', () => {
    const intent = classifyCodeIntent(BRAND_PROMPT)
    const contract = buildExecutorQualityContract({
      intent,
      prompt: BRAND_PROMPT,
      target: { path: 'index.html' },
    })
    assert.ok(
      contract.length <= EXECUTOR_QUALITY_CONTRACT_MAX_CHARS,
      `contrat ${contract.length} > budget ${EXECUTOR_QUALITY_CONTRACT_MAX_CHARS}`,
    )
  })

  test('un projet non visuel ne recoit aucune directive esthetique', () => {
    const prompt = 'script python qui parse un csv et sort un rapport'
    const intent = classifyCodeIntent(prompt)
    const contract = buildExecutorQualityContract({ intent, prompt, target: { path: 'main.py' } })
    assert.doesNotMatch(contract, /BARRE DE QUALITE VISUELLE/)
    assert.match(contract, /CONTRAT DE LIVRAISON/)
  })

  test('ne casse pas sur un assetPlan partiel (regression TypeError styleHints)', () => {
    // `detectDesignArchetype` faisait `ap?.styleHints.some(...)`: un assetPlan
    // sans styleHints levait un TypeError et faisait tomber la generation.
    const intent = { projectType: 'spa_react', complexity: 'complex', languages: [], frameworks: [], features: [], assetPlan: {} } as never
    assert.doesNotThrow(() => buildExecutorQualityContract({ intent, prompt: 'demo', target: { path: 'src/App.tsx' } }))
  })
})

describe('WS3 executor — le contrat qualite atteint reellement le prompt systeme', () => {
  const queueItem = {
    order: 1,
    path: 'index.html',
    language: 'html',
    role: 'page',
    required: true,
    imports: [],
    exports: [],
    notes: [],
  }
  const queue = { source: 'architecture_plan', items: [queueItem], requiredCount: 1, optionalCount: 0, omittedOrderPaths: [] } as never

  test('le prompt systeme porte le contrat quand l intent est fourni', () => {
    const intent = classifyCodeIntent(BRAND_PROMPT)
    const messages = buildCodeGenerationActionMessages({
      item: queueItem as never,
      itemIndex: 0,
      queue,
      files: [],
      prompt: BRAND_PROMPT,
      intent,
    })
    const system = messages.find((m) => m.role === 'system')
    assert.ok(system, 'un message systeme doit exister')
    assert.match(system.content, /EXECUTOR WS3 A OUTILS/, 'la plomberie WS3 reste presente')
    assert.match(system.content, /Mercedes-Benz/, 'le verrouillage marque doit atteindre le modele')
    assert.match(system.content, /CONTRAT DE LIVRAISON/, 'le contrat de livraison doit atteindre le modele')
  })

  test('sans intent, le prompt systeme reste la plomberie seule (retro-compatible)', () => {
    const messages = buildCodeGenerationActionMessages({
      item: queueItem as never,
      itemIndex: 0,
      queue,
      files: [],
      prompt: BRAND_PROMPT,
    })
    const system = messages.find((m) => m.role === 'system')
    assert.ok(system)
    assert.match(system.content, /EXECUTOR WS3 A OUTILS/)
    assert.doesNotMatch(system.content, /CONTRAT DE LIVRAISON/)
  })
})

// --- Cas de regression Mercedes (2026-08-10) -------------------------------
// Une landing Mercedes livree par le pipeline complet cassait au chargement
// (`Lenis is not defined`, URL CDN inventee en 404) et sortait son titre en
// 18 px. Trois contrats manquaient au codeur: les URL exactes, un seuil
// typographique mesurable, et l obligation de charger reellement la police.
describe('contrat qualite — regression Mercedes', () => {
  const PROMPT = 'landing page premium pour la marque Mercedes-Benz, hero anime, section specs'

  test('livre des URL CDN EXACTES au lieu de laisser le modele en inventer', () => {
    const intent = classifyCodeIntent(PROMPT)
    const c = buildExecutorQualityContract({ intent, prompt: PROMPT, target: { path: 'index.html' } })
    assert.match(c, /lenis@1\/dist\/lenis\.min\.js/, 'l URL Lenis exacte doit etre fournie')
    assert.match(c, /AUCUNE INVENTION/)
    assert.match(c, /gsap/i)
  })

  test('impose un seuil typographique mesurable, aligne sur le juge de rendu', () => {
    const intent = classifyCodeIntent(PROMPT)
    for (const target of ['index.html', 'css/styles.css']) {
      const c = buildExecutorQualityContract({ intent, prompt: PROMPT, target: { path: target } })
      assert.match(c, /clamp\(48px, 7vw, 96px\)/, `${target}: seuil hero absent`)
      assert.match(c, /QUATRE tailles/, `${target}: exigence d echelle absente`)
    }
  })

  test('exige le chargement REEL de la police (sinon fallback Georgia/Helvetica)', () => {
    const intent = classifyCodeIntent(PROMPT)
    const c = buildExecutorQualityContract({ intent, prompt: PROMPT, target: { path: 'index.html' } })
    assert.match(c, /fonts\.googleapis\.com/)
    assert.match(c, /Georgia\/Helvetica/)
  })

  test('avertit que les tailles par defaut peuvent etre reinitialisees', () => {
    const intent = classifyCodeIntent(PROMPT)
    const c = buildExecutorQualityContract({ intent, prompt: PROMPT, target: { path: 'css/styles.css' } })
    assert.match(c, /reinitialiser/i)
  })
})
