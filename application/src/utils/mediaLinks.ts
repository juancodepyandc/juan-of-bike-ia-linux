/**
 * mediaLinks — reconnaissance de ce qu'il y a AU BOUT d'un lien.
 *
 * Le module conversation reçoit des URL de trois côtés : la recherche web
 * (sources), la réponse du modèle (liens cités) et les fichiers produits par
 * les autres modules (image, 3D, vidéo). Jusqu'ici tout ça s'affichait en
 * bleu souligné : une photo se lisait « https://... .jpg », une vidéo aussi,
 * un GLB aussi. On ne pouvait rien voir sans quitter la conversation.
 *
 * Ce fichier ne fait que classer : il ne dessine rien, ne charge rien. Le
 * rendu vit dans components/chat/MediaEmbed.tsx. Séparer les deux permet de
 * tester la classification sans DOM (voir __tests__/mediaLinks.test.ts).
 */

export type MediaKind =
  | 'image'
  | 'video'        // fichier vidéo lisible par <video> (mp4, webm...)
  | 'videoEmbed'   // plateforme à iframe (YouTube, Vimeo, Dailymotion)
  | 'audio'
  | 'model3d'      // glb / gltf / obj / fbx / stl / ply
  | 'pdf'
  | 'page'         // lien ordinaire

