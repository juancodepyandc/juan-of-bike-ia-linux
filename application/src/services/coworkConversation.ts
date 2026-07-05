import {
  resolveClarificationContinuation,
  type CoworkConversationTurn,
} from './coworkClarification.ts'

export type CoworkConversationMode =
  | 'ordre_direct'
  | 'suite_de_mission'
  | 'reponse_clarification'
  | 'accompagnement'
  | 'discussion'
  | 'inconnu'

export type CoworkConversationFrame = {
  mode: CoworkConversationMode
  currentPrompt: string
  effectivePrompt: string
  shouldExecute: boolean
  reason: string
  previousMission?: string
}

export function resolveCoworkConversationFrame(
  userPrompt: string,
  conversationHistory: CoworkConversationTurn[] | undefined,
): CoworkConversationFrame {
  const currentPrompt = cleanText(userPrompt)
  const current = normalize(currentPrompt)

  if (!currentPrompt) {
    return {
      mode: 'inconnu',
      currentPrompt,
      effectivePrompt: currentPrompt,
      shouldExecute: false,
      reason: 'message vide',
    }
  }

  const clarification = resolveClarificationContinuation(currentPrompt, conversationHistory)
  if (clarification) {
    return {
      mode: 'reponse_clarification',
      currentPrompt,
      previousMission: clarification.originalRequest,
      effectivePrompt: [
        clarification.originalRequest,
        `Precision utilisateur: ${clarification.clarificationAnswer}`,
        `Question clarifiee: ${clarification.clarificationQuestion}`,
      ].join('\n'),
      shouldExecute: true,
      reason: 'le message repond a une question de clarification et reprend la mission precedente',
    }
  }

  if (isExecutableRequest(current)) {
    return {
      mode: 'ordre_direct',
      currentPrompt,
      effectivePrompt: currentPrompt,
      shouldExecute: true,
      reason: 'le dernier message contient un ordre actionnable',
    }
  }

  const previousMission = findPreviousActionableUserPrompt(currentPrompt, conversationHistory)
  if (previousMission && isMissionContinuation(current)) {
    return {
      mode: 'suite_de_mission',
      currentPrompt,
      previousMission,
      effectivePrompt: [
        previousMission,
        `Suite demandee maintenant: ${currentPrompt}`,
      ].join('\n'),
      shouldExecute: true,
      reason: 'le dernier message est une suite courte rattachee a la mission precedente',
    }
  }

  // Demande d'accompagnement / coaching / organisation / conseil / soutien.
  // Ce n'est PAS de la simple conversation : un vrai copilote doit LIVRER un
  // plan concret et structure, pas juste poser des questions ou renvoyer du
  // generique. On la marque executable pour declencher la posture "agir".
  if (isAccompanimentRequest(current)) {
    return {
      mode: 'accompagnement',
      currentPrompt,
      effectivePrompt: currentPrompt,
      shouldExecute: true,
      reason: 'demande d accompagnement/coaching/organisation : livrer un plan concret, pas une simple question',
    }
  }

  if (isPureConversation(current)) {
    return {
      mode: 'discussion',
      currentPrompt,
      effectivePrompt: currentPrompt,
      shouldExecute: false,
      reason: 'message conversationnel sans ordre local detectable',
    }
  }

  return {
    mode: 'inconnu',
    currentPrompt,
    effectivePrompt: currentPrompt,
    shouldExecute: false,
    reason: 'intention faible ou incomplete',
  }
}

export function buildCoworkConversationSection(frame: CoworkConversationFrame): string {
  const lines = [
    '## Cadre conversationnel Cowork',
    `Mode: ${frame.mode}.`,
    `Execution attendue: ${frame.shouldExecute ? 'oui' : 'non'}.`,
    `Raison: ${frame.reason}.`,
  ]
  if (frame.previousMission) {
    lines.push(`Mission precedente rattachee: ${compact(frame.previousMission, 420)}`)
  }
  if (frame.effectivePrompt !== frame.currentPrompt) {
    lines.push('Objectif effectif fusionne:')
    lines.push(compact(frame.effectivePrompt, 700))
  }
  if (frame.mode === 'accompagnement') {
    lines.push([
      'Regle ACCOMPAGNEMENT (coaching/organisation/planification/conseil/soutien) :',
      "- NE COMMENCE PAS par une question. Livre d abord une premiere version CONCRETE et structuree.",
      "- Produis un vrai plan exploitable : etapes ordonnees, priorites, decoupage par jour/creneau quand c est temporel, durees ou echeances, et 'pourquoi' bref. Pas de generalites ni de disclaimer du type 'ceci est un exemple, adapte-le'.",
      "- Fais des hypotheses raisonnables sur le contexte manquant et ENONCE-les en une ligne, au lieu de demander.",
      "- Quand un livrable reutilisable a du sens (planning, checklist, budget, fiche), PROPOSE de le creer comme fichier (write_file .md/.csv) et propose les prochaines actions concretes (rappels, suivi).",
      "- Tu peux poser AU PLUS une seule question ciblee, et seulement APRES avoir livre la premiere version, et seulement si une hypothese erronee couterait cher.",
    ].join('\n'))
  } else {
    lines.push(frame.shouldExecute
      ? 'Regle: ne transforme pas cet ordre en simple discussion. Observe, agis, verifie, puis reponds.'
      : 'Regle: une reponse directe est acceptable si aucun outil n est necessaire.')
  }
  return lines.join('\n')
}

