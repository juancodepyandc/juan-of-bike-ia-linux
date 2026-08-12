// ---------------------------------------------------------------------------
// codeProtocolLeakGuard — un fichier livre ne commence JAMAIS par un marqueur
// du protocole d emission Aurora.
//
// Run 1061, constat sur le flux reel: 15 534 octets contenant TOUT le projet
// (14 fichiers, marqueurs de protocole compris) ont ete ecrits tels quels dans
// un unique fichier nomme `main.js`. Le critique statique l a lu, a vu
// `<<<AURORA_CODE_VFS/1>>>` en tete et a diagnostique « jeton inattendu pres de
// import ». Il avait raison: ce n etait pas du JavaScript. Neuf passes de
// correction ont ete brulees a reparer une erreur de syntaxe qui n existait pas,
// et le run s est termine en `error` alors que les quatre portes de qualite
// etaient franchies.
//
// La cause premiere (un en-tete de fichier NU que le parseur n acceptait pas)
// est corrigee dans codeProjectEmission. Ce module est la seconde ligne: quelle
// que soit la derive de protocole a venir, un conteneur ne peut plus SORTIR
// deguise en fichier. Soit on le deballe, soit on refuse de le livrer — jamais
// on ne le fait passer pour du code.
// ---------------------------------------------------------------------------

import {
  isStructuredProjectEmission,
  parseProjectTreeEmission,
  STRUCTURED_PROJECT_EMISSION_VERSION,
} from './codeProjectEmission.ts'

export type ProtocolLeakDisposition = 'unpacked' | 'dropped'

export type ProtocolLeakReport = {
  /** Chemin sous lequel le conteneur avait ete deguise (ex: `main.js`). */
  path: string
  marker: string
  bytes: number
  disposition: ProtocolLeakDisposition
  /** Chemins reellement extraits quand le conteneur a pu etre deballe. */
  recovered: string[]
  message: string
}

type LeakableFile = { name: string; language: string; content: string }

/**
 * Marqueurs de tete. On ne teste QUE le debut du contenu: un fichier peut
 * legitimement citer `<<<AURORA_END>>>` en son sein (test de non-regression
 * existant), et le confondre avec une fuite de protocole serait le meme travers
 * de jugement sur la forme que ce module corrige.
 */
const HEAD_MARKERS = [
  `<<<${STRUCTURED_PROJECT_EMISSION_VERSION}>>>`,
  STRUCTURED_PROJECT_EMISSION_VERSION,
  '<<<AURORA_FILE ',
  'AURORA_FILE {',
  '<<<AURORA_END>>>',
]

/** Le contenu commence-t-il par un marqueur de protocole Aurora ? */
export function detectProtocolLeakMarker(content: string): string | null {
  const head = content.replace(/^﻿/, '').trimStart()
  if (!head) return null
  for (const marker of HEAD_MARKERS) {
    if (head.startsWith(marker)) return marker
  }
  return null
}

function unpackContainer(content: string): LeakableFile[] {
  if (!isStructuredProjectEmission(content)) return []
  return parseProjectTreeEmission(content).tree.files.map((file) => ({
    name: file.path,
    language: file.language ?? 'text',
    content: file.content,
  }))
}

/**
 * Remplace tout fichier qui est en realite un conteneur de protocole par les
 * fichiers qu il transporte. Si le conteneur est indeballable, le fichier est
 * RETIRE (et signale): livrer 15 Ko de marqueurs sous un nom en `.js` est pire
 * que ne rien livrer — cela envoie toute la boucle de correction reparer une
 * erreur de syntaxe imaginaire.
 */
export function salvageProtocolLeaks(files: LeakableFile[]): {
  files: LeakableFile[]
  leaks: ProtocolLeakReport[]
} {
  const leaks: ProtocolLeakReport[] = []
  const output: LeakableFile[] = []
  const seen = new Set(files.map((file) => file.name))

  for (const file of files) {
    const marker = detectProtocolLeakMarker(file.content)
    if (!marker) {
      output.push(file)
      continue
    }

    const unpacked = unpackContainer(file.content).filter((inner) => inner.content.trim().length > 0)
    if (unpacked.length > 0) {
      const added: string[] = []
      for (const inner of unpacked) {
        // Le conteneur ne peut pas ecraser un fichier deja livre sous le meme
        // chemin par un chemin nominal: on ajoute ce qui manque, on ne detruit
        // rien. La fusion nominale reste le travail de l appelant.
        if (seen.has(inner.name)) {
          const index = output.findIndex((existing) => existing.name === inner.name)
          if (index >= 0) output[index] = inner
          else output.push(inner)
        } else {
          output.push(inner)
          seen.add(inner.name)
        }
        added.push(inner.name)
      }
      leaks.push({
        path: file.name,
        marker,
        bytes: file.content.length,
        disposition: 'unpacked',
        recovered: added,
        message: `« ${file.name} » etait un conteneur ${STRUCTURED_PROJECT_EMISSION_VERSION} (${file.content.length} o), pas du code: ${added.length} fichier(s) extrait(s).`,
      })
      continue
    }

    leaks.push({
      path: file.name,
      marker,
      bytes: file.content.length,
      disposition: 'dropped',
      recovered: [],
      message: `« ${file.name} » commence par le marqueur de protocole « ${marker} » et n a pas pu etre deballe: fichier ecarte au lieu d etre livre comme du code.`,
    })
  }

  return { files: output, leaks }
}

export function formatProtocolLeakReport(leaks: ProtocolLeakReport[]): string {
  if (leaks.length === 0) return ''
  return ['## FUITE DE PROTOCOLE INTERCEPTEE', ...leaks.map((leak) => `- ${leak.message}`)].join('\n')
}
