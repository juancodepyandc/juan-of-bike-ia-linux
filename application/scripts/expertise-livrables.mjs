#!/usr/bin/env node
/**
 * Expertise des LIVRABLES REELS — on ouvre les fichiers que le module Code a
 * ecrits sur le disque et on les mesure. Ni suite de tests, ni compilation :
 * des octets presents, et des constats verifiables en ouvrant le fichier a la
 * ligne indiquee.
 *
 * Ce que l'on cherche, dans l'ordre de gravite :
 *
 *   1. DERAILLEMENT DE GENERATION — un motif court repete des centaines de
 *      fois. Mesure d'ouverture sur ce depot :
 *      `assets/viewers/run-960/project/src/pages/ContactPage.tsx` fait
 *      17 837 octets dont 13 356 sur la SEULE ligne 78, ou le motif
 *      `0-.841.004-1.682.004-1.682` est repete 486 fois — un modele parti en
 *      boucle au milieu d'un trace SVG.
 *   2. FICHIER TRONQUE — il s'arrete en plein token. Le meme fichier finit sur
 *      l'octet `8`, sans guillemet fermant, sans balise fermante, sans
 *      accolade fermante, sans `export default`. Il ne compile pas.
 *   3. TRACE DE MODELE — aveu de modele, balise de reflexion, balise Markdown
 *      dans un fichier de code, troncature annoncee en commentaire.
 *   4. PICTOGRAMME EN GUISE D'ICONE — mesure par la porte que le projet
 *      embarque deja (`codeCompositionGate`), pas par une regle inventee ici.
 *
 * Ce qui n'est PAS un constat, et pourquoi :
 *   - `example.com` : domaine RESERVE par la RFC 2606 pour la documentation
 *     et les exemples. Des donnees de demonstration qui l'emploient sont
 *     CORRECTES ; le signaler serait un faux positif. (Premiere version de ce
 *     script : 8 constats de ce type, tous faux.)
 *   - `•` en tete de liste : puce typographique, pas une icone de produit.
 *   - Les visionneuses (`assets/viewers/**`) reencapsulent le projet en JSON :
 *     compter leurs occurrences reviendrait a compter deux fois le meme
 *     fichier. Elles sont recensees a part.
 *
 *   node scripts/expertise-livrables.mjs [--json] [--racine <dossier>]
 */
