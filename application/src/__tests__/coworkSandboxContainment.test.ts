/**
 * Clôture du bac à sable Cowork — matrice d'échappement.
 *
 * POURQUOI CE FICHIER EXISTE. `isInsideWorkspace` décide seul si une action
 * fichier part en `allow` (sans confirmation) ou en `confirm`. Un chemin
 * portant un OCTET NUL — `<workspace>/\0/../../etc/passwd` — commençait bien
 * par la racine du workspace, passait donc la clôture, et ressortait
 * autorisé. Aucun test ne l'exerçait.
 *
 * Un octet nul dans un chemin n'est jamais légitime, et les couches
 * sous-jacentes TRONQUENT au premier octet nul : ce qui est examiné et ce qui
 * est ouvert peuvent différer. Même remarque pour les sauts de ligne, puisque
 * l'exécuteur interpole les chemins dans des lignes de commande PowerShell.
 *
 * MÉTHODE. Une matrice de cas, chacun accompagné de la raison pour laquelle
 * il doit passer ou non — un test de sécurité sans énoncé de la menace ne se
 * relit pas. On vérifie ensuite au niveau de `validateAction`, c'est-à-dire
 * là où la décision est réellement prise.
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/coworkSandboxContainment.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  isInsideWorkspace, normalizePath, resolvePath, pathHasControlChars,
  validateAction, clearSessionApprovals,
} from '../services/coworkSafety.ts'
import type { CoworkAction } from '../services/coworkTypes.ts'

const RACINE = '/home/juan/AuroraIA/workspace'

type Cas = { chemin: string; dedans: boolean; motif: string }

const MATRICE: Cas[] = [
  // --- doivent être acceptés
  { chemin: `${RACINE}/note.txt`, dedans: true, motif: 'fichier direct' },
  { chemin: `${RACINE}`, dedans: true, motif: 'la racine elle-même' },
  { chemin: `${RACINE}/`, dedans: true, motif: 'racine avec barre finale' },
  { chemin: `${RACINE}/a/b/c/d.txt`, dedans: true, motif: 'sous-arbre profond' },
  { chemin: `${RACINE}/./sous/../note.txt`, dedans: true, motif: 'points relatifs internes' },
  { chemin: `${RACINE}/dossier avec espaces/x`, dedans: true, motif: 'espaces' },
  { chemin: `${RACINE}/éàü漢🙂.txt`, dedans: true, motif: 'nom non-ASCII' },

  // --- doivent être refusés
  { chemin: '/etc/passwd', dedans: false, motif: 'hors de l’arbre' },
  { chemin: `${RACINE}/../../etc/passwd`, dedans: false, motif: 'traversée ../' },
  { chemin: `${RACINE}/..`, dedans: false, motif: 'remontée d’un cran' },
  { chemin: `${RACINE}//../../etc`, dedans: false, motif: 'double barre puis traversée' },
  { chemin: `${RACINE}/a/../../..`, dedans: false, motif: 'traversée par sous-dossier' },
  { chemin: '/home/juan/AuroraIA/workspace-evil/secret', dedans: false, motif: 'confusion de préfixe' },
  { chemin: '/home/juan/AuroraIA/workspaceX', dedans: false, motif: 'préfixe collé' },
  { chemin: '/home/juan/AuroraIA/works', dedans: false, motif: 'préfixe plus court' },
  { chemin: `${RACINE}\u0000/../../etc/passwd`, dedans: false, motif: 'OCTET NUL — troncature en aval' },
  { chemin: `${RACINE}/a\u0000b.txt`, dedans: false, motif: 'octet nul au milieu du nom' },
  { chemin: `${RACINE}/a\nrm -rf /`, dedans: false, motif: 'saut de ligne — injection de commande' },
  { chemin: `${RACINE}/a\rb`, dedans: false, motif: 'retour chariot' },
  { chemin: `${RACINE}/a\u001bb`, dedans: false, motif: 'échappement ANSI' },
]

describe('isInsideWorkspace — matrice d’échappement', () => {
  for (const { chemin, dedans, motif } of MATRICE) {
    test(`${dedans ? 'accepte' : 'REFUSE'} — ${motif}`, () => {
      assert.equal(
        isInsideWorkspace(chemin, RACINE), dedans,
        `${JSON.stringify(chemin)} : attendu ${dedans ? 'dedans' : 'DEHORS'} (${motif})`,
      )
    })
  }

  test('une racine elle-même malformée ne valide rien', () => {
    assert.equal(isInsideWorkspace(`${RACINE}/a.txt`, `${RACINE}\u0000`), false)
  })

  test('la comparaison est insensible à la casse (systèmes Windows)', () => {
    assert.equal(isInsideWorkspace('C:/Travail/note.txt', 'c:/travail'), true)
  })
})

describe('pathHasControlChars — les 33 caractères de contrôle', () => {
  test('tous les points de code C0 et DEL sont détectés', () => {
    for (let cp = 0; cp <= 0x1f; cp += 1) {
      assert.equal(
        pathHasControlChars(`a${String.fromCharCode(cp)}b`), true,
        `U+${cp.toString(16).padStart(4, '0')} non détecté`,
      )
    }
    assert.equal(pathHasControlChars('a\u007fb'), true, 'DEL non détecté')
  })

  test('aucun faux positif sur des noms de fichiers légitimes', () => {
    const legitimes = [
      'rapport final.pdf', 'données_2026.csv', 'été-résumé.txt', '漢字.md',
      'a b  c.txt', "l'apostrophe.txt", 'prix 12€.txt', 'v1.2.3-rc1.tar.gz',
      'émoji 🙂.png', 'C:/Users/Juan/Bureau/note.txt',
    ]
    for (const nom of legitimes) {
      assert.equal(pathHasControlChars(nom), false, `faux positif sur ${JSON.stringify(nom)}`)
    }
  })
})

describe('normalizePath / resolvePath', () => {
  test('les barres inverses deviennent des barres obliques', () => {
    assert.equal(normalizePath('a\\b/c'), 'a/b/c')
  })
  test('les segments redondants sont réduits', () => {
    assert.equal(normalizePath('a//b/./c/../d'), 'a/b/d')
  })
  test('un chemin relatif se résout dans le workspace', () => {
    assert.equal(resolvePath('sous/f.txt', RACINE), `${RACINE}/sous/f.txt`)
  })
  test('un chemin absolu n’est pas replacé sous la racine', () => {
    assert.equal(resolvePath('/etc/passwd', RACINE), '/etc/passwd')
  })
  test('une entrée vide rend la racine', () => {
    assert.equal(resolvePath('', RACINE), RACINE)
  })
})

describe('validateAction — la décision réellement prise', () => {
  const action = (path: string): CoworkAction =>
    ({ kind: 'read_file', path } as unknown as CoworkAction)

  test('un fichier du workspace part en « allow »', () => {
    clearSessionApprovals()
    assert.equal(validateAction(action(`${RACINE}/note.txt`), 'desktop', RACINE).decision, 'allow')
  })

  test('un fichier hors workspace demande confirmation', () => {
    clearSessionApprovals()
    assert.equal(validateAction(action('/etc/passwd'), 'desktop', RACINE).decision, 'confirm')
  })

  test('un chemin à octet nul est BLOQUÉ, pas seulement confirmé', () => {
    clearSessionApprovals()
    const v = validateAction(action(`${RACINE}\u0000/../../etc/passwd`), 'desktop', RACINE)
    assert.equal(v.decision, 'block', `décision obtenue : ${v.decision} — ${v.reason}`)
  })

  test('le déverrouillage total ne lève PAS le refus d’un chemin malformé', () => {
    clearSessionApprovals()
    const v = validateAction(
      action(`${RACINE}/a\u0000b`), 'desktop', RACINE, { fullyUnlocked: true },
    )
    assert.equal(
      v.decision, 'block',
      'un chemin malformé n’est pas une question de permission : aucun réglage '
      + 'de confiance ne doit le rendre exécutable.',
    )
  })

  test('idem avec danger + trust', () => {
    clearSessionApprovals()
    const v = validateAction(
      action(`${RACINE}/a\nrm -rf /`), 'desktop', RACINE, { dangerMode: true, trustMode: true },
    )
    assert.equal(v.decision, 'block')
  })
})
