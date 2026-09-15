#!/usr/bin/env node
/**
 * Banc de conformité inter-modules AuroraIA.
 *
 * Un seul point d'entrée pour rejouer les mesures qui ont motivé les
 * corrections, et vérifier qu'elles tiennent toujours.
 *
 *   node scripts/conformance.mjs              # suite de conformité
 *   node scripts/conformance.mjs --preuve     # + preuve rouge/vert
 *   node scripts/conformance.mjs --tout       # + suite complète du dépôt
 *   node scripts/conformance.mjs --json       # sortie machine
 *
 * La preuve rouge/vert remet les 9 services dans leur état d'origine (HEAD),
 * relance les mêmes tests, vérifie qu'ils ÉCHOUENT, puis restaure. Un test
 * qui reste vert sur le code d'avant ne prouve rien : c'est ce contrôle qui
 * écarte les faux positifs.
 */
import { execFileSync, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, copyFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const RACINE = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DEPOT = resolve(RACINE, '..')

/** Les 9 services corrigés, avec le défaut mesuré qui a motivé la correction. */
const SERVICES = [
  ['src/services/voiceFrPhonemizer.ts', 'voix', 'prononciation FR : 2 justes sur 18 (11 %)'],
  ['src/services/videoSubtitleExport.ts', 'vidéo', 'SRT/VTT cassés par un temps fractionnaire, une flèche ou une ligne vide'],
  ['src/services/videoTempoDetector.ts', 'vidéo', 'tempo faux de 3 BPM sur 4 mesures, annoncé avec une confiance de 1,000'],
  ['src/services/cyber/cryptoService.ts', 'cyber', 'haie : 254 aller-retours cassés sur 280 ; base64 lève sur un emoji tronqué'],
  ['src/services/coworkSafety.ts', 'cowork', 'un chemin à octet nul passait la clôture du bac à sable'],
  ['src/services/codeCompositionGate.ts', 'code', 'emoji ⭐ ▶️ 🇫🇷 non détectés ; ✓ détecté à tort'],
  ['src/services/imageAspectRecommender.ts', 'image', '« affiche » et « bannière » rendaient un carré'],
  ['src/services/conversationSentiment.ts', 'conversation', '« catastrophe totale, rien ne marche » noté NEUTRE'],
  ['src/services/learning/spacedRepetition.ts', 'apprentissage', 'retour à la moyenne mal ciblé ; brouillage à ±2,5 % au lieu de ±5 %'],
  ['src/services/threeDTextureAtlas.ts', '3D', 'atlas : 4 paires de textures se chevauchaient sur 12'],
  ['src/services/threeDGltfValidator.ts', '3D', '7 violations glTF sur 18 passaient, dont le cycle de nœuds'],
  ['src/services/threeDRigRetarget.ts', '3D', 'quaternions NaN sur durée nulle, temps NaN ou infini'],
  ['src/services/threeDBoundsAndCulling.ts', '3D', 'frustum faux si la matrice est rangée en colonnes (Three.js)'],
  ['src/services/codeImportExportShape.ts', 'code', 'imports et exports lus dans les commentaires et les chaînes'],
  ['src/services/codeGeneratedFileSanitizer.ts', 'code', 'README tronqué de sa clôture ; JSON altéré dans les chaînes'],
  ['python-services/anim_metrics.py', '3D/anim', 'un personnage FIGÉ passait la porte, indistinguable d’un personnage qui bouge'],
  ['python-services/mesh_quality_score.py', '3D/qualité', 'aucun plancher sur la densité : 12 sommets livrés comme modèle fini'],
  ['python-services/bake_vertex_colors.py', '3D/couleur', '« mechanism » et « mechanical » sans axe de projection'],
  ['python-services/auto_validate_mesh.py', '3D/reprise', '3 couples (générateur, axe) sans décision dans le graphe de reprise'],
]

/** Les 9 suites de conformité, une par module touché. */
const SUITES = [
  ['voiceFrPhonemizerCorpus', 'voix', 'corpus de 62 mots, IPA exacte'],
  ['videoSubtitleConformance', 'vidéo', 'aller-retour SRT/VTT avec analyseur indépendant'],
  ['videoTempoGroundTruth', 'vidéo', '11 tempos de synthèse à vérité connue'],
  ['cyberCryptoRoundTrip', 'cyber', 'vecteurs normalisés + 1 400 aller-retours UTF-8'],
  ['coworkSandboxContainment', 'cowork', 'matrice d’échappement du bac à sable'],
  ['codeAiTraceDetector', 'code', 'traces d’IA : détection ET absence de faux positif'],
  ['imageAspectGroundTruth', 'image', 'vocabulaire français des formats'],
  ['conversationSentimentCorpus', 'conversation', 'corpus de polarité + négation'],
  ['learningFsrsInvariants', 'apprentissage', 'invariants du planificateur'],
  ['threeDGeometryInvariants', '3D', 'atlas, sphère englobante, frustum, quaternions'],
  ['threeDGltfSpecConformance', '3D', '24 violations de la spécification glTF 2.0'],
  ['codeSourceAnalysisFidelity', 'code', 'analyse de source et nettoyage du livrable'],
]

/** Suites Python (unittest). Le 4ᵉ champ vaut 'couverture' quand la suite
 *  n'accompagne AUCUNE correction : elle couvre du code déjà juste, trouvé
 *  sain à la mesure. Une telle suite ne PEUT pas rougir sur le code d'avant,
 *  et l'exiger reviendrait à confondre « ce test ne prouve rien » avec
 *  « ce module n'avait rien à réparer ». Par défaut une suite est une preuve
 *  de correction, et doit rougir.
 *
 *  Lancées avec l'interpréteur du venv du projet :
 *  `shutil.which('python3')` du système n'a ni numpy ni trimesh, et lancer la
 *  suite avec lui rendait 36 erreurs d'import maquillées en régressions. */
const SUITES_PY = [
  ['test_anim_metrics_motion.py', '3D/anim', 'personnage figé vs personnage qui bouge'],
  ['test_motion_baker_fidelity.py', '3D/mouvement', '14 primitives + 45 presets bougent vraiment', 'couverture'],
  ['test_mesh_quality_gate.py', '3D/qualité', 'planchers du portail de livraison'],
  ['test_video_frame_contracts.py', 'vidéo', 'grilles d’images et validation d’image-clé', 'couverture'],
]

const PYTHON = join(RACINE, '.venv', 'bin', 'python')

/** Mesures comportementales des services Python (même contrat que côté TS). */
function mesurePython() {
  try {
    const sortie = execFileSync(PYTHON, [join(RACINE, 'scripts', 'conformance_mesures.py')],
      { cwd: RACINE, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 600_000 })
    return JSON.parse(sortie.slice(sortie.indexOf('[')))
  } catch (e) {
    return [{ module: 'python', quoi: 'mesures', defauts: 1,
              detail: `banc Python injoignable : ${String(e.message).slice(0, 160)}` }]
  }
}

const args = new Set(process.argv.slice(2))
const JSON_OUT = args.has('--json')
const log = (...a) => { if (!JSON_OUT) console.log(...a) }

function joueSuite(nom) {
  const fichier = `src/__tests__/${nom}.test.ts`
  try {
    const sortie = execFileSync(
      process.execPath,
      ['--experimental-strip-types', '--test', fichier],
      { cwd: RACINE, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 300_000 },
    )
    return lis(sortie)
  } catch (e) {
    return lis(`${e.stdout ?? ''}${e.stderr ?? ''}`)
  }
}

function joueSuitePython(fichier) {
  // `unittest` ecrit son compte rendu sur STDERR. `execFileSync` ne rend que
  // stdout en cas de succes: la lecture tombait alors sur du vide et rapportait
  // -1 test — un banc qui ne mesure rien tout en paraissant s executer.
  const r = spawnSync(
    PYTHON,
    ['-m', 'unittest', 'discover', '-s', '.', '-p', fichier, '-t', '.'],
    { cwd: join(RACINE, 'python-services'), encoding: 'utf8', timeout: 600_000 },
  )
  return lisPython(`${r.stdout ?? ''}\n${r.stderr ?? ''}`)
}

function lisPython(sortie) {
  const total = Number(/^Ran (\d+) tests?/m.exec(sortie)?.[1] ?? -1)
  const echecs = Number(/failures=(\d+)/.exec(sortie)?.[1] ?? 0)
  const erreurs = Number(/errors=(\d+)/.exec(sortie)?.[1] ?? 0)
  const sautes = Number(/skipped=(\d+)/.exec(sortie)?.[1] ?? 0)
  const fail = echecs + erreurs
  return { tests: total, pass: total < 0 ? -1 : total - fail - sautes, fail, skipped: sautes,
           chargement: /ImportError|ModuleNotFoundError/.test(sortie) }
}

function lis(sortie) {
  const n = (motif) => Number(new RegExp(`^ℹ ${motif} (\\d+)$`, 'm').exec(sortie)?.[1] ?? -1)
  return { tests: n('tests'), pass: n('pass'), fail: n('fail'), chargement: /Error|SyntaxError/.test(sortie) && n('tests') <= 1 }
}

// ---------------------------------------------------------------------------
log('\n\x1b[1mBANC DE CONFORMITÉ AURORAIA\x1b[0m')
log('─'.repeat(78))

const résultats = []
let totalTests = 0; let totalFail = 0
for (const [nom, module, quoi] of SUITES) {
  const r = joueSuite(nom)
  totalTests += Math.max(0, r.tests); totalFail += Math.max(0, r.fail)
  const état = r.fail === 0 && r.tests > 0 ? '\x1b[32mOK   \x1b[0m' : '\x1b[31mÉCHEC\x1b[0m'
  log(`${état} ${module.padEnd(14)} ${String(r.pass).padStart(4)}/${String(r.tests).padEnd(4)}  ${quoi}`)
  résultats.push({ suite: nom, module, ...r })
}
for (const [fichier, module, quoi] of SUITES_PY) {
  const r = joueSuitePython(fichier)
  totalTests += Math.max(0, r.tests); totalFail += Math.max(0, r.fail)
  const état = r.fail === 0 && r.tests > 0 ? '\x1b[32mOK   \x1b[0m' : '\x1b[31mÉCHEC\x1b[0m'
  const sautes = r.skipped ? ` (${r.skipped} ignorés)` : ''
  log(`${état} ${module.padEnd(14)} ${String(r.pass).padStart(4)}/${String(r.tests).padEnd(4)}  ${quoi}${sautes}`)
  résultats.push({ suite: fichier, module, langage: 'python', ...r })
}
log('─'.repeat(78))
log(`${totalFail === 0 ? '\x1b[32m' : '\x1b[31m'}${totalTests} tests de conformité, ${totalFail} échec(s)\x1b[0m`)

// ---------------------------------------------------------------------------
let preuve = null
let mesures = null

// --mesures : lecture seule, sur le code EN PLACE. Aucun fichier n'est touché,
// ce qui le rend sûr à exposer par le pont HTTP.
if (args.has('--mesures') && !args.has('--preuve')) {
  const { mesure } = await import(`./conformanceMesures.mjs?m=${Date.now()}`)
  mesures = { apres: [...await mesure(), ...mesurePython()], avant: null }
  log('\n\x1b[1mMESURES COMPORTEMENTALES\x1b[0m')
  log('─'.repeat(78))
  for (const m of mesures.apres) {
    const état = m.defauts === 0 ? '\x1b[32mOK   \x1b[0m' : `\x1b[31m${String(m.defauts).padStart(4)} \x1b[0m`
    log(`${état} ${m.module.padEnd(14)} ${m.quoi.padEnd(26)} ${m.detail}`)
  }
  const total = mesures.apres.reduce((a, b) => a + b.defauts, 0)
  log('─'.repeat(78))
  log(`${total === 0 ? '\x1b[32m' : '\x1b[31m'}${total} défaut(s) mesuré(s)\x1b[0m`)
}

// --preuve : rejoue le banc sur le code d'AVANT. Cette étape REVIENT
// temporairement à HEAD sur 9 fichiers puis restaure : elle reste réservée à
// la ligne de commande, sous l'œil de l'opérateur.
if (args.has('--preuve')) {
  log('\n\x1b[1mPREUVE ROUGE/VERT\x1b[0m — les mêmes tests contre le code d’avant')
  log('─'.repeat(78))
  const sauvegarde = join(RACINE, '.conformance-sauvegarde')
  for (const [f] of SERVICES) {
    const cible = join(sauvegarde, f)
    mkdirSync(dirname(cible), { recursive: true })
    copyFileSync(join(RACINE, f), cible)
  }
  // Mesures comportementales sur l'état APRÈS, avant de revenir en arrière.
  const { mesure } = await import(`./conformanceMesures.mjs?apres=${Date.now()}`)
  const apres = [...await mesure(), ...mesurePython()]

  try {
    for (const [f] of SERVICES) {
      execFileSync('git', ['checkout', 'HEAD', '--', `application/${f}`], { cwd: DEPOT, stdio: 'ignore' })
    }

    // Mêmes mesures sur l'état AVANT. Elles n'appellent que des fonctions déjà
    // exportées à l'époque : c'est ce qui rend la comparaison possible.
    const { mesure: mesureAvant } = await import(`./conformanceMesures.mjs?avant=${Date.now()}`)
    const avant = [...await mesureAvant(), ...mesurePython()]

    log('\n  \x1b[1mDéfauts mesurés — avant / après\x1b[0m')
    for (let i = 0; i < avant.length; i += 1) {
      const a = avant[i]
      const b = apres[i]
      const flèche = a.defauts > b.defauts ? '\x1b[32m→\x1b[0m' : (a.defauts === b.defauts ? '=' : '\x1b[31m→\x1b[0m')
      log(`  ${a.module.padEnd(14)} ${a.quoi.padEnd(26)} ${String(a.defauts).padStart(4)} ${flèche} ${String(b.defauts).padStart(4)}`)
      log(`  ${' '.repeat(41)} avant : ${a.detail}`)
      log(`  ${' '.repeat(41)} après : ${b.detail}`)
    }
    mesures = { avant, apres }

    log('\n  \x1b[1mSuites de conformité rejouées sur le code d’avant\x1b[0m')
    preuve = []
    const rapporte = (nom, module, quoi, r, role = 'correction') => {
      const rouge = r.fail > 0 || r.chargement || r.tests <= 0
      const attendu = role !== 'couverture'
      const état = !attendu
        ? '\x1b[36mNEUF \x1b[0m'
        : (rouge ? '\x1b[32mROUGE\x1b[0m' : '\x1b[31mVERT — ce test ne prouve rien\x1b[0m')
      const détail = !attendu
        ? 'couverture neuve : aucun défaut à prouver'
        : (r.chargement ? 'ne charge pas (symbole absent avant correction)' : `${r.fail} échec(s)`)
      log(`  ${état} ${module.padEnd(14)} ${détail.padEnd(46)} ${quoi}`)
      preuve.push({ suite: nom, rouge, role, doitRougir: attendu, ...r })
    }
    for (const [nom, module, quoi, role] of SUITES) {
      rapporte(nom, module, quoi, joueSuite(nom), role)
    }
    for (const [fichier, module, quoi, role] of SUITES_PY) {
      rapporte(fichier, module, quoi, joueSuitePython(fichier), role)
    }
  } finally {
    for (const [f] of SERVICES) copyFileSync(join(sauvegarde, f), join(RACINE, f))
    log('─'.repeat(78))
    log('services restaurés')
  }
  const complaisants = preuve.filter((p) => p.doitRougir && !p.rouge)
  log(complaisants.length === 0
    ? `\x1b[32maucun test complaisant : les ${preuve.filter((p) => p.doitRougir).length} suites `
      + `qui prouvent une correction échouent toutes sur le code d’avant, `
      + `${preuve.length - preuve.filter((p) => p.doitRougir).length} suites de couverture neuve\x1b[0m`
    : `\x1b[31m${complaisants.length} suite(s) restée(s) verte(s) : ${complaisants.map((c) => c.suite).join(', ')}\x1b[0m`)
}

// ---------------------------------------------------------------------------
let complète = null
if (args.has('--tout')) {
  log('\n\x1b[1mSUITE COMPLÈTE DU DÉPÔT\x1b[0m')
  log('─'.repeat(78))
  try {
    const sortie = execFileSync('npm', ['test'], { cwd: RACINE, encoding: 'utf8', timeout: 900_000 })
    complète = lis(sortie)
  } catch (e) { complète = lis(`${e.stdout ?? ''}${e.stderr ?? ''}`) }
  log(`${complète.pass}/${complète.tests} — ${complète.fail} échec(s)`)
}

if (JSON_OUT) {
  console.log(JSON.stringify({ conformance: résultats, mesures, preuve, complète, verdict: totalFail === 0 ? 'OK' : 'ECHEC' }, null, 2))
}
process.exit(totalFail === 0 ? 0 : 1)
