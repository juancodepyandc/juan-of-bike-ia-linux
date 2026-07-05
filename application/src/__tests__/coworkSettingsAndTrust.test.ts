/**
 * Tests for the new Cowork capabilities:
 *  - trustMode (downgrades 'confirm' to 'allow', keeps 'block')
 *  - think + connector action validators
 *  - coworkSettings load/save round-trip
 *  - planSignature for new kinds
 *
 * Run: node --experimental-strip-types --test src/__tests__/coworkSettingsAndTrust.test.ts
 */
import { test, describe, beforeEach } from 'node:test'
import assert from 'node:assert/strict'

// Stub localStorage before importing the modules.
class MemStorage {
  private store = new Map<string, string>()
  getItem(k: string) { return this.store.has(k) ? this.store.get(k)! : null }
  setItem(k: string, v: string) { this.store.set(k, v) }
  removeItem(k: string) { this.store.delete(k) }
  clear() { this.store.clear() }
  get length() { return this.store.size }
  key(i: number) { return Array.from(this.store.keys())[i] ?? null }
}

const storage = new MemStorage()
;(globalThis as unknown as { localStorage: MemStorage }).localStorage = storage

const { validateAction } = await import('../services/coworkSafety.ts')
const {
  loadSettings,
  saveSettings,
  mergeWithDefaults,
  DEFAULT_SETTINGS,
} = await import('../services/coworkSettings.ts')
const { validateAction: parserValidate } = await import('../services/coworkPlanParser.ts')
const { planSignature } = await import('../services/coworkPlanParser.ts')
const { ensureFinishAction } = await import('../services/coworkPlanParser.ts')
import type { CoworkPlan } from '../services/coworkTypes.ts'

const WS = '/c/Users/me/aurora'

describe('trust mode — downgrades confirm to allow', () => {
  test('write_file workspace: allow without trustMode', () => {
    const v = validateAction(
      { kind: 'write_file', path: 'foo.txt', content: 'x' },
      'tauri-desktop',
      WS,
    )
    assert.equal(v.decision, 'allow')
  })
  test('write_file outside workspace: confirm without trustMode', () => {
    const v = validateAction(
      { kind: 'write_file', path: '/tmp/foo.txt', content: 'x' },
      'tauri-desktop',
      WS,
    )
    assert.equal(v.decision, 'confirm')
  })
  test('write_file: allow with trustMode', () => {
    const v = validateAction(
      { kind: 'write_file', path: 'foo.txt', content: 'x' },
      'tauri-desktop',
      WS,
      { trustMode: true },
    )
    assert.equal(v.decision, 'allow')
  })
  test('write_file content > 5 MB: still BLOCKED with trustMode', () => {
    const big = 'x'.repeat(6 * 1024 * 1024)
    const v = validateAction(
      { kind: 'write_file', path: 'foo.txt', content: big },
      'tauri-desktop',
      WS,
      { trustMode: true },
    )
    assert.equal(v.decision, 'block', 'hard limit must survive trust mode')
  })
  test('shell sudo: BLOCKED even with trustMode', () => {
    const v = validateAction(
      { kind: 'shell', command: 'sudo', args: ['rm', '-rf', '/'] },
      'tauri-desktop',
      WS,
      { trustMode: true },
    )
    assert.equal(v.decision, 'block')
  })
  test('shell dd: BLOCKED even with trustMode', () => {
    const v = validateAction(
      { kind: 'shell', command: 'dd', args: ['if=/dev/zero'] },
      'tauri-desktop',
      WS,
      { trustMode: true },
    )
    assert.equal(v.decision, 'block')
  })
  test('mobile destructive: BLOCKED even with trustMode', () => {
    const v = validateAction(
      { kind: 'write_file', path: 'a', content: 'b' },
      'web-mobile',
      WS,
      { trustMode: true },
    )
    assert.equal(v.decision, 'block')
  })
  test('non-allowlist shell command: confirm without, allow with trustMode', () => {
    const v1 = validateAction(
      { kind: 'shell', command: 'someweirdtool', args: [] },
      'tauri-desktop',
      WS,
    )
    const v2 = validateAction(
      { kind: 'shell', command: 'someweirdtool', args: [] },
      'tauri-desktop',
      WS,
      { trustMode: true },
    )
    assert.equal(v1.decision, 'confirm')
    assert.equal(v2.decision, 'allow')
  })
})

describe('new action kinds — validateAction (safety)', () => {
  test('think: allow', () => {
    const v = validateAction(
      { kind: 'think', topic: 'plan', thought: 'reflechir au probleme' },
      'tauri-desktop',
      WS,
    )
    assert.equal(v.decision, 'allow')
  })
  test('think: empty thought blocked', () => {
    const v = validateAction(
      { kind: 'think', topic: 'plan', thought: '' },
      'tauri-desktop',
      WS,
    )
    assert.equal(v.decision, 'block')
  })
  test('connector list_repos: allow (read-only)', () => {
    const v = validateAction(
      { kind: 'connector', connector: 'github', action: 'list_repos', params: {} },
      'tauri-desktop',
      WS,
    )
    assert.equal(v.decision, 'allow')
  })
  test('connector create_issue: confirm (destructive write)', () => {
    const v = validateAction(
      { kind: 'connector', connector: 'github', action: 'create_issue', params: { title: 't' } },
      'tauri-desktop',
      WS,
    )
    assert.equal(v.decision, 'confirm')
  })
  test('connector send_message: confirm', () => {
    const v = validateAction(
      { kind: 'connector', connector: 'slack', action: 'send_message', params: {} },
      'tauri-desktop',
      WS,
    )
    assert.equal(v.decision, 'confirm')
  })
  test('connector empty connector: blocked', () => {
    const v = validateAction(
      { kind: 'connector', connector: '', action: 'x', params: {} },
      'tauri-desktop',
      WS,
    )
    assert.equal(v.decision, 'block')
  })
})

