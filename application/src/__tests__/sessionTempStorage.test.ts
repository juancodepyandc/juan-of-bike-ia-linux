import { after, before, describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, rm, symlink, utimes, writeFile, readFile, access } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { sessionDir, writeTempFile, readTempFile, listTempFiles, removeSessionDir, cleanupOlderThan } from '../services/sessionTempStorage.ts'

describe('temporary session storage', () => {
  let root: string
  const previousCwd = process.cwd()
  before(async () => {
    root = await mkdtemp(join(tmpdir(), 'aurora-sessions-'))
    process.chdir(root)
  })
  after(async () => {
    process.chdir(previousCwd)
    await rm(root, { recursive: true, force: true })
  })

  it('reads back text and binary data in an isolated session', async () => {
    await writeTempFile('session_1', 'note.txt', 'bonjour é🙂')
    await writeTempFile('session_1', 'data.bin', new Uint8Array([0, 1, 255]))
    assert.equal((await readTempFile('session_1', 'note.txt')).toString(), 'bonjour é🙂')
    assert.deepEqual([...await readTempFile('session_1', 'data.bin')], [0, 1, 255])
    assert.deepEqual((await listTempFiles('session_1')).sort(), ['data.bin', 'note.txt'])
    await removeSessionDir('session_1')
    assert.deepEqual(await listTempFiles('session_1'), [])
  })

  it('rejects paths that escape the session directory', async () => {
    for (const id of ['', '.', '..', '../outside', '/tmp', 'x\\y', 'x\0y']) {
      assert.throws(() => sessionDir(id), /Invalid session id/)
      await assert.rejects(removeSessionDir(id), /Invalid session id/)
    }
    for (const name of ['', '.', '..', '../outside', 'a/b', 'a\\b', 'x\0y']) {
      await assert.rejects(writeTempFile('session_2', name, 'x'), /Invalid session filename/)
    }
  })

  it('does not read or overwrite symbolic link targets', async () => {
    const outside = join(root, 'outside.txt')
    await writeFile(outside, 'keep')
    await writeTempFile('links', 'normal.txt', 'normal')
    await symlink(outside, join(sessionDir('links'), 'linked.txt'))
    await assert.rejects(writeTempFile('links', 'linked.txt', 'changed'), /symbolic links/)
    await assert.rejects(readTempFile('links', 'linked.txt'))
    assert.equal(await readFile(outside, 'utf8'), 'keep')
    await symlink(root, sessionDir('linked_session'))
    await assert.rejects(removeSessionDir('linked_session'), /symbolic links/)
    await access(outside)
  })

  it('expires only old session directories and preserves the audit log', async () => {
    await writeTempFile('expired', 'data.txt', 'old')
    await writeTempFile('recent', 'data.txt', 'new')
    const old = new Date(Date.now() - 10 * 86_400_000)
    await utimes(sessionDir('expired'), old, old)
    const audit = join(root, 'application', 'temp-sessions', 'session_audit.log')
    await writeFile(audit, 'audit')
    await utimes(audit, old, old)
    assert.deepEqual(await cleanupOlderThan(7), ['expired'])
    await access(sessionDir('recent'))
    assert.equal(await readFile(audit, 'utf8'), 'audit')
    for (const days of [0, -1, NaN, Infinity]) await assert.rejects(cleanupOlderThan(days), /Retention/)
  })

  it('resolves the same storage root when launched from application', async () => {
    const expected = sessionDir('same')
    await mkdir(join(root, 'application'), { recursive: true })
    process.chdir(join(root, 'application'))
    try { assert.equal(sessionDir('same'), expected) } finally { process.chdir(root) }
  })
})
