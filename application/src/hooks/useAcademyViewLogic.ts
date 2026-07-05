/**
 * useAcademyViewLogic — editorial Academy state machine, multi-mode.
 *
 * v82bq : refonte vers un vrai lab pédagogique. Foundation pour :
 *   - Upload de leçon (txt/md/pdf-extracted, images via vision passe N+1)
 *   - 4 modes d'exo : eval-type / free-form / question-dev / auto-correct
 *   - Subject picker (physique / chimie / maths / svt / lettres / histoire)
 *   - Génération adaptée à la matière (notation spéciale, manipulation,
 *     dissertation, etc.)
 *   - Soumission user + correction IA pour Q&D
 *
 * Voice + image-in-fichier (graphiques / schémas / tableaux à analyser)
 * et tableaux remplis en sortie : passes N+1 / N+2.
 *
 * v82jz : delegate MangaAcademyView retiré de AuroraV1AcademyView.
 * Ce hook backe maintenant la totalité de l'expérience aurora_v1
 * (les 10 modes ci-dessus + extraction Mermaid/JSON/markdown/etc.).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useGenerationFxEmitter } from '../components/generationFx/fxBus'
import { ollamaChatStream } from './useTauri'
import { selectAdaptiveReasoningModel, DEFAULT_MAIN_MODEL, AUXILIARY_ANALYSIS_MODEL, VISION_HIGH_QUALITY_MODEL } from '../config/models'
import { useAppStore } from '../stores/appStore'
import { useAcademyLeaderboardStore, type AcademyRun } from '../stores/academyLeaderboardStore'
import { useLearningSessionStore } from '../stores/learningSessionStore'
import { computeStreak } from '../utils/streak'
import { readTextFile } from '../utils/textFileExtract'
// iter34 : LLM-based oral classifier — replaces iter32/33 regex hardcode.
// Pas de regex sur "anglais|espagnol|ETLV", pas de "subject===langues = oral".
// gemma3:12b classifie {is_oral, language, format, duration_min}.
import { classifyOralMode, classificationToPromptBlock, type OralClassification } from '../services/oralModeClassifier'
import { buildBacInspirationBlock } from '../services/learning/bacInspirationDb'

export type AcademySubject =
  | 'auto'
  | 'physique'
  | 'chimie'
  | 'maths'
  | 'svt'
  | 'lettres'
  | 'histoire'
  | 'philo'
  | 'langues'
  | 'eco'
  | 'info'
  | 'cyber'

export type AcademyMode =
  | 'study-card'      // fiche d'étude rapide à partir d'un sujet
  | 'eval-type'       // génère 3-5 exos type bac/exam à partir d'une leçon
  | 'free-form'       // mini-projet / expérience / manipulation libre
  | 'question-dev'    // une question de développement, user développe, IA corrige
  | 'auto-correct'    // user soumet réponse, IA corrige l'analyse
  | 'mind-map'        // v82bv : carte mentale Mermaid interactive
  | 'flashcards'      // v82bv : génère un deck JSON pour révision flip-card
  | 'graph'           // v82bw : graph Mermaid (flowchart) interactif zoom/pan
  | 'table'           // v82bw : tableau markdown rempli adapté à la matière
  | 'streak'          // v82ca : exos aléatoires enchaînés sans répétition
  | 'parcours-bac'    // v82m4 : parcours révision complet 4-en-1
                      // synthèse 20/20 + fiches + exos + contrôle timé

const MODE_LABELS: Record<AcademyMode, string> = {
  'study-card': 'Fiche éclair',
  'eval-type': 'Exos type éval',
  'free-form': 'Sans template (libre)',
  'question-dev': 'Question + développement',
  'auto-correct': 'Corriger ma réponse',
  'mind-map': '🌳 Carte mentale',
  'flashcards': '🎴 Flashcards révision',
  'graph': '🕸 Graph concepts',
  'table': '📋 Tableau structuré',
  'streak': '🔥 Révision enchaînée',
  'parcours-bac': '🎯 Parcours BAC complet',
}

const SUBJECT_LABELS: Record<AcademySubject, string> = {
  auto: 'Auto-détection',
  physique: 'Physique',
  chimie: 'Chimie',
  maths: 'Mathématiques',
  svt: 'SVT',
  lettres: 'Français / Lettres',
  histoire: 'Histoire-Géo',
  philo: 'Philosophie',
  langues: 'Langues',
  eco: 'Économie',
  info: 'Informatique / NSI',
  cyber: 'Cybersécurité',
}

/**
 * v82bq : system prompts adaptés par mode + matière. Chaque matière
 * peut exiger une notation / manipulation spéciale — ces prompts
 * encodent les conventions (LaTeX pour maths, équations chimiques
 * équilibrées, schémas ASCII pour physique/SVT, dissert structurée
 * pour lettres/philo/histoire, etc.).
 */
const SUBJECT_DIRECTIVES: Record<AcademySubject, string> = {
  auto: '— détecte la matière à partir du contenu et adapte la notation.',
  physique: '— utilise des unités SI strictes, schémas ASCII (forces, vecteurs, circuits), équations en LaTeX `$...$`, valeurs numériques avec incertitudes.',
  chimie: '— équilibre TOUTES les équations, indique états (s)/(l)/(g)/(aq), notation chimique exacte (H₂O, Fe²⁺), tableau d\'avancement quand pertinent.',
  maths: '— rigueur formelle : énoncés en LaTeX `$...$`, démonstrations structurées (hypothèse → conclusion), distinction théorème/lemme/corollaire, contre-exemples si pertinent.',
  svt: '— schémas ASCII de cellules/organes, vocabulaire scientifique précis (mitose, méiose, photolyse), liens cause-conséquence explicites.',
  lettres: '— citations exactes avec référence (auteur, œuvre, page), figures de style nommées, dissertation structurée (intro 3 parties + dvpt + ccl), niveau de langue soutenu.',
  histoire: '— dates et chronologie systématiques, acteurs nommés, cartes/frises ASCII, problématisation, plan chrono OU thématique.',
  philo: '— concepts définis explicitement, références philosophiques précises (auteur, œuvre, courant), argumentation contradictoire, problématisation.',
  langues: '— grammaire ciblée, vocabulaire thématique, exemples avec traduction, exercices type (thème, version, expression, compréhension).',
  eco: '— graphiques offre/demande ASCII, modèles formalisés, données chiffrées, mécanismes de marché.',
  info: '— code dans le langage approprié, complexités O(.), schémas d\'architecture, tests unitaires si demandé.',
  cyber: '— apprentissage cyber preventif : crypto appliquee, hash/KDF, mots de passe, stegano, reseaux, websec, forensic et blue-team. Travaille sur labs locaux, CTF, artefacts fournis ou defense ; donne toujours la remediation et les criteres de verification.',
}

