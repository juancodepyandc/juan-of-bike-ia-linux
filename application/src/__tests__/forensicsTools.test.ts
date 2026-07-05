/**
 * Tests pour cyber/forensicsTools — extractStrings + detectMagic + hexDump.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { extractStrings, detectMagic, hexDump } from '../services/cyber/forensicsTools.ts'

function bytes(...arr: number[]): Uint8Array {
  return new Uint8Array(arr)
}

function bytesFromAscii(s: string): Uint8Array {
  return new Uint8Array(s.split('').map(c => c.charCodeAt(0)))
}

describe('extractStrings', () => {
  test('chaîne unique simple', () => {
    const b = bytesFromAscii('hello\x00world')
    const out = extractStrings(b, 4)
    assert.equal(out.length, 2)
    assert.equal(out[0].text, 'hello')
    assert.equal(out[1].text, 'world')
  })

  test('respecte minLen', () => {
    const b = bytesFromAscii('hi\x00foobar')
    const out = extractStrings(b, 4)
    // "hi" too short, "foobar" kept
    assert.equal(out.length, 1)
    assert.equal(out[0].text, 'foobar')
  })

  test('offsets corrects', () => {
    const b = bytesFromAscii('xxxhello\x00world')
    const out = extractStrings(b, 4)
    // "xxxhello" capturé en entier (xxx + hello sont contigus printable)
    assert.equal(out[0].text, 'xxxhello')
    assert.equal(out[0].offset, 0)
    assert.equal(out[1].text, 'world')
    assert.equal(out[1].offset, 9)
  })

  test('binaire pur → vide', () => {
    const b = bytes(0x00, 0x01, 0x02, 0xff, 0xfe)
    assert.deepEqual(extractStrings(b, 4), [])
  })

  test('chaîne en fin de buffer', () => {
    const b = bytesFromAscii('\x00\x00aurora')
    const out = extractStrings(b, 4)
    assert.equal(out.length, 1)
    assert.equal(out[0].text, 'aurora')
  })
})

describe('detectMagic', () => {
  test('JPEG header', () => {
    const hits = detectMagic(bytes(0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10))
    assert.ok(hits.some(h => h.type === 'JPEG'))
  })

  test('PNG header (8 bytes)', () => {
    const hits = detectMagic(bytes(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00))
    assert.ok(hits.some(h => h.type === 'PNG'))
  })

  test('GIF 87a', () => {
    const hits = detectMagic(bytesFromAscii('GIF87a'))
    assert.ok(hits.some(h => h.type === 'GIF'))
  })

  test('PDF', () => {
    const hits = detectMagic(bytesFromAscii('%PDF-1.4'))
    assert.ok(hits.some(h => h.type === 'PDF'))
  })

  test('ZIP / DOCX (PK signature)', () => {
    const hits = detectMagic(bytes(0x50, 0x4b, 0x03, 0x04))
    assert.ok(hits.some(h => h.type === 'ZIP/DOCX/JAR'))
  })

  test('PE/EXE Windows (MZ)', () => {
    const hits = detectMagic(bytes(0x4d, 0x5a, 0x90, 0x00))
    assert.ok(hits.some(h => h.type === 'PE/EXE'))
  })

  test('ELF Linux', () => {
    const hits = detectMagic(bytes(0x7f, 0x45, 0x4c, 0x46))
    assert.ok(hits.some(h => h.type === 'ELF'))
  })

  test('GZIP', () => {
    const hits = detectMagic(bytes(0x1f, 0x8b, 0x08))
    assert.ok(hits.some(h => h.type === 'GZIP'))
  })

  test('MP4 ftyp à offset 4', () => {
    // 4 bytes any + "ftyp"
    const hits = detectMagic(bytes(0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70))
    assert.ok(hits.some(h => h.type === 'MP4'))
  })

  test('Fichier inconnu → aucun hit', () => {
    const hits = detectMagic(bytes(0xab, 0xcd, 0xef, 0x12))
    assert.equal(hits.length, 0)
  })

  test('Buffer trop court → pas de hit pour signatures longues', () => {
    // PNG nécessite 8 bytes
    const hits = detectMagic(bytes(0x89, 0x50, 0x4e))
    assert.ok(!hits.some(h => h.type === 'PNG'))
  })
})

describe('hexDump', () => {
  test('format de ligne basique', () => {
    const out = hexDump(bytesFromAscii('hello'), 1, 16)
    // ligne unique : offset + hex + ascii
    const lines = out.split('\n').filter(l => l.length > 0)
    assert.equal(lines.length, 1)
    assert.ok(lines[0].startsWith('00000000'))
    assert.ok(lines[0].includes('hello'))
  })

  test('hex contient bytes corrects', () => {
    const out = hexDump(bytes(0xde, 0xad, 0xbe, 0xef), 1, 16)
    assert.ok(out.includes('de ad be ef'))
  })

  test('ascii printable mais bytes non-printable → "."', () => {
    const out = hexDump(bytes(0x00, 0x01, 0x02), 1, 16)
    // Aucune chaîne ASCII printable → on a 3 points
    const lines = out.split('\n')
    assert.ok(lines[0].endsWith('...'))
  })

  test('respecte maxLines', () => {
    const buf = new Uint8Array(1024)
    const out = hexDump(buf, 2, 16)
    const lines = out.split('\n').filter(l => l.startsWith('0000'))
    assert.ok(lines.length <= 2)
  })

  test('offset formaté en hex 8 chars', () => {
    const out = hexDump(new Uint8Array(32), 2, 16)
    const lines = out.split('\n')
    // Première ligne : offset 0, deuxième ligne : offset 16
    assert.ok(lines[0].startsWith('00000000'))
    assert.ok(lines[1].startsWith('00000010'))
  })
})