const IMAGE_EXT = /\.(png|jpe?g|webp|gif|bmp|avif|svg)(\?|#|$)/i
const VIDEO_EXT = /\.(mp4|webm|ogv|mov|m4v)(\?|#|$)/i
const AUDIO_EXT = /\.(mp3|wav|ogg|oga|flac|m4a|aac|opus)(\?|#|$)/i
const MODEL_EXT = /\.(glb|gltf|obj|fbx|stl|ply)(\?|#|$)/i
const PDF_EXT = /\.pdf(\?|#|$)/i

/** Extensions que le viewer three.js sait réellement charger sans conversion. */
const MODEL_VIEWABLE_EXT = /\.(glb|gltf)(\?|#|$)/i

export type VideoEmbed = {
  provider: 'youtube' | 'vimeo' | 'dailymotion'
  id: string
  embedUrl: string
  thumbUrl: string | null
}

/**
 * Identifiant de vidéo depuis n'importe quelle forme d'URL YouTube :
 * watch?v=, youtu.be/, /embed/, /shorts/, /live/.
 */
export function parseVideoEmbed(rawUrl: string): VideoEmbed | null {
  let url: URL
  try {
    url = new URL(rawUrl)
  } catch {
    return null
  }
  const host = url.hostname.replace(/^www\./, '').toLowerCase()

  if (host === 'youtu.be') {
    const id = url.pathname.slice(1).split('/')[0]
    return id ? youtube(id) : null
  }
  if (host === 'youtube.com' || host === 'm.youtube.com' || host === 'youtube-nocookie.com') {
    const v = url.searchParams.get('v')
    if (v) return youtube(v)
    const m = url.pathname.match(/^\/(?:embed|shorts|live|v)\/([^/?#]+)/)
    if (m) return youtube(m[1])
    return null
  }
  if (host === 'vimeo.com' || host === 'player.vimeo.com') {
    const m = url.pathname.match(/(\d{6,})/)
    if (!m) return null
    return {
      provider: 'vimeo',
      id: m[1],
      embedUrl: `https://player.vimeo.com/video/${m[1]}`,
      thumbUrl: null,
    }
  }
  if (host === 'dailymotion.com' || host === 'dai.ly') {
    const m = host === 'dai.ly'
      ? url.pathname.slice(1).match(/^([^/?#]+)/)
      : url.pathname.match(/^\/video\/([^/?#_]+)/)
    if (!m) return null
    return {
      provider: 'dailymotion',
      id: m[1],
      embedUrl: `https://www.dailymotion.com/embed/video/${m[1]}`,
      thumbUrl: `https://www.dailymotion.com/thumbnail/video/${m[1]}`,
    }
  }
  return null
}

function youtube(id: string): VideoEmbed {
  const clean = id.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 20)
  return {
    provider: 'youtube',
    id: clean,
    // nocookie : pas de cookie de tracking posé par une bulle de chat.
    embedUrl: `https://www.youtube-nocookie.com/embed/${clean}`,
    thumbUrl: `https://i.ytimg.com/vi/${clean}/hqdefault.jpg`,
  }
}

/** Nature de la ressource pointée par l'URL. */
export function classifyUrl(rawUrl: string): MediaKind {
  const url = (rawUrl || '').trim()
  if (!url) return 'page'
  if (url.startsWith('data:image/')) return 'image'
  if (url.startsWith('data:video/')) return 'video'
  if (url.startsWith('data:audio/')) return 'audio'
  if (parseVideoEmbed(url)) return 'videoEmbed'

  // On teste sur le chemin seul : un ?token=x.png ne fait pas une image,
  // et un /photo.jpg?width=800 en reste une.
  let path = url
  try {
    path = new URL(url, 'https://local.invalid').pathname
  } catch {
    /* URL relative bancale : on garde la chaîne brute */
  }
  if (IMAGE_EXT.test(path)) return 'image'
  if (VIDEO_EXT.test(path)) return 'video'
  if (AUDIO_EXT.test(path)) return 'audio'
  if (MODEL_EXT.test(path)) return 'model3d'
  if (PDF_EXT.test(path)) return 'pdf'
  return 'page'
}

/** Un .obj/.fbx est bien un modèle 3D, mais le viewer intégré ne lit que glTF. */
export function isViewableModel(rawUrl: string): boolean {
  let path = rawUrl
  try {
    path = new URL(rawUrl, 'https://local.invalid').pathname
  } catch {
    /* garde la chaîne brute */
  }
  return MODEL_VIEWABLE_EXT.test(path)
}

/** true si l'URL vaut la peine d'être rendue autrement qu'en lien texte. */
export function isRichMedia(rawUrl: string): boolean {
  return classifyUrl(rawUrl) !== 'page'
}

/** Domaine lisible : « lemonde.fr », pas « https://www.lemonde.fr/... ». */
export function domainOf(rawUrl: string): string {
  try {
    return new URL(rawUrl).hostname.replace(/^www\./, '')
  } catch {
    const m = (rawUrl || '').match(/^[a-z]+:\/\/([^/?#]+)/i)
    return m ? m[1].replace(/^www\./, '') : ''
  }
}

/**
 * Favicon du site. Service DuckDuckGo : pas de cookie, pas de compte, et
 * si le réseau est coupé le composant retombe sur la pastille à initiale.
 */
export function faviconUrl(rawUrl: string): string | null {
  const domain = domainOf(rawUrl)
  if (!domain) return null
  return `https://icons.duckduckgo.com/ip3/${domain}.ico`
}

// Les parentheses sont ACCEPTEES dans la capture — sinon les liens
// Wikipedia du type /wiki/Paris_(homonymie) seraient tronques. Celles qui
// ne sont pas ouvertes dans l'URL sont retirees juste apres.
const URL_RE = /\bhttps?:\/\/[^\s<>[\]{}"'`]+/gi

/**
 * URL présentes dans un texte libre ou du markdown.
 *
 * La ponctuation finale est retirée : « voir https://a.fr/page. » ne doit pas
 * produire une URL qui se termine par un point. Les parenthèses fermantes
 * sont retirées seulement si elles ne sont pas ouvertes dans l'URL, sinon on
 * casserait les liens Wikipédia du type /wiki/Paris_(homonymie).
 */
export function extractUrls(text: string, limit = 40): string[] {
  if (!text) return []
  const found: string[] = []
  for (const match of text.matchAll(URL_RE)) {
    let url = match[0]
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const last = url[url.length - 1]
      if (last === ')' && (url.match(/\(/g)?.length ?? 0) < (url.match(/\)/g)?.length ?? 0)) {
        url = url.slice(0, -1)
        continue
      }
      if ('.,;:!?»"\''.includes(last)) {
        url = url.slice(0, -1)
        continue
      }
      break
    }
    if (url.length > 8 && !found.includes(url)) found.push(url)
    if (found.length >= limit) break
  }
  return found
}

/** Les URL d'un texte qui méritent un lecteur intégré, dédoublonnées. */
export function extractRichMedia(text: string, limit = 12): string[] {
  return extractUrls(text).filter(isRichMedia).slice(0, limit)
}

/** Nom de fichier lisible pour une carte média. */
export function fileNameOf(rawUrl: string): string {
  try {
    const path = new URL(rawUrl, 'https://local.invalid').pathname
    const name = decodeURIComponent(path.split('/').filter(Boolean).pop() || '')
    return name || domainOf(rawUrl) || rawUrl
  } catch {
    return rawUrl
  }
}
