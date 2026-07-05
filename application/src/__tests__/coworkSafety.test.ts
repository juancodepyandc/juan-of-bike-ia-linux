/**
 * Unit tests for coworkSafety — the security gate that decides whether each
 * Cowork action is allowed, requires confirmation, or is hard-blocked.
 * Run: node --experimental-strip-types --test src/__tests__/coworkSafety.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  approveExternalPath,
  clearSessionApprovals,
  isInsideWorkspace,
  normalizePath,
  resolvePath,
  validateAction,
} from '../services/coworkSafety.ts'

const WS = '/c/Users/me/aurora'
const RT_DESKTOP = 'tauri-desktop'
const RT_MOBILE = 'web-mobile'
const RT_WEB = 'web-desktop'

describe('normalizePath', () => {
  test('collapses redundant slashes', () => {
    assert.equal(normalizePath('/a//b///c'), '/a/b/c')
  })
  test('resolves dot-dot segments', () => {
    assert.equal(normalizePath('/a/b/../c'), '/a/c')
  })
  test('refuses to escape root', () => {
    assert.equal(normalizePath('/../../etc'), '/etc')
  })
  test('keeps relative paths simple', () => {
    assert.equal(normalizePath('a/b/c'), 'a/b/c')
  })
})

describe('resolvePath', () => {
  test('relative path is anchored to workspace', () => {
    assert.equal(resolvePath('foo/bar.ts', WS), `${WS}/foo/bar.ts`)
  })
  test('absolute Unix path passes through', () => {
    assert.equal(resolvePath('/etc/passwd', WS), '/etc/passwd')
  })
  test('absolute Windows-like path passes through', () => {
    // Note: we normalize backslashes to forward slashes
    const out = resolvePath('C:\\Windows\\System32', WS)
    assert.ok(out.toLowerCase().includes('windows'))
  })
  test('path with .. cannot escape via relative resolution', () => {
    // Relative path "../../etc/passwd" anchored to /c/Users/me/aurora
    // should normalise to /c/Users/etc/passwd, NOT to /etc/passwd. The
    // workspace boundary check then rejects it as "outside".
    const escaped = resolvePath('../../etc/passwd', WS)
    assert.ok(!isInsideWorkspace(escaped, WS), 'must be flagged outside workspace')
  })
})

describe('isInsideWorkspace', () => {
  test('exact root counts as inside', () => {
    assert.ok(isInsideWorkspace(WS, WS))
  })
  test('child file counts as inside', () => {
    assert.ok(isInsideWorkspace(`${WS}/src/App.tsx`, WS))
  })
  test('sibling does not count as inside', () => {
    assert.ok(!isInsideWorkspace('/c/Users/me/other', WS))
  })
  test('case-insensitive match (Windows safety)', () => {
    assert.ok(isInsideWorkspace(WS.toUpperCase() + '/sub', WS))
  })
})

describe('validateAction — workspace paths', () => {
  test('reading a workspace file is allowed', () => {
    const v = validateAction({ kind: 'read_file', path: 'src/App.tsx' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'allow')
  })
  test('lister le Bureau utilisateur est autorise comme lecture standard', () => {
    const v = validateAction(
      { kind: 'list_dir', path: 'C:/Users/Juan/Desktop', depth: 8 },
      RT_DESKTOP,
      'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
    )
    assert.equal(v.decision, 'allow')
    assert.equal(v.destructive, false)
  })
  test('lire dans Documents est autorise comme lecture standard', () => {
    const v = validateAction(
      { kind: 'read_file', path: 'C:/Users/Juan/Documents/cours.pdf' },
      RT_DESKTOP,
      'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
    )
    assert.equal(v.decision, 'allow')
    assert.equal(v.destructive, false)
  })
  test('reading outside workspace requires confirmation', () => {
    clearSessionApprovals()
    const v = validateAction({ kind: 'read_file', path: '/etc/passwd' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'confirm')
  })
  test('approval is remembered for the session', () => {
    clearSessionApprovals()
    approveExternalPath('/etc/passwd')
    const v = validateAction({ kind: 'read_file', path: '/etc/passwd' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'allow')
  })
  test('approval for a folder covers child reads', () => {
    clearSessionApprovals()
    approveExternalPath('/home/me/Desktop')
    const v = validateAction({ kind: 'read_file', path: '/home/me/Desktop/note.txt' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'allow')
  })
})

describe('validateAction — destructive actions', () => {
  test('write_file inside workspace is allowed in preventive mode', () => {
    const v = validateAction(
      { kind: 'write_file', path: 'foo.txt', content: 'hi' },
      RT_DESKTOP,
      WS,
    )
    assert.equal(v.decision, 'allow')
    assert.equal(v.destructive, true)
  })
  test('write_file outside workspace requires confirmation', () => {
    clearSessionApprovals()
    const v = validateAction(
      { kind: 'write_file', path: '/tmp/foo.txt', content: 'hi' },
      RT_DESKTOP,
      WS,
    )
    assert.equal(v.decision, 'confirm')
  })
  test('ecrire sur le Bureau utilisateur demande toujours confirmation', () => {
    const v = validateAction(
      { kind: 'write_file', path: 'C:/Users/Juan/Desktop/note.txt', content: 'ok' },
      RT_DESKTOP,
      'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
    )
    assert.equal(v.decision, 'confirm')
    assert.equal(v.destructive, true)
  })
  test('write_file inside an approved external folder is allowed in preventive mode', () => {
    clearSessionApprovals()
    approveExternalPath('/home/me/Desktop')
    const v = validateAction(
      { kind: 'write_file', path: '/home/me/Desktop/revision.pdf', content: '%PDF-1.4\n' },
      RT_DESKTOP,
      WS,
    )
    assert.equal(v.decision, 'allow')
  })
  test('write_file sensitive workspace path requires confirmation', () => {
    const v = validateAction(
      { kind: 'write_file', path: '.env', content: 'TOKEN=x' },
      RT_DESKTOP,
      WS,
    )
    assert.equal(v.decision, 'confirm')
  })
  test('write_file content too large is blocked', () => {
    const big = 'x'.repeat(6 * 1024 * 1024)
    const v = validateAction(
      { kind: 'write_file', path: 'foo.txt', content: big },
      RT_DESKTOP,
      WS,
    )
    assert.equal(v.decision, 'block')
  })
  test('delete_file workspace root is blocked', () => {
    const v = validateAction({ kind: 'delete_file', path: '.' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'block')
  })
  test('delete_file system root is blocked', () => {
    const v = validateAction({ kind: 'delete_file', path: '/' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'block')
  })
})

describe('validateAction — mobile lockdown', () => {
  test('write_file on mobile is hard-blocked', () => {
    const v = validateAction(
      { kind: 'write_file', path: 'a', content: 'b' },
      RT_MOBILE,
      WS,
    )
    assert.equal(v.decision, 'block')
  })
  test('shell on mobile is hard-blocked', () => {
    const v = validateAction(
      { kind: 'shell', command: 'ls', args: [] },
      RT_MOBILE,
      WS,
    )
    assert.equal(v.decision, 'block')
  })
  test('reading a file on mobile is allowed', () => {
    const v = validateAction({ kind: 'read_file', path: 'src/App.tsx' }, RT_MOBILE, WS)
    assert.equal(v.decision, 'allow')
  })
  test('reply on mobile is allowed', () => {
    const v = validateAction({ kind: 'reply', message: 'hi' }, RT_MOBILE, WS)
    assert.equal(v.decision, 'allow')
  })
})

describe('validateAction — shell allow/deny', () => {
  test('git is allowlisted', () => {
    const v = validateAction({ kind: 'shell', command: 'git', args: ['status'] }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'allow')
  })
  test('npm is allowlisted', () => {
    const v = validateAction({ kind: 'shell', command: 'npm', args: ['test'] }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'allow')
  })
  test('sudo is hard-blocked', () => {
    const v = validateAction({ kind: 'shell', command: 'sudo', args: ['rm', '-rf', '/'] }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'block')
  })
  test('dd is hard-blocked', () => {
    const v = validateAction({ kind: 'shell', command: 'dd', args: ['if=/dev/zero', 'of=/dev/sda'] }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'block')
  })
  test('format is hard-blocked', () => {
    const v = validateAction({ kind: 'shell', command: 'format', args: ['c:'] }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'block')
  })
  test('git with -rf-looking arg requires confirmation', () => {
    const v = validateAction({ kind: 'shell', command: 'git', args: ['clean', '-rf'] }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'confirm')
    assert.equal(v.destructive, true)
  })
  test('non-allowlist command requires confirmation', () => {
    const v = validateAction({ kind: 'shell', command: 'someweirdtool', args: [] }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'confirm')
  })
  test('command resolved with full path uses base name', () => {
    const v = validateAction({ kind: 'shell', command: '/usr/bin/git', args: ['log'] }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'allow')
  })
})

describe('validateAction — fetch', () => {
  test('web_search is allowed without confirmation', () => {
    const v = validateAction({ kind: 'web_search', query: 'bac sti2d sin sujets officiels', limit: 99 }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'allow')
    assert.equal(v.destructive, false)
    assert.equal(v.normalized.kind, 'web_search')
    if (v.normalized.kind === 'web_search') {
      assert.equal(v.normalized.limit, 10)
    }
  })

  test('web_search empty query is blocked', () => {
    const v = validateAction({ kind: 'web_search', query: '' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'block')
  })

  test('https URL is allowed', () => {
    const v = validateAction({ kind: 'fetch', url: 'https://api.example.com/x' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'allow')
  })
  test('plain http to remote requires confirmation', () => {
    const v = validateAction({ kind: 'fetch', url: 'http://api.example.com/x' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'confirm')
  })
  test('http to localhost is allowed', () => {
    const v = validateAction({ kind: 'fetch', url: 'http://localhost:3001/api/health' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'allow')
  })
  test('file:// URL is blocked', () => {
    const v = validateAction({ kind: 'fetch', url: 'file:///etc/passwd' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'block')
  })
  test('javascript:// URL is blocked', () => {
    const v = validateAction({ kind: 'fetch', url: 'javascript:alert(1)' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'block')
  })
  test('garbage URL is blocked', () => {
    const v = validateAction({ kind: 'fetch', url: 'not a url' }, RT_DESKTOP, WS)
    assert.equal(v.decision, 'block')
  })
})

describe('validateAction — open_url + clipboard + simple kinds', () => {
  test('reply is always allowed', () => {
    const v = validateAction({ kind: 'reply', message: 'hello' }, RT_WEB, WS)
    assert.equal(v.decision, 'allow')
  })
  test('finish is always allowed', () => {
    const v = validateAction({ kind: 'finish', summary: 'done' }, RT_WEB, WS)
    assert.equal(v.decision, 'allow')
  })
  test('open_url with https is allowed', () => {
    const v = validateAction({ kind: 'open_url', url: 'https://example.com' }, RT_WEB, WS)
    assert.equal(v.decision, 'allow')
  })
  test('open_url with javascript: is blocked', () => {
    const v = validateAction({ kind: 'open_url', url: 'javascript:1' }, RT_WEB, WS)
    assert.equal(v.decision, 'block')
  })
  test('clipboard ops are allowed on desktop', () => {
    const v1 = validateAction({ kind: 'clipboard_read' }, RT_WEB, WS)
    assert.equal(v1.decision, 'allow')
    const v2 = validateAction({ kind: 'clipboard_write', text: 'x' }, RT_WEB, WS)
    assert.equal(v2.decision, 'allow')
  })
})
