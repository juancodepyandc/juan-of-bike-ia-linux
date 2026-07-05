import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

const { validateAction } = await import('../services/coworkSafety.ts')

const WS = '/c/Users/me/aurora'

describe('danger mode - overrides catastrophic blocklist on shell', () => {
  test('sudo: block (default)', () => {
    const v = validateAction({ kind: 'shell', command: 'sudo', args: ['ls'] }, 'tauri-desktop', WS)
    assert.equal(v.decision, 'block')
  })
  test('sudo + dangerMode only: confirm (still asks)', () => {
    const v = validateAction({ kind: 'shell', command: 'sudo', args: ['ls'] }, 'tauri-desktop', WS, { dangerMode: true })
    assert.equal(v.decision, 'confirm')
  })
  test('sudo + danger + trust: allow (zero garde fou)', () => {
    const v = validateAction({ kind: 'shell', command: 'sudo', args: ['ls'] }, 'tauri-desktop', WS, { dangerMode: true, trustMode: true })
    assert.equal(v.decision, 'allow')
  })
  test('dd + danger + trust: allow', () => {
    const v = validateAction({ kind: 'shell', command: 'dd', args: ['if=/dev/zero', 'of=/tmp/x', 'bs=1M', 'count=10'] }, 'tauri-desktop', WS, { dangerMode: true, trustMode: true })
    assert.equal(v.decision, 'allow')
  })
  test('format + danger + trust: allow', () => {
    const v = validateAction({ kind: 'shell', command: 'format', args: ['e:'] }, 'tauri-desktop', WS, { dangerMode: true, trustMode: true })
    assert.equal(v.decision, 'allow')
  })
})

describe('ZERO GARDE FOU mode (danger+trust) lifts ALL blocks', () => {
  test('mobile destructive write: ALLOW with danger+trust', () => {
    const v = validateAction({ kind: 'write_file', path: 'a', content: 'b' }, 'web-mobile', WS, { dangerMode: true, trustMode: true })
    assert.equal(v.decision, 'allow')
  })
  test('write_file > 5MB: ALLOW with danger+trust', () => {
    const big = 'x'.repeat(6 * 1024 * 1024)
    const v = validateAction({ kind: 'write_file', path: 'a', content: big }, 'tauri-desktop', WS, { dangerMode: true, trustMode: true })
    assert.equal(v.decision, 'allow')
  })
  test('delete root /: ALLOW with danger+trust', () => {
    const v = validateAction({ kind: 'delete_file', path: '/' }, 'tauri-desktop', WS, { dangerMode: true, trustMode: true })
    assert.equal(v.decision, 'allow')
  })
  test('reason mentions ZERO GARDE FOU', () => {
    const v = validateAction({ kind: 'write_file', path: '/tmp/a', content: 'b' }, 'tauri-desktop', WS, { dangerMode: true, trustMode: true })
    assert.match(v.reason, /ZERO GARDE FOU|danger\+trust/i)
  })
})

describe('danger WITHOUT trust : mode preventif', () => {
  test('mobile destructive: confirm instead of block', () => {
    const v = validateAction({ kind: 'write_file', path: 'a', content: 'b' }, 'web-mobile', WS, { dangerMode: true })
    assert.equal(v.decision, 'confirm')
  })
  test('write_file > 5MB: confirm instead of block', () => {
    const big = 'x'.repeat(6 * 1024 * 1024)
    const v = validateAction({ kind: 'write_file', path: 'a', content: big }, 'tauri-desktop', WS, { dangerMode: true })
    assert.equal(v.decision, 'confirm')
  })
  test('delete root: confirm instead of block', () => {
    const v = validateAction({ kind: 'delete_file', path: '/' }, 'tauri-desktop', WS, { dangerMode: true })
    assert.equal(v.decision, 'confirm')
  })
})

const { detectIdFromUA, getInstallInstructionsFor } = await import('../services/coworkBrowserDetectPure.ts')

describe('detectIdFromUA - pure UA detection', () => {
  test('Edge UA', () => {
    assert.equal(detectIdFromUA('Mozilla/5.0 (Windows NT 10.0) Chrome/120 Edg/120'), 'edge')
  })
  test('Chrome UA', () => {
    assert.equal(detectIdFromUA('Mozilla/5.0 (Macintosh) Chrome/120 Safari/537.36'), 'chrome')
  })
  test('Firefox UA', () => {
    assert.equal(detectIdFromUA('Mozilla/5.0 (X11; Ubuntu) Firefox/120.0'), 'firefox')
  })
  test('Safari UA', () => {
    assert.equal(detectIdFromUA('Mozilla/5.0 (iPhone) Safari/604.1'), 'safari')
  })
  test('Opera UA', () => {
    assert.equal(detectIdFromUA('Mozilla/5.0 ... OPR/100.0.0.0'), 'opera')
  })
  test('Vivaldi UA', () => {
    assert.equal(detectIdFromUA('Mozilla/5.0 ... Vivaldi/6.5'), 'vivaldi')
  })
  test('Brave (feature flag)', () => {
    assert.equal(detectIdFromUA('Mozilla/5.0 (Macintosh) Chrome/120 Safari/537.36', true), 'brave')
  })
  test('Empty UA -> unknown', () => {
    assert.equal(detectIdFromUA(''), 'unknown')
  })
})

describe('install instructions per browser', () => {
  test('chrome instructions', () => {
    const inst = getInstallInstructionsFor('chrome', 'http://x/dl')
    assert.equal(inst.title, 'Chrome / Chromium')
    assert.ok(inst.steps.length >= 4)
    assert.equal(inst.loadUnpackedUrl, 'http://x/dl')
  })
  test('firefox mentions about:debugging', () => {
    const inst = getInstallInstructionsFor('firefox')
    const allText = inst.steps.map((s) => `${s.label} ${s.detail ?? ''}`).join(' ').toLowerCase()
    assert.match(allText, /about:debugging/)
  })
  test('safari mentions Xcode', () => {
    const inst = getInstallInstructionsFor('safari')
    const allText = inst.steps.map((s) => `${s.label} ${s.detail ?? ''}`).join(' ')
    assert.match(allText, /Xcode/i)
  })
  test('edge mentions edge://extensions', () => {
    const inst = getInstallInstructionsFor('edge')
    const allText = inst.steps.map((s) => `${s.label} ${s.detail ?? ''}`).join(' ')
    assert.match(allText, /edge:\/\/extensions/)
  })
  test('brave mentions chromium', () => {
    const inst = getInstallInstructionsFor('brave')
    const allText = inst.steps.map((s) => `${s.label} ${s.detail ?? ''}`).join(' ').toLowerCase()
    assert.match(allText, /chrome|chromium|brave:\/\/extensions/)
  })
})