const MODE_DIRECTIVES: Record<AcademyMode, string> = {
  'study-card': `Produis une FICHE D'ÉTUDE COURTE en 5 sections obligatoires :

§ Définition (1-2 phrases)
§ Idée-clé (3 bullets max)
§ Question éclair : <une question concise>
§ Réponse : <réponse en 1-2 phrases>
§ Mnémonique : <une astuce mnémotechnique courte>

Maximum 200 mots. Pas de fluff markdown.`,

  'eval-type': `Génère 3 EXERCICES TYPE qui pourraient tomber à une éval/bac sur ce sujet.

Pour CHAQUE exercice :
  • Énoncé précis (avec les données nécessaires, schéma ASCII si utile)
  • Niveau de difficulté (facile / moyen / difficile)
  • Barème indicatif (ex. /5 points)
  • Solution attendue COMPLÈTE étape-par-étape
  • Pièges classiques à éviter

Cible la maîtrise complète : du calcul/raisonnement direct aux questions
de réflexion. Si la matière l'exige, inclus tableaux, équations, schémas.`,

  'free-form': `Génère UN mini-projet OUVERT (pas de template) sur ce sujet.

Le projet peut être : une expérience à faire, une manipulation, une
recherche, une production écrite originale, une analyse de cas réel,
une simulation. Pas de QCM. Pas d'exercice fermé.

Format :
  • Titre du projet
  • Objectif d'apprentissage
  • Matériel / sources / outils nécessaires
  • Étapes (3-7 étapes)
  • Critères d'évaluation (qu'est-ce qui fait un bon résultat ?)
  • Variantes possibles pour pousser plus loin`,

  'question-dev': `Génère UNE SEULE question de développement (type dissertation /
résolution longue / problème ouvert) sur ce sujet.

Format :
  • Question (claire, précise, exigeant développement)
  • Niveau attendu (Tle / Sup / etc.)
  • Critères de réussite (ce qu'une bonne réponse doit contenir)
  • Plan suggéré (3-4 axes, NON détaillés — juste des pistes)
  • Durée recommandée

L'utilisateur va ENSUITE rédiger sa réponse complète. Sois exigeant
sur la rigueur attendue.`,

  'auto-correct': `Tu es un correcteur exigeant. L'utilisateur t'a soumis sa réponse
à un exercice. Analyse-la et fournis :

§ Note globale : <X/20>
§ Points forts : (3 max)
§ Erreurs détectées : (avec citation exacte du passage erroné, type
  d'erreur, et correction)
§ Concepts manqués : (ce qu'il aurait fallu mentionner)
§ Conseil de progression : (1-2 phrases ciblées)

Sois précis, juste, mais bienveillant. Si la réponse est excellente,
dis-le ; ne cherche pas à inventer des défauts.`,

  'mind-map': `Génère une CARTE MENTALE en syntaxe Mermaid \`mindmap\` à partir de
la leçon. Le format DOIT être un bloc Mermaid valide rendu directement
par mermaid.js sans modification.

Format strict (rends UNIQUEMENT le bloc, sans texte autour) :

\`\`\`mermaid
mindmap
  root((Sujet central))
    Branche 1
      Concept 1.1
        Détail 1.1.a
        Détail 1.1.b
      Concept 1.2
    Branche 2
      Concept 2.1
\`\`\`

Règles :
  - racine au centre (utilise root((TITRE)) avec le sujet principal)
  - 3-6 branches principales (les grands axes de la leçon)
  - 2-5 sous-concepts par branche (notions clés)
  - 1-3 détails par sous-concept (formules, exemples, dates)
  - Indentation à 2 espaces stricte
  - Pas d'arrow custom, pas de class custom — juste l'arborescence
  - PAS de texte avant ou après le bloc \`\`\`mermaid

L'utilisateur va voir cette carte rendue en SVG cliquable et zoom-able.`,

  'streak': `Mode RÉVISION ENCHAÎNÉE — l'utilisateur veut une chaîne d'exos
courts pour révision rapide. Pour CET appel, génère UN SEUL exercice
sur un concept précis de la matière, court, ciblé.

Format strict :
  • Concept ciblé : <nom du concept>
  • Énoncé : <question concise, 1-2 phrases>
  • Réponse attendue : <réponse complète mais brève, 2-4 lignes max>
  • Astuce : <piste d'auto-correction si l'user se trompe>

Tu vas recevoir une LISTE de concepts DÉJÀ couverts cette session
(via "### CONCEPTS DÉJÀ VUS"). NE répète PAS un de ces concepts —
choisis un autre concept de la même matière ou progression logique.

Si la leçon est fournie, pioche dans ses concepts. Sinon, sélectionne
toi-même un concept fondamental cohérent avec la matière + niveau
implicite. Reste court : l'user va enchaîner 5-20 exos courts plutôt
qu'un seul long.`,

  'graph': `Génère un GRAPH de concepts liés en syntaxe Mermaid \`flowchart\`
ou \`graph LR\` (left-right) à partir de la leçon. Format strict (rends
UNIQUEMENT le bloc \`\`\`mermaid sans texte autour) :

\`\`\`mermaid
graph LR
  A[Concept A] -->|cause| B[Concept B]
  A --> C[Concept C]
  B --> D[Conclusion]
  C -->|exemple| D
  classDef root fill:#ff6a3d,stroke:#fff,color:#fff;
  class A root;
\`\`\`

Règles :
  - 5 à 12 nœuds reliés par des arêtes étiquetées
  - Étiquettes d'arêtes courtes (cause, conséquence, exemple, contre-
    exemple, dépend de, suit) — 1 mot ou 2 max
  - Préfère graph LR (left-right) sauf si le concept est hiérarchique
    (alors graph TB, top-bottom)
  - Mets la racine / concept central en classDef root (rouge ember)
  - Pas de subgraph imbriqué (lourd au render). Pas de click handlers
  - PAS de texte avant ou après le bloc

L'utilisateur va voir ce graph en SVG zoomable et pan-able interactif.`,

  'table': `Génère un TABLEAU MARKDOWN à partir de la leçon, adapté à la matière.

Format strict : un bloc \`\`\`markdown contenant UNIQUEMENT le tableau.

\`\`\`markdown
| Colonne 1 | Colonne 2 | Colonne 3 |
|-----------|-----------|-----------|
| valeur    | valeur    | valeur    |
| ...       | ...       | ...       |
\`\`\`

Règles selon la matière :
  - Physique/Chimie : grandeurs / unité SI / valeur / formule (LaTeX)
  - Maths : f(x) / domaine / dérivée / primitive / propriétés
  - SVT : organisme / niveau d'organisation / fonction / exemple
  - Lettres : œuvre / auteur / date / mouvement / thèmes
  - Histoire : date / événement / acteurs / cause / conséquence
  - Philo : auteur / œuvre / concept / position / opposition
  - Langues : forme / sens / exemple / traduction / niveau de langue
  - Eco : indicateur / formule / unité / interprétation
  - Info : structure / complexité / cas d'usage / contre-indication

Si la leçon contient un tableau partiel ou des données éparses, REMPLIS-le
avec les données implicites. 4-10 lignes en moyenne. Pas de texte avant
ou après le bloc.`,

  'flashcards': `Génère un DECK de flashcards de révision à partir de la leçon.

Format strict : un bloc \`\`\`json contenant UNIQUEMENT un array JSON
de cartes. Pas de texte autour.

\`\`\`json
[
  {
    "front": "Question / terme à reconnaître",
    "back": "Réponse / définition / formule complète",
    "hint": "Indice court optionnel (peut être omis)",
    "tag": "section de la leçon (optionnel)"
  }
]
\`\`\`

Règles :
  - 5 à 12 cartes selon densité de la leçon
  - "front" : court (1 phrase, ou un terme isolé)
  - "back" : précis et complet (1-3 phrases, formule entière, liste
    courte) — l'utilisateur doit POUVOIR retenir
  - "hint" : ne révèle pas la réponse, juste un déclic
  - Couvre les concepts critiques (pas du bruit) : définitions,
    formules, dates clés, théorèmes, mécanismes
  - Adapte la notation à la matière (LaTeX dans back si maths,
    équations chimiques équilibrées, schéma ASCII compact si SVT,
    citation exacte si lettres)
  - PAS de texte avant ou après le bloc \`\`\`json

L'utilisateur va voir ce deck rendu en flip-cards interactives.`,

  'parcours-bac': `Mode PARCOURS BAC COMPLET — l'utilisateur a uploadé sa
leçon (PDF analysés via vision multimodale incluant images/schémas).
Tu produis un parcours révision EXHAUSTIF en UN SEUL bloc JSON.

L'objectif : que l'utilisateur ait tout ce qu'il faut pour 20/20 au
contrôle, en passant par : synthèse essentielle → fiches stylisées →
exercices d'apprentissage → contrôle d'évaluation timé → grille de
correction stricte.

Format strict : un bloc \`\`\`json contenant UNIQUEMENT cet objet :

\`\`\`json
{
  "synthese_20_20": {
    "titre": "<titre du chapitre>",
    "ce_qu_il_faut_savoir": [
      "<connaissance critique 1, formulée comme une obligation : 'Tu DOIS savoir...'>",
      "<...>"
    ],
    "pieges_classiques": ["<piège évalués 1>", "<...>"],
    "vocabulaire_a_maitriser": [
      {"terme": "<terme>", "definition_exacte": "<def courte mais complète>"}
    ]
  },
  "fiches": [
    {
      "titre": "<titre fiche>",
      "icone": "<emoji représentatif>",
      "definition": "<def 1-2 phrases>",
      "idees_cles": ["<bullet 1>", "<bullet 2>", "<bullet 3>", "<bullet 4>", "<bullet 5>"],
      "developpement_court": "<paragraphe de 100-180 mots qui développe le concept avec exemples concrets, dates, chiffres, acteurs, mécanismes, contexte historique. PAS une liste, un texte fluide style cours BAC.>",
      "schema_ascii_ou_data": "<si la fiche bénéficie d'un schéma ASCII / tableau, sinon vide>",
      "mnemonique": "<astuce mnémotechnique courte>",
      "ressources_externes": ["<URL ou référence pour aller plus loin>"]
    }
  ],
  "exos_apprentissage": [
    {
      "type": "<flashcard | qcm | mini-exo>",
      "question": "<question concise>",
      "reponse": "<réponse complète>",
      "indice": "<hint optionnel>",
      "choix": ["<option A>", "<option B>", "<option C>", "<option D>"],
      "bonnes_reponses": [<index entiers des bonnes réponses, 0-based, ex [0] pour 1 seule, [0,2] pour multi>],
      "duree_sec": <temps recommandé en secondes pour répondre, 8-30s selon difficulté>
    }
  ],
  "cartes": [
    {
      "titre": "<titre du croquis schématique>",
      "legende": [
        {"libelle": "<sens du symbole>", "symbole": "<point | fleche | zone | hachure>", "couleur": "<#hex>"}
      ],
      "elements": [
        {"libelle": "<acteur/territoire/flux>", "type": "<point | fleche | zone | hachure>", "position": "<north | south | east | west | center | northeast | northwest | southeast | southwest>", "categorie": "<libellé court reliant à la légende>"}
      ]
    }
  ],
  "controle": {
    "duration_min": 60,
    "points_questions": 10,
    "points_developpement": 10,
    "questions": [
      {"id": 1, "q": "<question définition/connaissance>", "points": 1.5, "reponse_attendue": "<ce qui est attendu pour les pleins points>"}
    ],
    "developpement": {
      "consigne": "<sujet de développement construit, type bac>",
      "criteres_attendus": ["<critère 1>", "<critère 2>", "..."],
      "plan_indicatif": ["<axe 1>", "<axe 2>", "<axe 3>"],
      "points": 10
    }
  }
}
\`\`\`

Règles strictes :
  - "ce_qu_il_faut_savoir" : 8 à 12 connaissances cruciales pour 20/20,
    AVEC EXEMPLES CONCRETS (dates exactes, acteurs nommés, chiffres clés,
    cas d'étude). Pas de généralités vagues.
  - "fiches" : 6 à 10 fiches stylisées (selon densité de la leçon).
  - Chaque fiche : "idees_cles" 4-6 bullets précis + "developpement_court"
    paragraphe 100-180 mots qui développe le concept (exemples, dates,
    chiffres, acteurs, mécanismes, contexte). Le développement court est
    un VRAI cours, pas une liste — c'est ce qui sera lu en mode révision.
  - "exos_apprentissage" : 11 à 15 exos pour mémoriser, RÉPARTIS STRICTEMENT
    en 3 types — RÈGLE OBLIGATOIRE PEU IMPORTE LA MATIÈRE (Géo/Histoire/
    Philo/SES/Français/Maths/Physique/Langue/etc.) :
      * MINIMUM 4 "flashcard" (concept/notion ↔ définition rapide,
        définitions clés, dates, formules, vocabulaire à maîtriser)
      * MINIMUM 4 "qcm" (1 question + 4 choix + bonnes_reponses index) sur
        notions clés / dates / acteurs / mécanismes / cas. Multi-réponses
        autorisé. Pour matières texte (Géo/Histoire/Philo) c'est CRUCIAL :
        QCM sur acteurs, flux, territoires, périodisation, citations clés.
      * MINIMUM 3 "mini-exo" (rédaction courte 60-150 mots, semantic eval)
        sur problématiques larges, mise en contexte, raisonnement, analyse
        d'extrait, justification. Pour Géo : "Explique en 100 mots la
        métropolisation des espaces productifs en France". Pour Philo :
        "Distingue en 80 mots opinion et connaissance".
    JAMAIS un parcours qui ne contient qu'un seul type. Si tu hésites,
    privilégie l'équilibre 5 flashcard + 5 qcm + 4 mini-exo.
  - Pour CHAQUE exo de type "qcm" : OBLIGATOIRE 4 "choix" (un correct,
    3 distracteurs plausibles tirés du même sous-domaine), "bonnes_reponses"
    avec les index 0-based (1 ou plusieurs si question multi-réponse — la
    consigne doit alors le dire), "duree_sec" entre 8 et 30 selon difficulté
    (réponse rapide=8s, calcul=20s, analyse=30s).
  - Pour "flashcard" et "mini-exo" : "choix"/"bonnes_reponses" optionnels
    (ignorés par le rendu), "duree_sec" optionnel (défaut: pas de timer).
  - "cartes" : OBLIGATOIRE 1 à 3 croquis schématiques SI la leçon porte
    sur géographie/cartographie/territoires/flux/mondialisation/
    métropolisation/géopolitique/aires urbaines/façades maritimes/hubs.
    Sinon "cartes": [] (tableau vide). Format : titre + légende
    (3-6 entrées symbole/couleur) + elements (8-20 entrées avec position
    relative N/S/E/O/centre + 4 diagonales). Style croquis BAC, pas
    carte du monde réelle. Exemples positions : "Shanghai" → "east",
    "New York" → "northwest", "Lagos" → "southwest", "Triade" → 3 points
    distincts. Couleurs hex valides (#e63946, #1d3557, #f4a261...).
  - "controle.questions" : EXACTEMENT 10 questions courtes (def, date,
    formule, mécanisme). Les "points" totalisent 10 au TOTAL et SONT
    POSSIBLEMENT INÉGAUX (questions difficiles 2 points, faciles 0.5).
    Distribue logiquement selon la difficulté/importance.
  - "controle.developpement" : UN sujet long type "Sujet d'étude" /
    "composition" exigeant 30-45 min de rédaction. Vaut 10 points.
  - "controle.duration_min" : 60 par défaut, ajuste si la matière a une
    convention différente (ex: 4h pour un BAC philo, 2h pour HG).

Adapte selon la matière (cf SUBJECT_DIRECTIVES). Si géographie : cite
des cartes/dates précises, des exemples territoriaux concrets, le
plan-type "Étude de doc + composition". Si histoire : périodisation,
acteurs nommés, plan chronologique OU thématique.

PAS de texte avant ou après le bloc \`\`\`json.`,
}

// v82bx : image attachée à la leçon. base64 = sans le préfixe
// data:image/...;base64, parce que Ollama API attend juste le b64.
// dataUrl = pour preview thumbnail UI uniquement.
export interface AcademyImage {
  name: string
  base64: string
  dataUrl: string
  width?: number
  height?: number
}

async function fileToImage(file: File): Promise<AcademyImage> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader()
    fr.onerror = () => reject(new Error(`lecture image ${file.name} échouée`))
    fr.onload = () => {
      const dataUrl = String(fr.result || '')
      const base64 = dataUrl.replace(/^data:[^;]+;base64,/, '')
      // Mesure dimensions (best-effort, optional pour le hint UI)
      const img = new Image()
      img.onload = () => resolve({ name: file.name, base64, dataUrl, width: img.naturalWidth, height: img.naturalHeight })
      img.onerror = () => resolve({ name: file.name, base64, dataUrl })
      img.src = dataUrl
    }
    fr.readAsDataURL(file)
  })
}

// v82bv : extracteurs pour les modes mind-map et flashcards.
function extractMermaid(text: string): string | null {
  // Cherche le premier bloc ```mermaid ... ```. Tolère espaces/casse.
  const m = text.match(/```\s*mermaid\s*\n([\s\S]*?)```/i)
  if (m) return m[1].trim()
  // Fallback : si l'IA a omis les fences mais commencé par "mindmap"
  const m2 = text.match(/(mindmap[\s\S]+?)(?:```|$)/i)
  return m2 ? m2[1].trim() : null
}

export interface AcademyFlashcard {
  front: string
  back: string
  hint?: string
  tag?: string
}

// v82bw : extracteur graph Mermaid — accepte les graphs `graph` /
// `flowchart` en plus de `mindmap`. Réutilise le viewer iframe.
function extractGraph(text: string): string | null {
  const m = text.match(/```\s*mermaid\s*\n([\s\S]*?)```/i)
  if (m) return m[1].trim()
  const m2 = text.match(/((?:graph|flowchart)\s+[A-Z]{2}[\s\S]+?)(?:```|$)/i)
  return m2 ? m2[1].trim() : null
}

// v82bw : extracteur tableau markdown.
export interface AcademyTable {
  headers: string[]
  rows: string[][]
}

