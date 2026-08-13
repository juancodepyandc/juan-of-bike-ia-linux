// ---------------------------------------------------------------------------
// codeTargetedRepairScope — choisir les fichiers ou le defaut est OBSERVABLE,
// et fusionner la reparation sans jamais rien perdre.
//
// Run 1061: les quatre portes de qualite etaient franchies (rendu 100/100,
// accessibilite 100/100, performance 80/100, acceptation 2/2). Un seul defaut
// restait — `real_iconography`, des emoji en position d icone. La « passe
// ciblee » a alors relance le pipeline COMPLET: nouvelle classification
// d intention, nouveau plan d architecture, nouvelle generation. Elle a rendu un
// projet different, amputé de fichiers, de scripts et d exports. Le garde
// anti-regression l a refusee (comportement correct) et le defaut est reste.
//
// Corriger l iconographie, c est editer les fichiers qui portent des emoji.
// Ce n est pas reecrire un projet. La portee est donc DEDUITE d une preuve dans
// le contenu, et la fusion est structurellement incapable de supprimer quoi que
// ce soit: on remplace des chemins existants, on n en retire aucun.
// ---------------------------------------------------------------------------

import { detectEmojiIcons } from './codeCompositionGate.ts'
import type { CodeFile } from './codeOrchestratorTypes.ts'

export type TargetedRepairScope = {
  /** Fichiers que la passe a le droit de reecrire. */
  targets: CodeFile[]
  /** Tous les autres: intouchables. */
  protectedPaths: string[]
  /** Pourquoi chaque cible a ete retenue (id de critere echoue). */
  reasonsByPath: Record<string, string[]>
}

const MARKUP_RE = /\.(html?|vue|svelte|[jt]sx)$/i
const STYLE_RE = /\.(css|scss|sass|less)$/i

type Probe = (file: CodeFile) => boolean

const isMarkup: Probe = (f) => MARKUP_RE.test(f.name)
const isStyle: Probe = (f) => STYLE_RE.test(f.name)
const has = (re: RegExp): Probe => (f) => re.test(f.content)
const both = (a: Probe, b: Probe): Probe => (f) => a(f) && b(f)
const either = (a: Probe, b: Probe): Probe => (f) => a(f) || b(f)

/**
 * Pour chaque critere, le PROBE qui repere les fichiers reellement concernes.
 * Une regle sans preuve dans le contenu est une regle qui repeint tout le
 * projet: c est exactement le defaut qu on corrige ici.
 */
