import { test } from 'node:test'
import assert from 'node:assert/strict'
import { approveExternalPath, clearSessionApprovals, isInsideWorkspace, SAFETY_LIMITS, validateAction } from '../services/coworkSafety.ts'
import { planSignature } from '../services/coworkPlanParser.ts'
import type { CoworkAction } from '../services/coworkTypes.ts'

const ROOT = '/home/juan/AuroraIA'
const check = (action: CoworkAction) => validateAction(action, 'tauri-desktop', ROOT)

test('Linux containment preserves case and directory boundaries', () => {
  assert.equal(isInsideWorkspace(`${ROOT}/file`, ROOT), true)
  assert.equal(isInsideWorkspace('/home/juan/auroraia/file', ROOT), false)
  assert.equal(isInsideWorkspace(`${ROOT}-other/file`, ROOT), false)
  assert.equal(isInsideWorkspace('/etc/passwd', '/'), true)
  assert.equal(isInsideWorkspace('relative/file', '/'), false)
})

test('Windows drive paths still compare without case sensitivity', () => {
  assert.equal(isInsideWorkspace('C:/Users/Juan/Work/file', 'c:/users/juan/work'), true)
  assert.equal(isInsideWorkspace('/C/Users/Juan/Work/file', '/c/Users/juan/work'), true)
})

test('Unix approvals do not authorize a differently cased sibling', () => {
  clearSessionApprovals()
  try {
    approveExternalPath('/tmp/Approved')
    assert.equal(check({ kind: 'write_file', path: '/tmp/Approved/file', content: 'hello' }).decision, 'allow')
    assert.equal(check({ kind: 'write_file', path: '/tmp/approved/file', content: 'hello' }).decision, 'confirm')
  } finally {
    clearSessionApprovals()
  }
})

test('standard Unix read directories also preserve case', () => {
  assert.equal(check({ kind: 'read_file', path: '/home/juan/Documents/note' }).decision, 'allow')
  assert.equal(check({ kind: 'read_file', path: '/home/juan/documents/note' }).decision, 'confirm')
})

test('UTF-8 write and edit limits count bytes', () => {
  const oversized = 'é'.repeat(SAFETY_LIMITS.maxWriteFileBytes / 2 + 1)
  assert.equal(check({ kind: 'write_file', path: 'file', content: oversized }).decision, 'block')
  assert.equal(check({ kind: 'edit_file', path: 'file', oldText: 'old', newText: oversized }).decision, 'block')
  const exact = 'é'.repeat(SAFETY_LIMITS.maxWriteFileBytes / 2)
  assert.equal(check({ kind: 'write_file', path: 'file', content: exact }).decision, 'allow')
})

test('deleting a workspace with trailing separator remains blocked', () => {
  assert.equal(validateAction({ kind: 'delete_file', path: '.' }, 'tauri-desktop', ROOT + '/').decision, 'block')
})

test('new action kinds have explicit safety verdicts and distinct loop signatures', () => {
  const actions: CoworkAction[] = [
    { kind: 'ephemeral_tool', toolName: 'example', scriptCode: 'print(1)' },
    { kind: 'ephemeral_tool', toolName: 'example', scriptCode: 'print(2)' },
    { kind: 'file_bundle', moduleTarget: 'academic', files: [{ filename: 'notes.md', content: 'first' }] },
    { kind: 'file_bundle', moduleTarget: 'academic', files: [{ filename: 'notes.md', content: 'second' }] },
  ]
  for (const action of actions) {
    assert.equal(check(action).decision, 'block')
    assert.equal(check(action).destructive, true)
  }
  const signatures = actions.map((action) => planSignature({ reasoning: '', expectedOutcome: '', actions: [action] }))
  assert.equal(new Set(signatures).size, actions.length)
})