function extractTable(text: string): AcademyTable | null {
  // Cherche d'abord un bloc ```markdown ou ```md
  const block = text.match(/```\s*(?:markdown|md)?\s*\n([\s\S]*?)```/i)
  const raw = block ? block[1] : text
  // Parse pipe-rows
  const lines = raw.split('\n').map((l) => l.trim()).filter((l) => l.startsWith('|'))
  if (lines.length < 2) return null
  // Drop separator lines (---) — those whose cells contain only - / : /
  const isSep = (l: string) => /^\|[\s\-:|]+\|?$/.test(l)
  const dataLines = lines.filter((l) => !isSep(l))
  if (dataLines.length < 1) return null
  const splitRow = (l: string) =>
    l.replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())
  const headers = splitRow(dataLines[0])
  const rows = dataLines.slice(1).map(splitRow)
  if (headers.length === 0) return null
  return { headers, rows }
}

function extractFlashcards(text: string): AcademyFlashcard[] | null {
  // Cherche le premier bloc ```json ... ```
  const m = text.match(/```\s*json\s*\n([\s\S]*?)```/i)
  let raw = m ? m[1].trim() : null
  if (!raw) {
    // Fallback : trouve un array JSON top-level
    const start = text.indexOf('[')
    const end = text.lastIndexOf(']')
    if (start !== -1 && end > start) raw = text.slice(start, end + 1)
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    return parsed
      .filter((c) => c && typeof c === 'object' && typeof c.front === 'string' && typeof c.back === 'string')
      .map((c: AcademyFlashcard) => ({
        front: String(c.front),
        back: String(c.back),
        hint: c.hint ? String(c.hint) : undefined,
        tag: c.tag ? String(c.tag) : undefined,
      }))
  } catch {
    return null
  }
}

// v82m4 : Parcours BAC complet types + extractor.
export interface AcademyParcoursVocabulary {
  terme: string
  definition_exacte: string
}

export interface AcademyParcoursSynthese {
  titre: string
  ce_qu_il_faut_savoir: string[]
  pieges_classiques: string[]
  vocabulaire_a_maitriser: AcademyParcoursVocabulary[]
}

export interface AcademyParcoursFiche {
  titre: string
  icone?: string
  definition: string
  idees_cles: string[]
  /** iter32.I — développement court 100-180 mots avec exemples/dates/chiffres. */
  developpement_court?: string
  schema_ascii_ou_data?: string
  mnemonique?: string
  ressources_externes?: string[]
}

export interface AcademyParcoursExo {
  type: 'flashcard' | 'qcm' | 'mini-exo' | string
  question: string
  reponse: string
  indice?: string
  // iter31.G: vraies QCM kahoot-style (4 choix + 1 ou plusieurs bonnes réponses) +
  // timer par question pour bonus de vitesse.
  choix?: string[]
  bonnes_reponses?: number[]
  duree_sec?: number
  // iter33.D : si true, l'UI rendra un bouton micro au lieu d'une textarea
  // (mini-exo de production orale, pour matières langues / ETLV).
  speak?: boolean
}

export interface AcademyParcoursControleQuestion {
  id: number
  q: string
  points: number
  reponse_attendue: string
}

export interface AcademyParcoursControleDeveloppement {
  consigne: string
  criteres_attendus: string[]
  plan_indicatif: string[]
  points: number
}

export interface AcademyParcoursControle {
  duration_min: number
  points_questions: number
  points_developpement: number
  questions: AcademyParcoursControleQuestion[]
  developpement: AcademyParcoursControleDeveloppement
}

// iter35.C : croquis schématique style BAC (cartographie/géographie).
// Le LLM produit un JSON décrivant éléments + légende, le composant
// MapPreview rend ça en SVG via une grille de positions relatives.
export interface AcademyParcoursCarteLegende {
  libelle: string
  symbole: 'point' | 'fleche' | 'zone' | 'hachure' | string
  couleur: string
}

export interface AcademyParcoursCarteElement {
  libelle: string
  type: 'point' | 'fleche' | 'zone' | 'hachure' | string
  position: 'north' | 'south' | 'east' | 'west' | 'center' | 'northeast' | 'northwest' | 'southeast' | 'southwest' | string
  categorie?: string
}

export interface AcademyParcoursCarte {
  titre: string
  legende: AcademyParcoursCarteLegende[]
  elements: AcademyParcoursCarteElement[]
}

export interface AcademyParcoursPayload {
  synthese_20_20: AcademyParcoursSynthese
  fiches: AcademyParcoursFiche[]
  exos_apprentissage: AcademyParcoursExo[]
  controle: AcademyParcoursControle
  /** iter35.C : croquis schématiques BAC (vide [] si pas pertinent). */
  cartes?: AcademyParcoursCarte[]
  // iter34 : signaux mode oral, produits par le classifier LLM (cf.
  // services/oralModeClassifier.ts) puis injectés dans le system prompt
  // pour que le générateur les recopie en racine du JSON.
  // - is_oral : true → ParcoursActiveSession bascule ExamStep → ExamOralStep,
  //   les mini-exos avec speak:true rendent un bouton micro.
  // - language : nom français de la langue ("anglais", "russe", "japonais",
  //   "français"…) — utilisé pour calibrer Voxtral STT + la grille de
  //   notation oral BAC.
  // - oral_format : 'full' (présentation continue) | 'mixed' (présentation +
  //   questions de relance Q&A live) | 'questions_only' (juste interro) |
  //   'written' (jamais réellement set ici si is_oral=true).
  // - questions_relance : array de questions en `language` que le jury
  //   poserait après la présentation. Utilisé par ExamOralStep en format
  //   mixed pour le Q&A live.
  is_oral?: boolean
  language?: string
  oral_format?: 'full' | 'mixed' | 'questions_only' | 'written'
  questions_relance?: string[]
}

function extractParcoursPayload(text: string): AcademyParcoursPayload | null {
  // Try fenced ```json``` first.
  const fenced = text.match(/```\s*json\s*\n([\s\S]*?)```/i)
  let raw: string | null = fenced ? fenced[1].trim() : null
  if (!raw) {
    const first = text.indexOf('{')
    const last = text.lastIndexOf('}')
    if (first !== -1 && last > first) raw = text.slice(first, last + 1)
  }
  if (!raw) return null
  try {
    const obj = JSON.parse(raw) as Partial<AcademyParcoursPayload>
    if (!obj || typeof obj !== 'object') return null
    if (!obj.synthese_20_20 || !Array.isArray(obj.fiches) || !obj.controle) return null
    if (!Array.isArray(obj.controle.questions) || !obj.controle.developpement) return null
    // iter35.A : top-up garantissant les 3 types (4 flashcard + 4 qcm + 3 mini)
    // pour matières texte où le LLM tend à ne sortir que des flashcards.
    obj.exos_apprentissage = topUpExoTypes(
      Array.isArray(obj.exos_apprentissage) ? obj.exos_apprentissage : [],
      obj.synthese_20_20,
      obj.fiches,
    )
    if (!Array.isArray(obj.cartes)) obj.cartes = []
    return obj as AcademyParcoursPayload
  } catch {
    return null
  }
}

/**
 * iter35.A : garantit la présence des 3 types d'exos. Si le LLM en oublie un,
 * on synthétise depuis le vocabulaire et les idées-clés des fiches. Pas de
 * regen LLM (coûteux) — la dérivation des exos depuis la matière déjà
 * extraite est suffisante pour que les 3 onglets ne soient jamais vides.
 */
function topUpExoTypes(
  exos: AcademyParcoursExo[],
  synthese: AcademyParcoursSynthese | undefined,
  fiches: AcademyParcoursFiche[] | undefined,
): AcademyParcoursExo[] {
  const result = [...exos]
  const TARGETS = { flashcard: 4, qcm: 4, 'mini-exo': 3 } as const
  const counts = {
    flashcard: result.filter(e => e.type === 'flashcard').length,
    qcm: result.filter(e => e.type === 'qcm').length,
    'mini-exo': result.filter(e => e.type === 'mini-exo').length,
  }

  const vocab = synthese?.vocabulaire_a_maitriser ?? []
  const allIdeas = (fiches ?? []).flatMap(f => (f.idees_cles ?? []).map(idea => ({ idea, fiche: f })))

  // Top-up flashcards depuis le vocabulaire
  let vIdx = 0
  while (counts.flashcard < TARGETS.flashcard && vIdx < vocab.length) {
    const v = vocab[vIdx++]
    if (!v?.terme || !v?.definition_exacte) continue
    if (result.some(e => e.type === 'flashcard' && e.question.toLowerCase().includes(v.terme.toLowerCase()))) continue
    result.push({
      type: 'flashcard',
      question: `Définis : ${v.terme}`,
      reponse: v.definition_exacte,
    })
    counts.flashcard++
  }

  // Top-up QCM depuis les idées-clés (transforme en question avec distracteurs depuis autres idées)
  let iIdx = 0
  while (counts.qcm < TARGETS.qcm && iIdx < allIdeas.length) {
    const { idea, fiche } = allIdeas[iIdx++]
    if (!idea || idea.length < 20) continue
    // Distracteurs : 3 autres idées-clés différentes
    const distractors = allIdeas
      .filter(x => x.idea !== idea)
      .slice(0, 3)
      .map(x => x.idea.length > 80 ? x.idea.slice(0, 77) + '…' : x.idea)
    if (distractors.length < 3) break
    const choix = [idea, ...distractors]
    // Mélange déterministe (pas de Math.random pour stabilité regen)
    const correctIdx = (iIdx * 7) % 4
    const finalChoix = [...choix]
    if (correctIdx !== 0) {
      const tmp = finalChoix[0]
      finalChoix[0] = finalChoix[correctIdx]
      finalChoix[correctIdx] = tmp
    }
    result.push({
      type: 'qcm',
      question: `${fiche.titre} — quelle affirmation est exacte ?`,
      reponse: idea,
      choix: finalChoix,
      bonnes_reponses: [correctIdx],
      duree_sec: 20,
    })
    counts.qcm++
  }

  // Top-up mini-exo depuis les fiches (rédaction courte sur le titre)
  let fIdx = 0
  while (counts['mini-exo'] < TARGETS['mini-exo'] && fIdx < (fiches ?? []).length) {
    const f = fiches![fIdx++]
    if (!f?.titre) continue
    if (result.some(e => e.type === 'mini-exo' && e.question.includes(f.titre))) continue
    result.push({
      type: 'mini-exo',
      question: `Explique en 80-120 mots : ${f.titre}. Mobilise au moins 2 exemples concrets (dates, acteurs, chiffres, cas d'étude).`,
      reponse: f.developpement_court || f.idees_cles?.join(' ; ') || f.definition,
      indice: f.mnemonique || `Pense à : ${(f.idees_cles ?? []).slice(0, 2).join(' / ')}`,
    })
    counts['mini-exo']++
  }

  return result
}

// Correction grading payload returned after user submits.
export interface AcademyParcoursCorrection {
  questions_score: number
  questions_breakdown: { id: number; awarded: number; max: number; comment: string }[]
  developpement_score: number
  developpement_breakdown: {
    plan_score: number
    contenu_score: number
    rigueur_score: number
    expression_score: number
    total: number
    feedback: string
    erreurs: string[]
    progression: string
  }
  total: number
  total_max: number
  mention: string
}

function extractCorrectionPayload(text: string): AcademyParcoursCorrection | null {
  const fenced = text.match(/```\s*json\s*\n([\s\S]*?)```/i)
  let raw: string | null = fenced ? fenced[1].trim() : null
  if (!raw) {
    const first = text.indexOf('{')
    const last = text.lastIndexOf('}')
    if (first !== -1 && last > first) raw = text.slice(first, last + 1)
  }
  if (!raw) return null
  try {
    const obj = JSON.parse(raw)
    if (!obj || typeof obj.total !== 'number') return null
    return obj as AcademyParcoursCorrection
  } catch {
    return null
  }
}

// v82by : épreuve Academy — session timed avec score + leaderboard.
export type AcademySession = 'libre' | 'epreuve'

export interface AcademyEpreuveResult {
  score: number
  durationMs: number
  durationLimitSec: number
  timeoutHit: boolean
  flashcardsConfidence?: number
}

export interface UseAcademyViewLogic {
  // Mode + subject pickers
  mode: AcademyMode
  setMode: (m: AcademyMode) => void
  subject: AcademySubject
  setSubject: (s: AcademySubject) => void

