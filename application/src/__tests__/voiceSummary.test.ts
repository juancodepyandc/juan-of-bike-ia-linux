/**
 * Tests pour cleanFilenameForTTS — utilitaire qui nettoie un nom de fichier
 * pour le rendre confortable à lire en synthèse vocale.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { cleanFilenameForTTS } from '../utils/voiceSummary.ts'

describe('cleanFilenameForTTS', () => {
  test('retire l extension simple', () => {
    assert.equal(cleanFilenameForTTS('rendu_velo.png'), 'rendu velo')
    assert.equal(cleanFilenameForTTS('mesh.glb'), 'mesh')
    assert.equal(cleanFilenameForTTS('clip.mp4'), 'clip')
  })

  test('remplace un hash hex 8+ par …', () => {
    assert.equal(cleanFilenameForTTS('aurora_a8e3f1c2b9d4.png'), 'aurora …')
    assert.equal(cleanFilenameForTTS('mesh-e3b0c44298fc1c14.glb'), 'mesh …')
  })

  test('normalise les séparateurs', () => {
    assert.equal(cleanFilenameForTTS('aurora__velo--rouge.png'), 'aurora velo rouge')
    assert.equal(cleanFilenameForTTS('mon_fichier_super_cool.png'), 'mon fichier super cool')
  })

  test('tronque au-delà de maxChars', () => {
    const long = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png'
    const out = cleanFilenameForTTS(long, 20)
    assert.ok(out.length <= 21, `expected ≤ 21, got ${out.length}: ${out}`)
    assert.ok(out.endsWith('…'))
  })

  test('input vide / undefined → string vide', () => {
    assert.equal(cleanFilenameForTTS(''), '')
    assert.equal(cleanFilenameForTTS(undefined), '')
    assert.equal(cleanFilenameForTTS(null), '')
  })

  test('ne touche pas un nom déjà propre', () => {
    assert.equal(cleanFilenameForTTS('Mon Image'), 'Mon Image')
  })

  test('garde le contexte sémantique d un nom avec hash en plein milieu', () => {
    // "model_iris_4f8a3c2b_v2.glb" → "model iris … v2"
    const out = cleanFilenameForTTS('model_iris_4f8a3c2b_v2.glb')
    assert.equal(out, 'model iris … v2')
  })
})
