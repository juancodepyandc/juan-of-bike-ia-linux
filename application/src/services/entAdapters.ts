/**
 * entAdapters — registry of French ENT (Espace Numérique de Travail)
 * platforms with detection + section mapping. Browser-side helpers ;
 * the actual scraping happens via Aurora-Connect Chrome extension on
 * auth-protected pages.
 *
 * Each adapter exposes :
 *   - id, label, hostMatch (regex sur hostname pour detection)
 *   - sections : Record<section, pathTemplate>  → "agenda" → "/agenda.aspx"
 *   - selectors : DOM selectors pour extraction par section
 *   - extractHints : indications LLM sur la structure attendue
 *
 * v82je Pass 2/9 — Phase 2 P2.1 site detection.
 */

export type EntSection =
  | 'home'
  | 'agenda'             // emploi du temps + cahier de textes
  | 'devoirs'            // travail à faire
  | 'notes'              // notes et bulletin
  | 'fichiers'           // pièces jointes / cours déposés
  | 'messagerie'         // messages internes
  | 'absences'

export type EntAdapter = {
  id: string
  label: string
  /** Regex (case-insensitive) qui matche le hostname du site une fois loggué. */
  hostMatch: RegExp
  /** Racine du domaine (sans subpath) — pour reconstruire les URLs. */
  baseUrl?: (hostname: string) => string
  /** Markers DOM qui prouvent que l'user est authentifié (pas sur page login). */
  authMarkers: string[]
  /** Mapping section → URL relative (peut contenir {root} pour subpath dynamique). */
  sections: Partial<Record<EntSection, string>>
  /** Selectors CSS par section pour extraction. Liste, pas obligation : on
   *  prend le premier qui matche (chaque ENT a parfois plusieurs templates). */
  selectors: Partial<Record<EntSection, {
    listItem?: string[]      // un .item par devoir/note/etc.
    title?: string[]
    date?: string[]
    description?: string[]
    attachment?: string[]    // <a href> pour téléchargement
    grade?: string[]         // pour notes : "12.5 / 20"
    average?: string[]       // moyenne classe
    subject?: string[]       // matière (Maths, Physique...)
  }>>
  /** Hint LLM pour le parser quand DOM extraction échoue (fallback texte). */
  extractHint?: string
  /** v82je Phase 2 : URL pattern de l'iCal export quand connu (Pronote a une
   *  page Sécurité qui génère un lien). null si non standardisé. */
  icalExportPath?: string | null
}

