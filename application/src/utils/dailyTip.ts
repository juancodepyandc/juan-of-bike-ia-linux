/**
 * v82ft : pool de "tips of the day" rotatifs par module.
 * Seed = today.toDateString().charCodeAt sum → tip stable pour un
 * jour donné, change automatiquement chaque jour. Mutualise la
 * logique inline introduite dans v82fs (V1 Chat).
 */

export type TipModule =
  | 'chat'
  | 'image'
  | 'code'
  | 'drawing'
  | 'video'
  | '3d'
  | 'academy'
  | 'cyber'
  | 'cowork'
  | 'global'

const TIPS: Record<TipModule, string[]> = {
  chat: [
    '💡 Tape "/" pour voir les commandes : /fiche, /explain, /code, /summary…',
    '💡 Drag-drop un fichier (txt/pdf/docx/image) directement dans la fenêtre',
    '💡 Cmd+K ouvre la palette de modules — tape un nom pour switcher',
    '💡 Cmd+1 à Cmd+8 sautent directement aux modules (1=chat, 2=image, …)',
    '💡 Cmd+, ouvre Settings · ⇧? affiche tous les raccourcis',
    '💡 Bouton ⚡ surprise lance une conversation au hasard',
    '💡 Fin/Début (clavier End/Home) pour scroll bottom/top du thread',
    '💡 Settings → URL d\'accès courante : QR code pour scan mobile direct',
    '💡 Joins une image, Aurora la décrit (vision multimodale Qwen3-VL)',
  ],
  image: [
    '💡 Drag-drop une image sur la vue → référence IP-Adapter automatique',
    '💡 ⚡ surprise · go pioche un style FLUX + prompt aléatoire et génère',
    '💡 15 styles dispo : photoréaliste, anime, manga, sumi-e, cyberpunk…',
    '💡 Précise dimensions et seed pour reproductibilité',
    '💡 Cmd+↵ envoie le prompt, comme dans le chat',
  ],
  code: [
    '💡 Drag-drop un fichier code (.ts, .py, .rs, …) → contenu fence-wrappé dans le prompt',
    '💡 ⚡ surprise · go pioche une idée de code et génère',
    '💡 22 langages supportés dans le sandbox runner',
    '💡 Cmd+↵ envoie · sandbox auto-correction loop sur erreurs',
    '💡 "Ouvrir l\'orchestrateur" lance le full pipeline avec planification',
  ],
  drawing: [
    '💡 Drag-drop une image → base de tracé directe dans le canvas sumi-e',
    '💡 ⚡ surprise · go pioche encre + prompt et génère le rendu FLUX',
    '💡 Tablette + ML : Aurora suit la pression du stylet',
    '💡 Le sketch est analysé en vision avant le rendu (qwen3-vl)',
  ],
  video: [
    '💡 ⚡ surprise · go pioche un prompt cinéma et génère un storyboard',
    '💡 Drag-drop un brief texte → injecté dans le prompt',
    '💡 6 styles : cinematic, documentary, anime, noir, pastel, gritty',
    '💡 "Ouvrir la salle" lance le full Wan2.2 cinema pipeline',
  ],
  '3d': [
    '💡 Drop une image → bias le router vers Hunyuan3D',
    '💡 Drop un .glb/.obj/.ply → signal de variation post-process',
    '💡 ⚡ surprise · go pioche un objet 3D au hasard',
    '💡 4 pipelines : Hunyuan3D, DreamGaussian, Blender procédural, Meshroom photo',
  ],
  academy: [
    '💡 ⚡ surprise · go pioche matière + mode + topic et génère',
    '💡 10 modes : fiche, exos type, libre, question, correction, mind-map, flashcards, graph, table, streak',
    '💡 Drop une leçon multi-fichiers → concaténée en sections',
    '💡 PDF scanné détecté → bascule auto vers vision multimodale',
    '💡 Définis un objectif hebdo dans le panel achievements',
  ],
  cyber: [
    '💡 9 disciplines : crypto, forensics, hash, network, password, stego, threat intel, web sec, CTF',
    '💡 ⚡ kata · go pioche un kata et forge le lab immédiatement',
    '💡 Drop un writeup → contexte gradeAnswer pour feedback aligné',
    '💡 Mode épreuve avec timer pour challenge time-based',
  ],
  cowork: [
    '💡 Drop un brief client (txt/pdf/docx) → mission Cowork pré-remplie',
    '💡 Cowork orchestre un agent multi-step sur le navigateur via Aurora-Connect',
    '💡 Console technique : full streaming events log + plan + audit drawer',
    '💡 Toute action externe est gardée par cowork-safety (validateAction)',
  ],
  global: [
    '💡 ⇧? ouvre l\'aide clavier complète',
    '💡 Cmd+K palette · Cmd+, settings',
    '💡 Drag-drop fonctionne sur 9/9 modules V1',
  ],
}

// v82fx : key pour désactiver les tips si l'user les trouve distrayants.
export const TIPS_ENABLED_KEY = 'aurora-tips-enabled-v1'

/** Lit la préférence — true si pas explicitement désactivé. */
export function areTipsEnabled(): boolean {
  if (typeof window === 'undefined') return true
  try {
    const raw = window.localStorage.getItem(TIPS_ENABLED_KEY)
    return raw === null ? true : raw === '1' || raw === 'true'
  } catch { return true }
}

export function getDailyTip(module: TipModule): string {
  if (!areTipsEnabled()) return ''
  const pool = TIPS[module] || TIPS.global
  if (pool.length === 0) return ''
  const today = new Date().toDateString()
  const seed = today.split('').reduce((s, c) => s + c.charCodeAt(0), 0)
  return pool[seed % pool.length]
}