const PROBES: Record<string, Probe> = {
  // Composition — le detecteur du juge lui-meme, fichier par fichier.
  real_iconography: (f) => detectEmojiIcons([{ name: f.name, content: f.content }]).length > 0,
  no_overlap: either(isStyle, both(isMarkup, has(/position\s*:\s*(absolute|fixed)|absolute |fixed /i))),
  no_empty_section: either(isStyle, both(isMarkup, has(/<section|min-h|100vh|py-\d|padding/i))),

  // Accessibilite.
  document_lang: has(/<html/i),
  images_have_name: both(isMarkup, has(/<img\b|<Image\b/i)),
  controls_have_name: both(isMarkup, has(/<button|<a\s|role=["']button/i)),
  fields_have_label: both(isMarkup, has(/<input|<select|<textarea/i)),
  heading_order: both(isMarkup, has(/<h[1-6]\b/i)),
  text_contrast: either(isStyle, has(/color\s*:|text-\w+-\d{3}|bg-\w+-\d{3}/i)),
  keyboard_reachable: both(isMarkup, has(/onClick|addEventListener\(\s*['"]click/i)),

  // Performance.
  first_paint: both(isMarkup, has(/<img\b|<script|<link/i)),
  interactive: both(isMarkup, has(/onClick|useEffect|addEventListener/i)),
  layout_stability: either(isStyle, both(isMarkup, has(/<img\b|<Image\b|aspect|height/i))),
  image_dimensions: both(isMarkup, has(/<img\b|<Image\b/i)),
  dom_weight: isMarkup,
  payload_weight: either(isMarkup, isStyle),
  main_thread: both(isMarkup, has(/useEffect|addEventListener|setInterval|requestAnimationFrame/i)),

  // Style rendu.
  runtime_clean: isMarkup,
  display_typography: either(isStyle, both(isMarkup, has(/text-\d?xl|font-|clamp\(/i))),
  type_scale: either(isStyle, both(isMarkup, has(/text-|font-size/i))),
  real_typeface: either(isStyle, has(/font-family|@font-face|fonts\.googleapis/i)),
  visual_content: both(isMarkup, has(/<section|<img|<svg|<canvas/i)),
  depth: either(isStyle, both(isMarkup, has(/shadow|gradient|blur|border/i))),
  content_density: isMarkup,
  interactivity: both(isMarkup, has(/onClick|<button|<form|addEventListener/i)),
}

/** Repli quand un critere inconnu remonte: markup et styles, jamais la config. */
const FALLBACK_PROBE: Probe = either(isMarkup, isStyle)

/**
 * Delimite la portee de la passe ciblee. `maxTargets` borne le contexte envoye
 * au modele — un patch qui embarque 35 fichiers est une regeneration deguisee.
 */
export function buildTargetedRepairScope(args: {
  files: CodeFile[]
  failedChecks: string[]
  maxTargets?: number
}): TargetedRepairScope {
  const maxTargets = args.maxTargets ?? 8
  const reasonsByPath: Record<string, string[]> = {}

  for (const check of args.failedChecks) {
    const probe = PROBES[check] ?? FALLBACK_PROBE
    for (const file of args.files) {
      if (!probe(file)) continue
      ;(reasonsByPath[file.name] ??= []).push(check)
    }
  }

  // Un fichier retenu par PLUSIEURS criteres est celui ou la reparation paie le
  // plus. A egalite, le plus gros porte le plus de markup.
  const ranked = Object.keys(reasonsByPath).sort((a, b) => {
    const byReasons = reasonsByPath[b].length - reasonsByPath[a].length
    if (byReasons !== 0) return byReasons
    const fileA = args.files.find((f) => f.name === a)!
    const fileB = args.files.find((f) => f.name === b)!
    return fileB.content.length - fileA.content.length
  })

  const keep = new Set(ranked.slice(0, maxTargets))
  for (const path of Object.keys(reasonsByPath)) {
    if (!keep.has(path)) delete reasonsByPath[path]
  }

  return {
    targets: args.files.filter((file) => keep.has(file.name)),
    protectedPaths: args.files.filter((file) => !keep.has(file.name)).map((file) => file.name),
    reasonsByPath,
  }
}

export type TargetedRepairApplication = {
  files: CodeFile[]
  /** Chemins reellement remplaces. */
  patched: string[]
  /** Chemins ajoutes (nouveaux fichiers reellement importes par un patch). */
  added: string[]
  /** Ce que la passe a propose et qui a ete refuse, avec le motif. */
  rejected: Array<{ path: string; reason: string }>
}

function normalize(path: string) {
  return path.replace(/\\/g, '/').replace(/^\.\/+/, '').trim().toLowerCase()
}

/**
 * Applique la reparation. Regles, dans cet ordre:
 *  1. un chemin HORS portee n ecrase jamais un fichier existant;
 *  2. aucun fichier n est supprime — la fusion ne fait que remplacer ou ajouter;
 *  3. un fichier NOUVEAU n est accepte que s il est reellement importe par un
 *     fichier patche (sinon c est du poids mort, pas une reparation);
 *  4. un remplacement vide est refuse: vider un fichier n est pas le reparer.
 */
export function applyTargetedRepair(args: {
  before: CodeFile[]
  scope: TargetedRepairScope
  produced: CodeFile[]
  maxAdditions?: number
}): TargetedRepairApplication {
  const maxAdditions = args.maxAdditions ?? 3
  const allowed = new Set(args.scope.targets.map((file) => normalize(file.name)))
  const existing = new Map(args.before.map((file) => [normalize(file.name), file]))
  const rejected: TargetedRepairApplication['rejected'] = []
  const patchedByPath = new Map<string, CodeFile>()
  const candidateAdditions: CodeFile[] = []

  for (const file of args.produced) {
    const key = normalize(file.name)
    if (file.content.trim().length === 0) {
      rejected.push({ path: file.name, reason: 'contenu vide' })
      continue
    }
    if (existing.has(key)) {
      if (!allowed.has(key)) {
        rejected.push({ path: file.name, reason: 'fichier protege hors portee de la passe' })
        continue
      }
      patchedByPath.set(key, { ...file, name: existing.get(key)!.name })
      continue
    }
    candidateAdditions.push(file)
  }

  const patchedText = [...patchedByPath.values()].map((file) => file.content).join('\n')
  const added: CodeFile[] = []
  for (const file of candidateAdditions) {
    if (added.length >= maxAdditions) {
      rejected.push({ path: file.name, reason: 'plafond d ajouts atteint' })
      continue
    }
    const stem = file.name.replace(/\.[^./]+$/, '').split('/').pop() ?? file.name
    if (stem.length < 2 || !patchedText.includes(stem)) {
      rejected.push({ path: file.name, reason: 'fichier neuf jamais importe par un fichier patche' })
      continue
    }
    added.push(file)
  }

  const files = args.before.map((file) => patchedByPath.get(normalize(file.name)) ?? file)
  return {
    files: [...files, ...added],
    patched: [...patchedByPath.values()].map((file) => file.name),
    added: added.map((file) => file.name),
    rejected,
  }
}