export const ENT_ADAPTERS: EntAdapter[] = [
  {
    id: 'pronote',
    label: 'Pronote',
    // Pronote = chaque établissement a son propre sous-domaine
    // sur index-education.com, OU un host institutionnel (ex.
    // 0780015h.index-education.com, mon-lycee.index-education.com).
    hostMatch: /(?:^|\.)index-education\.com$|pronote/i,
    baseUrl: (h) => `https://${h}`,
    authMarkers: [
      // Accueil Pronote affiche typiquement le menu latéral
      '.GTLContent', '.cellule_NavCentrale', '#Pied_avis_eleve',
      '.menu-utilisateur', '[data-testid="user-menu"]',
    ],
    sections: {
      home: '/pronote/eleve.html',
      agenda: '/pronote/eleve.html?fd=1#page=Agenda',
      devoirs: '/pronote/eleve.html?fd=1#page=CahierDeTexte_TravailAFaire',
      notes: '/pronote/eleve.html?fd=1#page=Notes',
      fichiers: '/pronote/eleve.html?fd=1#page=CahierDeTexte_ContenuCours',
      messagerie: '/pronote/eleve.html?fd=1#page=Discussions',
      absences: '/pronote/eleve.html?fd=1#page=AbsencesEleve',
    },
    selectors: {
      devoirs: {
        listItem: ['.travailAFaire .ligne', '.cdt-devoir', '.cellule_TravailAFaire'],
        title: ['.titre', '.intitule-devoir', 'h3'],
        date: ['.date', '.echeance', '[data-testid="due-date"]'],
        description: ['.description', '.contenu-devoir', '.detail'],
        attachment: ['a[href*="telechargement"]', 'a.piece-jointe', 'a[download]'],
        subject: ['.matiere', '.discipline'],
      },
      notes: {
        listItem: ['.ligne-note', '.cellule_Note', 'tr.note-row'],
        grade: ['.note', '.valeur-note'],
        average: ['.moyenne-classe', '.average-class'],
        subject: ['.matiere', '.discipline'],
        date: ['.date', '.date-evaluation'],
        title: ['.titre-evaluation', '.intitule'],
      },
      fichiers: {
        listItem: ['.cdt-cours', '.cellule_Cours'],
        title: ['.titre-seance', '.intitule-cours'],
        attachment: ['a[href*="telechargement"]', 'a.piece-jointe'],
        date: ['.date'],
        subject: ['.matiere'],
      },
      agenda: {
        listItem: ['.cours', '.creneau', '.cell-agenda'],
        title: ['.intitule', '.matiere'],
        date: ['.heure', '.date-cours'],
      },
    },
    extractHint: 'Pronote utilise des cellule_X classes. Le contenu peut être chargé en async via JS — attendre quelques secondes après navigation. Le sélecteur principal de listings est typiquement .ligne ou .cellule_X.',
    icalExportPath: '/pronote/eleve.html?fd=1#page=GestionParametresPersonnels_Securite_Authentification',
  },
  {
    id: 'ecoledirecte',
    label: 'ÉcoleDirecte',
    hostMatch: /(?:^|\.)ecoledirecte\.com$/i,
    baseUrl: (h) => `https://${h}`,
    authMarkers: [
      '.menu-principal', '.user-info', '#sidebar-eleve',
      '[ui-view="content"]', '.layout-eleve',
    ],
    sections: {
      home: '/eleve/accueil',
      agenda: '/eleve/edt',
      devoirs: '/eleve/cahierdetextes',
      notes: '/eleve/notes',
      fichiers: '/eleve/cahierdetextes',  // attaché aux cours
      messagerie: '/eleve/messagerie',
      absences: '/eleve/viedeleve/absences',
    },
    selectors: {
      devoirs: {
        listItem: ['.devoir-item', '.row-devoir', 'div[ng-repeat*="devoir"]'],
        title: ['.matiere', '.titre-devoir'],
        date: ['.date-devoir', '.due-date'],
        description: ['.description', '.contenu-devoir'],
        attachment: ['a.piece-jointe', 'a[ng-click*="telecharger"]'],
        subject: ['.matiere'],
      },
      notes: {
        listItem: ['.row-note', 'div[ng-repeat*="note"]'],
        grade: ['.note-value', '.valeur'],
        average: ['.moyenne-classe', '.avg-classe'],
        subject: ['.matiere'],
        title: ['.libelle', '.titre-eval'],
        date: ['.date-eval'],
      },
    },
    extractHint: 'ÉcoleDirecte est en AngularJS — beaucoup de ng-repeat et data binding. Les sélecteurs ng-* sont stables.',
    icalExportPath: '/eleve/edt',  // bouton iCal en haut à droite
  },
  {
    id: 'skolengo',
    label: 'Skolengo',
    hostMatch: /(?:^|\.)skolengo\.com$|kosmoscloud\.com|monbureaunumerique/i,
    baseUrl: (h) => `https://${h}`,
    authMarkers: [
      '.skolengo-app', '.user-profile', '[data-testid="main-nav"]',
      '.SkoApp-header',
    ],
    sections: {
      home: '/dashboard',
      agenda: '/agenda',
      devoirs: '/agenda/devoirs',
      notes: '/notes',
      fichiers: '/documents',
      messagerie: '/messagerie',
      absences: '/scolarite/absences',
    },
    selectors: {
      devoirs: {
        listItem: ['.devoir-card', '[data-testid="homework-item"]'],
        title: ['.devoir-title', 'h3'],
        date: ['.devoir-date', 'time'],
        description: ['.devoir-content', '.devoir-description'],
        attachment: ['.devoir-attachment a', 'a[download]'],
        subject: ['.devoir-subject', '.matiere'],
      },
      notes: {
        listItem: ['.grade-row', '[data-testid="grade-item"]'],
        grade: ['.grade-value'],
        average: ['.class-average'],
        subject: ['.subject-name'],
      },
    },
    extractHint: 'Skolengo utilise React + des data-testid stables. Préférer ces attributs aux classes CSS.',
    icalExportPath: '/agenda/export',
  },
  {
    id: 'ent-idf',
    label: 'ENT Île-de-France',
    hostMatch: /(?:^|\.)iledefrance\.fr$|monlycee\.net|moncollege/i,
    baseUrl: (h) => `https://${h}`,
    authMarkers: ['.portal-header', '#userspace', '.entcore-user'],
    sections: {
      home: '/',
      agenda: '/timeline/timeline',
      devoirs: '/cahierdetextes',
      messagerie: '/conversation',
      fichiers: '/workspace/workspace',
    },
    selectors: {
      devoirs: {
        listItem: ['.homework-item', '.cdt-entry'],
        title: ['.title'],
        date: ['.date'],
        description: ['.description'],
      },
    },
    extractHint: 'ENT IDF utilise OneNet/EntCore — markup générique mais pages auth via SAML.',
    icalExportPath: null,
  },
]