  // Lesson upload
  lessonName: string | null
  lessonText: string
  setLessonText: (s: string) => void
  uploadLesson: (file: File) => Promise<void>
  clearLesson: () => void
  // v82fg : coller depuis presse-papiers comme leçon ad-hoc
  pasteLessonFromClipboard: () => Promise<void>
  // v82fh : snapshot du texte d'origine pour badge "edited"
  lessonOriginalText: string
  // v82fk : upload multi-fichiers concaténés en une leçon
  uploadLessonsMulti: (files: File[]) => Promise<void>
  // iter31 : retire une section "=== nom ===" précise du lessonText
  // accumulé sans vider toute la leçon (chip × dans l'UI multi-PDF).
  removeLessonSection: (sectionName: string) => void
  // iter31 : liste des fichiers présents dans la leçon accumulée,
  // dérivée du parsing des séparateurs "=== nom ===".
  lessonFileNames: string[]
  // v82es : matière aléatoire
  randomSubject: () => void
  // v82et : mode aléatoire
  randomMode: () => void
  // v82eu : matière + mode + topic aléatoires
  randomAll: () => void
  // v82ev : randomAll + auto-submit immédiat
  randomAllAndGenerate: () => Promise<void>
  // v82ck : feedback live pendant l'upload (PDF render = lent)
  lessonUploading: boolean
  lessonUploadStage: string
  cancelLessonUpload: () => void

  // v82bx : vision multimodale — l'user peut drag-drop des images
  // (graphes, schémas, tableaux scannés, photos de leçon manuscrite,
  // etc.). qwen3-vl analyse + intègre dans la génération.
  lessonImages: AcademyImage[]
  addLessonImage: (file: File) => Promise<void>
  removeLessonImage: (idx: number) => void
  clearLessonImages: () => void

  // Topic / question (legacy : fast study-card)
  topic: string
  setTopic: (s: string) => void

  // User response (for question-dev / auto-correct modes)
  userResponse: string
  setUserResponse: (s: string) => void

  // Output
  streaming: boolean
  output: string
  error: string | null
  model: string
  generate: () => Promise<void>
  abort: () => void
  reset: () => void
  hasResult: boolean

  // Reference data for the UI
  modeLabels: typeof MODE_LABELS
  subjectLabels: typeof SUBJECT_LABELS

  // v82bv : output extracted parsed data for special modes.
  mermaidCode: string | null
  flashcards: AcademyFlashcard[] | null
  // v82bw : graph mermaid + tableau markdown
  graphCode: string | null
  table: AcademyTable | null

  // v82by : session épreuve
  session: AcademySession
  epreuveDurationSec: number
  epreuveTimeLeftSec: number
  epreuveScore: number
  epreuveResult: AcademyEpreuveResult | null
  startEpreuve: (durationSec?: number) => void
  stopEpreuve: (reason?: 'success' | 'abandon' | 'timeout') => void
  topRuns: { score: number; durationMs: number; subject: string; mode: string; topic: string; timeoutHit: boolean }[]
  // v82ce : leaderboard groupé par matière (max 3 par matière)
  runsBySubject: Record<string, AcademyRun[]>
  // v82dm : série temporelle (asc) score par matière pour sparklines
  seriesBySubject: Record<string, number[]>

  // v82ca : streak révision enchaînée
  streakHistory: string[]
  streakIndex: number
  nextStreakExo: () => Promise<void>
  resetStreak: () => void

  // v82cl : export markdown de la session courante pour archive
  exportSessionMarkdown: () => void

  // v82cz : reset session courante (sans toucher leaderboard)
  resetCurrentSession: () => void

  // v82cb : flashcards confidence live persistance
  flashcardsConfidence: number
  setFlashcardsConfidence: (pct: number) => void

  // Legacy compat (used by the V1 view's existing minimal UI)
  card: string
  generateStudyCard: () => Promise<void>

  // v82m4 / v82m5 : parcours BAC complet (synthèse + fiches + exos +
  // contrôle). Le payload est extrait au vol depuis output quand mode
  // === 'parcours-bac'. iter31 ajoute la page dédiée full-screen +
  // l'auto-open + l'exit guard pendant l'examen.
  parcoursPayload: AcademyParcoursPayload | null
  parcoursAnswers: Record<number, string>
  parcoursDevAnswer: string
  parcoursCorrection: AcademyParcoursCorrection | null
  parcoursCorrecting: boolean
  parcoursControleStartedAt: number | null
  parcoursControleTimeLeftSec: number | null
  setParcoursAnswer: (id: number, val: string) => void
  setParcoursDevAnswer: (val: string) => void
  startParcoursControle: () => void
  submitParcoursControle: () => Promise<void>
  // v82m5 : permet d'injecter un parcours pré-généré côté serveur dans
  // l'output pour activer le rendu sans nouvelle inférence.
  setOutput: (s: string) => void
  // v82lg : compteur de chars en mode thinking (qwen3-vl reasoning) — utilisé
  // par AuroraV1AcademyView pour afficher "🧠 réflexion 12k tokens..." pendant
  // la phase pré-content qui peut tenir 60-120s sur parcours-bac.
  thinkingChars: number
  // v82dn / v82i6 : agrégats UI (top scores + cumul + streak jours).
  scoreCumulativeSeries: number[]
  totalAcademyPoints: number
  bestMention: { glyph: string; label: string; avg: number } | null
  academyStreak: ReturnType<typeof computeStreak>

  // iter34 : classifier oral exposé (UI peut afficher la prédiction
  // courante / la rafraîchir manuellement avant de lancer le parcours).
  oralClassification: OralClassification | null
  ensureOralClassification: () => Promise<OralClassification>
}

// v82er : readTextFile extrait dans utils/textFileExtract pour
// partage avec useCyberViewLogic (notes/writeup uploadable côté Cyber).

