// Pure utility functions for the Learning module (no React)
import { buildAcademicLevelInstructions, type LearningSource, type AcademicIntent } from '../../services/learningResearch.ts'
import { SUBJECT_HINTS } from '../../stores/flashcardsStore.ts'
import type { SubjectKind } from '../../stores/flashcardsStore.ts'
import type { Tab, QuizQuestion, FlashcardDraft, LearningPathNode, TocEntry } from './types.ts'

export function buildLearningSystemPrompt(
  mode: 'quiz' | 'course' | 'path' | 'quiz_verify' | 'flashcards',
  options?: { subjectKind?: SubjectKind; academicIntent?: AcademicIntent; forceOpenQuestions?: boolean; forceMcqQuestions?: boolean },
) {
  const academicIntent = options?.academicIntent
  const levelLine = academicIntent
    ? `NIVEAU ACADEMIQUE DETECTE: ${academicIntent.level.toUpperCase()} · profondeur ${academicIntent.depth}${academicIntent.isExamFocus ? ' · intention EXAMEN' : ''}.`
    : ''
  const levelInstructions = academicIntent ? buildAcademicLevelInstructions(academicIntent) : ''

  if (mode === 'quiz') {
    const isExam = Boolean(academicIntent?.isExamFocus)
    const subjectKind = options?.subjectKind
    // Matieres dont l epreuve est une REDACTION (dissertation, analyse de
    // document, commentaire compose, ecriture d invention, explication de
    // texte, argumentation). Sur ces matieres, un pur QCM ne prepare PAS
    // reellement a l epreuve — on exige un mix QCM + questions ouvertes
    // avec plan de reponse attendu et bareme detaille.
    const isEssaySubject = subjectKind === 'philo'
      || subjectKind === 'litterature'
      || subjectKind === 'histoire'
      || subjectKind === 'geo'
      || subjectKind === 'langue'
    const mustEmitOpenQuestions =
      options?.forceOpenQuestions === true
      || (!options?.forceMcqQuestions && isEssaySubject && isExam)
    return [
      'Tu es le module Academie de Aurora IA, un expert pedagogique intelligent et cultive.',
      levelLine,
      levelInstructions ? `CALIBRAGE: ${levelInstructions}` : '',
      '',
      'METHODE — ANALYSE AVANT GENERATION:',
      '1. D abord, COMPRENDS le sujet demande en profondeur.',
      '2. Identifie les concepts cles DU PROGRAMME OFFICIEL au niveau demande, les faits verifiables, les pieges courants.',
      '3. Pour chaque question, REFAIS le calcul ou le raisonnement independamment avant de fixer la reponse.',
      '4. PRIORISE les sources factuelles fournies (Sxx) quand elles couvrent un point. Si un bloc "ATTENDUS DE L EPREUVE" (Exx) est fourni, CALQUE la formulation des questions dessus.',
      '5. SURTOUT: decide le BON FORMAT. Un pur QCM n est pas adapte si la vraie epreuve est une redaction (philo, dissertation, commentaire, analyse de document, langues niveau examen). Pour ces cas, emets des questions OUVERTES avec plan attendu et bareme.',
      '',
      'INTELLIGENCE NATIVE:',
      'Tu possedes des connaissances solides dans tous les domaines (sciences, histoire, geographie, maths, informatique, culture, etc.).',
      'Utilise-les avec assurance. Si un fait est dans tes connaissances generales, ne le devines pas — affirme-le avec certitude.',
      'Pour les questions techniques, mathematiques ou scientifiques: CALCULE ou RAISONNE avant de fixer la reponse.',
      '',
      isExam ? 'MODE EXAMEN:' : 'MODE STANDARD:',
      isExam
        ? [
            '- Les questions ressemblent aux items reellement tombes en examen au niveau cible (tournure, vocabulaire, longueur).',
            '- Couvre les attendus officiels: au moins 3 des 5 questions portent sur des points deja tombes en epreuve.',
            '- Une question doit faire travailler une METHODE (ex: resoudre, demontrer, analyser un document, interpreter un resultat).',
            '- Ajoute dans explanation: "Methode type: ..." avec la strategie de reponse attendue en examen.',
          ].join('\n')
        : '- Questions pedagogiques neutres, axees comprehension.',
      '',
      mustEmitOpenQuestions
        ? [
            'FORMAT MIXTE OBLIGATOIRE (matiere de redaction + mode examen):',
            '- 2 questions QCM (kind="mcq") pour verifier des connaissances factuelles.',
            '- 3 questions OUVERTES (kind="open") = sujet de dissertation, analyse de document, commentaire compose ou explication de texte niveau ' + (academicIntent ? academicIntent.level : 'demande') + '.',
            '- Pour chaque question ouverte:',
            '    * question = enonce complet style epreuve (1-3 phrases).',
            '    * options = [] (tableau vide).',
            '    * correctIndex = 0 (ignore cote UI mais garde pour validation JSON).',
            '    * answerOutline = tableau de 3 a 6 items: plan de reponse attendu (introduction / parties / conclusion) OU axes d analyse incontournables.',
            '    * gradingCriteria = tableau {label, points} qui detaille le bareme: ex [{"label":"Problematisation claire","points":4},{"label":"Mobilisation de 2 references pertinentes","points":6},{"label":"Argumentation progressive","points":6},{"label":"Qualite de redaction","points":4}].',
            '    * totalPoints = somme exacte des points de gradingCriteria (souvent 20).',
            '    * explanation = corrige complet redige comme un eleve excellent aurait repondu (6-12 phrases), au niveau demande.',
          ].join('\n')
        : 'FORMAT: QCM (kind="mcq") standard. Les questions ouvertes ne sont pas necessaires pour ce sujet.',
      '',
      'CONTRAINTES DE SORTIE:',
      '- Repondre UNIQUEMENT en JSON valide (tableau de 5 objets)',
      academicIntent
        ? `- Exactement 5 questions, TOUTES au niveau ${academicIntent.level.toUpperCase()}. Progression autorisee = du + abordable au + exigeant A L INTERIEUR de ce niveau uniquement. INTERDICTION formelle de descendre d un niveau pour donner une "question facile" : si l utilisateur demande terminale ou prepa, aucune question ne doit etre de niveau college ou seconde, meme pour "demarrer en douceur".`
        : '- Exactement 5 questions, difficulte progressive du plus abordable au plus exigeant (sans tomber sous le niveau attendu par le sujet).',
      '- Pour une question QCM: kind="mcq", 4 options, UNE SEULE correcte (correctIndex = index 0-3), explication qui PROUVE la reponse.',
      '- Pour une question ouverte: kind="open", options=[], correctIndex=0, answerOutline (3-6 items), gradingCriteria (tableau {label, points}), totalPoints, explanation = corrige complet.',
      '- Champs obligatoires: question, explanation, kind. Les autres champs dependent du kind.',
      '- Champs optionnels fortement recommandes: concept (1-3 mots, thematique), sourceHint (renvoi vers Sxx ou Exx si applicable)',
      '- Les distracteurs (mauvaises reponses) des QCM doivent etre plausibles (erreurs frequentes des candidats) mais clairement faux si on reflechit',
      '- JAMAIS de questions ambigues ou a interpretations multiples',
      '- INTERDICTION d inventer des faits: si tu n es pas sur, ne pose pas la question',
      '- INTERDICTION de promettre "une version plus simple" ou d adoucir le niveau : l utilisateur a deja choisi. Tiens le niveau.',
    ].filter(Boolean).join('\n')
  }

  if (mode === 'flashcards') {
    const kind = options?.subjectKind ?? 'general'
    const matterFocus: Record<SubjectKind, string[]> = {
      philo: [
        'Toujours inclure une citation (quote + quoteAuthor).',
        'Faire apparaitre la these, l antithese et la synthese dans keyPoints.',
        'Cite les auteurs cles et leurs concepts.',
      ],
      histoire: [
        'Remplir dates[] avec les dates pivots (annee + evenement court).',
        'keyPoints: causes, acteurs, consequences.',
        'Exemple: un episode marquant bien date.',
      ],
      geo: [
        'keyPoints structures: espaces / acteurs / enjeux / dynamiques.',
        'example: une region / etude de cas concrete avec chiffres.',
        'Mentionner les echelles (locale, nationale, mondiale) quand pertinent.',
      ],
      maths: [
        'Toujours remplir formula (notation simple, pas LaTeX complexe). Ex: "a^2 + b^2 = c^2".',
        'keyPoints: definition, proprietes, conditions d application.',
        'example: un calcul resolu pas a pas.',
        'mnemonic: moyen mnemotechnique si classique (SOHCAHTOA, etc.).',
      ],
      science: [
        'Definir puis expliquer le mecanisme.',
        'keyPoints: etapes du processus, lois associees, unites.',
        'example: experience ou observation concrete.',
        'formula quand la relation physique/chimique le demande.',
      ],
      langue: [
        'keyPoints: regle + exception + traduction courante.',
        'example: une phrase type.',
        'mnemonic: astuce de memorisation (rime, pattern).',
      ],
      litterature: [
        'Toujours inclure une citation representative (quote + quoteAuthor).',
        'keyPoints: contexte, courant, themes, style.',
      ],
      informatique: [
        'formula = syntaxe/snippet court quand pertinent.',
        'keyPoints: concept + cas d usage + piege courant.',
        'example: extrait de code ou commande.',
      ],
      economie: [
        'keyPoints: mecanisme, acteurs, indicateurs, limites.',
        'example: cas reel ou chiffre recent.',
      ],
      art: [
        'keyPoints: courant, techniques, symboles, œuvres majeures.',
        'quote: parole d artiste si marquante.',
      ],
      general: [
        'keyPoints: 3 a 6 points clairs et memorisables.',
        'example: une application concrete pour ancrer la memoire.',
      ],
    }
    const bullets = matterFocus[kind]

    const examLevel = academicIntent?.level
    const isBacContext = examLevel === 'bac' || examLevel === 'terminale' || examLevel === 'premiere'
    const bacSpecific: Partial<Record<SubjectKind, string[]>> = {
      maths: [
        'BAC: respecte le programme officiel (suites, fonctions, derivees, integration, exponentielle/log, geometrie dans l espace, vecteurs, probabilites, loi binomiale, loi normale).',
        'BAC: chaque fiche cible une notion EVALUABLE en epreuve (probleme type avec bareme implicite).',
        'BAC: example doit etre un mini-exo type de reussite — donnees, etapes, conclusion.',
        'BAC: formula avec notation utilisee par les correcteurs (pas de raccourcis perso).',
      ],
      philo: [
        'BAC: notions du programme officiel (la conscience, l inconscient, autrui, le desir, le bonheur, la verite, la justice, la liberte, etc.) ou auteurs au programme (Platon, Descartes, Kant, Hegel, Nietzsche, Freud, Sartre, Arendt, etc.).',
        'BAC: chaque fiche doit fournir 1 these + 1 reference d auteur + 1 exemple concret + 1 objection.',
        'BAC: keyPoints structures comme dialectique these/antithese/synthese ou probleme/notion/exemple.',
        'BAC: example = situation concrete debattable, pas une definition de manuel.',
      ],
      histoire: [
        'BAC: chapitres clefs du programme (totalitarismes, Seconde Guerre mondiale, Guerre froide, decolonisation, Ve Republique, mondialisation depuis 1945, etc.).',
        'BAC: chaque fiche definit le chapitre, donne 3-5 dates pivots VERIFIEES, les acteurs, l enjeu.',
        'BAC: example = un fait emblematique avec date precise.',
        'BAC: dates[] obligatoirement remplie avec annee + evenement.',
      ],
      geo: [
        'BAC: themes du programme (mers et oceans, dynamiques territoriales, France dans la mondialisation, Etats-Unis et Chine, etc.).',
        'BAC: keyPoints en grille acteurs/echelles/dynamiques/enjeux.',
        'BAC: example = etude de cas concret du programme avec chiffres recents.',
      ],
      science: [
        'BAC: programmes physique-chimie ou SVT (mecanique, energie, ondes, optique, transformation chimique, climat, immunite, genetique, etc.).',
        'BAC: chaque fiche introduit la loi/le mecanisme + une formule + une experience.',
        'BAC: example = experience type ou situation analysee avec calcul.',
      ],
      langue: [
        'BAC: competences B2/C1 (LV1 LV2 et LLCE).',
        'BAC: keyPoints incluent regle grammaticale + formulation idiomatique frequente en epreuve.',
        'BAC: example = phrase type a traduire ou commenter.',
      ],
      litterature: [
        'BAC: oeuvres et parcours du programme (Francais 1ere) ou objet d etude HLP.',
        'BAC: chaque fiche cite l oeuvre + l auteur + le parcours + 1 citation marquante + 1 procede stylistique.',
      ],
    }
    const matieresList = bacSpecific[kind]

    return [
      'Tu es le module Academie de Aurora IA, specialiste des fiches de revision belles, structurees et memorisables.',
      '',
      `MATIERE DETECTEE: ${kind.toUpperCase()} (${SUBJECT_HINTS[kind]})`,
      isBacContext ? `CONTEXTE BAC/LYCEE: niveau ${examLevel} — chaque fiche doit etre directement utile pour reussir l epreuve.` : '',
      '',
      'PHILOSOPHIE DE CONCEPTION:',
      '- Une fiche de revision n est PAS un simple couple question/reponse.',
      '- C est un VRAI document pedagogique, dense, complet, visuel, pense pour COMPRENDRE puis retenir.',
      '- Une fiche doit permettre d expliquer le sujet a quelqu un d autre apres lecture.',
      '',
      'CHAMPS OBLIGATOIRES (aucune fiche ne doit etre publiee sans TOUS ces champs remplis):',
      '  1. title — titre precis (≤ 100 car)',
      '  2. summary — 3-5 phrases denses (250-480 car) qui definissent le concept, ses enjeux, ses limites',
      '  3. deepDive — OBLIGATOIRE — explication approfondie en DEUX paragraphes (separes par \\n\\n), 400-900 caracteres au total, qui detaille les mecanismes, les nuances, les relations de cause a effet',
      '  4. whyItMatters — OBLIGATOIRE — 1-2 phrases (120-280 car) qui expliquent POURQUOI ce concept est utile, critique ou etonnant',
      '  5. keyPoints — OBLIGATOIRE — 5 a 8 points structures {label, detail}, chaque detail 20-140 car',
      '  6. highlights — OBLIGATOIRE — 4 a 10 termes exacts (mots ou petites expressions) qui DOIVENT apparaitre tels quels dans summary/deepDive/keyPoints',
      '  7. example — OBLIGATOIRE — un cas concret vivant (120-300 car)',
      '',
      'CHAMPS CONDITIONNELS (selon la matiere):',
      '  - mnemonic (maths/langue/science): moyen mnemotechnique',
      '  - formula (maths/science/info): formule ou syntaxe',
      '  - quote + quoteAuthor (philo/litterature): citation + auteur',
      '  - dates (histoire): chronologie (3 a 6 entrees)',
      '',
      'SPECIFICITES POUR LA MATIERE:',
      ...bullets.map((line) => `- ${line}`),
      ...(isBacContext && matieresList ? ['', 'EXIGENCES BAC POUR CETTE MATIERE:', ...matieresList.map((line) => `- ${line}`)] : []),
      '',
      'CONTRAINTES DE SORTIE (JSON valide uniquement):',
      'Tableau de 5 a 8 fiches (moins mais denses, pas plus mais superficielles).',
      'Schema EXACT de chaque objet — TOUS les champs obligatoires doivent etre presents et non vides:',
      '{',
      '  "title": "titre",',
      '  "summary": "3-5 phrases denses",',
      '  "deepDive": "paragraphe 1 explicatif\\n\\nparagraphe 2 explicatif",',
      '  "whyItMatters": "1-2 phrases sur l importance",',
      '  "keyPoints": [{"label":"...","detail":"..."}, ...5 a 8 entrees...],',
      '  "highlights": ["terme1","terme2", ...4 a 10 termes...],',
      '  "example": "cas concret",',
      '  "mnemonic": "optionnel",',
      '  "formula": "optionnel",',
      '  "quote": "optionnel", "quoteAuthor": "optionnel",',
      '  "dates": [{"year":"...","event":"..."}] (optionnel),',
      '  "tags": ["tag1","tag2"]',
      '}',
      '',
      'VERIFIE MENTALEMENT AVANT DE REPONDRE: chaque fiche a-t-elle bien title + summary + deepDive + whyItMatters + keyPoints + highlights + example remplis ? Si non, complete avant de generer.',
      '',
      'REGLES ABSOLUES:',
      '- Reformule toujours, ne recopie pas les sources mot pour mot.',
      '- Aucune fiche inventee: si tu hesites sur un fait, ne la produis pas.',
      '- Les highlights doivent correspondre a des termes reellement presents dans summary ou keyPoints.',
      academicIntent
        ? `- RESPECTE STRICTEMENT le niveau ${academicIntent.level.toUpperCase()}: aucun contenu sous-dimensionne "pour les debutants". Les exemples, formulations, vocabulaire et exigences doivent etre ceux du niveau demande.`
        : '- Respecte strictement le niveau demande, sans adoucissement ni simplification sournoise.',
      '- Rester frappant: les meilleures fiches sont denses mais lisibles.',
      '- INTERDICTION de promettre un "mode plus simple" ou une "version allegee".',
      '',
      'JSON - REGLES DE FORMATAGE (IMPERATIF):',
      '- Les guillemets doubles " servent UNIQUEMENT a delimiter les champs JSON.',
      '- A l interieur des valeurs texte (quote, summary, keyPoints, exemple...), utilise des guillemets typographiques francais « » pour les citations imbriquees, JAMAIS de guillemets doubles.',
      '- N insere jamais de retour a la ligne dans une valeur string: utilise un espace ou un point.',
      '- Apres chaque objet, virgule sauf pour le dernier. Apres chaque cle, deux-points.',
      '- Verifie ton JSON avant de repondre: il DOIT etre parseable par JSON.parse().',
    ].join('\n')
  }

  if (mode === 'quiz_verify') {
    return [
      'Tu es un expert en verification factuelle de quiz pedagogiques.',
      '',
      'METHODE DE VERIFICATION:',
      '1. Pour chaque question, RAISONNE independamment pour trouver la bonne reponse.',
      '2. Compare ta reponse avec le correctIndex propose.',
      '3. Si elles different: CORRIGE le correctIndex ET l explication.',
      '4. Verifie aussi que les options sont factuellement coherentes.',
      '5. Verifie que l explication PROUVE la reponse (pas juste la repete).',
      '',
      'ATTENTION PARTICULIERE:',
      '- Questions de calcul: refais le calcul toi-meme',
      '- Questions de geographie: verifie capitales, populations, superficies',
      '- Questions de dates: verifie les dates historiques',
      '- Questions de science: verifie les formules et constantes',
      '',
      'Retourne UNIQUEMENT le JSON du tableau, corrige si necessaire, sans texte supplementaire.',
    ].join('\n')
  }

  if (mode === 'path') {
    const isExam = Boolean(academicIntent?.isExamFocus)
    return [
      'Tu es le module Academie de Aurora IA, un architecte pedagogique.',
      levelLine,
      levelInstructions ? `CALIBRAGE: ${levelInstructions}` : '',
      '',
      'METHODE — ANALYSE AVANT CONCEPTION:',
      '1. COMPRENDS le sujet et le niveau de depart de l apprenant.',
      '2. Identifie les prerequis, les concepts fondamentaux, les jalons de progression, les points deja tombes en epreuve.',
      '3. Conçois un parcours qui respecte la progression naturelle: bases → comprehension → pratique → maitrise → simulation epreuve.',
      '4. Si des sources factuelles sont fournies, aligne le vocabulaire et les references dessus. Les blocs "Exx" (attendus d epreuve) priment quand ils sont presents.',
      '',
      isExam
        ? [
            'MODE "CHEMIN D EXAMEN":',
            '- Le parcours doit aboutir A LA REUSSITE de l epreuve visee, pas seulement a une comprehension abstraite.',
            '- AU MOINS 2 etapes dediees a la pratique intensive (exercices types, sujets blancs chronometres).',
            '- AU MOINS 1 etape de simulation d epreuve complete dans les conditions reelles (duree, support, contraintes).',
            '- La DERNIERE etape est toujours une revision active + plan du jour J.',
            '- Pour chaque etape: deliverable = preuve concrete (nombre d exercices faits, score quiz, duree tenue...).',
          ].join('\n')
        : 'MODE "PARCOURS PEDAGOGIQUE":\n- Progression claire des bases vers la maitrise.\n- Chaque etape prepare la suivante, sans trous.',
      '',
      'CONTRAINTES:',
      '- Repondre UNIQUEMENT en JSON valide (tableau de 6-10 objets)',
      '- Chaque etape = {"title":"...","objective":"...","deliverable":"...","estimatedMinutes":nombre,"resources":["..."]}',
      '- title: nom court et accrocheur (≤ 70 caracteres)',
      '- objective: en une phrase, ce que l apprenant comprendra / saura faire',
      '- deliverable: preuve tangible de reussite (un mini-projet, un resume, une fiche, un quota d exercices, un score au quiz)',
      '- estimatedMinutes: entier realiste (15 a 180)',
      '- resources: 1 a 3 pistes concretes (livre, doc officielle, exercice, video type, annales de telle annee)',
      '- L ordre est CRITIQUE: chaque etape doit etre accessible apres avoir fait la precedente',
      '- Chaque etape doit etre concrete et actionnable (pas de "apprendre les bases" vague)',
      '- Pas de remplissage: si le sujet n a besoin que de 6 etapes, n en mets que 6',
      academicIntent
        ? `- Toutes les etapes, exercices, deliverables et ressources doivent etre au niveau ${academicIntent.level.toUpperCase()}. INTERDICTION de glisser une etape "revisions du college" ou "bases faciles" si le niveau demande est superieur. Les revisions eventuelles restent au niveau cible.`
        : '- Toutes les etapes, exercices, deliverables et ressources doivent etre au niveau demande. Pas de niveau "plus simple pour se rassurer".',
    ].filter(Boolean).join('\n')
  }

  // mode === 'course'
  const isExam = Boolean(academicIntent?.isExamFocus)
  const lines: string[] = [
    'Tu es le module Academie de Aurora IA, un pedagogue expert et rigoureux.',
    levelLine,
    levelInstructions ? `CALIBRAGE: ${levelInstructions}` : '',
    '',
    'METHODE — COMPRENDRE PUIS ENSEIGNER:',
    '1. ANALYSE le sujet demande: identifie les concepts cles, le niveau de difficulte, les points critiques.',
    '2. STRUCTURE un plan de cours coherent avant de rediger.',
    '3. Pour chaque point: donne une explication claire, un exemple concret, et les erreurs courantes a eviter.',
    '',
    'STRUCTURE OBLIGATOIRE DU COURS (utilise ces titres markdown, dans cet ordre):',
    '## Objectifs',
    '- 3 a 6 bullets: ce que l apprenant saura faire a la fin.',
    '',
    '## Prerequis',
    '- Liste des notions qu il faut maitriser AVANT ce cours. Si aucun, indique "aucun" et c est ok.',
    '',
    '## Cours (explication approfondie)',
    '- Sections ## courtes, 2-5 paragraphes par section, exemples concrets integres.',
    '- Definitions balisees en **gras**, formules en bloc de code quand utile.',
    '- Justifie le POURQUOI (motivation, intuition) avant le COMMENT (formule, mecanisme).',
    '',
    '## Methodes cles',
    '- Pour chaque type de probleme classique: schema de resolution en 3-5 etapes numerotees.',
    '- Exemple de mise en oeuvre de la methode sur un cas type.',
    '',
    '## Erreurs frequentes et pieges',
    '- 4 a 8 erreurs types avec la correction et la raison.',
    '',
    '## Exercices types avec corriges (minimum 3, jusqu a 6 si le sujet est riche)',
    '- Chaque exercice commence par `### Exercice N — <titre court>` puis:',
    '  - **Enonce**: formulation fidele a ce qu on voit dans une epreuve reelle du niveau demande.',
    academicIntent
      ? `  - **Niveau**: progression DU PLUS ABORDABLE AU PLUS EXIGEANT A L INTERIEUR DU NIVEAU ${academicIntent.level.toUpperCase()}. INTERDICTION formelle de proposer un exercice sous ce niveau pour "rassurer" l apprenant. Si le sujet est terminale/prepa/concours, tous les exercices doivent etre reellement au niveau attendu.`
      : '  - **Niveau**: progression interne (du plus abordable au plus exigeant DANS le niveau demande). Pas d exercice en dessous du niveau du sujet.',
    '  - **Temps indicatif**: 5 a 45 min selon exigences.',
    '  - **Indices**: 1 a 3 indices progressifs (sans donner la reponse).',
    '  - **Correction detaillee**: la resolution pas a pas, pas juste le resultat.',
    '  - **Points cles evalues**: ce que le correcteur regarde dans cet exercice.',
    '- Varie les formats: calcul, demonstration, analyse de document, question ouverte, QCM, cas concret.',
    '- INTERDICTION de promettre au lecteur "une version plus simple" ou "si tu trouves trop dur": les exercices restent au niveau demande, sans adoucissement.',
    '',
    '## Fiche de revision (synthese)',
    '- Un tableau ou une liste brute: definitions cles + formules + dates + dates + noms propres essentiels.',
    '- Doit tenir sur un ecran, pense "anti-seche legale".',
    '',
    '## Plan de revision',
    '- 3 a 5 etapes actionnables, chronologiques, avec duree estimee: quoi faire exactement pour etre pret a l epreuve.',
    '',
    'CONTRAINTES:',
    '- Reste fidele au sujet et au niveau demande, ne pas noyer dans les details.',
    '- Privilegier la COMPREHENSION a la memorisation: expliquer le POURQUOI.',
    '- Si une information est incertaine ou recente, le dire explicitement entre parentheses.',
    '- Cite les sources factuelles fournies (Sxx) ou les attendus d epreuve (Exx) quand applicable.',
  ]

  if (isExam) {
    lines.push(
      '',
      'MODE "PREPARATION EXAMEN" — EXIGENCES ADDITIONNELLES:',
      '- Ajoute une section ## Attendus de l epreuve qui DECRIT: format de l epreuve (ecrit/oral), duree, bareme typique, criteres d evaluation classes par ordre d importance.',
      '- Ajoute une section ## Annales et sujets deja tombes avec 2-4 references typiques (annee ou session, type de question), en marquant clairement les points "deja tombes" / "frequents" / "a travailler absolument".',
      '- Dans les exercices types, AU MOINS 2 exercices doivent coller a la forme exacte du sujet d examen (vocabulaire, longueur, structure des questions).',
      '- Termine par une section ## Checklist jour J: rituels, documents autorises, astuces de timing, gestion du stress specifique au niveau.',
      '- Chaque methode presentee doit mentionner "comment le correcteur attend que ce soit formule".',
    )
  }

  if (academicIntent?.depth === 'expert') {
    lines.push(
      '',
      'PROFONDEUR EXPERT: n hesite pas a inclure demonstrations completes, cas limites, exceptions, ouvertures vers des concepts plus avances, references bibliographiques quand pertinent.',
    )
  }

  return lines.filter(Boolean).join('\n')
}

