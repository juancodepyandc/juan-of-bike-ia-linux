// Lecture de la demande 3D côté interface : la même lecture que le pipeline
// (python-services/lecture_demande.py), pour que la référence synthétisée par
// l'interface montre le sujet AVANT son mouvement quand l'animation est activée.
//
// 15/11/2026 : « natsu Dragneel qui cours », animation activée, a été reconstruit
// en pleine course. L'interface demandait à FLUX de « ne jamais remplacer une
// pose demandée par une pose neutre » et le pipeline ignorait que l'animation
// était activée : la sculpture portait le mouvement que le squelette devait porter.
import { runPythonScript } from '../hooks/useTauri'
import { parsePythonResult } from '../utils/pythonResult.ts'
import type { ThreeDRestState } from './threeDIntent'

export interface ThreeDRequestSubject {
  nom: string | null
  nomme: boolean
  nature: string
  nature_en: string
  clause: string
  mouvement: string
  mouvement_en: string
  milieu: { matiere: 'solide' | 'liquide' | 'gaz' | null; relation: 'sur' | 'immerge' | 'a_la_surface' | 'dans_l_air' | null; justification: string }
}

export interface ThreeDRequestReading {
  source: 'llm' | 'indisponible'
  sujet: string
  mouvement: string
  exemplaires: number | null
  corps_articule: boolean | null
  conception?: boolean | null
  raison?: string
  /** contrat v2 (15/11/2026) : un élément par sujet, le style à part */
  sujets?: ThreeDRequestSubject[]
  style?: { texte: string; cible: string | null; justification: string }
}

/** Un sujet nommé sans photo jointe : son identité vient de vraies images, établies par le pipeline. */
export function namesASubject(reading: ThreeDRequestReading | null): boolean {
  return reading?.source === 'llm' && (reading.sujets || []).some((subject) => subject.nomme)
}

/**
 * Un seul sujet dont le mouvement se fait dans un liquide ou un gaz (« un homme qui nage ») : son
 * milieu doit être construit autour du corps animé, comme pour une scène à plusieurs sujets. Sans
 * cela, le nageur seul partait vers l'animation simple et nageait dans le vide.
 */
export function singleSubjectInMedium(reading: ThreeDRequestReading | null): boolean {
  const subjects = reading?.source === 'llm' ? reading.sujets || [] : []
  const matter = subjects.length === 1 ? subjects[0].milieu?.matiere : null
  return matter === 'liquide' || matter === 'gaz'
}

export async function readThreeDRequest(workspacePath: string, prompt: string): Promise<ThreeDRequestReading | null> {
  try {
    const output = await runPythonScript(`${workspacePath}/python-services/lecture_demande.py`, ['--prompt', prompt])
    const reading = parsePythonResult<ThreeDRequestReading>(String(output || ''))
    return reading && typeof reading.sujet === 'string' ? reading : null
  } catch {
    return null
  }
}

/**
 * Ce que la référence doit montrer quand l'animation est activée. Sans lecture du
 * modèle de langage, la demande reste entière ; la pose de repos s'applique alors
 * à tout sujet que l'analyse d'intention range parmi les corps qui s'animent.
 */
export function restStateFromReading(
  reading: ThreeDRequestReading | null,
  prompt: string,
  bodyByIntent: boolean,
): ThreeDRestState {
  if (reading?.source === 'llm') {
    return {
      sujet: reading.sujet.trim() || prompt,
      mouvement: (reading.mouvement || '').trim(),
      corpsArticule: reading.corps_articule === true,
    }
  }
  return { sujet: prompt, mouvement: '', corpsArticule: bodyByIntent }
}

/** Phrase de vérification de la référence : on juge le sujet au repos, pas l'action. */
export function restStateVerificationPrompt(rest: ThreeDRestState): string {
  const pose = rest.corpsArticule ? ' in a neutral rest pose, limbs held away from the body' : ''
  const motion = rest.mouvement ? ` The movement "${rest.mouvement}" is animated later and must NOT be shown.` : ''
  return `${rest.sujet} — shown at rest before any movement${pose}.${motion}`
}
