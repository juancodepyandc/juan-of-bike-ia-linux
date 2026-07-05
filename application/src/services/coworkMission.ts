// Classification generique des missions Cowork.

import type { CoworkAction, CoworkActionResult, CoworkRuntime } from './coworkTypes.ts'

export type CoworkMissionKind =
  | 'conversation'
  | 'research'
  | 'artifact'
  | 'code'
  | 'analysis'
  | 'debug'
  | 'creative'
  | 'accompaniment'
  | 'remote'
  | 'cyber'
  | 'automation'
  | 'unknown'

export type CoworkMissionProfile = {
  kind: CoworkMissionKind
  confidence: number
  label: string
  requiredEvidence: string[]
  preferredTools: string[]
  fallbackTools: string[]
  finishRule: string
}

type MissionHistoryEntry = {
  action: CoworkAction
  result: CoworkActionResult
}

export function classifyCoworkMission(prompt: string): CoworkMissionProfile {
  const text = normalize(prompt)
  const scores: Record<CoworkMissionKind, number> = {
    conversation: 0,
    research: 0,
    artifact: 0,
    code: 0,
    analysis: 0,
    debug: 0,
    creative: 0,
    accompaniment: 0,
    remote: 0,
    cyber: 0,
    automation: 0,
    unknown: 0,
  }

  add(scores, 'research', text, /\b(recherche|chercher|trouve|trouver|internet|web|en ligne|sources?|officiel|annales?|sujets?|banque|docs?|documentation)\b/, 3)
  add(scores, 'artifact', text, /\b(cree|cr[ée]er|genere|g[ée]n[èe]re|ecris|[ée]cris|produis|pdf|xlsx|excel|pptx|docx|csv|site|app|fichier|document|rapport|fiche)\b/, 3)
  add(scores, 'code', text, /\b(code|repo|projet|typescript|javascript|python|rust|css|html|assembleur|asm|api|tests?|build|component|service|module|bug|feature|application|desktop|tauri|electron)\b/, 3)
  add(scores, 'analysis', text, /\b(analyse|audit|resume|r[ée]sume|recap|topo|compare|explique|comprends|cartographie|scan|liste|parcours|navigue)\b/, 3)
  add(scores, 'debug', text, /\b(corrige|fix|debug|erreur|bug|non fonctionnel|bloque|bloqu[ée]|crash|test|teste|tester|validation|verifie|regression|ne marche pas|autocorrige|version application|version desktop|app desktop)\b/, 4)
  add(scores, 'creative', text, /\b(creatif|cr[ée]atif|imagine|ambitieux|design|idee|id[ée]e|concept|ameliore|am[ée]liore|invente|vision)\b/, 3)
  add(scores, 'remote', text, /\b(distance|remote|ssh|serveur|vps|machine|raspberry|pi|nas|tailscale|vpn|connecte|connexion|deploy|deploie|d[ée]ploie|scp|systemd)\b/, 5)
  add(scores, 'cyber', text, /\b(cyber|attaque|defense|d[ée]fense|pentest|audit s[ée]curit[ée]|nmap|cve|vuln|osint|forensic|malware|blue.?team|red.?team)\b/, 5)
  add(scores, 'automation', text, /\b(automatise|automation|workflow|cron|rappel|monitor|surveille|tache planifi[ée]e|script)\b/, 3)
  add(scores, 'accompaniment', text, /\b(aide[ -]?moi|accompagne|accompagner|coache|coacher|conseille|conseiller|oriente|guide[ -]?moi|motive|soutien|soutiens|organise|organiser|planifie|planifier|priorise|prioriser|structure ma|prepare[ -]?moi|gere mon|gerer mon|deborde|d[ée]bord[ée]|perdu|d[ée]pass[ée]|reconversion|emploi du temps|semaine de r[ée]vision)\b/, 3)
  add(scores, 'conversation', text, /\b(bonjour|salut|merci|question|avis|tu penses|que penses)\b/, 1)

  if (/\b(test|teste|tester|validation|verifie)\b/.test(text) && /\b(application|desktop|tauri|electron)\b/.test(text)) {
    scores.debug += 8
  }

  // Les missions composites gardent l axe qui change le plus l action a faire.
  const priority: CoworkMissionKind[] = [
    'remote',
    'cyber',
    'debug',
    'artifact',
    'code',
    'research',
    'analysis',
    'automation',
    'creative',
    'accompaniment',
    'conversation',
    'unknown',
  ]
  let kind: CoworkMissionKind = 'unknown'
  let score = 0
  for (const candidate of priority) {
    if (scores[candidate] > score) {
      kind = candidate
      score = scores[candidate]
    }
  }
  if (score <= 0) kind = 'unknown'
  return buildProfile(kind, Math.min(1, Math.max(0.1, score / 8)))
}