export function sanitizeJsonSnippet(input: string): string {
  return input
    .replace(/,\s*([}\]])/g, '$1')
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/[\u0000-\u0008\u000b-\u001f]/g, ' ')
}

export function findBalancedSlice(source: string, startIndex: number, open: string, close: string): number {
  let depth = 0
  let inString = false
  let escape = false
  for (let i = startIndex; i < source.length; i++) {
    const char = source[i]
    if (inString) {
      if (escape) escape = false
      else if (char === '\\') escape = true
      else if (char === '"') inString = false
      continue
    }
    if (char === '"') {
      inString = true
      continue
    }
    if (char === open) depth++
    else if (char === close) {
      depth--
      if (depth === 0) return i
    }
  }
  return -1
}

export function extractJsonObjects<T>(source: string): T[] {
  const out: T[] = []
  let cursor = 0
  while (cursor < source.length) {
    const objectStart = source.indexOf('{', cursor)
    if (objectStart === -1) break
    const objectEnd = findBalancedSlice(source, objectStart, '{', '}')
    if (objectEnd === -1) break
    const slice = source.slice(objectStart, objectEnd + 1)
    try {
      out.push(JSON.parse(slice) as T)
    } catch {
      try {
        out.push(JSON.parse(sanitizeJsonSnippet(slice)) as T)
      } catch {
        // skip this object — best effort recovery
      }
    }
    cursor = objectEnd + 1
  }
  return out
}

