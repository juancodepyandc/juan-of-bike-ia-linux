import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  detectIntentCategory,
  directHumanPrompt,
} from '../services/humanPromptDirector.ts'

describe('Human Prompt Director - Intent Precision & Natural Prose', () => {
  it('detects and directs photorealistic requests with natural human prose', () => {
    const inputs = [
      'fais moi une photo réaliste d un vieil artisan horloger dans son atelier',
      'portrait photo 85mm d une jeune femme au soleil couchant',
      'photographie documentaire d une rue de Kyoto sous la pluie',
    ]

    for (const input of inputs) {
      const category = detectIntentCategory(input)
      assert.equal(category, 'photo_realistic')

      const result = directHumanPrompt(input)
      assert.equal(result.category, 'photo_realistic')
      assert.ok(result.humanPrompt.length > 50)
      // Must NOT contain robotic comma-tag spam
      assert.ok(!result.humanPrompt.includes('8k, masterpiece'))
      assert.ok(!result.humanPrompt.includes('trending on artstation'))
      assert.ok(!result.humanPrompt.includes('ultra realistic, highly detailed'))
      // Must contain natural photographer terms (e.g. lens, daylight/lighting, texture)
      assert.ok(result.humanPrompt.includes('lens') || result.humanPrompt.includes('lighting') || result.humanPrompt.includes('texture'))
      assert.equal(result.suggestedDirectory, 'photos')
    }
  })

  it('detects and directs game assets (pixel art, isometric, UI icons, textures)', () => {
    // 1. Pixel Art Sprite
    const pixelInput = 'un sprite pixel art 16-bit d un chevalier qui brandit une épée'
    assert.equal(detectIntentCategory(pixelInput), 'game_asset_pixel_art')
    const pixelRes = directHumanPrompt(pixelInput)
    assert.equal(pixelRes.category, 'game_asset_pixel_art')
    assert.ok(pixelRes.gameAssetMeta?.isolatedBackground)
    assert.equal(pixelRes.gameAssetMeta?.assetType, 'sprite')
    assert.equal(pixelRes.suggestedDirectory, 'game_assets')
    assert.ok(pixelRes.humanPrompt.includes('integer grid'))
    assert.ok(pixelRes.humanPrompt.includes('palette'))

    // 2. Isometric 3D Game Prop
    const isoInput = 'un batiment medieval vue isometrique 3d pour un jeu de strategie'
    assert.equal(detectIntentCategory(isoInput), 'game_asset_isometric')
    const isoRes = directHumanPrompt(isoInput)
    assert.equal(isoRes.category, 'game_asset_isometric')
    assert.equal(isoRes.gameAssetMeta?.assetType, 'isometric_building')
    assert.ok(isoRes.humanPrompt.includes('orthographic isometric'))

    // 3. Game UI / Inventory Icon
    const iconInput = 'une potion magique lumineuse pour icone d inventaire rpg'
    assert.equal(detectIntentCategory(iconInput), 'game_asset_icon_ui')
    const iconRes = directHumanPrompt(iconInput)
    assert.equal(iconRes.category, 'game_asset_icon_ui')
    assert.equal(iconRes.gameAssetMeta?.assetType, 'ui_icon')
    assert.ok(iconRes.humanPrompt.includes('inventory icon'))

    // 4. Tileable Texture
    const textureInput = 'texture sol carrelage de donjon seamless tileable'
    assert.equal(detectIntentCategory(textureInput), 'game_asset_texture')
    const texRes = directHumanPrompt(textureInput)
    assert.equal(texRes.category, 'game_asset_texture')
    assert.equal(texRes.gameAssetMeta?.assetType, 'tileable_texture')
    assert.ok(texRes.humanPrompt.includes('seamless'))
  })

  it('detects and directs established artistic styles (Pixar, Ghibli, Manga, Cyberpunk)', () => {
    // 1. Pixar 3D Animation
    const pixarInput = 'un petit renard explorateur style pixar 3d'
    assert.equal(detectIntentCategory(pixarInput), 'stylized_pixar_3d')
    const pixarRes = directHumanPrompt(pixarInput)
    assert.equal(pixarRes.category, 'stylized_pixar_3d')
    assert.ok(pixarRes.humanPrompt.includes('Pixar'))
    assert.ok(pixarRes.humanPrompt.includes('subsurface scattering'))

    // 2. Anime Ghibli
    const ghibliInput = 'un chateau flottant dans les nuages style anime ghibli'
    assert.equal(detectIntentCategory(ghibliInput), 'stylized_anime_ghibli')
    const ghibliRes = directHumanPrompt(ghibliInput)
    assert.equal(ghibliRes.category, 'stylized_anime_ghibli')
    assert.ok(ghibliRes.humanPrompt.includes('Ghibli'))

    // 3. Manga Ink N&B
    const mangaInput = 'duel de samourais encre noir et blanc planche manga'
    assert.equal(detectIntentCategory(mangaInput), 'stylized_manga_ink')
    const mangaRes = directHumanPrompt(mangaInput)
    assert.equal(mangaRes.category, 'stylized_manga_ink')
    assert.ok(mangaRes.humanPrompt.includes('manga'))
    assert.ok(mangaRes.humanPrompt.includes('screentone'))

    // 4. Cyberpunk Neon
    const cyberInput = 'marche nocturne cyberpunk sous la pluie avec neons'
    assert.equal(detectIntentCategory(cyberInput), 'stylized_cyberpunk')
    const cyberRes = directHumanPrompt(cyberInput)
    assert.equal(cyberRes.category, 'stylized_cyberpunk')
    assert.ok(cyberRes.humanPrompt.includes('cyberpunk'))
    assert.ok(cyberRes.humanPrompt.includes('neon'))
  })

  it('produces valid dimension constraints and quality checklists across all categories', () => {
    const testCases = [
      'photo de chat sur un canape',
      'sprite pixel art monstre des cavernes',
      'tour de garde isometrique 3d',
      'epee legendaire icone de jeu',
      'texture rocheuse repetable',
      'petit robot style animation pixar',
      'foret magique style ghibli',
    ]

    for (const tc of testCases) {
      const res = directHumanPrompt(tc)
      assert.ok(res.width >= 768 && res.width <= 1536)
      assert.ok(res.height >= 640 && res.height <= 1344)
      assert.ok(res.steps >= 28 && res.steps <= 36)
      assert.ok(res.guidance >= 3.5 && res.guidance <= 6.0)
      assert.ok(res.qualityChecklist.length >= 3)
      assert.ok(res.negativePrompt.length > 20)
    }
  })
})
