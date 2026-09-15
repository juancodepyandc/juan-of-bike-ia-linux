/**
 * Tests de la reconnaissance de liens du module conversation.
 *
 * Le point qui compte : une URL doit etre classee sur son CHEMIN, pas sur la
 * chaine entiere. Les images de Wikimedia Commons arrivent avec un
 * `?utm_source=...` colle apres le `.jpg` — la version naive
 * `/\.jpg$/.test(url)` les manquait toutes, et une photo parfaitement valide
 * finissait affichee en lien bleu.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  classifyUrl,
  domainOf,
  extractRichMedia,
  extractUrls,
  fileNameOf,
  isRichMedia,
  isViewableModel,
  parseVideoEmbed,
} from '../utils/mediaLinks.ts'

describe('classifyUrl', () => {
  test('image avec parametres de requete apres l extension', () => {
    assert.equal(
      classifyUrl('https://upload.wikimedia.org/wikipedia/commons/b/b7/Tour.jpg?utm_source=commons'),
      'image',
    )
  })

  test('extensions courantes', () => {
    assert.equal(classifyUrl('https://a.fr/x.png'), 'image')
    assert.equal(classifyUrl('https://a.fr/x.mp4'), 'video')
    assert.equal(classifyUrl('https://a.fr/x.mp3'), 'audio')
    assert.equal(classifyUrl('https://a.fr/scene.glb'), 'model3d')
    assert.equal(classifyUrl('https://a.fr/doc.pdf'), 'pdf')
    assert.equal(classifyUrl('https://lemonde.fr/article/123'), 'page')
  })

  test('un parametre qui ressemble a un fichier ne fait pas un media', () => {
    // Le nom de fichier est dans la query, pas dans le chemin : la page
    // reste une page.
    assert.equal(classifyUrl('https://a.fr/viewer?file=photo.png'), 'page')
  })

  test('data URL', () => {
    assert.equal(classifyUrl('data:image/png;base64,AAAA'), 'image')
  })
})

describe('parseVideoEmbed', () => {
  test('toutes les formes YouTube donnent le meme identifiant', () => {
    const forms = [
      'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
      'https://youtu.be/dQw4w9WgXcQ',
      'https://www.youtube.com/embed/dQw4w9WgXcQ',
      'https://www.youtube.com/shorts/dQw4w9WgXcQ',
      'https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=42s',
    ]
    for (const url of forms) {
      const embed = parseVideoEmbed(url)
      assert.ok(embed, `pas reconnu : ${url}`)
      assert.equal(embed.id, 'dQw4w9WgXcQ')
      assert.equal(embed.provider, 'youtube')
    }
  })

  test('l embed YouTube passe par nocookie', () => {
    assert.match(parseVideoEmbed('https://youtu.be/abc12345678')!.embedUrl, /youtube-nocookie\.com/)
  })

  test('vimeo et dailymotion', () => {
    assert.equal(parseVideoEmbed('https://vimeo.com/123456789')?.provider, 'vimeo')
    assert.equal(parseVideoEmbed('https://www.dailymotion.com/video/x8qpbz1')?.provider, 'dailymotion')
  })

  test('une page ordinaire n est pas une video', () => {
    assert.equal(parseVideoEmbed('https://lemonde.fr/article'), null)
    assert.equal(parseVideoEmbed('pas une url'), null)
  })

  test('une video de plateforme est un media riche', () => {
    assert.equal(classifyUrl('https://youtu.be/dQw4w9WgXcQ'), 'videoEmbed')
    assert.ok(isRichMedia('https://youtu.be/dQw4w9WgXcQ'))
    assert.ok(!isRichMedia('https://lemonde.fr/article'))
  })
})

describe('isViewableModel', () => {
  test('le viewer integre ne lit que glTF', () => {
    assert.ok(isViewableModel('https://a.fr/x.glb'))
    assert.ok(isViewableModel('https://a.fr/x.gltf'))
    // .obj et .fbx sont bien des modeles 3D, mais le viewer ne les charge
    // pas : il faut le dire au lieu d afficher un cadre vide.
    assert.ok(!isViewableModel('https://a.fr/x.obj'))
    assert.ok(!isViewableModel('https://a.fr/x.fbx'))
    assert.equal(classifyUrl('https://a.fr/x.obj'), 'model3d')
  })
})

describe('extractUrls', () => {
  test('la ponctuation finale ne fait pas partie de l URL', () => {
    assert.deepEqual(
      extractUrls('Voir https://a.fr/page. Et aussi https://b.fr/x,'),
      ['https://a.fr/page', 'https://b.fr/x'],
    )
  })

  test('une parenthese ouverte dans l URL est conservee', () => {
    assert.deepEqual(
      extractUrls('https://fr.wikipedia.org/wiki/Paris_(homonymie)'),
      ['https://fr.wikipedia.org/wiki/Paris_(homonymie)'],
    )
  })

  test('une URL entre parentheses ne garde pas la fermante', () => {
    assert.deepEqual(
      extractUrls('la source (https://a.fr/x) le dit'),
      ['https://a.fr/x'],
    )
  })

  test('les doublons sont ecartes', () => {
    assert.deepEqual(extractUrls('https://a.fr/x https://a.fr/x'), ['https://a.fr/x'])
  })

  test('extractRichMedia ne garde que ce qui se regarde', () => {
    const text = 'photo https://a.fr/p.jpg article https://b.fr/texte video https://youtu.be/dQw4w9WgXcQ'
    assert.deepEqual(extractRichMedia(text), ['https://a.fr/p.jpg', 'https://youtu.be/dQw4w9WgXcQ'])
  })
})

describe('domainOf / fileNameOf', () => {
  test('le www saute', () => {
    assert.equal(domainOf('https://www.lemonde.fr/article'), 'lemonde.fr')
    assert.equal(domainOf('pas une url'), '')
  })

  test('nom de fichier decode', () => {
    assert.equal(fileNameOf('https://a.fr/dossier/Tour%20Eiffel.jpg'), 'Tour Eiffel.jpg')
    // Sans nom de fichier, on retombe sur le domaine plutot que sur du vide.
    assert.equal(fileNameOf('https://a.fr/'), 'a.fr')
  })
})