import { createRequire } from 'node:module'
import { readFileSync, readdirSync } from 'node:fs'
import { deflateSync } from 'node:zlib'
import { join, relative, extname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { detectEmojiIcons, containsTrueEmoji } from '../src/services/codeCompositionGate.ts'

const require_ = createRequire(import.meta.url)
/** Le compilateur TypeScript du depot — l'autorite, pas une heuristique. */
const ts = require_('typescript')

const RACINE = fileURLToPath(new URL('..', import.meta.url))
const args = process.argv.slice(2)
const JSON_OUT = args.includes('--json')
const iR = args.indexOf('--racine')
const CIBLE = iR >= 0 ? args[iR + 1] : join(RACINE, 'output', 'code')

const IGNORE = new Set(['node_modules', 'dist', '.git', '.vite', 'build', 'coverage', '__pycache__'])
const SOURCE = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.html', '.md', '.json'])
const CODE = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'])

function marche(dossier, out = []) {
  let entrees
  try { entrees = readdirSync(dossier, { withFileTypes: true }) } catch { return out }
  for (const e of entrees) {
    if (IGNORE.has(e.name)) continue
    const p = join(dossier, e.name)
    if (e.isDirectory()) marche(p, out)
    else if (SOURCE.has(extname(e.name))) out.push(p)
  }
  return out
}

function livrables(racine) {
  const out = []
  const visite = (dossier, prof) => {
    if (prof > 5) return
    let entrees
    try { entrees = readdirSync(dossier, { withFileTypes: true }) } catch { return }
    const noms = new Set(entrees.filter((e) => e.isFile()).map((e) => e.name))
    if (noms.has('index.html') || noms.has('package.json')) { out.push(dossier); return }
    for (const e of entrees) {
      if (e.isDirectory() && !IGNORE.has(e.name)) visite(join(dossier, e.name), prof + 1)
    }
  }
  visite(racine, 0)
  return out
}

/** Une visionneuse embarque le projet entier ; ses constats feraient doublon. */
const estVisionneuse = (chemin) => /(^|[\\/])(viewers?|viewer_proof|apk-build)([\\/]|$)/.test(chemin)

// ---------------------------------------------------------------------------
/**
 * Deraillement : le motif le plus repete d'une longue ligne, et le taux de
 * compression. Une ligne minifiee normale se comprime 3 a 6 fois ; une boucle
 * degeneree depasse 30.
 */
function deraillement(ligne) {
  if (ligne.length < 400) return null
  const brut = Buffer.byteLength(ligne)
  const taux = brut / deflateSync(Buffer.from(ligne)).length
  if (taux < 20) return null
  let meilleur = { motif: '', repets: 0 }
  for (let taille = 8; taille <= 40; taille += 4) {
    const compte = new Map()
    for (let i = 0; i + taille <= ligne.length; i += taille) {
      const bout = ligne.slice(i, i + taille)
      compte.set(bout, (compte.get(bout) || 0) + 1)
    }
    for (const [motif, n] of compte) {
      if (n > meilleur.repets) meilleur = { motif, repets: n }
    }
  }
  if (meilleur.repets < 20) return null
  return { taux: Math.round(taux), ...meilleur, longueur: ligne.length }
}

/**
 * Le fichier s'analyse-t-il ? On demande au COMPILATEUR, pas a un compteur.
 *
 * Les deux versions precedentes de cette fonction se sont trompees, et il faut
 * le dire :
 *   - « le dernier caractere doit fermer quelque chose » a rendu 20 faux
 *     positifs sur `audit_v108/run1061_files`, ou chaque composant finit par
 *     `export default Footer` — valide, sans saut de ligne final;
 *   - le comptage de delimiteurs apres masquage a rendu un faux positif sur
 *     `HomePage.test.tsx` : l'apostrophe de `/Presqu'île/i`, dans un litteral
 *     d'expression reguliere, etait prise pour une ouverture de chaine. Le
 *     fichier a en realite 50 parentheses ouvrantes et 50 fermantes.
 *
 * Une heuristique de delimiteurs ne peut pas trancher sur du TSX : il faut un
 * analyseur. `ts.createSourceFile` rend les diagnostics de SYNTAXE (pas de
 * type) sans avoir besoin d'un projet ni d'un `tsconfig`. C'est exact, et
 * c'est le meme analyseur qui refuserait le fichier a la compilation.
 */
const KIND_TS = {
  '.ts': 'TS', '.mts': 'TS', '.cts': 'TS',
  '.tsx': 'TSX', '.jsx': 'TSX',
  '.js': 'JS', '.mjs': 'JS', '.cjs': 'JS',
}

function analyse(contenu, ext, chemin) {
  if (KIND_TS[ext]) {
    const kind = { TS: ts.ScriptKind.TS, TSX: ts.ScriptKind.TSX, JS: ts.ScriptKind.JS }[KIND_TS[ext]]
    const sf = ts.createSourceFile(chemin, contenu, ts.ScriptTarget.Latest, true, kind)
    const diags = sf.parseDiagnostics || []
    if (!diags.length) return null
    return diags.slice(0, 3).map((d) => {
      const { line, character } = sf.getLineAndCharacterOfPosition(d.start ?? 0)
      return { ligne: line + 1, colonne: character + 1,
               message: ts.flattenDiagnosticMessageText(d.messageText, ' ') }
    })
  }
  if (ext === '.json') {
    try { JSON.parse(contenu); return null } catch (e) {
      return [{ ligne: 1, colonne: 1, message: String(e.message).slice(0, 120) }]
    }
  }
  if (ext === '.css') {
    // Le CSS n'a ni litteral d'expression reguliere ni gabarit : le comptage
    // d'accolades y est fiable, contrairement au TSX.
    const sansCommentaires = contenu.replace(/\/\*[\s\S]*?\*\//g, '')
    const o = sansCommentaires.split('{').length - 1
    const f = sansCommentaires.split('}').length - 1
    if (o === f) return null
    return [{ ligne: contenu.split('\n').length, colonne: 1,
              message: `${o} accolades ouvertes pour ${f} fermees` }]
  }
  if (ext === '.html') {
    // Un commentaire ou de l'espace APRES `</html>` est du HTML parfaitement
    // legal. Premiere version de cette regle : elle exigeait que `</html>` soit
    // le dernier caractere du fichier, et signalait donc
    // `output/code/assets/viewers/index.html`, qui se termine par
    // `</body></html>\n<!-- 26 projets -->`. Faux positif. On ignore desormais
    // les commentaires et les blancs de fin avant de conclure.
    const fin = contenu.replace(/<!--[\s\S]*?-->/g, '').trimEnd()
    if (/<html[\s>]/i.test(contenu) && !/<\/html>$/i.test(fin)) {
      return [{ ligne: contenu.split('\n').length, colonne: 1,
                message: 'balise <html> ouverte, aucun </html> de fermeture' }]
    }
    return null
  }
  return null
}

const TRACES = [
  { id: 'aveu-de-modele', re: /\b(as an ai|as a language model|en tant qu[’']?\s*(?:ia|intelligence artificielle)|je suis une ia)\b/i,
    quoi: 'aveu de modele laisse dans le livrable' },
  { id: 'balise-reflexion', re: /<\/?think>/i, quoi: 'balise de reflexion du modele fuitee' },
  { id: 'fence-markdown', re: /^```/m, exts: CODE,
    quoi: 'balise de bloc Markdown dans un fichier de code : la reponse brute a ete ecrite telle quelle' },
  { id: 'troncature-annoncee', re: /(\/\/|\/\*|#|<!--)\s*\.{3}\s*(rest of|reste d[ue]|suite d|etc\b|and so on|le reste|inchang)/i,
    quoi: 'le modele annonce lui-meme que le code est incomplet' },
  { id: 'lorem', re: /\blorem\s+ipsum\b/i, quoi: 'texte de remplissage latin' },
  { id: 'retour-echappe', re: /\\n\\n/, exts: CODE,
    quoi: 'retours a la ligne restes echappes : le fichier est une chaine, pas du code' },
]

function lignesDe(contenu, re, max = 2) {
  const out = []
  const lignes = contenu.split('\n')
  for (let i = 0; i < lignes.length && out.length < max; i += 1) {
    if (re.test(lignes[i])) out.push({ ligne: i + 1, extrait: lignes[i].trim().slice(0, 120) })
  }
  return out
}

// ---------------------------------------------------------------------------
const rapport = []
for (const projet of livrables(CIBLE)) {
  const relProjet = relative(CIBLE, projet) || '.'
  const fichiers = marche(projet)
  const constats = []
  let octets = 0

  for (const f of fichiers) {
    const ext = extname(f)
    let contenu
    try { contenu = readFileSync(f, 'utf8') } catch { continue }
    octets += Buffer.byteLength(contenu)
    const rel = relative(projet, f)
    const ajoute = (type, ligne, extrait, quoi) => constats.push({ type, fichier: rel, ligne, extrait, quoi })

    if (!contenu.trim()) { ajoute('fichier-vide', 1, '', 'fichier livre vide'); continue }

    // 1. deraillement
    const lignes = contenu.split('\n')
    for (let i = 0; i < lignes.length; i += 1) {
      const d = deraillement(lignes[i])
      if (d) {
        ajoute('deraillement', i + 1,
               `${d.longueur} caracteres ; motif « ${d.motif.trim()} » repete ${d.repets} fois ; compression x${d.taux}`,
               'generation partie en boucle : le contenu est du bruit repete')
        break
      }
    }

    // 2. le fichier s'analyse-t-il ? (verdict du compilateur)
    const diags = analyse(contenu, ext, f)
    if (diags) {
      for (const d of diags) {
        ajoute('n-analyse-pas', d.ligne, `colonne ${d.colonne} — ${d.message}`,
               'le compilateur refuse ce fichier : il ne peut pas etre livre en l etat')
      }
    }

    // 3. traces de modele
    for (const m of TRACES) {
      if (m.exts && !m.exts.has(ext)) continue
      for (const l of lignesDe(contenu, m.re)) ajoute(m.id, l.ligne, l.extrait, m.quoi)
    }

    // 4. pictogrammes — porte reelle du projet
    if (/\.(html?|vue|svelte|[jt]sx)$/i.test(f)) {
      for (const glyphe of detectEmojiIcons([{ name: basename(f), content: contenu }])) {
        if (glyphe === '•') continue  // puce typographique, pas une icone produit
        const l = lignesDe(contenu, new RegExp(glyphe.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), 1)
        ajoute('emoji-icone', l[0]?.ligne ?? 0, l[0]?.extrait ?? glyphe,
               `pictogramme « ${glyphe} » employe comme icone produit`)
      }
    }
    if (/\.(html?|[jt]sx?|mjs|css|md)$/i.test(f) && containsTrueEmoji(contenu)) {
      const l = lignesDe(contenu, /\p{Emoji_Presentation}|\p{Emoji}️/u, 1)
      ajoute('emoji-dans-le-texte', l[0]?.ligne ?? 0, l[0]?.extrait ?? '',
             'emoji dans le contenu livre')
    }
  }
  rapport.push({ projet: relProjet, visionneuse: estVisionneuse(relProjet),
                 fichiers: fichiers.length, octets, constats })
}

// ---------------------------------------------------------------------------
const reels = rapport.filter((p) => !p.visionneuse)
const vues = rapport.filter((p) => p.visionneuse)

if (JSON_OUT) {
  console.log(JSON.stringify({ cible: CIBLE, livrables: reels, visionneuses: vues }, null, 2))
} else {
  const GRAVE = new Set(['deraillement', 'n-analyse-pas', 'fichier-vide', 'aveu-de-modele',
                         'balise-reflexion', 'fence-markdown', 'troncature-annoncee', 'retour-echappe'])
  console.log(`\n\x1b[1mEXPERTISE DES LIVRABLES REELS\x1b[0m  —  ${CIBLE}`)
  console.log('='.repeat(100))
  const rendre = (liste, titre) => {
    console.log(`\n\x1b[1m${titre}\x1b[0m`)
    console.log('─'.repeat(100))
    for (const p of liste) {
      const graves = p.constats.filter((c) => GRAVE.has(c.type)).length
      const etat = p.constats.length === 0 ? '\x1b[32mPROPRE  \x1b[0m'
        : (graves ? `\x1b[31m${String(graves).padStart(3)} GRAVE\x1b[0m` : `\x1b[33m${String(p.constats.length).padStart(3)} mineur\x1b[0m`)
      console.log(`${etat} ${String(p.fichiers).padStart(4)} fich. ${String(Math.round(p.octets / 1024)).padStart(5)} Kio  ${p.projet}`)
      for (const c of p.constats) {
        const couleur = GRAVE.has(c.type) ? '\x1b[31m' : '\x1b[33m'
        console.log(`          ${couleur}${c.type}\x1b[0m  ${p.projet}/${c.fichier}:${c.ligne}`)
        console.log(`            ${c.quoi}`)
        if (c.extrait) console.log(`            > ${c.extrait}`)
      }
    }
  }
  rendre(reels, `LIVRABLES (${reels.length})`)
  if (vues.length) rendre(vues, `VISIONNEUSES — recensees a part, elles reencapsulent les livrables (${vues.length})`)

  const parType = new Map()
  for (const p of rapport) for (const c of p.constats) parType.set(c.type, (parType.get(c.type) || 0) + 1)
  const totalReels = reels.reduce((a, p) => a + p.constats.length, 0)
  console.log('\n' + '='.repeat(100))
  console.log(`${reels.reduce((a, p) => a + p.fichiers, 0)} fichiers de livrable ouverts, `
              + `${Math.round(reels.reduce((a, p) => a + p.octets, 0) / 1024)} Kio lus`)
  if (totalReels === 0) console.log('\x1b[32maucun constat sur les livrables\x1b[0m')
  for (const [t, n] of [...parType].sort((a, b) => b[1] - a[1])) {
    console.log(`  ${String(n).padStart(4)}  ${GRAVE.has(t) ? '\x1b[31m' : '\x1b[33m'}${t}\x1b[0m`)
  }
}