describe('parser — new action kinds', () => {
  test('think with topic+thought parses', () => {
    const r = parserValidate({ kind: 'think', topic: 't', thought: 'th' })
    assert.equal(r.ok, true)
  })
  test('think missing thought rejected', () => {
    const r = parserValidate({ kind: 'think', topic: 't' })
    assert.equal(r.ok, false)
  })
  test('connector parses with params object', () => {
    const r = parserValidate({ kind: 'connector', connector: 'github', action: 'list_repos', params: { x: 1 } })
    assert.equal(r.ok, true)
  })
  test('connector parses without params (default {})', () => {
    const r = parserValidate({ kind: 'connector', connector: 'github', action: 'list_repos' })
    assert.equal(r.ok, true)
    if (r.ok && r.action.kind === 'connector') {
      assert.deepEqual(r.action.params, {})
    }
  })
  test('connector missing connector field rejected', () => {
    const r = parserValidate({ kind: 'connector', action: 'list_repos' })
    assert.equal(r.ok, false)
  })
})

describe('planSignature — new kinds', () => {
  test('think variations distinct', () => {
    const a: CoworkPlan = { reasoning: 'r', expectedOutcome: 'o', actions: [{ kind: 'think', topic: 't1', thought: 'a' }] }
    const b: CoworkPlan = { reasoning: 'r', expectedOutcome: 'o', actions: [{ kind: 'think', topic: 't1', thought: 'b' }] }
    assert.notEqual(planSignature(a), planSignature(b))
  })
  test('connector variations distinct', () => {
    const a: CoworkPlan = { reasoning: 'r', expectedOutcome: 'o', actions: [{ kind: 'connector', connector: 'github', action: 'list_repos', params: {} }] }
    const b: CoworkPlan = { reasoning: 'r', expectedOutcome: 'o', actions: [{ kind: 'connector', connector: 'github', action: 'list_issues', params: {} }] }
    assert.notEqual(planSignature(a), planSignature(b))
  })
})

describe('ensureFinishAction handles new kinds', () => {
  test('think alone gets finish appended', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [{ kind: 'think', topic: 't', thought: 'th' }],
    }
    const out = ensureFinishAction(plan)
    assert.equal(out.actions.length, 2)
    assert.equal(out.actions[1].kind, 'finish')
  })
})

describe('coworkSettings persistence', () => {
  beforeEach(() => storage.clear())

  test('load returns defaults when empty', () => {
    const s = loadSettings()
    assert.equal(s.systemPromptText, DEFAULT_SETTINGS.systemPromptText)
    assert.equal(s.trustMode, DEFAULT_SETTINGS.trustMode)
  })

  test('save then load round-trips', () => {
    const custom = { ...DEFAULT_SETTINGS, systemPromptText: 'tu es un mage' }
    saveSettings(custom)
    const reloaded = loadSettings()
    assert.equal(reloaded.systemPromptText, 'tu es un mage')
  })

  test('trustMode persists through save/load', () => {
    saveSettings({ ...DEFAULT_SETTINGS, trustMode: false })
    const reloaded = loadSettings()
    assert.equal(reloaded.trustMode, false)
  })

  test('connectors config persists', () => {
    const custom = {
      ...DEFAULT_SETTINGS,
      connectors: {
        ...DEFAULT_SETTINGS.connectors,
        github: { enabled: true, apiKey: 'ghp_test' },
      },
    }
    saveSettings(custom)
    const reloaded = loadSettings()
    assert.equal(reloaded.connectors.github.enabled, true)
    assert.equal(reloaded.connectors.github.apiKey, 'ghp_test')
  })

  test('mergeWithDefaults fills missing fields', () => {
    const partial = { systemPromptText: 'custom' }
    const full = mergeWithDefaults(partial)
    assert.equal(full.systemPromptText, 'custom')
    assert.equal(full.trustMode, DEFAULT_SETTINGS.trustMode)
    assert.equal(full.connectors.github.enabled, false)
  })

  test('mergeWithDefaults migrates old zero-guardrail defaults to preventive profile', () => {
    const full = mergeWithDefaults({
      trustMode: true,
      dangerMode: true,
      fullyUnlocked: true,
    })
    assert.equal(full.safetyProfileVersion, DEFAULT_SETTINGS.safetyProfileVersion)
    assert.equal(full.trustMode, false)
    assert.equal(full.dangerMode, true)
    assert.equal(full.fullyUnlocked, false)
  })

  test('mergeWithDefaults preserves explicit v2 full unlock', () => {
    const full = mergeWithDefaults({
      safetyProfileVersion: 2,
      trustMode: true,
      dangerMode: true,
      fullyUnlocked: true,
    })
    assert.equal(full.fullyUnlocked, true)
  })

  test('corrupted localStorage falls back to defaults', () => {
    storage.setItem('cowork:settings', 'not-json{{{')
    const s = loadSettings()
    assert.equal(s.systemPromptText, DEFAULT_SETTINGS.systemPromptText)
  })
})
