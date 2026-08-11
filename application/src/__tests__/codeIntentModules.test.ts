import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyCodeIntent } from '../services/codeIntent.ts'
import { classifyCodeAssetPlan } from '../services/codeIntentAssets.ts'
import { BRAND_DICTIONARY } from '../services/codeIntentBrandProfiles.ts'
import { getBuildCommand, getDevCommand, getTestCommand } from '../services/codeIntentCommands.ts'
import { estimateComplexity } from '../services/codeIntentComplexity.ts'
import { estimateFileCount, isWholeProductRequest, minimumFileCountForIntent } from '../services/codeIntentFileCount.ts'
import { classifyGameKind, detectKnownGame } from '../services/codeIntentGameCatalog.ts'
import { detectPromptLanguage } from '../services/codeIntentLanguage.ts'
import { looksLikeDesktopAppRequest, looksLikeMobileAppRequest } from '../services/codeIntentPlatformHeuristics.ts'
import { FRAMEWORK_SIGNALS, GAME_SIGNALS } from '../services/codeIntentSignals.ts'
import { containsAnySignal, containsSignal, normalizeSignalText } from '../services/codeIntentSignalUtils.ts'
import { detectSubject } from '../services/codeIntentSubject.ts'

describe('codeIntent modules — signal tables and utilities', () => {
  test('normalise les accents et garde une detection par mot entier', () => {
    const lower = normalizeSignalText('Crée un DÉMINEUR en canvas')
    assert.equal(lower, 'cree un demineur en canvas')
    assert.equal(containsSignal(lower, 'demineur'), true)
    assert.equal(containsSignal('reactive dashboard', 'react'), false)
  })

  test('expose les tables de routage critiques', () => {
    assert.equal(FRAMEWORK_SIGNALS.react.projectType, 'spa_react')
    assert.equal(containsAnySignal('jeu tetris canvas', GAME_SIGNALS), true)
  })
})

describe('codeIntent modules — games, brands and subjects', () => {
  test('classe un clone connu avec ses mecaniques', () => {
    const known = detectKnownGame('jeu tetris dans le navigateur')
    assert.equal(known?.canonical, 'Tetris')

    const result = classifyGameKind('jeu tetris dans le navigateur', true)
    assert.equal(result.gameKind, 'clone')
    assert.equal(result.knownGame?.canonical, 'Tetris')
  })

  test('detecte une marque connue mais ne fabrique pas de marque pour un jeu generique', () => {
    const nike = detectSubject('Landing page Nike premium')
    assert.equal(nike.source, 'brand')
    assert.equal(nike.canonical, 'Nike')

    const game = detectSubject('Jeu de plateforme. Plusieurs niveaux et ennemis.')
    assert.equal(game.source, 'none')

    assert.ok(BRAND_DICTIONARY.some((entry) => entry.canonical === 'Nike'))
  })
})

describe('codeIntent modules — assets and language', () => {
  test('construit un asset plan avec marque, palette, recherche et langue', () => {
    const plan = classifyCodeAssetPlan('Crée une landing page Nike premium #ff00aa avec image hero')
    assert.equal(plan.subject.canonical, 'Nike')
    assert.equal(plan.language, 'fr')
    assert.equal(plan.wantsImages, true)
    assert.equal(plan.wantsResearch, true)
    assert.deepEqual(plan.paletteHints, ['#ff00aa'])
    assert.ok(plan.researchQueries.some((q) => q.includes('Nike')))
  })

  test('detecte les langues principales', () => {
    assert.equal(detectPromptLanguage('Fais moi une page web avec un bouton'), 'fr')
    assert.equal(detectPromptLanguage('Please build a modern dashboard with charts'), 'en')
  })
})

describe('codeIntent modules — commands and sizing', () => {
  test('route les commandes runtime selon le type de projet', () => {
    assert.equal(getDevCommand('spa_react'), 'npm run dev')
    assert.equal(getBuildCommand('api_gin'), 'go build ./...')
    assert.equal(getTestCommand('api_fastapi'), 'pytest')
  })

  test('estime complexite et taille minimale sans appauvrir les produits complets', () => {
    assert.equal(estimateComplexity('plateforme SaaS production scalable'), 'enterprise')
    assert.equal(isWholeProductRequest('application complete dashboard crm client'), true)
    assert.ok(estimateFileCount('complex', 'spa_react') >= 20)
    assert.equal(minimumFileCountForIntent('static_web', ['multipage'], false), 4)
  })
})

describe('codeIntent modules — platform and prompt appenders', () => {
  test('distingue les demandes natives explicites', () => {
    assert.equal(looksLikeMobileAppRequest('application Android avec APK'), true)
    assert.equal(looksLikeDesktopAppRequest('application de bureau Tauri'), true)
  })

})

// --- Formulation HUMAINE vs application native (2026-08-11) ----------------
// Cas reel: un artisan torrefacteur ecrit « je me lance dans un vrai site […]
// Doit marcher nickel sur mobile parce que 80% des gens qui nous trouvent c est
// sur leur telephone ». Le pipeline a livre une application REACT NATIVE
// (babel.config.js, App.tsx, AppNavigator.tsx) au lieu d un site.
//
// Cause: `MOBILE_SIGNALS` contient le mot NU « mobile » — alors que
// `DESKTOP_SIGNALS`, lui, n emploie que des locutions ("application de bureau").
// Un garde web existait (v89b) mais ne couvrait que la formulation TECHNIQUE
// ("site web", "responsive", "navigateur"), jamais « un vrai site » ni « page
// d accueil ».
describe('classification — « marche sur mobile » ne fait pas une appli native', () => {
  test('un site dont on dit qu il doit marcher sur mobile reste du WEB', () => {
    const intent = classifyCodeIntent(
      "je veux un vrai site pour ma marque de cafe, une page d accueil qui donne envie. "
      + "Doit marcher nickel sur mobile parce que 80% des gens sont sur leur telephone",
    )
    assert.ok(!intent.projectType.startsWith('mobile_'), `attendu du web, obtenu ${intent.projectType}`)
  })

  test('une VRAIE demande d appli native reste native', () => {
    for (const p of [
      'cree une application mobile React Native pour android et ios avec navigation',
      'je veux une appli pour telephone, publiee sur le play store',
    ]) {
      assert.ok(classifyCodeIntent(p).projectType.startsWith('mobile_'), p)
    }
  })

  test('« sur site » signifie sur place, pas site web', () => {
    const intent = classifyCodeIntent('un outil pour gerer les interventions sur site de nos techniciens')
    assert.ok(!intent.projectType.startsWith('mobile_'))
  })

  test('un site vitrine ordinaire reste du web', () => {
    assert.ok(!classifyCodeIntent('un site vitrine pour mon restaurant avec la carte').projectType.startsWith('mobile_'))
  })
})