export function buildMissionContractSection(args: {
  prompt: string
  runtime: CoworkRuntime
  history?: MissionHistoryEntry[]
}): string {
  const profile = classifyCoworkMission(args.prompt)
  const progress = summarizeMissionProgress(args.history ?? [])
  return [
    '## Contrat de mission Cowork (classification generique)',
    `Mission probable: ${profile.label} (confiance ${(profile.confidence * 100).toFixed(0)}%).`,
    `Runtime: ${args.runtime}.`,
    '',
    'Outils a considerer en premier:',
    ...profile.preferredTools.map((tool) => `- ${tool}`),
    '',
    'Fallbacks si le premier outil echoue:',
    ...profile.fallbackTools.map((tool) => `- ${tool}`),
    '',
    'Preuves attendues avant finish:',
    ...profile.requiredEvidence.map((evidence) => `- ${evidence}`),
    '',
    `Regle de fin: ${profile.finishRule}`,
    progress ? `\nProgression observee:\n${progress}` : '',
  ].filter(Boolean).join('\n')
}

export function summarizeMissionProgress(history: MissionHistoryEntry[]): string {
  if (history.length === 0) return ''
  const ok = history.filter((entry) => entry.result.ok).map((entry) => entry.action.kind)
  const ko = history.filter((entry) => !entry.result.ok).map((entry) => entry.action.kind)
  const wrote = history.some((entry) => entry.result.ok && ['write_file', 'edit_file', 'delete_file'].includes(entry.action.kind))
  const verified = history.some((entry) => entry.result.ok && ['read_file', 'list_dir', 'shell', 'fetch', 'web_search', 'browser', 'connector'].includes(entry.action.kind))
  const lines = [
    `- Actions OK: ${ok.length ? compactKinds(ok) : 'aucune'}.`,
    `- Actions KO: ${ko.length ? compactKinds(ko) : 'aucune'}.`,
  ]
  if (wrote && !verified) lines.push('- Attention: une modification existe mais aucune verification lisible/testee n est encore visible.')
  if (ko.length > 0) lines.push('- Au moins un outil a echoue: choisir une strategie alternative plutot que repeter la meme action.')
  return lines.join('\n')
}

