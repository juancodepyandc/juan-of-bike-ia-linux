import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyCodeIntent } from '../services/codeIntent.ts'
import { detectDesignArchetype } from '../services/codeDesignDirectives.ts'
import {
  CODE_DESIGN_SPEC_SCHEMA,
  buildCodeDesignSpec,
  formatCodeDesignSpecPrompt,
  verifyCodeDesignSpecAgainstFiles,
} from '../services/codeDesignSpec.ts'

describe('codeDesignSpec', () => {
  test('genere une design-spec JSON verifiable pour une landing web', () => {
    const intent = classifyCodeIntent('landing page SaaS premium')
    const archetype = detectDesignArchetype('landing page SaaS premium', intent)
    const spec = buildCodeDesignSpec('landing page SaaS premium', intent, archetype)
    const block = formatCodeDesignSpecPrompt(spec)

    assert.equal(spec.schemaVersion, CODE_DESIGN_SPEC_SCHEMA)
    assert.equal(spec.platform, 'web')
    assert.ok(spec.palette.some((color) => color.role === 'accent'))
    assert.match(block, /AURORA_CODE_DESIGN_SPEC\/1/)
    assert.match(block, /"palette"/)
  })

  test('verifie palette perceptuelle, tokens et wireframe web', () => {
    const intent = classifyCodeIntent('landing page SaaS premium')
    const spec = buildCodeDesignSpec('landing page SaaS premium', intent, 'saas_marketing')
    const report = verifyCodeDesignSpecAgainstFiles(spec, [
      {
        name: 'index.html',
        language: 'html',
        content: '<section class="hero">hero</section><section>features</section><section>cta</section><nav>nav</nav><footer>footer</footer>',
      },
      {
        name: 'style.css',
        language: 'css',
        content: ':root{--accent:#7c3aed;--bg:oklch(0.13 0.012 252);--fg:oklch(0.96 0.004 252)} .feature{color:var(--accent)}',
      },
    ])

    assert.equal(report.ok, true, JSON.stringify(report.issues))
  })

  test('detecte ecarts palette et plateforme mobile native', () => {
    const intent = classifyCodeIntent('react native expo mobile app')
    const spec = buildCodeDesignSpec('react native expo mobile app', intent, 'mobile_native_premium')
    const report = verifyCodeDesignSpecAgainstFiles(spec, [
      { name: 'App.tsx', language: 'tsx', content: 'export default function App(){ return null }' },
      { name: 'style.css', language: 'css', content: 'body{color:#111}' },
    ])

    assert.equal(report.ok, false)
    assert.ok(report.issues.some((issue) => issue.kind === 'platform'))
    assert.ok(report.issues.some((issue) => issue.kind === 'palette'))
  })

  test('jeu canvas exige boucle canvas au lieu de landing deguisee', () => {
    const intent = classifyCodeIntent('jeu pong arcade canvas')
    const spec = buildCodeDesignSpec('jeu pong arcade canvas', intent, 'game_visual_premium')
    const report = verifyCodeDesignSpecAgainstFiles(spec, [
      { name: 'index.html', language: 'html', content: '<main><h1>Pong</h1></main>' },
    ])

    assert.equal(spec.platform, 'game_canvas')
    assert.ok(report.issues.some((issue) => issue.detail === 'game_canvas_missing_canvas_loop'))
  })
})