/** Détecte quel adapter correspond à un hostname donné. */
export function detectAdapter(hostname: string): EntAdapter | null {
  for (const a of ENT_ADAPTERS) {
    if (a.hostMatch.test(hostname)) return a
  }
  return null
}

/** Détecte si la page courante est un ENT auth-loggué.
 *  Retourne l'adapter + score 0-1 selon nombre de markers DOM trouvés.
 *  Doit être appelé depuis un context où window/document existent
 *  (Aurora-Connect extension content script). */
export function detectAuthState(hostname: string, doc: Document): {
  adapter: EntAdapter | null
  authenticated: boolean
  score: number
} {
  const a = detectAdapter(hostname)
  if (!a) return { adapter: null, authenticated: false, score: 0 }
  const markersFound = a.authMarkers.filter((sel) => {
    try { return doc.querySelector(sel) !== null } catch { return false }
  }).length
  const score = a.authMarkers.length > 0 ? markersFound / a.authMarkers.length : 0
  return { adapter: a, authenticated: score >= 0.3, score }
}

/** Construit l'URL complète d'une section pour un adapter + hostname donnés. */
export function buildSectionUrl(adapter: EntAdapter, hostname: string, section: EntSection): string | null {
  const path = adapter.sections[section]
  if (!path) return null
  const base = adapter.baseUrl ? adapter.baseUrl(hostname) : `https://${hostname}`
  return base + (path.startsWith('/') ? path : `/${path}`)
}

/** Pour le LLM : retourne un brief structuré sur ce que l'adapter sait faire. */
export function adapterBrief(adapter: EntAdapter): string {
  const sections = (Object.keys(adapter.sections) as EntSection[]).filter(
    (s) => adapter.sections[s] !== undefined,
  )
  return [
    `Adapter ${adapter.id} (${adapter.label})`,
    `Sections accessibles : ${sections.join(', ')}`,
    `Markers auth : ${adapter.authMarkers.length} CSS selectors`,
    adapter.icalExportPath ? `iCal export path : ${adapter.icalExportPath}` : 'iCal export : non standardisé',
    adapter.extractHint ? `Hint extraction : ${adapter.extractHint}` : '',
  ].filter(Boolean).join('\n')
}