function buildProfile(kind: CoworkMissionKind, confidence: number): CoworkMissionProfile {
  switch (kind) {
    case 'research':
      return {
        kind,
        confidence,
        label: 'recherche et synthese',
        preferredTools: ['web_search pour decouvrir les sources', 'fetch pour lire les URLs utiles', 'read_file/list_dir si des documents locaux sont cites'],
        fallbackTools: ['requete web plus ciblee', 'source officielle alternative', 'synthese partielle avec sources et limites explicites'],
        requiredEvidence: ['sources lues ou resultats web cites', 'selection critique des sources', 'reponse structuree avec pourquoi/comment'],
        finishRule: 'Ne finis pas apres une recherche brute; finis seulement apres synthese ou creation verifiee du livrable demande.',
      }
    case 'artifact':
      return {
        kind,
        confidence,
        label: 'creation de livrable',
        preferredTools: ['write_file/edit_file pour creer le livrable', 'shell si un generateur ou une dependance est utile', 'read_file/list_dir pour verifier'],
        fallbackTools: ['format equivalent si l outil exact manque', 'script local pour generer le fichier', 'nom de fichier plus simple en cas d echec d ecriture'],
        requiredEvidence: ['fichier cree au chemin attendu', 'fichier relu ou presence verifiee', 'test/build/render si le format le permet'],
        finishRule: 'Ne promets jamais un livrable; cree-le, verifie-le, puis donne le chemin et le resultat de verification.',
      }
    case 'code':
      return {
        kind,
        confidence,
        label: 'developpement logiciel',
        preferredTools: ['rg --files/git ls-files pour cartographier', 'read_file sur les pivots', 'edit_file/apply patch via actions Cowork', 'shell tests/build/lint', 'tauri info/build ou cargo check si l user demande la version application'],
        fallbackTools: ['list_dir si rg echoue', 'test cible si build complet indisponible', 'lecture manuelle des fichiers touches', 'build web seulement comme complement, jamais comme substitut a Tauri si desktop est demande'],
        requiredEvidence: ['fichiers pertinents lus', 'modifications appliquees dans le bon module', 'verification commandee ou raison precise si impossible', 'verification desktop/Tauri quand la demande cible l application'],
        finishRule: 'Finis avec les fichiers touches et les checks passes/echoues; si l user demande la version application, valide Tauri ou explique le blocage Tauri exact.',
      }
    case 'analysis':
      return {
        kind,
        confidence,
        label: 'analyse et cartographie',
        preferredTools: ['list_dir/rg/read_file pour fichiers', 'fetch/web_search pour web public', 'browser/screenshot/vision si le contenu est visuel'],
        fallbackTools: ['lecture plus large', 'synthese partielle avec inconnues marquees', 'question courte seulement si l objet a analyser est introuvable'],
        requiredEvidence: ['contenu observe', 'structure de synthese', 'distinction entre faits vus et hypotheses'],
        finishRule: 'Lecture d abord, synthese ensuite; pas de finish apres lecture seule.',
      }
    case 'debug':
      return {
        kind,
        confidence,
        label: 'debug et auto-correction',
        preferredTools: ['reproduction de l erreur', 'lecture des logs/fichiers', 'edit_file pour corriger', 'test/build pour valider', 'tauri build/cargo check quand le bug concerne l application desktop'],
        fallbackTools: ['test plus petit', 'commande alternative si outil absent', 'isoler la cause puis appliquer un correctif minimal', 'si Tauri bloque par outillage, donner le message exact et valider au moins tests + build web'],
        requiredEvidence: ['cause probable identifiee', 'correctif applique', 'verification ou echec de verification explique', 'preuve desktop quand le probleme cible l application'],
        finishRule: 'Ne finis pas au premier echec; replannifie avec une alternative jusqu a correction, preuve partielle solide, ou vrai blocage. Ne remplace pas un test application par un simple test web si Tauri est disponible.',
      }
    case 'creative':
      return {
        kind,
        confidence,
        label: 'creation creative',
        preferredTools: ['think_long pour explorer', 'write_file/edit_file si un artefact peut exister', 'verification visuelle ou lecture du resultat'],
        fallbackTools: ['prototype plus simple', 'plusieurs variantes puis choix recommande', 'reponse structuree si aucun support de creation n est disponible'],
        requiredEvidence: ['direction creative choisie', 'contraintes respectees', 'artefact ou proposition exploitable'],
        finishRule: 'La creativite doit aboutir a quelque chose d utilisable: prototype, fichier, plan detaille ou variantes argumentees.',
      }
    case 'remote':
      return {
        kind,
        confidence,
        label: 'connexion ou travail a distance',
        preferredTools: ['connector machine_ssh/machine_linux/machine_pi si configure', 'tailscale pour decouvrir les machines', 'shell ssh/scp si disponible et confirme'],
        fallbackTools: ['connector machine_ssh.keygen pour preparer la cle', 'probe avant run/upload', 'instructions de configuration uniquement si secret ou cible manque'],
        requiredEvidence: ['cible identifiee', 'connexion/probe teste', 'commande distante ou upload verifie', 'aucune action destructive sans confirmation'],
        finishRule: 'Ne demande pas une extension web pour le remote; prepare/teste la connexion, puis agit. Demande seulement host/user/secret si introuvable.',
      }
    case 'cyber':
      return {
        kind,
        confidence,
        label: 'cyber securite',
        preferredTools: ['read-only/OSINT d abord si scope non confirme', 'shell/connectors cyber quand la cible est autorisee', 'web_search/fetch pour CVE et sources'],
        fallbackTools: ['audit defensif local', 'recherche multi-sources', 'question de scope courte si une action active touche une cible reelle'],
        requiredEvidence: ['scope ou limite clairement marque', 'methodologie', 'sources ou commandes verifiees', 'remediation quand utile'],
        finishRule: 'Posture preventive: aider techniquement, confirmer seulement les actions actives risquee/destructrices/externes.',
      }
    case 'automation':
      return {
        kind,
        confidence,
        label: 'automatisation',
        preferredTools: ['shell/scripts locaux', 'connectors API', 'write_file pour workflow/config', 'test dry-run si possible'],
        fallbackTools: ['script manuel equivalent', 'connecteur a configurer si secret/API requis', 'plan de declenchement local'],
        requiredEvidence: ['declencheur defini', 'action testee ou dry-run', 'etat final observable'],
        finishRule: 'Finis apres test ou simulation; cite les secrets/connecteurs manquants seulement s ils bloquent vraiment.',
      }
    case 'accompaniment':
      return {
        kind,
        confidence,
        label: 'accompagnement et organisation',
        preferredTools: [
          'reply structure = le livrable (plan/etapes/priorites/echeances), pas une question',
          'think_long si l organisation demande un vrai raisonnement avant de structurer',
          'write_file pour persister un planning/checklist/budget reutilisable quand c est pertinent',
          'connector (rappels/agenda/notif) pour le suivi quand l user le souhaite',
        ],
        fallbackTools: [
          'une seule question ciblee APRES avoir livre une premiere version concrete',
          'hypothese raisonnable annoncee en une ligne plutot que demande de precisions',
        ],
        requiredEvidence: [
          'plan concret et structure (etapes ordonnees, priorites, decoupage temporel, durees/echeances)',
          'hypotheses de contexte enoncees au lieu de questions ouvertes',
          'prochaine action concrete ou proposition de livrable persistant',
        ],
        finishRule: 'Ne finis JAMAIS sur une simple question ni sur un conseil generique : livre un plan exploitable et adapte, puis propose le suivi.',
      }
    case 'conversation':
      return {
        kind,
        confidence,
        label: 'conversation ou conseil',
        preferredTools: ['reply direct', 'think si la reponse demande une vraie analyse'],
        fallbackTools: ['question courte si le sujet est impossible a deduire'],
        requiredEvidence: ['reponse claire et adaptee au contexte recent'],
        finishRule: 'Une reponse directe suffit si aucune action concrete n est demandee.',
      }
    case 'unknown':
    default:
      return {
        kind: 'unknown',
        confidence,
        label: 'mission a clarifier par observation',
        preferredTools: ['think court pour poser l hypothese', 'outils d observation non destructifs selon les mots du user'],
        fallbackTools: ['question courte avec option recommandee si plusieurs livrables incompatibles'],
        requiredEvidence: ['hypothese annoncee', 'premiere observation utile ou question minimale'],
        finishRule: 'Si une hypothese raisonnable existe, agis; sinon une seule question courte.',
      }
  }
}

function add(
  scores: Record<CoworkMissionKind, number>,
  kind: CoworkMissionKind,
  text: string,
  pattern: RegExp,
  weight: number,
): void {
  const matches = text.match(new RegExp(pattern.source, pattern.flags.includes('g') ? pattern.flags : pattern.flags + 'g'))
  if (!matches) return
  scores[kind] += matches.length * weight
}

function compactKinds(kinds: string[]): string {
  const counts = new Map<string, number>()
  for (const kind of kinds) counts.set(kind, (counts.get(kind) || 0) + 1)
  return [...counts.entries()].map(([kind, count]) => `${kind}x${count}`).join(', ')
}

function normalize(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}