export function useAcademyViewLogic(): UseAcademyViewLogic {
  const hardware = useAppStore((s) => s.hardware)
  const mainModel = useAppStore((s) => s.mainModel)

  // v82cq : persist + restore la session courante depuis localStorage
  // pour que le reload ne perde pas mode/subject/topic/leçon/réponse.
  // Pas le streamOutput (qui est le résultat IA, ré-générable) ni les
  // images base64 (lourdes). Lecture sync à l'init via lazy useState.
  const PERSIST_KEY = 'aurora-academy-session-v1'
  const restored = (() => {
    if (typeof window === 'undefined') return null
    try {
      const raw = window.localStorage.getItem(PERSIST_KEY)
      if (!raw) return null
      const parsed = JSON.parse(raw) as {
        mode?: AcademyMode; subject?: AcademySubject;
        topic?: string; userResponse?: string;
        lessonName?: string | null; lessonText?: string;
      }
      return parsed
    } catch { return null }
  })()
  const [mode, setMode] = useState<AcademyMode>(restored?.mode || 'study-card')
  const [subject, setSubject] = useState<AcademySubject>(restored?.subject || 'auto')
  const [topic, setTopic] = useState(restored?.topic || '')
  const [userResponse, setUserResponse] = useState(restored?.userResponse || '')
  const [lessonName, setLessonName] = useState<string | null>(restored?.lessonName || null)
  const [lessonText, setLessonText] = useState(restored?.lessonText || '')
  // v82fh : snapshot du texte d'origine (à l'upload/paste) pour
  // détecter les modifs locales depuis. Pas persisté — au reload,
  // on considère le restored comme "original" jusqu'à la prochaine
  // upload/paste.
  const [lessonOriginalText, setLessonOriginalText] = useState(restored?.lessonText || '')
  const [lessonImages, setLessonImages] = useState<AcademyImage[]>([])
  // v82ck : upload progress feedback
  const [lessonUploading, setLessonUploading] = useState(false)
  const [lessonUploadStage, setLessonUploadStage] = useState('')
  const lessonCancelRef = useRef<{ cancelled: boolean }>({ cancelled: false })

  const cancelLessonUpload = useCallback(() => {
    lessonCancelRef.current.cancelled = true
    setLessonUploading(false)
    setLessonUploadStage('')
  }, [])

  // v82ca : streak state
  const [streakHistory, setStreakHistory] = useState<string[]>([])
  const [streakIndex, setStreakIndex] = useState(0)

  // v82cq : persist debounced sur changement
  useEffect(() => {
    if (typeof window === 'undefined') return
    const id = window.setTimeout(() => {
      try {
        window.localStorage.setItem(PERSIST_KEY, JSON.stringify({
          mode, subject, topic, userResponse, lessonName,
          // Tronque lessonText si > 100KB pour ne pas saturer
          // localStorage (5MB total typical).
          lessonText: lessonText.length > 100_000
            ? lessonText.slice(0, 100_000) + '\n\n…(tronqué pour persistance)'
            : lessonText,
        }))
      } catch { /* quota exceeded ou private mode */ }
    }, 300)
    return () => window.clearTimeout(id)
  }, [mode, subject, topic, userResponse, lessonName, lessonText, PERSIST_KEY])
  // v82cb : confidence live des flashcards (callback enfant)
  const [flashcardsConfidence, setFlashcardsConfidence] = useState(0)

  const [streaming, setStreaming] = useState(false)
  useGenerationFxEmitter('learning', streaming)
  const [output, setOutput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [thinkingChars, setThinkingChars] = useState(0)
  const abortRef = useRef<AbortController | null>(null)

  // v82by : session épreuve state
  const [session, setSession] = useState<AcademySession>('libre')
  const [epreuveDurationSec, setEpreuveDurationSec] = useState(900)
  const [epreuveStartedAt, setEpreuveStartedAt] = useState<number | null>(null)
  const [now, setNow] = useState(Date.now())
  const [epreuveResult, setEpreuveResult] = useState<AcademyEpreuveResult | null>(null)
  const addAcademyRun = useAcademyLeaderboardStore((s) => s.addRun)
  const allRuns = useAcademyLeaderboardStore((s) => s.runs)
  // v82i6 + v82i7 : streak via util mutualisé computeStreak.
  const academyStreak = useMemo(
    () => computeStreak(allRuns.map((r) => r.endedAt || r.startedAt)),
    [allRuns],
  )

  // Tick 1 Hz pendant épreuve
  useEffect(() => {
    if (session !== 'epreuve' || epreuveStartedAt === null) return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [session, epreuveStartedAt])

  const epreuveTimeLeftSec: number =
    session !== 'epreuve' || epreuveStartedAt === null
      ? 0
      : Math.max(0, epreuveDurationSec - Math.floor((now - epreuveStartedAt) / 1000))

  // Score = 0 si pas d'output, sinon base output presence + bonus
  // temps restant si épreuve ; v82cb flashcards confidence ajoute
  // jusqu'à 500 points en mode 'flashcards' selon % cartes "su".
  const epreuveScore: number = (() => {
    if (session !== 'epreuve' || epreuveStartedAt === null) return 0
    const hasOut = output.length > 200 ? 500 : output.length > 0 ? 200 : 0
    const timeBonus = hasOut > 0
      ? Math.round((epreuveTimeLeftSec / Math.max(1, epreuveDurationSec)) * 500)
      : 0
    const confidenceBonus = mode === 'flashcards'
      ? Math.round((flashcardsConfidence / 100) * 500)
      : 0
    return Math.max(0, hasOut + timeBonus + confidenceBonus)
  })()

  // v82bx : si des images sont attachées, on bascule sur un model
  // vision (qwen3-vl). Sinon on reste sur le modèle textuel adapté
  // au hardware.
  const model = useMemo(() => {
    if (lessonImages.length > 0) return VISION_HIGH_QUALITY_MODEL
    return selectAdaptiveReasoningModel(hardware ?? null, mainModel || DEFAULT_MAIN_MODEL, AUXILIARY_ANALYSIS_MODEL)
  }, [hardware, mainModel, lessonImages.length])

  const uploadLesson = useCallback(async (file: File) => {
    lessonCancelRef.current = { cancelled: false }
    setError(null)
    setLessonUploading(true)
    setLessonUploadStage(`lecture ${file.name}`)
    try {
      const text = await readTextFile(file)
      if (lessonCancelRef.current.cancelled) {
        setLessonUploading(false)
        setLessonUploadStage('')
        return
      }
      // iter31 : ACCUMULE le nouveau fichier au lieu de remplacer la
      // leçon existante. Si l'utilisateur ajoute un 2ème PDF après un
      // 1er, on concatène avec un séparateur "=== nom ===" pour garder
      // les deux sources intactes (même règle que uploadLessonsMulti).
      // Cela résout le bug "le 2ème PDF remplace le 1er au lieu de
      // s'ajouter" remonté par l'utilisateur en iter30.
      setLessonText((prev) => {
        if (!prev || prev.trim().length === 0) return text
        return `${prev}\n\n=== ${file.name} ===\n\n${text.trim()}`
      })
      setLessonName((prev) => {
        if (!prev) return file.name
        // Compose un libellé "(N fichiers · A, B, +X)" quand on accumule.
        const m = prev.match(/^\((\d+) fichiers · (.+)\)$/)
        if (m) {
          const count = Number(m[1]) + 1
          const labels = m[2]
          const extended = labels.includes('+')
            ? labels.replace(/\+\d+$/, `+${count - 3 < 0 ? 1 : count - 3}`)
            : `${labels}, ${file.name}`
          return `(${count} fichiers · ${extended})`
        }
        // De 1 fichier vers 2 fichiers : on bascule sur le format multi.
        return `(2 fichiers · ${prev}, ${file.name})`
      })
      setLessonOriginalText((prev) => {
        if (!prev || prev.trim().length === 0) return text
        return `${prev}\n\n=== ${file.name} ===\n\n${text.trim()}`
      })
      const isPdf = (file.name || '').toLowerCase().endsWith('.pdf')
        || file.type === 'application/pdf'
      const looksScanned = isPdf
        && (text.trim().length < 80 || /sans texte extractible|PDF scanné/.test(text))
      if (looksScanned) {
        try {
          setLessonUploadStage('PDF scanné détecté · préparation du rendu pages')
          const { renderPdfPagesToImages } = await import('../utils/pdfExtract')
          if (lessonCancelRef.current.cancelled) {
            setLessonUploading(false); setLessonUploadStage(''); return
          }
          // v82ck : on ne peut pas wrapper renderPdfPagesToImages avec
          // un per-page progress sans le refactor, mais on update le
          // stage avant et après — ~2-6s typique pour 6 pages.
          setLessonUploadStage('rendu des pages en image (1-2s/page)…')
          const pageFiles = await renderPdfPagesToImages(file, 6)
          if (lessonCancelRef.current.cancelled) {
            setLessonUploading(false); setLessonUploadStage(''); return
          }
          for (let i = 0; i < pageFiles.length; i++) {
            if (lessonCancelRef.current.cancelled) break
            setLessonUploadStage(`encode page ${i + 1}/${pageFiles.length}`)
            const pf = pageFiles[i]
            const fr = new FileReader()
            const dataUrl = await new Promise<string>((resolve, reject) => {
              fr.onerror = () => reject(new Error('lecture page failed'))
              fr.onload = () => resolve(String(fr.result || ''))
              fr.readAsDataURL(pf)
            })
            const base64 = dataUrl.replace(/^data:[^;]+;base64,/, '')
            const img = new Image()
            const dim = await new Promise<{ w: number; h: number }>((resolve) => {
              img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight })
              img.onerror = () => resolve({ w: 0, h: 0 })
              img.src = dataUrl
            })
            setLessonImages((prev) => [...prev, {
              name: pf.name, base64, dataUrl,
              width: dim.w || undefined, height: dim.h || undefined,
            }].slice(-6))
          }
          if (!lessonCancelRef.current.cancelled) {
            // iter31 : on ne remplace plus la leçon précédente — on
            // remplace juste la section "stub" insérée par l'append
            // ci-dessus pour ce fichier scanné, en ajoutant une note
            // claire pour le prompt utilisateur.
            const stubMarker = `\n\n=== ${file.name} ===\n\n${text.trim()}`
            const noteScanned = `\n\n=== ${file.name} (PDF scanné) ===\n\n(${pageFiles.length} page(s) rendue(s) en image et basculée(s) en vision multimodale ; le contenu textuel n'a pas pu être extrait — voir les images.)`
            setLessonText((prev) => prev.endsWith(stubMarker)
              ? prev.slice(0, prev.length - stubMarker.length) + noteScanned
              : prev + noteScanned)
            setLessonOriginalText((prev) => prev.endsWith(stubMarker)
              ? prev.slice(0, prev.length - stubMarker.length) + noteScanned
              : prev + noteScanned)
          }
        } catch (e) {
          setError(`Fallback PDF→images échoué : ${e instanceof Error ? e.message : String(e)}`)
        }
      }
    } catch (e) {
      // iter31 : ne plus wipe la leçon entière en cas d'erreur sur
      // UN fichier — ça détruirait les uploads précédents accumulés.
      // On rapporte l'erreur, on laisse l'état précédent intact.
      setError(`Lecture fichier : ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setLessonUploading(false)
      setLessonUploadStage('')
    }
  }, [])

  const clearLesson = useCallback(() => {
    setLessonName(null)
    setLessonText('')
    setLessonOriginalText('')
  }, [])

  // iter31 : retire une section "=== nom ===" précise du lessonText
  // accumulé. Permet à l'utilisateur de cliquer × sur le 1er PDF dans
  // la liste sans tout vider.
  const removeLessonSection = useCallback((sectionName: string) => {
    const pattern = new RegExp(
      `(\\n*=== ${sectionName.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\$&')}( \\(PDF scanné\\))? ===\\n[\\s\\S]*?)(?=\\n=== |$)`,
      'g',
    )
    setLessonText((prev) => prev.replace(pattern, '').replace(/^\n+/, '').trim())
    setLessonOriginalText((prev) => prev.replace(pattern, '').replace(/^\n+/, '').trim())
    setLessonName((prev) => {
      if (!prev) return null
      const m = prev.match(/^\((\d+) fichiers · (.+)\)$/)
      if (m) {
        const count = Math.max(0, Number(m[1]) - 1)
        if (count <= 0) return null
        if (count === 1) {
          // Reste un seul fichier : essaie de récupérer son nom depuis
          // le lessonText restant (premier === nom ===).
          // On n'a pas accès au texte mis à jour synchroné ici, donc on
          // garde un libellé safe.
          return null
        }
        const labels = m[2].split(',').map((s) => s.trim()).filter((s) => s !== sectionName)
        return `(${count} fichiers · ${labels.join(', ')})`
      }
      // Précédent était un seul fichier de ce nom.
      return prev === sectionName ? null : prev
    })
  }, [])

  // iter31 : extrait la liste des fichiers présents dans la leçon
  // accumulée (en parsant les séparateurs "=== nom ===") pour rendre
  // une rangée de chips × dans l'UI.
  const lessonFileNames = useMemo(() => {
    if (!lessonText) return [] as string[]
    const names: string[] = []
    const re = /=== ([^=]+?)( \(PDF scanné\))? ===/g
    let m: RegExpExecArray | null
    while ((m = re.exec(lessonText)) !== null) {
      const name = m[1].trim()
      if (name && !names.includes(name)) names.push(name)
    }
    return names
  }, [lessonText])

  // v82fk : upload de plusieurs fichiers texte concatenés en une
  // seule leçon. Chaque fichier reçoit un séparateur "=== nom ==="
  // pour que l'IA puisse identifier la source de chaque section.
  // iter31 : ACCUMULE désormais avec la leçon courante au lieu de la
  // remplacer (résout le bug "le 2ème upload remplace le 1er").
  const uploadLessonsMulti = useCallback(async (files: File[]) => {
    if (files.length === 0) return
    if (files.length === 1) {
      await uploadLesson(files[0])
      return
    }
    setError(null)
    setLessonUploading(true)
    setLessonUploadStage(`lecture de ${files.length} fichiers…`)
    try {
      const sections: string[] = []
      for (let i = 0; i < files.length; i++) {
        const f = files[i]
        setLessonUploadStage(`lecture ${f.name} (${i + 1}/${files.length})`)
        try {
          const text = await readTextFile(f)
          sections.push(`=== ${f.name} ===\n\n${text.trim()}`)
        } catch (e) {
          sections.push(`=== ${f.name} ===\n\n(échec lecture : ${e instanceof Error ? e.message : String(e)})`)
        }
      }
      const newBlock = sections.join('\n\n')
      const namesPreview = files.map((f) => f.name).slice(0, 3).join(', ')
      const namesLabel = files.length > 3 ? `${namesPreview}, +${files.length - 3}` : namesPreview
      // iter31 : si une leçon existe déjà, on la garde et on append.
      setLessonName((prev) => {
        if (!prev) return `(${files.length} fichiers · ${namesLabel})`
        // Tente de parser un libellé existant "(N fichiers · ...)".
        const m = prev.match(/^\((\d+) fichiers · (.+)\)$/)
        if (m) {
          const total = Number(m[1]) + files.length
          const existing = m[2]
          const compact = total > 3
            ? `${existing.split(',').slice(0, 3).join(',')}, +${total - 3}`
            : `${existing}, ${namesLabel}`
          return `(${total} fichiers · ${compact})`
        }
        // Précédent = 1 fichier : on bascule sur le format multi.
        return `(${files.length + 1} fichiers · ${prev}, ${namesLabel})`
      })
      setLessonText((prev) => prev && prev.trim().length > 0 ? `${prev}\n\n${newBlock}` : newBlock)
      setLessonOriginalText((prev) => prev && prev.trim().length > 0 ? `${prev}\n\n${newBlock}` : newBlock)
    } catch (e) {
      setError(`Multi-upload : ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setLessonUploading(false)
      setLessonUploadStage('')
    }
  }, [uploadLesson])

  // v82es : pioche une matière aléatoire (parmi les non-auto).
  // Évite la répétition immédiate de la matière courante.
  const randomSubject = useCallback(() => {
    const all: AcademySubject[] = [
      'physique', 'chimie', 'maths', 'svt', 'lettres',
      'histoire', 'philo', 'langues', 'eco', 'info', 'cyber',
    ]
    let next = all[Math.floor(Math.random() * all.length)]
    let tries = 0
    while (next === subject && tries < 5) {
      next = all[Math.floor(Math.random() * all.length)]
      tries++
    }
    setSubject(next)
  }, [subject])

  // v82et : pioche un mode aléatoire parmi les 10 disponibles.
  // Retry anti-répétition.
  const randomMode = useCallback(() => {
    const all: AcademyMode[] = [
      'study-card', 'eval-type', 'free-form', 'question-dev',
      'auto-correct', 'mind-map', 'flashcards', 'graph', 'table', 'streak',
    ]
    let next = all[Math.floor(Math.random() * all.length)]
    let tries = 0
    while (next === mode && tries < 5) {
      next = all[Math.floor(Math.random() * all.length)]
      tries++
    }
    setMode(next)
  }, [mode])

  // v82eu : "ALL random" pioche subject + mode + topic d'un coup.
  // Le topic est tiré d'un petit pool générique adapté à la matière.
  const randomAll = useCallback(() => {
    // 1. Subject
    const allSubjects: AcademySubject[] = [
      'physique', 'chimie', 'maths', 'svt', 'lettres',
      'histoire', 'philo', 'langues', 'eco', 'info', 'cyber',
    ]
    const nextSubject = allSubjects[Math.floor(Math.random() * allSubjects.length)]
    setSubject(nextSubject)
    // 2. Mode
    const allModes: AcademyMode[] = [
      'study-card', 'eval-type', 'free-form', 'question-dev',
      'auto-correct', 'mind-map', 'flashcards', 'graph', 'table', 'streak',
    ]
    setMode(allModes[Math.floor(Math.random() * allModes.length)])
    // 3. Topic — pool générique par matière (15+ par matière)
    const topicPool: Record<AcademySubject, string[]> = {
      auto: ['un concept au choix'],
      physique: ['cinétique', 'gravitation', 'électromagnétisme', 'optique', 'thermodynamique', 'mécanique des fluides', 'ondes mécaniques', 'effet Doppler', 'lois de Newton', 'énergie cinétique', 'travail d\'une force', 'résonance'],
      chimie: ['cinétique chimique', 'équilibre acide-base', 'pile et électrolyse', 'isomérie', 'réaction redox', 'titrages', 'enthalpie', 'liaison covalente', 'modèle de Bohr', 'cinétique de Michaelis'],
      maths: ['dérivées', 'intégrales', 'limites', 'suites arithmétiques', 'matrices', 'probabilités conditionnelles', 'polynômes', 'fonctions exponentielles', 'logarithmes', 'géométrie vectorielle', 'continuité', 'théorème de Thalès'],
      svt: ['photosynthèse', 'mitose et méiose', 'génétique mendélienne', 'évolution darwinienne', 'écosystème', 'cycle de l\'eau', 'système immunitaire', 'neurone', 'tectonique des plaques'],
      lettres: ['figures de style', 'analyse d\'un poème', 'argumentation', 'narrateur omniscient', 'champ lexical', 'tragédie classique', 'romantisme', 'naturalisme', 'théâtre de l\'absurde'],
      histoire: ['Révolution française', '1ère Guerre mondiale', 'Trente Glorieuses', 'décolonisation', 'guerre froide', 'Renaissance', 'Empire romain', 'Lumières', 'chute du mur de Berlin'],
      philo: ['conscience', 'liberté', 'devoir et morale', 'vérité', 'art', 'travail et technique', 'religion', 'État', 'justice', 'temps'],
      langues: ['present perfect anglais', 'subjonctif espagnol', 'declinaisons allemand', 'temps en italien', 'idiomes anglais', 'phrasal verbs', 'concordance des temps'],
      eco: ['offre et demande', 'inflation', 'PIB et indicateurs', 'monnaie', 'croissance', 'mondialisation', 'chômage', 'politique budgétaire', 'élasticité prix'],
      info: ['algorithmes de tri', 'récursivité', 'complexité', 'POO', 'tables de hachage', 'arbres binaires', 'graphes', 'protocole TCP/IP', 'big O notation', 'machines de Turing'],
      cyber: ['cryptographie appliquee', 'hash et salage', 'Argon2id et bcrypt', 'steganographie LSB', 'analyse de logs SSH', 'OWASP Top 10', 'XSS en lab', 'SQLi en lab', 'durcissement SSH', 'Sigma et YARA', 'forensic timeline', 'reconnaissance reseau autorisee'],
    }
    const pool = topicPool[nextSubject] || topicPool.auto
    const nextTopic = pool[Math.floor(Math.random() * pool.length)]
    setTopic(nextTopic)
  }, [])

  // v82fg : coller depuis le presse-papiers comme leçon ad-hoc
  // (utile pour copier un cours depuis le navigateur sans télécharger).
  const pasteLessonFromClipboard = useCallback(async () => {
    try {
      const text = await navigator.clipboard?.readText?.()
      if (!text || !text.trim()) {
        setError('Presse-papiers vide ou inaccessible')
        return
      }
      const stamp = new Date().toLocaleString('fr-FR', { hour: '2-digit', minute: '2-digit' })
      setLessonName(`(presse-papiers · ${stamp})`)
      setLessonText(text)
      setLessonOriginalText(text) // v82fh
      setError(null)
    } catch (e) {
      setError(`Paste échec : ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [])

  // v82bx : gestion des images
  const addLessonImage = useCallback(async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setError(`"${file.name}" n'est pas une image (type ${file.type || 'inconnu'})`)
      return
    }
    // v82ee : guard taille
    const { validateImageFile } = await import('../utils/textFileExtract')
    const sizeErr = validateImageFile(file)
    if (sizeErr) { setError(sizeErr); return }
    try {
      const img = await fileToImage(file)
      setLessonImages((prev) => [...prev, img].slice(-6)) // max 6 images pour ne pas saturer le contexte
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const removeLessonImage = useCallback((idx: number) => {
    setLessonImages((prev) => prev.filter((_, i) => i !== idx))
  }, [])

  const clearLessonImages = useCallback(() => {
    setLessonImages([])
  }, [])

  // iter34 : classifier oral via LLM (gemma3:12b) — pas de regex / hardcode.
  //
  // Remplace la détection iter32/33 (regex sur "anglais|espagnol|ETLV" +
  // "subject==='langues'"). User clarification :
  //   « le français peut être écrit OU oral, et il y a d'autres langues
  //     que je ne peux pas toutes citer (russe, japonais, latin...). Faut
  //     que l'IA comprenne du multilangue. »
  //
  // Le classifier est appelé :
  //   1. À la demande explicite (bouton "vérifier le format") — non implémenté
  //      ici, on s'en passe pour l'instant.
  //   2. AVANT chaque generate() en mode parcours-bac (cf. generate() infra).
  //   3. Le résultat est mis en cache local par signature (topic+lesson hash)
  //      pour éviter de re-classifier à chaque keystroke.
  //
  // Tant qu'on n'a pas classifié, oralClassification est null → mode écrit
  // par défaut (UI montre "Examen blanc", pas "Passation orale").
  const [oralClassification, setOralClassification] = useState<OralClassification | null>(null)
  const oralCacheRef = useRef<{ key: string; cls: OralClassification } | null>(null)

  const oralSignature = useMemo(() => {
    // Signature stable pour invalider le cache quand le user édite le sujet
    // ou la leçon. On ne hash que le début pour ne pas re-classifier sur
    // chaque char d'un long PDF.
    return `${topic.trim()}|${(lessonText || '').slice(0, 400).trim()}|${(lessonName || '').trim()}|${subject}`
  }, [topic, lessonText, lessonName, subject])

  // Si la signature change drastiquement (nouvelle leçon ou nouveau sujet),
  // on invalide la classification précédente — elle ne s'applique plus.
  useEffect(() => {
    if (oralCacheRef.current && oralCacheRef.current.key !== oralSignature) {
      // Invalide silencieusement — la prochaine generate() re-classifiera.
      setOralClassification(null)
      oralCacheRef.current = null
    }
  }, [oralSignature])

  /**
   * Run the LLM classifier (with cache by signature). Used by generate()
   * before parcours-bac to inject the verdict into the system prompt.
   * Returns the classification (cached or fresh).
   */
  const ensureOralClassification = useCallback(async (): Promise<OralClassification> => {
    if (oralCacheRef.current && oralCacheRef.current.key === oralSignature) {
      return oralCacheRef.current.cls
    }
    const cls = await classifyOralMode({
      userPrompt: `${topic}\n${userResponse || ''}`.trim(),
      uploadedTextSample: (lessonText || '').slice(0, 2000),
      subject: subject === 'auto' ? '' : SUBJECT_LABELS[subject],
    })
    oralCacheRef.current = { key: oralSignature, cls }
    setOralClassification(cls)
    return cls
  }, [oralSignature, topic, userResponse, lessonText, subject])

  const buildSystemPrompt = useCallback((overrideOral?: OralClassification | null) => {
    const subjDirective = SUBJECT_DIRECTIVES[subject]
    const modeDirective = MODE_DIRECTIVES[mode]
    // v84n — bloc d'inspiration BAC : injecte titres + concepts de vrais
    // sujets récents pour que les exos générés ressemblent à l'épreuve.
    const bacBlock = buildBacInspirationBlock(`${subject} ${topic}`, 5)
    // iter34 : le bloc oral est désormais produit par le classifier LLM
    // (cf. classificationToPromptBlock). Pas de regex hardcode. On
    // n'injecte le bloc qu'en mode parcours-bac (les autres modes ne
    // produisent pas de payload structuré controle/fiches/exos).
    const cls = overrideOral ?? oralClassification
    const oralBlock = mode === 'parcours-bac' && cls
      ? classificationToPromptBlock(cls)
      : ''
    // v83e — si l'utilisateur a choisi format=jeu pour ce parcours, on
    // injecte des consignes "jeu éducatif" dans le system prompt pour que le
    // CONTENU généré (synthèse → fiches → exos → contrôle) soit également
    // habillé en aventure narrative, pas juste l'UI. Lecture directe du
    // store (hors React render path, ok dans un callback).
    const isGameFormat = mode === 'parcours-bac'
      && useLearningSessionStore.getState().parcours?.profile?.examFormat === 'jeu'
    const gameBlock = isGameFormat
      ? `

### FORMAT JEU ÉDUCATIF (impose, pour CE parcours)
Le parcours est rendu côté UI comme une aventure à 4-5 manches (Préparation
→ Carnet de bord → Choix de l'épreuve → Défis → 🏆 Boss final). Adapte le
CONTENU dans le même esprit, SANS toucher au schéma JSON ni diluer le
programme :
- "synthese_20_20.titre" : titre narratif accrocheur (« Mission : … »,
  « Enquête sur … », « Expédition vers … ») qui pose l'enjeu.
- "synthese_20_20.ce_qu_il_faut_savoir" : ouvre avec un mini-scénario
  d'accroche (« Tu débarques sur le terrain. Voilà ce que tu sais
  déjà… »), puis les obligations connaissance.
- "fiches[].titre" : style "carnet de bord d'enquêteur" (« Indice 1 — … »,
  « Témoin clé — … »).
- "exos_apprentissage" : VARIE les types (flashcard / qcm / mini-exo)
  avec des consignes ludiques (« 🧩 Énigme », « ⚔️ Défi éclair »,
  « 🎯 Test de terrain »). 1 exo "twist" plus retors que les autres.
- "controle" : c'est le BOSS FINAL — formule "developpement.consigne" comme
  un défi de synthèse total (« Boss final : explique à ton équipe… »),
  fais que ça ait un goût d'épreuve culminante.
- Pas d'édulcoration du programme : le jeu est l'emballage, le savoir
  reste rigoureux et conforme au BAC.`
      : ''
    return `Tu es Aurora, professeur particulier exigeant et bienveillant.

Matière ${SUBJECT_LABELS[subject]} ${subjDirective}

Mode demandé : ${MODE_LABELS[mode]}.
${modeDirective}${oralBlock}${gameBlock}

${bacBlock ? `\n${bacBlock}\n` : ''}
Réponds TOUJOURS en français (sauf contenu oral en LANGUE_CIBLE quand demandé).
Pas de disclaimers. Pas de "je suis un LLM".
Si la matière nécessite des éléments visuels (schéma, tableau, graphique),
rends-les en ASCII-art ou en notation textuelle structurée — l'utilisateur
les lira directement dans la fiche, pas besoin d'images.

LECTURE MULTI-DOCUMENT :
- Si la leçon fournie contient plusieurs sections (avec "###" ou "[fichier:...]"
  ou "===" comme séparateur), CITE explicitement la source quand tu utilises
  un passage. Format : « selon le doc XYZ, … ».
- Cross-référence : si deux passages se contredisent, le dis explicitement et
  tranche en faveur du plus rigoureux.
- Ne fabrique JAMAIS un fait absent des sources. Si le sujet n'est pas couvert,
  dis-le ("non couvert par les docs, mais je peux raisonner depuis le programme").

DIRECTIVES POUR EXOS RÉALISTES :
- Tes exercices générés doivent ressembler aux sujets BAC ci-dessus dans
  leur structure : ANALYSE_DOC + CALCULS_JUSTIFIÉS + SYNTHÈSE.
- Utilise les MÊMES ordres de grandeur que les sujets réels (W, kWh, MHz,
  Mb/s, °C, Pa, etc.) — pas de nombres absurdes.
- Cite des normes/produits réels quand pertinent (Arduino, ESP32, RT2020,
  MQTT, OCPP, etc.) — pas de marque inventée.`
  }, [mode, subject, topic, oralClassification])

  const buildUserPrompt = useCallback(() => {
    const parts: string[] = []
    if (lessonText.trim()) {
      parts.push(`### LEÇON / SOURCE FOURNIE${lessonName ? ` (${lessonName})` : ''}\n\n${lessonText.trim()}`)
    }
    if (lessonImages.length > 0) {
      parts.push(`### IMAGES ATTACHÉES\n${lessonImages.length} image(s) jointe(s) — analyse leur contenu (graphes, schémas, tableaux, formules manuscrites, photos de leçon). Intègre les informations visuelles dans la génération.\n${lessonImages.map((im, i) => `- image ${i + 1} : ${im.name}${im.width ? ` (${im.width}×${im.height})` : ''}`).join('\n')}`)
    }
    if (topic.trim()) {
      parts.push(`### SUJET / FOCUS\n${topic.trim()}`)
    }
    if (mode === 'auto-correct' && userResponse.trim()) {
      parts.push(`### RÉPONSE DE L'ÉTUDIANT À CORRIGER\n${userResponse.trim()}`)
    }
    if (mode === 'question-dev' && userResponse.trim()) {
      parts.push(`### DÉVELOPPEMENT DE L'ÉTUDIANT À ÉVALUER\n${userResponse.trim()}\n\nCorrige ce développement maintenant.`)
    }
    if (mode === 'streak' && streakHistory.length > 0) {
      parts.push(`### CONCEPTS DÉJÀ VUS (NE PAS RÉPÉTER)\n${streakHistory.map((c, i) => `${i + 1}. ${c}`).join('\n')}`)
    }
    if (parts.length === 0) {
      parts.push('Aucune leçon ni sujet fourni — propose toi-même un sujet d\'exemple pour ce mode et la matière sélectionnée.')
    }
    return parts.join('\n\n')
  }, [lessonText, lessonName, lessonImages, topic, mode, userResponse, streakHistory])

  const generate = useCallback(async () => {
    if (streaming) return
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setStreaming(true)
    setOutput('')
    setError(null)
    setThinkingChars(0)
    // iter34 : pour parcours-bac, on classifie d'abord (oral / écrit / langue
    // / format / durée) via gemma3:12b. Le verdict est injecté dans le
    // system prompt avant la génération du parcours, garantissant que le
    // LLM produit un parcours adapté (oral mixed = présentation + relances,
    // oral full = présentation continue, écrit = comportement standard).
    let oralOverride: OralClassification | null = null
    if (mode === 'parcours-bac') {
      try {
        oralOverride = await ensureOralClassification()
      } catch (e) {
        // Classifier en panne : on continue en mode écrit (fallback déjà
        // géré par classifyOralMode mais on couvre une exception inattendue).
        console.warn('[academy] oral classifier failed, falling back to written', e)
      }
    }
    try {
      // v82bx : injecte les images base64 dans le user message si
      // présentes — Ollama API supporte messages[].images: string[].
      const userMsg = {
        role: 'user' as const,
        content: buildUserPrompt(),
        ...(lessonImages.length > 0
          ? { images: lessonImages.map((im) => im.base64) }
          : {}),
      }
      // v82lg: parcours-bac génère un JSON massif (synthèse + 4-8 fiches +
      // 8-15 exos + 10 contrôle questions + développement). Sur un modèle
      // vision via tunnel Cloudflare, le time-to-first-byte peut dépasser 90s.
      // On accorde 4 min pour le TTFB pour ce mode (le streaming lui n'a
      // jamais été timé une fois lancé).
      const firstByteTimeoutMs = mode === 'parcours-bac' ? 240_000 : 90_000
      // v82lg: même chose pour le contexte — un parcours-bac avec leçon
      // PDF longue + images peut nécessiter plus de 8k tokens d'input.
      const num_ctx = mode === 'parcours-bac' ? 16384 : 8192
      await ollamaChatStream(
        model,
        [
          { role: 'system', content: buildSystemPrompt(oralOverride) },
          userMsg,
        ],
        (tok) => setOutput((prev) => prev + tok),
        () => setStreaming(false),
        {
          temperature: 0.4,
          signal: ctrl.signal,
          num_ctx,
          firstByteTimeoutMs,
          // v82lg: live thinking pour parcours-bac (qwen3-vl reasoning mode
          // peut tenir 60-120s en réflexion avant de produire le JSON).
          onThinking: mode === 'parcours-bac'
            ? (t) => setThinkingChars((c) => c + t.length)
            : undefined,
        },
      )
    } catch (e) {
      if (ctrl.signal.aborted) {
        setStreaming(false)
        return
      }
      // v82lg: AbortError sur fetch = TTFB dépassé. Message actionnable.
      const raw = e instanceof Error ? e.message : String(e)
      const isAbort = raw.includes('AbortError') || raw.includes('aborted') || raw.includes('signal is aborted')
      const friendly = isAbort && mode === 'parcours-bac'
        ? `Le modèle n'a pas répondu dans les 4 minutes. Essaie : (1) une leçon plus courte, (2) un modèle textuel sans images, (3) relancer (le modèle est peut-être en cold-start). Détail : ${raw}`
        : isAbort
          ? `Le modèle n'a pas répondu dans les 90 secondes. Relance, ou simplifie la demande. Détail : ${raw}`
          : raw
      setError(friendly)
      setStreaming(false)
    }
  }, [streaming, model, mode, buildSystemPrompt, buildUserPrompt, lessonImages, ensureOralClassification])

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
    setOutput('')
    setUserResponse('')
    setTopic('')
    setError(null)
  }, [])

  const startEpreuve = useCallback((durationSec: number = 900) => {
    setSession('epreuve')
    setEpreuveDurationSec(durationSec)
    setEpreuveStartedAt(Date.now())
    setEpreuveResult(null)
  }, [])

  const stopEpreuve = useCallback((reason: 'success' | 'abandon' | 'timeout' = 'abandon') => {
    if (session !== 'epreuve') return
    const startedAt = epreuveStartedAt ?? Date.now()
    const endedAt = Date.now()
    const durationMs = endedAt - startedAt
    const result: AcademyEpreuveResult = {
      score: epreuveScore,
      durationMs,
      durationLimitSec: epreuveDurationSec,
      timeoutHit: reason === 'timeout',
      flashcardsConfidence: mode === 'flashcards' ? flashcardsConfidence : undefined,
    }
    setEpreuveResult(result)
    addAcademyRun({
      id: `aca-${startedAt.toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
      subject: SUBJECT_LABELS[subject],
      mode: MODE_LABELS[mode],
      topic: topic.trim() || lessonName || '—',
      startedAt,
      endedAt,
      durationMs,
      durationLimitSec: epreuveDurationSec,
      score: epreuveScore,
      timeoutHit: reason === 'timeout',
      flashcardsConfidence: mode === 'flashcards' ? flashcardsConfidence : undefined,
      // v82de : style apprentissage
      usedVision: lessonImages.length > 0,
      imagesCount: lessonImages.length || undefined,
    })
    setSession('libre')
    setEpreuveStartedAt(null)
  }, [session, epreuveStartedAt, epreuveScore, epreuveDurationSec, addAcademyRun, subject, mode, topic, lessonName, flashcardsConfidence, lessonImages])

  // Auto-stop sur timeout
  useEffect(() => {
    if (session === 'epreuve' && epreuveTimeLeftSec === 0 && epreuveStartedAt !== null) {
      stopEpreuve('timeout')
    }
  }, [session, epreuveTimeLeftSec, epreuveStartedAt, stopEpreuve])

  // Top 3 runs leaderboard global, dérivé via useMemo (pattern v82av)
  const topRuns = useMemo(() => {
    return allRuns
      .slice()
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map((r) => ({
        score: r.score,
        durationMs: r.durationMs,
        subject: r.subject,
        mode: r.mode,
        topic: r.topic,
        timeoutHit: r.timeoutHit,
      }))
  }, [allRuns])

  // v82ce : leaderboard groupé par matière — { Physique: [run, ...],
  // Maths: [run, ...], ... } sortés par score desc, max 3 par matière.
  const runsBySubject = useMemo(() => {
    const groups: Record<string, typeof allRuns> = {}
    for (const r of allRuns) {
      if (!groups[r.subject]) groups[r.subject] = []
      groups[r.subject].push(r)
    }
    const out: Record<string, typeof allRuns> = {}
    for (const k of Object.keys(groups)) {
      out[k] = groups[k].slice().sort((a, b) => b.score - a.score).slice(0, 3)
    }
    return out
  }, [allRuns])

  // v82dm : série temporelle des scores par matière (chronological asc)
  // pour rendre une mini-sparkline à côté de chaque colonne du
  // leaderboard "Best par matière".
  const seriesBySubject = useMemo(() => {
    const groups: Record<string, number[]> = {}
    for (const r of allRuns.slice().sort((a, b) => a.startedAt - b.startedAt)) {
      if (r.score <= 0) continue
      if (!groups[r.subject]) groups[r.subject] = []
      groups[r.subject].push(r.score)
    }
    return groups
  }, [allRuns])

  // v82dr : série CUMULATIVE des scores Academy (somme glissante sur
  // tous les runs asc). Permet une sparkline globale qui montre la
  // courbe d'accumulation de points (équivalent XP-like Academy).
  const scoreCumulativeSeries = useMemo(() => {
    const sorted = allRuns.slice().sort((a, b) => a.startedAt - b.startedAt).slice(-30)
    if (sorted.length === 0) return []
    const series: number[] = [0]
    let cum = 0
    for (const r of sorted) {
      cum += r.score || 0
      series.push(cum)
    }
    return series
  }, [allRuns])

  const totalAcademyPoints = useMemo(
    () => allRuns.reduce((a, r) => a + (r.score || 0), 0),
    [allRuns],
  )

  // v82ed : meilleure mention actuelle (selon Bac complet + score moyen
  // all-time). Mirror exact des achievements ac-mention-* + félicitations
  // + Bac débloqué seul. Affiché dans le header academy.
  const bestMention = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const r of allRuns) {
      if (r.timeoutHit) continue
      counts[r.subject] = (counts[r.subject] || 0) + 1
    }
    const checkBac = (need: string[]) =>
      need.every((s) => (counts[s] || 0) >= 2)
    const hasBac =
      checkBac(['Physique', 'Chimie', 'Mathématiques', 'SVT'])
      || checkBac(['Français / Lettres', 'Histoire-Géo', 'Philosophie', 'Langues'])
      || checkBac(['Mathématiques', 'Histoire-Géo', 'Économie', 'Langues'])
    if (!hasBac) return null
    const scored = allRuns.filter((r) => (r.score || 0) > 0)
    const avg = scored.length === 0 ? 0
      : scored.reduce((a, r) => a + (r.score || 0), 0) / scored.length
    if (avg >= 1700) return { glyph: '👑', label: 'Félicitations', avg: Math.round(avg) }
    if (avg >= 1500) return { glyph: '🥇', label: 'Mention TB', avg: Math.round(avg) }
    if (avg >= 1300) return { glyph: '🥈', label: 'Mention B', avg: Math.round(avg) }
    if (avg >= 1000) return { glyph: '🥉', label: 'Mention AB', avg: Math.round(avg) }
    return { glyph: '🎓', label: 'Bac obtenu', avg: Math.round(avg) }
  }, [allRuns])

  // Legacy compat for the existing v82bg minimal UI which calls
  // .generateStudyCard() and reads .card directly.
  const generateStudyCard = useCallback(async () => {
    setMode('study-card')
    await generate()
  }, [generate])

  // v82ev : randomAll + génère immédiatement (workflow surprise full).
  // Tick 0 pour que React commit les setState avant que generate lise
  // les valeurs courantes via closure stale.
  const randomAllAndGenerate = useCallback(async () => {
    randomAll()
    await new Promise<void>((resolve) => window.setTimeout(resolve, 0))
    await generate()
  }, [randomAll, generate])

  // v82ca : nextStreakExo capture le concept du précédent exo (heuristique :
  // ligne "Concept ciblé : X") et le push dans streakHistory, puis re-call
  // generate pour un nouvel exo qui évite ce concept.
  const nextStreakExo = useCallback(async () => {
    if (output) {
      const m = output.match(/Concept\s+ciblé\s*:\s*([^\n•]+)/i)
      if (m) {
        const concept = m[1].trim().replace(/[.…]+$/, '')
        if (concept && !streakHistory.includes(concept)) {
          setStreakHistory((prev) => [...prev.slice(-15), concept])
        }
      }
      setStreakIndex((i) => i + 1)
    }
    setMode('streak')
    setOutput('')
    await generate()
  }, [output, streakHistory, generate])

  const resetStreak = useCallback(() => {
    setStreakHistory([])
    setStreakIndex(0)
    setOutput('')
  }, [])

  // v82cl : export markdown de la session courante. Inclut métadonnées
  // (matière, mode, sujet, leçon source si présente, images count) +
  // contenu généré + score épreuve si applicable. L'user peut sauver
  // le tout pour révision offline.
  const exportSessionMarkdown = useCallback(() => {
    const now = new Date()
    const stamp = now.toISOString().slice(0, 19).replace('T', ' ')
    const lines: string[] = []
    lines.push(`# Aurora Academy — Session ${stamp}`)
    lines.push('')
    lines.push(`- **Matière** : ${SUBJECT_LABELS[subject]}`)
    lines.push(`- **Mode** : ${MODE_LABELS[mode]}`)
    if (topic.trim()) lines.push(`- **Sujet / focus** : ${topic.trim()}`)
    if (lessonName) lines.push(`- **Leçon source** : ${lessonName}`)
    if (lessonImages.length > 0) lines.push(`- **Images jointes** : ${lessonImages.length} (vision multimodale active)`)
    if (streakHistory.length > 0) lines.push(`- **Streak** : ${streakIndex + 1} exo(s) · concepts couverts : ${streakHistory.join(', ')}`)
    if (epreuveResult) {
      const { score, durationMs, timeoutHit, flashcardsConfidence } = epreuveResult
      lines.push(`- **Épreuve** : score **${score}** pts · ${Math.floor(durationMs / 60000)}m ${Math.floor((durationMs / 1000) % 60)}s${timeoutHit ? ' (timeout)' : ''}${flashcardsConfidence !== undefined ? ` · flashcards ${flashcardsConfidence}%` : ''}`)
    }
    if (userResponse.trim()) {
      lines.push('')
      lines.push('## Réponse soumise')
      lines.push('')
      lines.push(userResponse.trim())
    }
    if (output.trim()) {
      lines.push('')
      lines.push('## Contenu généré')
      lines.push('')
      lines.push(output.trim())
    }
    if (lessonText.trim()) {
      lines.push('')
      lines.push('## Source consultée')
      lines.push('')
      lines.push('```')
      lines.push(lessonText.trim().slice(0, 4000) + (lessonText.length > 4000 ? '\n…(tronqué)' : ''))
      lines.push('```')
    }
    const md = lines.join('\n')
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `aurora-academy_${SUBJECT_LABELS[subject].toLowerCase().replace(/[^a-z0-9]+/g, '-')}_${now.toISOString().slice(0, 10)}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [subject, mode, topic, lessonName, lessonImages, streakHistory, streakIndex, epreuveResult, userResponse, output, lessonText])

  // v82bv : computed only when mode matches (avoid wasted parsing).
  const mermaidCode = useMemo(
    () => (mode === 'mind-map' && output ? extractMermaid(output) : null),
    [mode, output],
  )
  const flashcards = useMemo(
    () => (mode === 'flashcards' && output ? extractFlashcards(output) : null),
    [mode, output],
  )
  // v82bw
  const graphCode = useMemo(
    () => (mode === 'graph' && output ? extractGraph(output) : null),
    [mode, output],
  )
  const table = useMemo(
    () => (mode === 'table' && output ? extractTable(output) : null),
    [mode, output],
  )

  // v82m4 : parcours-bac payload
  // iter34 : si le classifier LLM a déclaré is_oral=true, on PATCHE le
  // payload même quand le générateur oublie d'ajouter is_oral / language /
  // oral_format / questions_relance en racine. C'est un safety net — l'UI
  // a besoin de ces flags pour basculer ExamStep → ExamOralStep.
  const parcoursPayload = useMemo(() => {
    if (mode !== 'parcours-bac' || !output) return null
    const base = extractParcoursPayload(output)
    if (!base) return null
    if (oralClassification?.is_oral) {
      const patched: AcademyParcoursPayload = {
        ...base,
        is_oral: base.is_oral === undefined ? true : base.is_oral,
        language: base.language ?? oralClassification.language ?? undefined,
        oral_format: base.oral_format ?? oralClassification.format,
        // Safety net : si le LLM oublie de mettre la durée demandée par le
        // user dans payload.controle.duration_min, on la force depuis la
        // classif (l'UI ExamOralStep / Q&A en a besoin).
        controle: {
          ...base.controle,
          duration_min: base.controle?.duration_min || oralClassification.duration_min || 10,
        },
      }
      return patched
    }
    return base
  }, [mode, output, oralClassification])

  // iter31 : dès que le payload arrive, on lève le signal global pour
  // que App.tsx (cross-module) bascule sur Academy + auto-ouvre la
  // page parcours dédiée. La signature évite de re-déclencher tant
  // que le payload reste le même.
  // iter35.D : on archive aussi automatiquement dans la banque de
  // générations pour que l'utilisateur retrouve tous ses parcours
  // triés par matière (comme image / video).
  useEffect(() => {
    if (!parcoursPayload) return
    const sig = `${parcoursPayload.synthese_20_20.titre}|${parcoursPayload.controle.questions.length}|${parcoursPayload.controle.duration_min}`
    const store = useLearningSessionStore.getState()
    store.signalParcoursReady(sig)
    // ID stable basé sur signature + topic pour ne pas dupliquer en cas
    // de re-render. Utilise crypto.randomUUID si dispo, sinon fallback hash.
    const idBase = `${sig}|${topic}|${lessonName ?? ''}`
    const id = (() => {
      let h = 0
      for (let i = 0; i < idBase.length; i++) h = ((h << 5) - h + idBase.charCodeAt(i)) | 0
      return `pb_${Math.abs(h).toString(36)}_${Date.now().toString(36).slice(-4)}`
    })()
    store.addToParcoursBank({
      id,
      createdAt: Date.now(),
      subject: SUBJECT_LABELS[subject] || subject,
      topic: parcoursPayload.synthese_20_20.titre || topic || 'Parcours sans titre',
      payload: parcoursPayload,
      lessonText,
      lessonName,
    })
  }, [parcoursPayload, subject, topic, lessonName, lessonText])

  // v82m4 : parcours controle timer + answers state
  const [parcoursControleStartedAt, setParcoursControleStartedAt] = useState<number | null>(null)
  const [parcoursAnswers, setParcoursAnswers] = useState<Record<number, string>>({})
  const [parcoursDevAnswer, setParcoursDevAnswer] = useState('')
  const [parcoursCorrection, setParcoursCorrection] = useState<AcademyParcoursCorrection | null>(null)
  const [parcoursCorrecting, setParcoursCorrecting] = useState(false)
  const [parcoursControleNow, setParcoursControleNow] = useState(Date.now())

  // Tick 1 Hz pendant le contrôle timé.
  useEffect(() => {
    if (parcoursControleStartedAt === null) return
    const id = window.setInterval(() => setParcoursControleNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [parcoursControleStartedAt])

  const parcoursControleTimeLeftSec = (() => {
    if (!parcoursPayload || parcoursControleStartedAt === null) return null
    const limit = (parcoursPayload.controle.duration_min || 60) * 60
    return Math.max(0, limit - Math.floor((parcoursControleNow - parcoursControleStartedAt) / 1000))
  })()

  const startParcoursControle = useCallback(() => {
    setParcoursControleStartedAt(Date.now())
    setParcoursAnswers({})
    setParcoursDevAnswer('')
    setParcoursCorrection(null)
  }, [])

  const setParcoursAnswer = useCallback((qid: number, value: string) => {
    setParcoursAnswers((prev) => ({ ...prev, [qid]: value }))
  }, [])

  const submitParcoursControle = useCallback(async () => {
    if (!parcoursPayload || parcoursCorrecting) return
    setParcoursCorrecting(true)
    setParcoursCorrection(null)
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    // Build the strict correction prompt.
    const sysPrompt = `Tu es un correcteur exigeant et juste. L'utilisateur a passé un
contrôle de ${SUBJECT_LABELS[subject]} en ${parcoursPayload.controle.duration_min} min.
Tu corriges avec rigueur — pas de complaisance.

Barème :
  - Questions courtes : ${parcoursPayload.controle.points_questions} points au total,
    distribués selon ce que TOI tu juges juste (les points par question
    ne sont PAS forcément 1 chacun, certaines valent plus que d'autres).
  - Développement construit : ${parcoursPayload.controle.points_developpement} points,
    réparti en plan / contenu / rigueur / expression.

Tu retournes UN SEUL bloc JSON :
\`\`\`json
{
  "questions_score": <somme des points obtenus sur ${parcoursPayload.controle.points_questions}>,
  "questions_breakdown": [
    {"id": 1, "awarded": <points obtenus>, "max": <points max de cette question>,
     "comment": "<commentaire bref justifiant la note>"}
  ],
  "developpement_score": <somme sur ${parcoursPayload.controle.points_developpement}>,
  "developpement_breakdown": {
    "plan_score": <sur 2.5>,
    "contenu_score": <sur 4>,
    "rigueur_score": <sur 2>,
    "expression_score": <sur 1.5>,
    "total": <somme = developpement_score>,
    "feedback": "<3-5 phrases : ce qui marche + ce qui manque>",
    "erreurs": ["<erreur factuelle 1>", "<...>"],
    "progression": "<2 phrases : conseil concret pour la prochaine fois>"
  },
  "total": <questions_score + developpement_score>,
  "total_max": ${parcoursPayload.controle.points_questions + parcoursPayload.controle.points_developpement},
  "mention": "<TB | B | AB | passable | insuffisant — selon total>"
}
\`\`\`

Sois STRICT : si une réponse est imprécise, vague, ou manque un mot-clé
exigé par "reponse_attendue", n'attribue PAS les pleins points.
Pas de "presque correct" valant 100%.`

    const userPrompt = `### CONTRÔLE ORIGINAL
${JSON.stringify(parcoursPayload.controle, null, 2)}

### RÉPONSES DE L'ÉTUDIANT (questions courtes)
${parcoursPayload.controle.questions.map((q) =>
  `Q${q.id} (${q.points} pts) : ${q.q}\n  Réponse : ${parcoursAnswers[q.id] || '(pas de réponse)'}`
).join('\n\n')}

### DÉVELOPPEMENT DE L'ÉTUDIANT
Sujet : ${parcoursPayload.controle.developpement.consigne}

Réponse de l'étudiant :
${parcoursDevAnswer || '(pas de développement rendu)'}

Corrige maintenant en JSON strict.`

    try {
      let buffer = ''
      await ollamaChatStream(
        model,
        [
          { role: 'system', content: sysPrompt },
          { role: 'user', content: userPrompt },
        ],
        (tok) => { buffer += tok },
        () => {
          const correction = extractCorrectionPayload(buffer)
          setParcoursCorrection(correction)
          setParcoursCorrecting(false)
        },
        // v82lg: la correction stricte (10 questions + dvpt 4-axes) demande
        // beaucoup au modèle — on aligne sur le timeout parcours-bac.
        { temperature: 0.2, signal: ctrl.signal, num_ctx: 16384, firstByteTimeoutMs: 240_000 },
      )
    } catch (e) {
      if (!ctrl.signal.aborted) {
        setError(e instanceof Error ? e.message : String(e))
      }
      setParcoursCorrecting(false)
    }
  }, [parcoursPayload, parcoursAnswers, parcoursDevAnswer, parcoursCorrecting, model, subject])

  return {
    mode, setMode,
    subject, setSubject,
    lessonName, lessonText, setLessonText, uploadLesson, clearLesson,
    // v82fg : coller depuis presse-papiers
    pasteLessonFromClipboard,
    // v82fh : texte d'origine pour badge "edited"
    lessonOriginalText,
    // v82es : matière aléatoire
    randomSubject,
    // v82et : mode aléatoire
    randomMode,
    // v82eu : matière + mode + topic aléatoires
    randomAll,
    // v82ev : randomAll + auto-submit
    randomAllAndGenerate,
    // v82fk : multi-fichiers concaténés
    uploadLessonsMulti,
    // iter31 : helpers pour UI multi-PDF accumulé (chip remove)
    removeLessonSection,
    lessonFileNames,
    lessonUploading, lessonUploadStage, cancelLessonUpload,
    lessonImages, addLessonImage, removeLessonImage, clearLessonImages,
    topic, setTopic,
    userResponse, setUserResponse,
    streaming,
    output,
    setOutput, // v82m5 : exposed pour load session-preset (parcours pré-généré côté serveur)
    error,
    model,
    // v82lg : compteur de chars en mode thinking (qwen3-vl reasoning).
    // Permet à l'UI parcours-bac d'afficher "🧠 réflexion 12k tokens..."
    // pendant la phase pré-content qui peut tenir 60-120s.
    thinkingChars,
    generate,
    abort,
    reset,
    hasResult: output.length > 0,
    modeLabels: MODE_LABELS,
    subjectLabels: SUBJECT_LABELS,
    mermaidCode,
    flashcards,
    graphCode,
    table,
    // v82m4 : parcours BAC complet
    parcoursPayload,
    parcoursAnswers,
    parcoursDevAnswer,
    parcoursCorrection,
    parcoursCorrecting,
    parcoursControleStartedAt,
    parcoursControleTimeLeftSec,
    setParcoursAnswer,
    setParcoursDevAnswer,
    startParcoursControle,
    submitParcoursControle,
    // v82by : session épreuve
    session,
    epreuveDurationSec,
    epreuveTimeLeftSec,
    epreuveScore,
    epreuveResult,
    startEpreuve,
    stopEpreuve,
    topRuns,
    runsBySubject,
    seriesBySubject,
    scoreCumulativeSeries,
    totalAcademyPoints,
    bestMention,
    // v82i6 : streak jours consécutifs Academy
    academyStreak,
    // v82ca : streak révision enchaînée
    streakHistory,
    streakIndex,
    nextStreakExo,
    resetStreak,
    exportSessionMarkdown,
    flashcardsConfidence,
    setFlashcardsConfidence,
    // v82cz : reset session courante (topic / userResponse / output /
    // leçon source + images) sans toucher aux runs leaderboardStore.
    resetCurrentSession: () => {
      abortRef.current?.abort()
      setStreaming(false)
      setOutput('')
      setTopic('')
      setUserResponse('')
      setLessonText('')
      setLessonName(null)
      setLessonImages([])
      setError(null)
      setStreakHistory([])
      setStreakIndex(0)
    },
    card: output, // alias retro-compat
    generateStudyCard,
    // iter34 : classifier oral
    oralClassification,
    ensureOralClassification,
  }
}
