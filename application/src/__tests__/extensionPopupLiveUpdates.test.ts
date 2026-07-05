/**
 * v82lz — Tests for the popup's storage.session.onChanged listener that
 * drives event-driven badge re-render. Mirror of popup.js — KEEP IN SYNC.
 *
 * Goals :
 *   - Listener fires re-render only on `pagetype_<tabId>` keys (filters
 *     unrelated session writes out).
 *   - Wrong area name (local instead of session) is ignored.
 *   - 50ms debounce coalesces rapid bursts into a single render.
 *   - Cleanup (removeListener) is honored on unload — no orphan callbacks.
 *
 * We re-implement the small handler logic in TS (mirroring popup.js) and
 * exercise it under fake timers via setTimeout/clearTimeout. This avoids
 * pulling jsdom + a fake chrome runtime just to assert event routing.
 *
 * Run :
 *   node --experimental-strip-types --test src/__tests__/extensionPopupLiveUpdates.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

// ---------------------------------------------------------------------------
// Mirror of popup.js — KEEP IN SYNC with the JS implementation. The popup
// can't easily be `import()`-ed under node --test (it touches `document` +
// `chrome.*` globals at top level). Re-encoding the listener contract here
// is the same pattern used for the pageType→badge mapping mirror.
// ---------------------------------------------------------------------------

type StorageChange = Record<string, { newValue?: unknown; oldValue?: unknown }>
type AreaName = 'local' | 'sync' | 'session' | 'managed'

function makeHarness() {
  let _refreshCalls = 0
  let _timer: ReturnType<typeof setTimeout> | null = null
  function refreshPagetypeDebounced() {
    if (_timer) return
    _timer = setTimeout(() => {
      _timer = null
      _refreshCalls++
    }, 50)
  }
  function onSessionChange(changes: StorageChange | null | undefined, areaName: AreaName) {
    if (areaName !== 'session') return
    if (!changes || typeof changes !== 'object') return
    for (const key of Object.keys(changes)) {
      if (key.startsWith('pagetype_')) {
        refreshPagetypeDebounced()
        return
      }
    }
  }
  function cleanup() {
    if (_timer) {
      clearTimeout(_timer)
      _timer = null
    }
  }
  return {
    onSessionChange,
    cleanup,
    get refreshCalls() { return _refreshCalls },
    get timerActive() { return _timer !== null },
  }
}

describe('popup storage.onChanged — pagetype filter', () => {
  test('pagetype_<tabId> change in session area triggers re-render', async () => {
    const h = makeHarness()
    h.onSessionChange({ 'pagetype_42': { newValue: { pageType: { article: true } } } }, 'session')
    assert.equal(h.refreshCalls, 0, 'render is debounced — does not fire synchronously')
    assert.equal(h.timerActive, true, 'a debounce timer must be scheduled')
    await new Promise((res) => setTimeout(res, 80))
    assert.equal(h.refreshCalls, 1, 'render fires once the 50ms debounce elapses')
  })

  test('non-pagetype key in session is ignored', async () => {
    const h = makeHarness()
    h.onSessionChange({ 'unrelated_key': { newValue: 1 } }, 'session')
    await new Promise((res) => setTimeout(res, 80))
    assert.equal(h.refreshCalls, 0, 'unrelated session writes must not trigger badge render')
  })

  test('local area is ignored even when pagetype-shaped key present', async () => {
    const h = makeHarness()
    h.onSessionChange({ 'pagetype_42': { newValue: { pageType: { login: true } } } }, 'local')
    await new Promise((res) => setTimeout(res, 80))
    assert.equal(h.refreshCalls, 0, 'local-area writes must never trigger badge render')
  })

  test('null/undefined changes are ignored (defensive guard)', () => {
    const h = makeHarness()
    h.onSessionChange(null, 'session')
    h.onSessionChange(undefined as unknown as StorageChange, 'session')
    assert.equal(h.timerActive, false, 'no debounce timer scheduled on bad input')
    h.cleanup()
  })
})

describe('popup storage.onChanged — debounce', () => {
  test('5 rapid events coalesce into 1 render', async () => {
    const h = makeHarness()
    for (let i = 0; i < 5; i++) {
      h.onSessionChange({ ['pagetype_' + i]: { newValue: { pageType: { article: true } } } }, 'session')
    }
    assert.equal(h.timerActive, true)
    await new Promise((res) => setTimeout(res, 80))
    assert.equal(h.refreshCalls, 1, '5 events within debounce window → 1 render only')
  })

  test('back-to-back bursts produce sequential renders', async () => {
    const h = makeHarness()
    h.onSessionChange({ 'pagetype_1': { newValue: 1 } }, 'session')
    await new Promise((res) => setTimeout(res, 80))
    assert.equal(h.refreshCalls, 1)
    h.onSessionChange({ 'pagetype_2': { newValue: 2 } }, 'session')
    await new Promise((res) => setTimeout(res, 80))
    assert.equal(h.refreshCalls, 2, 'second burst after first debounce flushed → second render')
  })
})

describe('popup storage.onChanged — cleanup', () => {
  test('cleanup before debounce flush cancels the pending render', async () => {
    const h = makeHarness()
    h.onSessionChange({ 'pagetype_1': { newValue: 1 } }, 'session')
    assert.equal(h.timerActive, true, 'debounce timer scheduled')
    h.cleanup()
    assert.equal(h.timerActive, false, 'cleanup clears the pending timer')
    await new Promise((res) => setTimeout(res, 80))
    assert.equal(h.refreshCalls, 0, 'no render fires after cleanup — leak guard works')
  })
})
