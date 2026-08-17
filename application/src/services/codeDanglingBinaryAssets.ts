// ---------------------------------------------------------------------------
// codeDanglingBinaryAssets — une reference qui pointe un binaire absent.
//
// Run 1161, mesure sur le livrable reel: `index.html` contenait la ligne de
// gabarit que tout modele recopie d un projet Vite,
//
//     <link rel="icon" href="/favicon.ico" />
//
// et la critique statique a repondu, en severite `error` sur l axe `runtime`:
// « ressource locale referencee mais absente (/favicon.ico) — Livrer le fichier
// reference ». Cette seule ligne a fait sortir le run en `phase: error` alors
// que la sandbox venait de valider la livraison a 100 %, que l acceptation
// comportementale etait 2/2 et que l accessibilite comme la performance
// notaient 100/100.
//
// « Livrer le fichier » est INACHEVABLE ici. Depuis le run 1081 les binaires
// sont volontairement hors de la file de generation: aucune consigne, aucune
// relance, aucun repli ne fera ecrire un `.ico` valide a un modele de texte —
// la preuve avait coute 42 297 octets de base64 mort et un JPEG tronque a 388
// octets. Une porte reclamait donc exactement ce que la file a cesse de
// produire, et condamnait le run pour cette absence: le piege du conseil
// irrealisable, deja paye au run 1031 (secret sans backend), au run 1081 (le
// JPEG) et au run 1111 (le fichier de codegen).
//
// Deux reponses, dans cet ordre:
//
//  1. REPARER, parce que c est deterministe. Une icone de page se fabrique en
//     SVG — du texte — et s inline en data URL. Rien a demander a un modele
//     probabiliste pour un remplacement mecanique.
//  2. NE PAS CONDAMNER ce qui reste. Un binaire lie et absent est un defaut
//     d apparence, pas une panne d execution: il pese sur le score, il porte un
//     conseil REALISABLE (SVG inline, data URL, ou retirer la reference), et il
//     ne fait jamais echouer une livraison qui tourne.
// ---------------------------------------------------------------------------

import { isBinaryAssetPath } from './codeBinaryAssetPaths.ts'

export type DanglingAssetFile = { name: string; language: string; content: string }

/** Une balise `<link>` complete, attributs compris. */
const LINK_TAG_RE = /<link\b[^>]*?\/?>/gi

function attributeOf(tag: string, name: string): string | null {
  const match = new RegExp(`\\b${name}\\s*=\\s*["']([^"']*)["']`, 'i').exec(tag)
  return match ? match[1] : null
}

/** `rel` qui designe une icone de page (favicon et variantes). */
function isIconRel(rel: string | null): boolean {
  if (!rel) return false
  return /(?:^|\s)(?:shortcut\s+)?icon(?:\s|$)|apple-touch-icon|mask-icon|fluid-icon/i.test(rel)
}

/** Une icone SVG ne remplace une `.ico` que pour le `rel` qui sait la lire. */
function relAcceptsSvg(rel: string): boolean {
  return !/apple-touch-icon|mask-icon|fluid-icon/i.test(rel)
}

function normalizePath(path: string): string {
  return path.replace(/\\/g, '/').replace(/^\.?\//, '').trim().toLowerCase()
}

/** Une URL externe, un data:, un ancrage — rien de local a livrer. */
function isLocalReference(url: string): boolean {
  if (!url) return false
  return !/^(?:https?:)?\/\//i.test(url) && !/^(?:data:|mailto:|tel:|#|blob:)/i.test(url)
}

/**
 * Initiale de marque, tiree du `<title>` livre. Les accents sont replies sur
 * leur lettre de base pour que « Éthiopie » donne « E » et non un glyphe que
 * le SVG devrait echapper.
 */
export function faviconInitialFromHtml(html: string): string | null {
  const title = /<title[^>]*>([\s\S]*?)<\/title>/i.exec(html)?.[1] ?? ''
  const plain = title.normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim()
  const letter = /[A-Za-z0-9]/.exec(plain)?.[0]
  return letter ? letter.toUpperCase() : null
}

/**
 * Icone de page en SVG inline. Deterministe: meme entree, meme sortie, aucun
 * appel de modele. Sans initiale lisible on pose une pastille sans texte —
 * mieux vaut une marque neutre qu un glyphe invente.
 */
export function buildInlineFaviconDataUrl(initial: string | null): string {
  const mark = initial
    ? `<text x="32" y="44" font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="34" font-weight="700" text-anchor="middle" fill="#f9fafb">${initial}</text>`
    : '<circle cx="32" cy="32" r="12" fill="#f9fafb"/>'
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    + '<rect width="64" height="64" rx="14" fill="#111827"/>'
    + `${mark}</svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

/** Conseil REALISABLE pour un binaire lie et absent. Jamais « livre le fichier ». */
export function describeMissingBinaryAssetRemediation(url: string): string {
  return `Ce pipeline n ecrit pas de binaire (${url} ne sera jamais produit par un modele de texte).`
    + ' Remplace la reference par un SVG inline ou une data URL, ou retire-la.'
}

/**
 * Repare, sans modele, les liens d icone qui pointent un binaire absent.
 *
 * Ne touche a rien d autre: un `<img>` casse releve du contenu, une feuille de
 * style absente est un vrai defaut reparable par ecriture. Ici on ne traite que
 * le cas ou la reparation est entierement mecanique.
 */
export function repairDanglingIconLinks<T extends DanglingAssetFile>(files: T[]): T[] {
  const present = new Set(files.map((file) => normalizePath(file.name)))
  let touched = false

  const repaired = files.map((file) => {
    if (!/\.html?$/i.test(file.name)) return file
    let inlineUsed = false

    const content = file.content.replace(LINK_TAG_RE, (tag) => {
      const rel = attributeOf(tag, 'rel')
      if (!isIconRel(rel)) return tag
      const href = attributeOf(tag, 'href')
      if (!href || !isLocalReference(href)) return tag
      const target = normalizePath(href.split(/[?#]/)[0])
      if (!isBinaryAssetPath(target) || present.has(target)) return tag

      touched = true
      // Un `rel` qui n accepte pas le SVG (apple-touch-icon, mask-icon) n a
      // aucun substitut textuel: on retire la promesse plutot que de la mentir.
      if (!relAcceptsSvg(rel!)) return ''
      if (inlineUsed) return ''
      inlineUsed = true
      const dataUrl = buildInlineFaviconDataUrl(faviconInitialFromHtml(file.content))
      return `<link rel="icon" type="image/svg+xml" href="${dataUrl}" />`
    })

    return content === file.content ? file : { ...file, content }
  })

  return touched ? repaired : files
}
