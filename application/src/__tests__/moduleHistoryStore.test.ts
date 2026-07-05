import { beforeEach, describe, test } from 'node:test'
import assert from 'node:assert/strict'

const store = new Map<string, string>()
const fakeLocalStorage = {
  getItem: (k: string) => store.get(k) ?? null,
  setItem: (k: string, v: string) => { store.set(k, v) },
  removeItem: (k: string) => { store.delete(k) },
  clear: () => store.clear(),
  key: (i: number) => Array.from(store.keys())[i] ?? null,
  get length() { return store.size },
}

;(globalThis as Record<string, unknown>).window = { localStorage: fakeLocalStorage }
;(globalThis as Record<string, unknown>).localStorage = fakeLocalStorage

const { useModuleHistoryStore } = await import('../stores/moduleHistoryStore.ts')

beforeEach(() => {
  store.clear()
  useModuleHistoryStore.setState({
    histories: {},
    sessions: [],
    activeSessionId: {},
  })
})

describe('moduleHistoryStore prompt sessions', () => {
  test('openPromptSession cree une conversation isolee depuis un prompt', () => {
    const session = useModuleHistoryStore.getState().openPromptSession('video', 'Scene dialogue Einstein')
    const state = useModuleHistoryStore.getState()

    assert.equal(state.activeSessionId.video, session.id)
    assert.equal(state.sessions.length, 1)
    assert.equal(state.sessions[0].messages.length, 1)
    assert.equal(state.sessions[0].messages[0].role, 'user')
    assert.equal(state.sessions[0].messages[0].content, 'Scene dialogue Einstein')
  })

  test('openPromptSession rouvre par sessionId sans dupliquer', () => {
    const first = useModuleHistoryStore.getState().openPromptSession('image', 'portrait coherent')
    useModuleHistoryStore.getState().createSession('image', 'Autre')

    const reopened = useModuleHistoryStore.getState().openPromptSession('image', 'portrait coherent', first.id)
    const state = useModuleHistoryStore.getState()

    assert.equal(reopened.id, first.id)
    assert.equal(state.activeSessionId.image, first.id)
    assert.equal(state.sessions.filter((s) => s.module === 'image').length, 2)
  })

  test('openPromptSession retrouve une session existante par prompt', () => {
    const first = useModuleHistoryStore.getState().openPromptSession('3d', 'robot articule')
    useModuleHistoryStore.getState().createSession('3d', 'Nouvelle')

    const reopened = useModuleHistoryStore.getState().openPromptSession('3d', 'robot articule')

    assert.equal(reopened.id, first.id)
    assert.equal(useModuleHistoryStore.getState().activeSessionId['3d'], first.id)
  })
})
