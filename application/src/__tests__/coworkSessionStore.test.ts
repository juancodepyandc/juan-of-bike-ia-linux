import { describe, test } from 'node:test'
import assert from 'node:assert/strict'

const {
  createSessionStore,
  createSession,
  listSessions,
  attachTempFile,
  exportStore,
  importStore,
} = await import('../services/coworkSessionStore.ts')

describe('coworkSessionStore', () => {
  test('cree des sessions sans dependance externe', () => {
    createSessionStore()

    const first = createSession({ title: 'Mission locale' })
    const second = createSession()

    assert.match(first.id, /^sess_/)
    assert.match(second.id, /^sess_/)
    assert.notEqual(first.id, second.id)
    assert.equal(first.title, 'Mission locale')
    assert.equal(second.title, 'Session 2')
    assert.equal(listSessions().length, 2)
  })

  test('exporte et restaure les fichiers temporaires de session', () => {
    createSessionStore()
    const session = createSession({ title: 'Avec fichiers' })

    attachTempFile(session.id, 'tmp/note.md')
    const snapshot = exportStore()
    createSessionStore()
    importStore(snapshot)

    const restored = listSessions()[0]
    assert.equal(restored.id, session.id)
    assert.deepEqual(restored.tempFiles, ['tmp/note.md'])
  })
})
