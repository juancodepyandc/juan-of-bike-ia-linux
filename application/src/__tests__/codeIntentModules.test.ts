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
import { appendAssetPromptSections } from '../services/codeIntentPromptAssets.ts'
import { appendGamePrompt } from '../services/codeIntentPromptGame.ts'
import { appendProjectPromptSections } from '../services/codeIntentPromptProject.ts'
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

  test('ajoute les sections de prompt extraites', () => {
    const gameIntent = classifyCodeIntent('Crée le jeu Tetris en canvas HTML5 avec score')
    const gameLines: string[] = []
    appendGamePrompt(gameLines, gameIntent)
    assert.ok(gameLines.join('\n').includes('Clone fidele de Tetris'))

    const projectIntent = classifyCodeIntent('application web complete dashboard CRM avec routing')
    const projectLines: string[] = []
    appendProjectPromptSections(projectLines, projectIntent)
    assert.ok(projectLines.join('\n').includes('Instructions dev server'))

    const assetIntent = classifyCodeIntent('landing page Nike premium avec images')
    const assetLines: string[] = []
    appendAssetPromptSections(assetLines, assetIntent)
    assert.ok(assetLines.join('\n').includes('FIDELITE AU SUJET'))
  })
})
