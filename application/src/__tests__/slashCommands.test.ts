/**
 * Tests pour utils/slashCommands — librairie de slash commands de chat.
 */
import { test, describe, before, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  SLASH_COMMANDS,
  findCommand,
  applySlashCommand,
  getRecentSlash,
  recordSlashUsage,
  suggestCommands,
} from '../utils/slashCommands.ts'

before(() => {
  if (typeof globalThis.localStorage === 'undefined') {
    const store = new Map<string, string>()
    Object.defineProperty(globalThis, 'localStorage', {
      value: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => store.set(k, String(v)),
        removeItem: (k: string) => store.delete(k),
        clear: () => store.clear(),
        get length() { return store.size },
        key: (i: number) => Array.from(store.keys())[i] ?? null,
      },
      writable: true,
      configurable: true,
    })
  }
  if (typeof (globalThis as any).window === 'undefined') {
    Object.defineProperty(globalThis, 'window', {
      value: globalThis,
      writable: true,
      configurable: true,
    })
  }
})

beforeEach(() => {
  globalThis.localStorage?.removeItem('aurora-slash-recent-v1')
})

describe('SLASH_COMMANDS catalogue', () => {
  test('contient au moins 10 commandes', () => {
    assert.ok(SLASH_COMMANDS.length >= 10)
  })

  test('chaque commande a name + aliases + description + example + transform', () => {
    for (const c of SLASH_COMMANDS) {
      assert.ok(c.name)
      assert.ok(c.aliases.length > 0)
      assert.ok(c.description.length > 5)
      assert.ok(c.example.startsWith('/'))
      assert.ok(typeof c.transform === 'function')
    }
  })

  test('names uniques', () => {
    const names = SLASH_COMMANDS.map((c) => c.name)
    assert.equal(new Set(names).size, names.length)
  })

  test('contient fiche, explain, quiz, plan, code, summary, proof', () => {
    const names = SLASH_COMMANDS.map((c) => c.name)
    for (const n of ['fiche', 'explain', 'quiz', 'plan', 'code', 'summary', 'proof']) {
      assert.ok(names.includes(n), `${n} manquant`)
    }
  })
})

describe('findCommand', () => {
  test('"/fiche dérivées" → fiche command + arg', () => {
    const r = findCommand('/fiche dérivées')
    assert.ok(r)
    assert.equal(r?.cmd.name, 'fiche')
    assert.equal(r?.arg, 'dérivées')
  })

  test('"/revision Algèbre" → fiche command (alias)', () => {
    const r = findCommand('/revision Algèbre')
    assert.equal(r?.cmd.name, 'fiche')
  })

  test('"/explique entropie" → explain command (alias FR)', () => {
    const r = findCommand('/explique entropie')
    assert.equal(r?.cmd.name, 'explain')
  })

  test('case-insensitive sur la commande', () => {
    const r = findCommand('/FICHE quoi que ce soit')
    assert.equal(r?.cmd.name, 'fiche')
  })

  test('sans / → null', () => {
    assert.equal(findCommand('fiche dérivées'), null)
  })

  test('commande inconnue → null', () => {
    assert.equal(findCommand('/inexistant arg'), null)
  })

  test('"/summary" sans arg → arg vide', () => {
    const r = findCommand('/summary')
    assert.equal(r?.cmd.name, 'summary')
    assert.equal(r?.arg, '')
  })

  test('arg multi-ligne préservé', () => {
    const r = findCommand('/debug Stack trace:\nline 1\nline 2')
    assert.equal(r?.cmd.name, 'debug')
    assert.ok(r?.arg.includes('line 1'))
  })
})

describe('applySlashCommand', () => {
  test('"/fiche x" → prompt fiche enrichi', () => {
    const r = applySlashCommand('/fiche Dérivées')
    assert.ok(r.includes('FICHE DE RÉVISION'))
    assert.ok(r.includes('Dérivées'))
  })

  test('input sans / → renvoyé tel quel', () => {
    assert.equal(applySlashCommand('un texte sans slash'), 'un texte sans slash')
  })

  test('/translate en Hello → traduction prompt', () => {
    const r = applySlashCommand('/translate en Bonjour le monde')
    assert.ok(r.includes('en'))
    assert.ok(r.includes('Bonjour'))
  })

  test('/translate sans target lang → fallback', () => {
    const r = applySlashCommand('/translate Bonjour seul')
    // Le pattern attend "<lang> <text>" — sans match, fallback
    assert.ok(r.includes('Traduis'))
  })

  test('/quiz x → prompt 5 QCM', () => {
    const r = applySlashCommand('/quiz Guerre froide')
    assert.ok(r.includes('5 questions'))
    assert.ok(r.includes('Guerre froide'))
  })

  test('/summary sans arg → résume conversation', () => {
    const r = applySlashCommand('/summary')
    assert.ok(r.toLowerCase().includes('conversation'))
  })

  test('/summary avec arg → résume texte', () => {
    const r = applySlashCommand('/summary mon long texte ici')
    assert.ok(r.includes('mon long texte ici'))
    assert.ok(r.includes('Résume'))
  })

  test('arg vide → placeholder "(précise...)"', () => {
    const r = applySlashCommand('/fiche')
    assert.ok(r.includes('précise'))
  })
})

describe('LRU recent slash commands', () => {
  test('recordSlashUsage enregistre', () => {
    recordSlashUsage('fiche')
    const r = getRecentSlash()
    assert.deepEqual(r, ['fiche'])
  })

  test('LRU cap à 3', () => {
    recordSlashUsage('fiche')
    recordSlashUsage('quiz')
    recordSlashUsage('plan')
    recordSlashUsage('code')
    const r = getRecentSlash()
    assert.equal(r.length, 3)
    assert.equal(r[0], 'code')
  })

  test('même commande → bouge en tête, pas de doublon', () => {
    recordSlashUsage('fiche')
    recordSlashUsage('quiz')
    recordSlashUsage('fiche')
    const r = getRecentSlash()
    assert.equal(r[0], 'fiche')
    assert.equal(r.length, 2)
  })

  test('applySlashCommand enregistre la commande', () => {
    applySlashCommand('/quiz histoire')
    const r = getRecentSlash()
    assert.ok(r.includes('quiz'))
  })

  test('name vide → ignoré', () => {
    recordSlashUsage('')
    const r = getRecentSlash()
    assert.equal(r.length, 0)
  })
})

describe('suggestCommands', () => {
  test('"/" seul → toutes commandes', () => {
    const r = suggestCommands('/')
    assert.equal(r.length, SLASH_COMMANDS.length)
  })

  test('"/" seul + recent → recent en tête', () => {
    recordSlashUsage('quiz')
    const r = suggestCommands('/')
    assert.equal(r[0].name, 'quiz')
  })

  test('"/fi" → filtre par alias prefix', () => {
    const r = suggestCommands('/fi')
    assert.ok(r.some((c) => c.name === 'fiche'))
  })

  test('sans / → []', () => {
    assert.deepEqual(suggestCommands('fi'), [])
  })

  test('"/expl" → filtre + match alias', () => {
    const r = suggestCommands('/expl')
    assert.ok(r.some((c) => c.name === 'explain'))
  })

  test('filtre par description aussi', () => {
    const r = suggestCommands('/dissertation')
    // plan a "dissertation" dans description
    assert.ok(r.some((c) => c.name === 'plan'))
  })
})
