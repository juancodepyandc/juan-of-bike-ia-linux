#!/usr/bin/env node
/**
 * Script d'exécution réelle des 20 tests d'images avec ultra-précision.
 * Enregistre STRICTEMENT dans application/output/image/cli/<slug>/
 * avec prompt.txt, image.png et metadata.json sans duplication.
 */

import { existsSync, mkdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { execSync } from 'node:child_process'

const OUT_DIR = '/home/juan/AuroraIA/application/output/image/cli'
mkdirSync(OUT_DIR, { recursive: true })

const TESTS = [
  // =========================================================================
  // 1. GENERATION PURE (10 IMAGES)
  // =========================================================================

  // 1.1 Paysage Anime (Magnolia & Guilde Fairy Tail avec personnages fidèles)
  {
    slug: 'paysage_magnolia',
    prompt: 'le village de magnolia dans fairy tail avec le batiment officiel de la guilde fairy tail au bord de la riviere orne de sa grande banniere avec le symbole de la guilde, et les membres celebres de la guilde reconnaissables sur le perron, architecture anime fidele',
    style: 'anime',
    steps: 32,
    ref: null,
  },

  // 1.2 Paysage Réaliste (Plage tropicale déserte sans présence humaine)
  {
    slug: 'paysage_plage',
    prompt: 'une plage tropicale sauvage deserte au coucher de soleil avec de majestueuses falaises rocheuses et des vagues calmes sur le sable fin, paysage naturel vierge de toute presence humaine, photographie de paysage naturelle',
    style: 'realistic',
    steps: 32,
    ref: null,
  },

  // 1.3 Scène Comic (Springfield)
  {
    slug: 'scene_springfield',
    prompt: 'le centre ville de springfield avec la taverne de moe et la centrale nucleaire au loin, decor anime fidele avec perspective, sans passants',
    style: 'comic',
    steps: 32,
    ref: null,
  },

  // 1.4 Scène Cinématique (Duel nocturne)
  {
    slug: 'scene_duel_nocturne',
    prompt: 'un duel magique nocturne dans une vieille ruelle pavee sous une pluie fine, reflets de lumiere magique sur les paves humides, ambiance cinematographique',
    style: 'cinematic',
    steps: 32,
    ref: null,
  },

  // 1.5 Personnage Anime (Natsu Dragneel)
  {
    slug: 'perso_natsu',
    prompt: 'natsu dragneel avec ses cheveux roses en bataille, son echarpe blanche en ecailles, un grand sourire confiant et son poing enflamme de flammes rouges',
    style: 'anime',
    steps: 32,
    ref: null,
  },

  // 1.6 Personnage Cinématique (Guerrière cyber)
  {
    slug: 'perso_guerriere_cyber',
    prompt: 'une jeune guerriere cybernetique avec des cheveux courts violets, une veste lumineuse cyberpunk et des implants de circuits dores, rendu cinematographique',
    style: 'cinematic',
    steps: 32,
    ref: null,
  },

  // 1.7 Objet Concept Art (Épée magique)
  {
    slug: 'objet_epee_magique',
    prompt: 'une epee magique ancienne incrustee de cristaux luminescents bleus sur un socle de pierre runique, concept art de production detaille',
    style: 'concept_art',
    steps: 32,
    ref: null,
  },

  // 1.8 Objet Réaliste (Montre à gousset - pur objet d'horlogerie sans personnage)
  {
    slug: 'objet_montre_gousset',
    prompt: 'une montre a gousset mecanique de collection en or ouvrage avec rouages et engrenages apparents au centre, cadran circulaire blanc avec les 12 chiffres des heures et deux fines aiguilles noires, fond neutre studio, photographie macro',
    style: 'realistic',
    steps: 32,
    ref: null,
  },

  // 1.9 Créature Fantasy (Dragon rouge)
  {
    slug: 'creature_dragon_rouge',
    prompt: 'un dragon rouge majestueux pose sur le sommet d une montagne enneigee, ecailles brillantes et ailes repliees, decor epique',
    style: 'fantasy',
    steps: 32,
    ref: null,
  },

  // 1.10 Véhicule Réaliste (Combi van 70s)
  {
    slug: 'vehicule_combi_van',
    prompt: 'un vieux van combi hippie orange et blanc des annees 70 gare face a l ocean au coucher du soleil, photo argentique chaleureuse',
    style: 'realistic',
    steps: 32,
    ref: null,
  },

  // =========================================================================
  // 2. MODIFICATION & RETOUCHE (6 IMAGES)
  // =========================================================================

  // 2.1 Ajout Référence Réaliste (Pikachu réaliste sur la plage)
  {
    slug: 'retouche_pikachu_sur_plage',
    prompt: 'ajoute pikachu qui dort sur le sable pres de l eau dans le meme style photo realiste avec de la fourrure et des ombres naturelles',
    style: 'realistic',
    steps: 32,
    denoise: 0.62,
    ref: join(OUT_DIR, 'paysage_plage', 'image.png'),
  },

  // 2.2 Ajout Référence Anime (Happy volant à côté de Natsu)
  {
    slug: 'retouche_happy_avec_natsu',
    prompt: 'ajoute le chat bleu happy de fairy tail avec ses petites ailes blanches qui vole joyeusement a cote de natsu en souriant',
    style: 'anime',
    steps: 32,
    denoise: 0.60,
    ref: join(OUT_DIR, 'perso_natsu', 'image.png'),
  },

  // 2.3 Ajout Élément Inventé (Tente rouge & feu de camp sous le dragon)
  {
    slug: 'retouche_dragon_tente_feu',
    prompt: 'ajoute une tente de camping rouge et un feu de camp crepitant avec de la fumee sur la neige au premier plan',
    style: 'fantasy',
    steps: 32,
    denoise: 0.62,
    ref: join(OUT_DIR, 'creature_dragon_rouge', 'image.png'),
  },

  // 2.4 Ajout Vêtement & Flammes (Cape noire + flammes bleues sur Natsu)
  {
    slug: 'retouche_natsu_cape_noire_flammes_bleues',
    prompt: 'ajoute une grande cape noire sur ses epaules et des flammes magiques bleues vives autour de ses poings en plus du feu rouge',
    style: 'anime',
    steps: 32,
    denoise: 0.56,
    ref: join(OUT_DIR, 'perso_natsu', 'image.png'),
  },

  // 2.5 Changement d'Ambiance (Nuit étoilée sur Magnolia)
  {
    slug: 'retouche_magnolia_nuit_etoilee',
    prompt: 'change le ciel et le decor en une nuit etoilee avec une grande pleine lune brillante et des reflets sur l eau',
    style: 'anime',
    steps: 32,
    denoise: 0.58,
    ref: join(OUT_DIR, 'paysage_magnolia', 'image.png'),
  },

  // 2.6 Changement d'Ambiance (Coucher de soleil sur guerrière cyber)
  {
    slug: 'retouche_guerriere_coucher_soleil',
    prompt: 'change l arriere-plan en un coucher de soleil chaleureux avec un ciel orange et dore',
    style: 'cinematic',
    steps: 32,
    denoise: 0.55,
    ref: join(OUT_DIR, 'perso_guerriere_cyber', 'image.png'),
  },

  // =========================================================================
  // 3. TRANSFERT & RECONNAISSANCE (4 IMAGES)
  // =========================================================================

  // 3.1 Transfert Sujet Connu (Natsu dans décor de Magnolia)
  {
    slug: 'transfert_natsu_dans_magnolia',
    prompt: 'reproduis fidelement natsu de cette image et place le dans le village de magnolia devant la guilde',
    style: 'anime',
    steps: 32,
    denoise: 0.62,
    ref: join(OUT_DIR, 'perso_natsu', 'image.png'),
  },

  // 3.2 Transfert Sujet Connu (Homer Simpson cosmonaute sur la Lune)
  {
    slug: 'transfert_homer_sur_lune',
    prompt: 'prends homer de cette photo et mets le en costume de cosmonaute sur la lune avec la terre dans l espace',
    style: 'comic',
    steps: 32,
    denoise: 0.65,
    ref: join(OUT_DIR, 'scene_springfield', 'image.png'),
  },

  // 3.3 Transfert Sujet Descriptif (Guerrière dans un temple en ruines)
  {
    slug: 'transfert_guerriere_dans_temple',
    prompt: 'fais une reproduction fidele de la guerriere de cette reference mais debout dans un temple ancien en ruines envahi de lianes',
    style: 'cinematic',
    steps: 32,
    denoise: 0.62,
    ref: join(OUT_DIR, 'perso_guerriere_cyber', 'image.png'),
  },

  // 3.4 Transfert Sujet Descriptif (Épée plantée dans un rocher enchanté)
  {
    slug: 'transfert_epee_dans_rocher',
    prompt: 'garde la meme epee magique ornee de cristaux mais place la plantee dans un rocher au milieu d une clairiere enchantee',
    style: 'concept_art',
    steps: 32,
    denoise: 0.62,
    ref: join(OUT_DIR, 'objet_epee_magique', 'image.png'),
  },
]

console.log('='.repeat(70))
console.log(`🎨 EXÉCUTION RÉELLE STRICTE DANS application/output/image/cli/<slug>/`)
console.log(`📁 Dossier racine : ${OUT_DIR}`)
console.log('='.repeat(70))

for (let i = 0; i < TESTS.length; i++) {
  const t = TESTS[i]
  const targetSubdir = join(OUT_DIR, t.slug)
  const targetImage = join(targetSubdir, 'image.png')
  const targetPrompt = join(targetSubdir, 'prompt.txt')

  if (existsSync(targetImage) && existsSync(targetPrompt) && !process.env.FORCE_RERUN) {
    const size = (statSync(targetImage).size / (1024 * 1024)).toFixed(2)
    console.log(`\n[${i + 1}/${TESTS.length}] ⏩ DÉJÀ GÉNÉRÉ : ${t.slug} (${size} Mo)`)
    continue
  }

  if (t.ref && !existsSync(t.ref)) {
    console.error(`\n[${i + 1}/${TESTS.length}] ⚠️ Image de référence manquante : ${t.ref}`)
    continue
  }

  console.log(`\n[${i + 1}/${TESTS.length}] ⏳ GÉNÉRATION RÉELLE : ${t.slug}`)
  console.log(`   Prompt: "${t.prompt}"`)
  if (t.ref) console.log(`   Réf: ${t.ref}`)

  const cmdParts = [
    'node',
    '--experimental-strip-types',
    'application/scripts/image_cli.mjs',
    `--prompt "${t.prompt.replace(/"/g, '\\"')}"`,
    `--tag "${t.slug}"`,
    `--out "${OUT_DIR}"`,
    `--steps ${t.steps}`,
  ]
  if (t.style && t.style !== 'none') cmdParts.push(`--style ${t.style}`)
  if (t.denoise !== undefined) cmdParts.push(`--denoise ${t.denoise}`)
  if (t.ref) cmdParts.push(`--ref "${t.ref}"`)

  const cmd = cmdParts.join(' ')
  const startTime = Date.now()
  try {
    execSync(cmd, { cwd: '/home/juan/AuroraIA', stdio: 'inherit' })
    const duration = Math.round((Date.now() - startTime) / 1000)
    if (existsSync(targetImage)) {
      const size = (statSync(targetImage).size / (1024 * 1024)).toFixed(2)
      console.log(`✅ [${i + 1}/${TESTS.length}] SUCCÈS : ${t.slug} (${size} Mo en ${duration}s)`)
    } else {
      console.error(`❌ [${i + 1}/${TESTS.length}] Fichier attendu non trouvé : ${targetImage}`)
    }
  } catch (err) {
    console.error(`❌ [${i + 1}/${TESTS.length}] ERREUR sur ${t.slug}:`, err.message)
  }
}

console.log('\n' + '='.repeat(70))
console.log('🏁 TOUTES LES GÉNÉRATIONS RÉELLES SONT TERMINÉES ET CLASSÉES !')
console.log('='.repeat(70))