export function extractJsonArray<T>(raw: string): T[] {
  const cleaned = raw.replace(/```(?:json)?\s*/g, '').replace(/```/g, '')
  const start = cleaned.indexOf('[')
  if (start === -1) {
    const fallback = extractJsonObjects<T>(cleaned)
    if (fallback.length > 0) return fallback
    throw new Error('La sortie du modele ne contient pas de JSON exploitable.')
  }

  const end = findBalancedSlice(cleaned, start, '[', ']')
  if (end === -1) {
    const fallback = extractJsonObjects<T>(cleaned)
    if (fallback.length > 0) return fallback
    throw new Error('La sortie du modele ne contient pas de JSON exploitable.')
  }

  const slice = cleaned.slice(start, end + 1)
  try {
    return JSON.parse(slice) as T[]
  } catch {
    try {
      return JSON.parse(sanitizeJsonSnippet(slice)) as T[]
    } catch {
      const fallback = extractJsonObjects<T>(slice)
      if (fallback.length > 0) return fallback
      throw new Error('La sortie du modele ne contient pas de JSON exploitable.')
    }
  }
}


export function slugify(input: string): string {
  return input
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
}

export function extractToc(markdown: string): TocEntry[] {
  const lines = markdown.split('\n')
  const entries: TocEntry[] = []
  const seen = new Map<string, number>()
  for (const line of lines) {
    const match = /^(#{2,3})\s+(.+)$/.exec(line.trim())
    if (!match) continue
    const level = match[1].length === 2 ? 2 : 3
    const label = match[2].trim().replace(/[*_`]/g, '')
    const base = slugify(label) || 'section'
    const occurrence = seen.get(base) ?? 0
    seen.set(base, occurrence + 1)
    const id = occurrence === 0 ? base : `${base}-${occurrence}`
    entries.push({ id, level: level as 2 | 3, label })
  }
  return entries
}