function findPreviousActionableUserPrompt(
  currentPrompt: string,
  conversationHistory: CoworkConversationTurn[] | undefined,
): string | undefined {
  const current = normalize(currentPrompt)
  const turns = conversationHistory ?? []
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    const turn = turns[i]
    if (turn.role !== 'user') continue
    const content = cleanText(turn.content)
    if (!content || normalize(content) === current) continue
    if (isExecutableRequest(normalize(content))) return content
  }
  return undefined
}

function isExecutableRequest(current: string): boolean {
  const hasActionVerb = /\b(analyse|analyser|audit|audite|inspecte|scan|scanne|parcours|parcourir|navigue|naviguer|lis|lire|cherche|recherche|trouve|trouver|fetch|ouvre|ouvrir|clique|remplis|connecte|telecharge|cree|creer|genere|generer|produis|produire|ecris|ecrire|redige|rediger|modifie|modifier|corrige|corriger|fix|debug|teste|tester|verifie|verifier|build|compile|installe|installer|lance|lancer|execute|executer|automatise|automatiser|deploie|deployer|reprends|reprendre|continue|continuer|ameliore|ameliorer|applique|appliquer|utilise|utiliser|retire|retirer|ajoute|ajouter|remplace|remplacer|fais|faire|fait|transforme|transformer|convertis|convertir|modelise|modeliser|modele|modeler|construis|construire|developpe|developper|prototype|prototyper)\b/.test(current)
  const hasConcreteTarget = /\b(fichier|fichiers|dossier|workspace|repo|projet|code|application|app|tauri|desktop|module|cowork|bureau|documents|telechargements|pdf|docx|xlsx|excel|site|page|onglet|photo|image|visuel|illustration|portrait|decor|fond|celebrite|video|voix|3d|modele|model|mesh|glb|asset|assets|personnage|jeu|game|gameplay|reference|style|test|build|erreur|bug|machine|serveur|api|git|npm|cargo|nmap|outil|commande)\b/.test(current)
  const directSystemAsk = /\b(npm run|package\.json|terminal|powershell|commande|localhost|exe|executable)\b/.test(current)
  return (hasActionVerb && hasConcreteTarget) || directSystemAsk
}

function isMissionContinuation(current: string): boolean {
  if (current.length > 180 && !/^(donc|maintenant|reprends|continue|ok|oui|go|vas y|vas-y)\b/.test(current)) {
    return false
  }
  return /^(oui|ok|go|vas y|vas-y|d accord|d'accord|continue|continuer|reprends|reprendre|maintenant|donc|fais le|fait le|lance|applique|corrige|ameliore|teste|verifie|pareil|la meme|encore|au max|vraiment)\b/.test(current)
    || /\b(continue|reprends|fais le|fait le|applique|corrige|ameliore|teste|verifie|au max|vraiment|comme ca|pareil|la meme|celui ci|celle ci|celui-ci|celle-ci|ce modele|cette image|via ce|a partir de|en faire|transforme ca|transforme le|modelise le|modelise celui)\b/.test(current)
}

// Demande d'accompagnement : coaching, organisation, planification, conseil,
// soutien, "aide-moi a...". Ces demandes n'ont souvent ni verbe d'action
// systeme ni cible concrete (donc isExecutableRequest=false), mais un vrai
// coopérateur doit y repondre par un LIVRABLE structure, pas une question.
// `current` est deja normalise (minuscules, sans accents, espaces compactes).
function isAccompanimentRequest(current: string): boolean {
  const supportPhrase = /\b(aide[ -]?moi|aidez[ -]?moi|accompagne[ -]?moi|conseille[ -]?moi|guide[ -]?moi|oriente[ -]?moi|motive[ -]?moi|coache[ -]?moi|aide a (reflechir|decider|choisir|m organiser|s organiser|y voir clair)|y voir clair|par ou commencer|je suis (deborde|debordee|perdu|perdue|depasse|depassee|bloque|bloquee|noye|noyee)|je me sens (perdu|perdue|deborde|debordee|depasse|depassee)|je n arrive pas a|j ai besoin d aide|besoin d etre accompagne|besoin d etre accompagnee)\b/
  if (supportPhrase.test(current)) return true
  const coachVerb = /\b(accompagne|accompagner|conseille|conseiller|coache|coacher|organise|organiser|planifie|planifier|priorise|prioriser|structure|structurer|motive|motiver|prepare|preparer|gere|gerer|optimise|optimiser)\b/
  const lifeTarget = /\b(semaine|semaines|journee|journees|jour|jours|mois|emploi du temps|planning|agenda|temps|budget|argent|finances|objectif|objectifs|projet|projets|revision|revisions|reviser|bac|examen|examens|entretien|entretiens|sport|sante|habitude|habitudes|routine|routines|carriere|reconversion|etudes|vie|taches|priorites|stress|organisation|deadline|deadlines|echeance|echeances|semaine de revision)\b/
  return coachVerb.test(current) && lifeTarget.test(current)
}

function isPureConversation(current: string): boolean {
  return /^(bonjour|salut|hello|merci|thanks|ok merci|ca va|tu vas bien|bonne nuit)\b/.test(current)
    && !isExecutableRequest(current)
    && !isAccompanimentRequest(current)
}

function cleanText(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function normalize(value: string): string {
  return cleanText(value)
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
}

function compact(value: string, max: number): string {
  const clean = cleanText(value)
  return clean.length > max ? `${clean.slice(0, max - 1)}...` : clean
}
