/**
 * Tests pour services/codeIntent — classification déterministe du type de
 * projet code (sans LLM).
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  classifyCodeIntent,
  hasExplicitStackMention,
  classifyPivotKindHeuristic,
} from '../services/codeIntent.ts'

describe('classifyCodeIntent — static_web', () => {
  test('page HTML simple', () => {
    const r = classifyCodeIntent('Fais-moi une landing page HTML/CSS pour mon café')
    assert.equal(r.projectType, 'static_web')
    assert.equal(r.needsDevServer, false)
  })

  test('site vitrine vintage', () => {
    const r = classifyCodeIntent('site vitrine pour un cabinet d\'avocats, html css js')
    assert.equal(r.projectType, 'static_web')
  })
})

describe('classifyCodeIntent — frameworks SPA', () => {
  test('React app détecté', () => {
    const r = classifyCodeIntent('Crée une app React avec un compteur')
    assert.equal(r.projectType, 'spa_react')
    assert.ok(r.languages.length > 0)
  })

  test('Vue app détecté', () => {
    const r = classifyCodeIntent('petite app Vue.js avec router')
    assert.equal(r.projectType, 'spa_vue')
  })

  test('Svelte détecté', () => {
    const r = classifyCodeIntent('crée une app en Svelte')
    assert.equal(r.projectType, 'spa_svelte')
  })
})

describe('classifyCodeIntent — APIs', () => {
  test('FastAPI', () => {
    const r = classifyCodeIntent('API REST en FastAPI avec endpoint /users')
    assert.equal(r.projectType, 'api_fastapi')
  })

  test('Express', () => {
    const r = classifyCodeIntent('API Node.js Express avec auth JWT')
    assert.equal(r.projectType, 'api_express')
  })

  test('Flask', () => {
    const r = classifyCodeIntent('serveur Flask Python simple')
    assert.equal(r.projectType, 'api_flask')
  })
})

describe('classifyCodeIntent — CLI', () => {
  test('Python CLI', () => {
    const r = classifyCodeIntent('script Python en ligne de commande pour renommer des fichiers')
    assert.ok(['cli_python', 'script', 'data_python'].includes(r.projectType))
  })

  test('Rust CLI', () => {
    const r = classifyCodeIntent('CLI Rust avec clap pour parser des args')
    assert.ok(['cli_rust', 'system_rust'].includes(r.projectType), `got ${r.projectType}`)
    assert.ok(r.languages.includes('rust') || r.frameworks.length > 0 || r.projectType.includes('rust'))
  })
})

describe('classifyCodeIntent — Games', () => {
  test('Snake game canvas → web ou jeu', () => {
    const r = classifyCodeIntent('Crée le jeu Snake en canvas HTML5 avec score')
    assert.ok(
      ['game_web', 'static_web', 'cli_node', 'spa_react'].includes(r.projectType),
      `got ${r.projectType}`,
    )
  })

  test('Tetris dans le navigateur → web', () => {
    const r = classifyCodeIntent('jeu Tetris dans le navigateur')
    assert.ok(['game_web', 'static_web'].includes(r.projectType))
  })
})

describe('classifyCodeIntent — Next.js fullstack', () => {
  test('Next.js détecté', () => {
    const r = classifyCodeIntent('app Next.js avec SSR et API routes')
    assert.ok(['ssr_nextjs', 'fullstack_nextjs'].includes(r.projectType))
  })
})

describe('classifyCodeIntent — taxonomie WS6 et cibles extremes', () => {
  test('firmware ESP32 route vers embedded_esp32', () => {
    const r = classifyCodeIntent('firmware ESP32 avec capteur temperature et logs serie')
    assert.equal(r.projectType, 'embedded_esp32')
    assert.ok(r.frameworks.includes('esp-idf'))
    assert.equal(r.previewType, 'console')
  })

  test('compilateur route vers compiler', () => {
    const r = classifyCodeIntent('cree un compilateur avec lexer parser AST et tests du langage')
    assert.equal(r.projectType, 'compiler')
    assert.ok(r.features.includes('compiler'))
    assert.equal(r.testCommand, 'cargo test')
  })

  test('noyau bootable QEMU route vers os_kernel', () => {
    const r = classifyCodeIntent('noyau OS minimal bootable sous QEMU avec heartbeat')
    assert.equal(r.projectType, 'os_kernel')
    assert.ok(r.features.includes('qemu'))
    assert.equal(r.buildCommand, 'make')
  })

  test('systeme distribue multi noeuds route vers distributed_system', () => {
    const r = classifyCodeIntent('systeme distribue multi noeuds avec consensus Raft et tests integration')
    assert.equal(r.projectType, 'distributed_system')
    assert.ok(r.frameworks.includes('docker-compose'))
  })

  test('mobile natif iOS/Android distingue les stacks natives', () => {
    assert.equal(classifyCodeIntent('app iOS native SwiftUI avec liste offline').projectType, 'mobile_ios')
    assert.equal(classifyCodeIntent('app Android native Kotlin Jetpack Compose').projectType, 'mobile_android')
  })

  test('IDE et moteur 3D ont un routage dedie', () => {
    assert.equal(classifyCodeIntent('IDE editeur de code avec arborescence et preview').projectType, 'ide')
    assert.equal(classifyCodeIntent('moteur 3D avec renderer scene camera et demo').projectType, 'engine_3d')
  })
})

describe('classifyCodeIntent — Edge cases', () => {
  test('prompt vide → unknown ou minimal', () => {
    const r = classifyCodeIntent('')
    assert.ok(r.projectType)
    assert.ok(r.complexity)
  })

  test('prompt très vague → still has fields', () => {
    const r = classifyCodeIntent('aide moi')
    assert.ok(typeof r.needsDevServer === 'boolean')
    assert.ok(typeof r.estimatedFileCount === 'number')
  })

  test('CodeIntent contient toujours assetPlan', () => {
    const r = classifyCodeIntent('un truc cool')
    assert.ok(r.assetPlan)
    assert.ok(Array.isArray(r.assetPlan.styleHints))
  })

  test('app client complete → planification + livrable multi-fichiers', () => {
    const r = classifyCodeIntent('cree une application complete pour un client: dashboard CRM avec auth, recherche, notifications, workflows et interface pro')
    assert.ok(['desktop_tauri', 'spa_react', 'fullstack_mern', 'fullstack_nextjs'].includes(r.projectType), `got ${r.projectType}`)
    assert.equal(r.needsArchitecturePlanning, true)
    assert.ok(r.estimatedFileCount >= 10, `estimatedFileCount=${r.estimatedFileCount}`)
  })

  test('application web client → UI dev-server/tunnel, pas console', () => {
    const r = classifyCodeIntent('application web complete pour gerer un tunnel de vente avec dashboard, clients, paiements et UI responsive')
    assert.ok(['spa_react', 'fullstack_mern', 'fullstack_nextjs'].includes(r.projectType), `got ${r.projectType}`)
    assert.notEqual(r.previewType, 'console')
    assert.ok(r.needsBundling || r.needsDevServer)
    assert.ok(r.estimatedFileCount >= 10)
  })

  test('SPA complexe avec 3D conserve la feature 3d et la planification', () => {
    const r = classifyCodeIntent('plateforme web complete multipage avec simulateur 3D, dashboard, tunnel preview et rendu premium')
    assert.equal(r.needsArchitecturePlanning, true)
    assert.ok(r.features.includes('3d'), `features=${r.features.join(',')}`)
    assert.ok(r.frameworks.includes('three.js'), `frameworks=${r.frameworks.join(',')}`)
    assert.notEqual(r.previewType, 'console')
  })

  test('vraie demande CLI reste console mais pas fichier unique pauvre', () => {
    const r = classifyCodeIntent('outil CLI Python complet pour analyser des logs avec sous-commandes, export CSV, configuration et tests')
    assert.ok(['cli_python', 'script', 'data_python'].includes(r.projectType), `got ${r.projectType}`)
    assert.equal(r.previewType, 'console')
    assert.ok(r.estimatedFileCount >= 5, `estimatedFileCount=${r.estimatedFileCount}`)
  })
})

describe('hasExplicitStackMention', () => {
  test('react → true', () => {
    assert.equal(hasExplicitStackMention('avec react et hooks'), true)
  })

  test('python → true', () => {
    assert.equal(hasExplicitStackMention('en python'), true)
  })

  test('aucun stack → false', () => {
    assert.equal(hasExplicitStackMention('fais un truc cool sympa'), false)
  })

  test('flask → true', () => {
    assert.equal(hasExplicitStackMention('serveur flask'), true)
  })
})

describe('classifyPivotKindHeuristic', () => {
  test('sans historique ni fichiers → fresh_start', () => {
    const r = classifyPivotKindHeuristic('nouveau projet', false, false)
    assert.equal(r, 'fresh_start')
  })

  test('refais la même chose en python → pivot_platform', () => {
    const r = classifyPivotKindHeuristic('refais la meme chose en python', true, true)
    assert.equal(r, 'pivot_platform')
  })

  test('court follow-up avec fichiers → increment', () => {
    const r = classifyPivotKindHeuristic('change la couleur en bleu', true, true)
    assert.equal(r, 'increment')
  })

  test('mention de stack court → pivot_platform', () => {
    const r = classifyPivotKindHeuristic('en vue', true, true)
    assert.equal(r, 'pivot_platform')
  })
})

