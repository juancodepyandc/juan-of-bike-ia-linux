import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  resolveImageBlob,
  convertBlobFormat,
  downloadImageUniversal,
} from '../utils/imageDownload.ts'

describe('imageDownload - resolveImageBlob & format conversion', () => {
  test('resolves direct Blob instance immediately', async () => {
    const rawBlob = new Blob(['test-image-data'], { type: 'image/png' })
    const resolved = await resolveImageBlob(rawBlob)

    assert.equal(resolved, rawBlob)
    assert.equal(resolved?.type, 'image/png')
  })

  test('converts blob format to same type without distortion', async () => {
    const rawBlob = new Blob(['test-binary'], { type: 'image/png' })
    const converted = await convertBlobFormat(rawBlob, 'png')

    assert.equal(converted, rawBlob)
  })

  test('downloadImageUniversal handles direct Blob source gracefully', async () => {
    const blob = new Blob(['mock-pixels'], { type: 'image/png' })
    const result = await downloadImageUniversal(blob, {
      filename: 'custom-name.png',
      preferShareOnMobile: false,
    })

    assert.equal(result.ok, true)
    assert.equal(result.filename, 'custom-name.png')
    assert.ok(result.method === 'object-url' || result.method === 'data-url' || result.method === 'blob-ready')
  })

  test('downloadImageUniversal handles direct URL fallback', async () => {
    const result = await downloadImageUniversal('https://example.com/generated-photo.png', {
      preferShareOnMobile: false,
    })

    assert.equal(result.ok, true)
    assert.ok(result.filename.startsWith('creation_') || result.filename.startsWith('aurora-image-'))
  })
})
