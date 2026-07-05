import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, BookOpen, Clock, GraduationCap, Search, Sparkles, Star, Tag } from 'lucide-react'

// ===== PRELOADED RICH COURSE LIBRARY =====
type Course = {
  id: string
  title: string
  emoji: string
  subject: string
  level: 'collège' | 'lycée' | 'sup'
  duration: string
  tags: string[]
  summary: string
  sections: Array<{ heading: string; body: string }>
}

const COURSES: Course[] = [
  {
    id: 'phy-newton',
    title: 'Les 3 lois de Newton',
    emoji: '🍎',
    subject: 'Physique',
    level: 'lycée',
    duration: '15 min',
    tags: ['mécanique', 'forces', 'mouvement'],
    summary: 'Comprendre les lois fondamentales du mouvement à partir d\'exemples concrets.',
    sections: [
      {
        heading: '1ʳᵉ loi : principe d\'inertie',
        body: `Tout corps reste au repos ou en mouvement rectiligne uniforme tant qu'aucune force ne lui est appliquée.

**Exemple** : un palet sur la glace continue à glisser parce que les frottements sont quasi-nuls. Sur le sol, il s'arrête vite à cause des frottements.

**Conséquence** : le mouvement n'a pas besoin de cause — c'est le **changement** de mouvement qui en a une.`
      },
      {
        heading: '2ᵉ loi : F = m·a',
        body: `La somme des forces appliquées à un corps est égale à sa masse multipliée par son accélération.

\`\`\`
ΣF = m × a
\`\`\`

**Unités** : F en Newton (N), m en kg, a en m/s².

**Exemple** : un ballon de 0,5 kg accéléré à 10 m/s² subit une force de 5 N.

Plus la masse est grande, plus la force nécessaire pour produire la même accélération est élevée — c'est pourquoi un camion freine moins vite qu'une moto.`
      },
      {
        heading: '3ᵉ loi : action-réaction',
        body: `Si un corps A exerce une force sur un corps B, alors B exerce sur A une force égale et opposée.

**Exemple 1** : tu pousses un mur (action). Le mur te repousse avec la même force (réaction). Si le mur ne pousse pas en retour, tu le traverses !

**Exemple 2** : la fusée éjecte des gaz vers le bas (action). Les gaz poussent la fusée vers le haut (réaction).`
      },
      {
        heading: 'Pour aller plus loin',
        body: `- Lien avec l'énergie cinétique : Ec = ½ · m · v²
- Lien avec l'énergie potentielle : Ep = m · g · h
- Conservation de l'énergie mécanique en l'absence de frottements
- Loi de gravitation : F = G · m₁ · m₂ / r²`
      }
    ]
  },
  {
    id: 'chem-mole',
    title: 'La mole et la quantité de matière',
    emoji: '⚗️',
    subject: 'Chimie',
    level: 'lycée',
    duration: '12 min',
    tags: ['mole', 'avogadro', 'molarité'],
    summary: 'Manipuler la quantité de matière n et le nombre d\'Avogadro.',
    sections: [
      {
        heading: 'Définition',
        body: `Une **mole** contient exactement **6,022 × 10²³ entités** (atomes, molécules, ions…). C'est le **nombre d'Avogadro** N_A.

**Pourquoi ?** Un atome est trop petit pour être pesé. La mole permet de passer du monde microscopique au monde macroscopique : 1 mole de carbone-12 pèse 12 g exactement.`
      },
      {
        heading: 'Masse molaire M',
        body: `La masse molaire d'une espèce, c'est la masse d'**1 mole** de cette espèce, en g/mol.

| Élément | M (g/mol) |
|---------|-----------|
| H | 1 |
| C | 12 |
| N | 14 |
| O | 16 |
| Na | 23 |
| Cl | 35,5 |

**Exemple** : H₂O → M = 2(1) + 16 = 18 g/mol.`
      },
      {
        heading: 'Conversions',
        body: `Pour passer de la masse à la quantité de matière :

\`\`\`
n = m / M
\`\`\`

**Exemple** : 36 g d'eau → n = 36 / 18 = **2 mol** → 2 × 6,022 × 10²³ = **1,2 × 10²⁴ molécules**.

Pour les gaz dans les CNTP (0°C, 1 atm) :

\`\`\`
n = V / Vm     avec Vm ≈ 22,4 L/mol
\`\`\``
      },
      {
        heading: 'Concentration molaire',
        body: `Pour les solutions liquides :

\`\`\`
C = n / V        en mol/L
\`\`\`

**Exemple** : on dissout 0,1 mol de NaCl dans 500 mL → C = 0,1 / 0,5 = **0,2 mol/L**.`
      }
    ]
  },
  {
    id: 'bio-cell',
    title: 'La cellule eucaryote',
    emoji: '🧬',
    subject: 'SVT',
    level: 'lycée',
    duration: '14 min',
    tags: ['cellule', 'organites', 'vie'],
    summary: 'Architecture, organites, fonctions essentielles.',
    sections: [
      {
        heading: 'Eucaryote vs procaryote',
        body: `- **Procaryotes** (bactéries) : pas de noyau, ADN circulaire libre dans le cytoplasme.
- **Eucaryotes** (animaux, plantes, champignons, protistes) : noyau membrané, organites compartimentés.

La complexité eucaryote permet une **spécialisation** des fonctions cellulaires.`
      },
      {
        heading: 'Membrane plasmique',
        body: `Bicouche de **phospholipides** parsemée de protéines (canaux, récepteurs, enzymes).

**Rôles** :
- Délimiter la cellule
- Filtrer les échanges (perméabilité sélective)
- Détecter des signaux externes
- Reconnaître les autres cellules`
      },
      {
        heading: 'Noyau',
        body: `Contient l'**ADN** sous forme de chromatine. Site de la **transcription** (ADN → ARN messager).

L'enveloppe nucléaire est percée de **pores** qui laissent sortir l'ARNm vers le cytoplasme.`
      },
      {
        heading: 'Mitochondries — la centrale énergétique',
        body: `Produisent l'**ATP** (énergie utilisable) par respiration cellulaire :

\`\`\`
Glucose + 6 O₂ → 6 CO₂ + 6 H₂O + ATP
\`\`\`

Possèdent leur propre ADN (origine bactérienne, théorie de l'endosymbiose).`
      },
      {
        heading: 'Réticulum, Golgi, lysosomes',
        body: `- **Réticulum endoplasmique** : synthèse des protéines (rugueux, avec ribosomes) ou des lipides (lisse).
- **Appareil de Golgi** : modifie, trie et expédie les protéines vers leur destination.
- **Lysosomes** : "estomac" de la cellule, digèrent les déchets.`
      },
      {
        heading: 'Spécificités végétales',
        body: `Les cellules végétales possèdent **en plus** :
- **Paroi de cellulose** rigide
- **Chloroplastes** (photosynthèse)
- **Grande vacuole centrale** (réserve d'eau, pression de turgescence)`
      }
    ]
  },
  {
    id: 'math-derivative',
    title: 'Dérivées : la règle universelle',
    emoji: '📈',
    subject: 'Maths',
    level: 'lycée',
    duration: '18 min',
    tags: ['dérivée', 'pente', 'analyse'],
    summary: 'De la pente à l\'optimisation : la dérivée comme outil le plus puissant des sciences.',
    sections: [
      {
        heading: 'Idée géométrique',
        body: `La dérivée f'(x) en un point x, c'est la **pente** de la tangente à la courbe en ce point.

Quand x augmente d'une petite quantité dx, f(x) varie d'environ f'(x)·dx. C'est la **meilleure approximation linéaire**.`
      },
      {
        heading: 'Définition formelle',
        body: `\`\`\`
f'(x) = lim (h→0) [ f(x+h) − f(x) ] / h
\`\`\`

C'est le **taux d'accroissement** quand h tend vers 0.`
      },
      {
        heading: 'Dérivées usuelles',
        body: `| f(x) | f'(x) |
|------|-------|
| k (constante) | 0 |
| x | 1 |
| xⁿ | n·xⁿ⁻¹ |
| eˣ | eˣ |
| ln(x) | 1/x |
| sin(x) | cos(x) |
| cos(x) | −sin(x) |
| tan(x) | 1 + tan²(x) |`
      },
      {
        heading: 'Règles de calcul',
        body: `- Somme : (f + g)' = f' + g'
- Produit : (f·g)' = f'·g + f·g'
- Quotient : (f/g)' = (f'·g − f·g') / g²
- Composition : (g(f))' = f'·g'(f)`
      },
      {
        heading: 'Application : optimisation',
        body: `f'(x₀) = 0 ⇒ x₀ est un **extremum local** (max ou min).

**Exemple** : volume max d'une boîte. On exprime V(x), on dérive, on cherche x tel que V'(x) = 0.`
      },
      {
        heading: 'En physique',
        body: `- Vitesse = dérivée de la position
- Accélération = dérivée de la vitesse
- Puissance = dérivée du travail
- Force = dérivée de l'énergie potentielle (à un signe près)`
      }
    ]
  },
  {
    id: 'hist-revolution',
    title: 'La Révolution française (1789-1799)',
    emoji: '🇫🇷',
    subject: 'Histoire',
    level: 'lycée',
    duration: '20 min',
    tags: ['révolution', '1789', 'République'],
    summary: 'De la prise de la Bastille au coup d\'État de Bonaparte.',
    sections: [
      {
        heading: 'Causes',
        body: `**Crise économique** (mauvaises récoltes, dette de l'État après la guerre d'indépendance américaine).
**Crise sociale** : société d'ordres injuste (clergé + noblesse exemptés d'impôts, Tiers État écrasé).
**Crise politique** : Louis XVI faible, ministres successifs incapables.
**Crise des idées** : Lumières (Voltaire, Rousseau, Montesquieu) diffusent l'idée d'égalité.`
      },
      {
        heading: '1789 — l\'année de toutes les ruptures',
        body: `- **5 mai** : États généraux à Versailles.
- **17 juin** : le Tiers se proclame **Assemblée nationale**.
- **20 juin** : serment du Jeu de paume.
- **14 juillet** : prise de la Bastille → fête nationale.
- **4 août** : abolition des privilèges.
- **26 août** : Déclaration des Droits de l'Homme et du Citoyen.`
      },
      {
        heading: '1791 — Constitution monarchique',
        body: `Monarchie constitutionnelle, suffrage censitaire (seuls les hommes payant un impôt).
Le roi tente de fuir (**Varennes, juin 1791**) → discrédit total.`
      },
      {
        heading: '1792-1794 — République et Terreur',
        body: `- **10 août 1792** : prise des Tuileries, fin de la monarchie.
- **22 septembre 1792** : I**ʳᵉ République**.
- **21 janvier 1793** : exécution de Louis XVI.
- **1793-94** : **Terreur** — Robespierre, Comité de salut public, ~17 000 exécutions.
- **27 juillet 1794** (9 thermidor) : chute de Robespierre.`
      },
      {
        heading: '1795-1799 — Directoire et fin',
        body: `Régime instable, militaire, corrompu. Bonaparte s'illustre en Italie et en Égypte.

**18 brumaire (9 nov 1799)** : coup d'État → Consulat → Empire (1804).`
      },
      {
        heading: 'Héritage',
        body: `- Devise : Liberté, Égalité, Fraternité
- Code civil (1804)
- Système métrique
- Souveraineté nationale, séparation des pouvoirs
- Modèle exporté à l'Europe puis au monde`
      }
    ]
  },
  {
    id: 'cs-binary',
    title: 'Le binaire et le code informatique',
    emoji: '💾',
    subject: 'Informatique',
    level: 'lycée',
    duration: '12 min',
    tags: ['binaire', 'bit', 'octet', 'ASCII'],
    summary: 'Comprendre comment un ordinateur stocke et manipule l\'information.',
    sections: [
      {
        heading: 'Bit et octet',
        body: `Un **bit** (binary digit) vaut 0 ou 1.
Un **octet** (byte) = 8 bits → peut représenter 2⁸ = **256 valeurs** (0 à 255).

L'unité de mesure :
- 1 ko = 1 024 octets
- 1 Mo = 1 024 ko
- 1 Go = 1 024 Mo
- 1 To = 1 024 Go`
      },
      {
        heading: 'Conversion décimal → binaire',
        body: `Décompose en puissances de 2 :

\`\`\`
13 en binaire :
13 = 8 + 4 + 1 = 2³ + 2² + 2⁰
   = 1101 (en binaire)
\`\`\`

Méthode des divisions successives :
- 13 / 2 = 6 reste 1
- 6 / 2 = 3 reste 0
- 3 / 2 = 1 reste 1
- 1 / 2 = 0 reste 1
- Lecture en remontant : **1101**`
      },
      {
        heading: 'Texte → ASCII',
        body: `Chaque caractère est codé sur un octet :
- 'A' = 65 = 01000001
- 'a' = 97 = 01100001
- ' ' = 32 = 00100000

L'**Unicode** étend ASCII pour représenter tous les caractères du monde (UTF-8 utilise 1 à 4 octets).`
      },
      {
        heading: 'Image → bits',
        body: `Une image RGB :
- Chaque pixel = 3 octets (R, G, B), chacun 0-255.
- Une image 1920×1080 = 2 073 600 pixels × 3 octets ≈ **6,2 Mo non compressée**.

Le JPEG compresse en supprimant les détails que l'œil ne distingue pas.`
      },
      {
        heading: 'Opérateurs binaires',
        body: `- **AND** (&) : 1010 & 1100 = 1000
- **OR** (|) : 1010 | 1100 = 1110
- **XOR** (^) : 1010 ^ 1100 = 0110
- **NOT** (~) : inverse les bits
- **Décalage** : 0001 << 3 = 1000 (×8)`
      }
    ]
  },
  {
    id: 'phy-electricity',
    title: 'Électricité : tension, courant, puissance',
    emoji: '⚡',
    subject: 'Physique',
    level: 'collège',
    duration: '13 min',
    tags: ['électricité', 'ohm', 'circuit'],
    summary: 'De la pile à l\'ampoule — comprendre ce qui circule.',
    sections: [
      {
        heading: 'Trois grandeurs liées',
        body: `- **Tension U** : "force" qui pousse les électrons. Unité : **Volt (V)**, mesurée avec un voltmètre **en parallèle**.
- **Courant I** : quantité d'électrons qui passent. Unité : **Ampère (A)**, mesurée avec un ampèremètre **en série**.
- **Résistance R** : ce qui s'oppose au passage. Unité : **Ohm (Ω)**.`
      },
      {
        heading: 'Loi d\'Ohm',
        body: `\`\`\`
U = R × I
\`\`\`

**Exemple** : une résistance de 220 Ω traversée par 0,02 A :
U = 220 × 0,02 = **4,4 V**.`
      },
      {
        heading: 'Puissance',
        body: `\`\`\`
P = U × I       en Watts (W)
\`\`\`

**Exemple** : une ampoule 230V — 60W tire un courant I = P/U = 60/230 ≈ **0,26 A**.

Pour l'énergie consommée sur une durée :

\`\`\`
E = P × t       en Wh ou kWh
\`\`\`

Une ampoule 60W allumée 10h → E = 0,6 kWh.`
      },
      {
        heading: 'Circuits série / parallèle',
        body: `**En série** : I unique partout, U se répartit, R_total = R₁ + R₂ + …

**En parallèle** : U identique, I se répartit, 1/R_total = 1/R₁ + 1/R₂ + …

Conséquence : ajouter une résistance en série **diminue** le courant. En parallèle ça l'**augmente**.`
      }
    ]
  },
  {
    id: 'geo-climate',
    title: 'Le réchauffement climatique',
    emoji: '🌍',
    subject: 'Géographie',
    level: 'lycée',
    duration: '16 min',
    tags: ['climat', 'CO₂', 'GIEC'],
    summary: 'Causes, conséquences, leviers d\'action.',
    sections: [
      {
        heading: 'Effet de serre — comment ça marche',
        body: `Le Soleil envoie un rayonnement à courte longueur d'onde qui traverse l'atmosphère.
La Terre le réémet sous forme d'**infrarouge**.
Les **gaz à effet de serre** (CO₂, CH₄, N₂O, vapeur d'eau) absorbent ces infrarouges et réchauffent l'atmosphère.

C'est un phénomène **naturel et indispensable** : sans GES, la Terre serait à -18°C.
Le problème : **l'augmentation rapide** de leur concentration depuis 1850.`
      },
      {
        heading: 'Chiffres clés (GIEC, 2026)',
        body: `- CO₂ atmosphérique : 280 ppm (1850) → **421 ppm** aujourd'hui.
- Température globale : +1,2°C depuis l'ère préindustrielle.
- Mer : +20 cm depuis 1900, +3,7 mm/an actuellement.
- Glaciers : recul généralisé.
- Évènements extrêmes : multipliés par 5 depuis 1970.`
      },
      {
        heading: 'Causes humaines',
        body: `Émissions de CO₂ :
- **Énergie** (charbon, pétrole, gaz) — 73%
- **Agriculture, élevage, déforestation** — 18%
- **Industrie** (ciment, métaux) — 5%
- **Déchets** — 3%

Le méthane (CH₄) issu des élevages bovins et du gaz naturel a un pouvoir de réchauffement **80× plus puissant** que le CO₂ sur 20 ans.`
      },
      {
        heading: 'Conséquences',
        body: `- Vagues de chaleur, sécheresses, mégafeux.
- Acidification des océans → coraux blanchis.
- Migrations climatiques.
- Perturbation des cycles agricoles.
- Disparition d'espèces (1 million menacées).`
      },
      {
        heading: 'Leviers d\'action',
        body: `**Atténuation** : réduire les émissions.
- Décarboner l'énergie (renouvelable, nucléaire).
- Sobriété (chauffage, transport, consommation).
- Reforestation.

**Adaptation** : se préparer aux effets inévitables.
- Digues, plans canicule, agriculture résiliente.

Objectif Accord de Paris : **+1,5°C max** → fenêtre qui se referme.`
      }
    ]
  },
  {
    id: 'eco-supply-demand',
    title: 'L\'offre et la demande',
    emoji: '💰',
    subject: 'Économie',
    level: 'lycée',
    duration: '11 min',
    tags: ['marché', 'prix', 'équilibre'],
    summary: 'La loi fondamentale qui fixe les prix.',
    sections: [
      {
        heading: 'Demande',
        body: `La **demande** est la quantité qu'un consommateur veut acheter à un prix donné.

**Loi de la demande** : quand le prix monte, la quantité demandée baisse (et inversement).

Sur un graphique : courbe **descendante**.

**Exceptions** : biens de luxe (effet Veblen), biens Giffen.`
      },
      {
        heading: 'Offre',
        body: `L'**offre** est la quantité que les producteurs veulent vendre à un prix donné.

**Loi de l'offre** : quand le prix monte, les producteurs veulent vendre plus (plus rentable).

Sur un graphique : courbe **ascendante**.`
      },
      {
        heading: 'Équilibre',
        body: `Le **point d'équilibre** est l'intersection des deux courbes : prix et quantité où offre = demande.

**Si prix > équilibre** → surplus invendu → baisse de prix.
**Si prix < équilibre** → pénurie → hausse de prix.

Le marché tend à l'équilibre… en théorie.`
      },
      {
        heading: 'Élasticité',
        body: `Mesure la sensibilité de la demande au prix :

\`\`\`
ε = (ΔQ/Q) / (ΔP/P)
\`\`\`

- |ε| > 1 : élastique (luxe, voyages) — petit changement de prix → grand changement de demande.
- |ε| < 1 : inélastique (essence, médicaments) — la demande bouge peu.`
      },
      {
        heading: 'Limites du modèle',
        body: `- Information parfaite supposée (rare).
- Pas de monopole, pas d'externalités.
- Pas de psychologie (mode, urgence).
- Délais d'ajustement ignorés.

C'est un modèle de référence, pas la réalité.`
      }
    ]
  },
  {
    id: 'phi-descartes',
    title: 'Descartes : « Je pense donc je suis »',
    emoji: '🧠',
    subject: 'Philosophie',
    level: 'lycée',
    duration: '14 min',
    tags: ['philosophie', 'cogito', 'doute'],
    summary: 'La fondation rationnelle de toute connaissance.',
    sections: [
      {
        heading: 'Le doute méthodique',
        body: `Descartes (1596-1650) cherche une vérité **indubitable** sur laquelle bâtir toute la science.

Sa méthode : **douter de tout** pour trouver ce qui résiste au doute.

- Doute des sens : ils peuvent tromper (illusions, rêves).
- Doute des mathématiques : un Dieu trompeur pourrait fausser même 2+2=4.
- Doute du monde extérieur : peut-être un rêve, une simulation.`
      },
      {
        heading: 'Le cogito',
        body: `Mais une chose résiste : **pour douter, il faut penser**. Et pour penser, il faut **exister**.

\`\`\`
Cogito ergo sum.
Je pense, donc je suis.
\`\`\`

C'est la **première certitude** : tant que je pense (même fausses choses), j'existe en tant que **chose pensante** (res cogitans).`
      },
      {
        heading: 'Conséquences',
        body: `À partir de cette fondation, Descartes reconstruit :
1. La distinction **corps / esprit** (dualisme cartésien).
2. L'existence de Dieu (preuve ontologique).
3. La fiabilité de la raison comme méthode scientifique.

Le **rationalisme** moderne est né.`
      },
      {
        heading: 'Critiques contemporaines',
        body: `- **Hume** : le "je" n'est qu'un faisceau de perceptions changeantes.
- **Nietzsche** : c'est la grammaire qui crée le sujet ("ça pense" plutôt que "je pense").
- **Sciences cognitives** : la conscience est plus distribuée que Descartes ne le pensait.

Le cogito reste pourtant le **point zéro** de toute philosophie qui veut être rigoureuse.`
      }
    ]
  },
]

const SUBJECT_COLORS: Record<string, string> = {
  'Physique': 'from-blue-400 to-indigo-500',
  'Chimie': 'from-emerald-400 to-teal-500',
  'SVT': 'from-green-400 to-emerald-500',
  'Maths': 'from-violet-400 to-purple-500',
  'Histoire': 'from-orange-400 to-rose-500',
  'Informatique': 'from-cyan-400 to-blue-500',
  'Géographie': 'from-teal-400 to-cyan-500',
  'Économie': 'from-amber-400 to-orange-500',
  'Philosophie': 'from-violet-400 to-pink-500',
}

export default function LabCourses() {
  const [picked, setPicked] = useState<Course | null>(null)
  const [search, setSearch] = useState('')
  const [filterSubject, setFilterSubject] = useState<string | null>(null)

  const subjects = useMemo(() => Array.from(new Set(COURSES.map(c => c.subject))), [])

  const filtered = useMemo(() => {
    return COURSES.filter(c => {
      if (filterSubject && c.subject !== filterSubject) return false
      if (search) {
        const q = search.toLowerCase()
        return c.title.toLowerCase().includes(q) || c.tags.some(t => t.includes(q)) || c.subject.toLowerCase().includes(q)
      }
      return true
    })
  }, [search, filterSubject])

  if (picked) {
    return (
      <div className="space-y-5 animate-fade-in-up max-w-4xl mx-auto">
        <button onClick={() => setPicked(null)} className="btn-ghost"><ArrowLeft size={14} /> Retour à la bibliothèque</button>
        <div className="holo-card p-6 sm:p-8">
          <div className="flex items-start gap-4">
            <div className={`text-5xl rounded-2xl bg-gradient-to-br ${SUBJECT_COLORS[picked.subject]} h-20 w-20 flex items-center justify-center shadow-2xl shrink-0`}>
              {picked.emoji}
            </div>
            <div className="flex-1">
              <div className="mono-kicker text-[10px] text-aurora-text-dim mb-1">{picked.subject} · {picked.level}</div>
              <h1 className="text-3xl font-black gradient-text">{picked.title}</h1>
              <p className="text-sm text-aurora-text-muted mt-2">{picked.summary}</p>
              <div className="flex flex-wrap gap-2 mt-3">
                <span className="chip-xp"><Clock size={11}/> {picked.duration}</span>
                {picked.tags.map(t => (
                  <span key={t} className="btn-pill text-[10px]"><Tag size={10}/> {t}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="space-y-4">
          {picked.sections.map((sec, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="holo-card p-5 sm:p-6"
            >
              <div className="flex items-center gap-2 mb-3">
                <div className="rounded-full bg-gradient-to-br from-violet-400 to-purple-500 h-7 w-7 flex items-center justify-center text-xs font-bold text-white shrink-0">{i + 1}</div>
                <h2 className="text-lg font-bold gradient-text-cosmic">{sec.heading}</h2>
              </div>
              <CourseBody body={sec.body} />
            </motion.div>
          ))}
        </div>
        <div className="text-center text-xs text-aurora-text-dim py-4">
          ✨ Fin du cours · Lance un quiz pour tester tes connaissances
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mono-kicker text-[10px] text-aurora-text-dim">Bibliothèque</div>
          <h1 className="text-3xl font-black gradient-text">Cours préchargés</h1>
          <p className="text-sm text-aurora-text-dim mt-1">{COURSES.length} cours rédigés, prêts à lire — pas de génération IA, immédiat.</p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-aurora-text-dim"/>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher un cours…"
            className="w-full rounded-xl border border-white/10 bg-white/5 pl-9 pr-3 py-2 text-sm text-aurora-text placeholder:text-aurora-text-dim focus:border-violet-400/40 outline-none"
          />
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
        <button onClick={() => setFilterSubject(null)} className={`btn-pill ${filterSubject === null ? 'is-active' : ''}`}>Tout</button>
        {subjects.map(s => (
          <button key={s} onClick={() => setFilterSubject(s)} className={`btn-pill ${filterSubject === s ? 'is-active' : ''}`}>{s}</button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((c, i) => (
          <motion.button
            key={c.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.03 }}
            whileHover={{ y: -4 }}
            onClick={() => setPicked(c)}
            className="holo-card p-5 text-left group"
          >
            <div className="flex items-start gap-3 mb-3">
              <div className={`text-3xl rounded-xl bg-gradient-to-br ${SUBJECT_COLORS[c.subject]} h-14 w-14 flex items-center justify-center shadow-lg shrink-0`}>
                {c.emoji}
              </div>
              <div className="flex-1 min-w-0">
                <div className="mono-kicker text-[9px] text-aurora-text-dim">{c.subject} · {c.level}</div>
                <h3 className="text-base font-bold text-aurora-text mt-1 leading-tight">{c.title}</h3>
              </div>
            </div>
            <p className="text-xs text-aurora-text-muted leading-relaxed line-clamp-3">{c.summary}</p>
            <div className="flex items-center justify-between mt-4">
              <span className="text-[10px] text-aurora-text-dim inline-flex items-center gap-1"><Clock size={10}/> {c.duration}</span>
              <span className="text-[11px] text-violet-300 group-hover:text-violet-200 inline-flex items-center gap-1">Lire <Sparkles size={11}/></span>
            </div>
          </motion.button>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="holo-card p-8 text-center text-aurora-text-dim text-sm">
          Aucun cours trouvé — essaie un autre filtre.
        </div>
      )}
    </div>
  )
}

function CourseBody({ body }: { body: string }) {
  // Simple markdown-like renderer (paragraphs, code blocks, tables, bold, italic)
  const blocks = useMemo(() => {
    const out: Array<{ type: string; content: string; rows?: string[][] }> = []
    const lines = body.split('\n')
    let inCode = false
    let codeBuf: string[] = []
    let inTable = false
    let tableRows: string[][] = []
    let para: string[] = []
    const flushPara = () => { if (para.length) { out.push({ type: 'p', content: para.join(' ') }); para = [] } }
    const flushTable = () => { if (tableRows.length) { out.push({ type: 'table', content: '', rows: tableRows }); tableRows = [] } }

    for (const line of lines) {
      if (line.startsWith('```')) {
        if (inCode) {
          out.push({ type: 'code', content: codeBuf.join('\n') })
          codeBuf = []
          inCode = false
        } else {
          flushPara(); flushTable()
          inCode = true
        }
        continue
      }
      if (inCode) { codeBuf.push(line); continue }
      if (line.trim().startsWith('|') && line.includes('|', 1)) {
        if (!inTable) { flushPara(); inTable = true }
        if (line.includes('---')) continue
        const cols = line.split('|').slice(1, -1).map(c => c.trim())
        tableRows.push(cols)
        continue
      } else if (inTable) {
        flushTable()
        inTable = false
      }
      if (line.trim() === '') { flushPara(); continue }
      if (line.trim().startsWith('- ')) {
        flushPara()
        out.push({ type: 'li', content: line.trim().slice(2) })
        continue
      }
      para.push(line)
    }
    flushPara(); flushTable()
    if (inCode) out.push({ type: 'code', content: codeBuf.join('\n') })
    return out
  }, [body])

  const renderInline = (s: string) => {
    // **bold**, *italic*, `code`
    const parts: Array<{ text: string; bold?: boolean; italic?: boolean; code?: boolean }> = []
    let buf = ''
    let i = 0
    const flush = () => { if (buf) { parts.push({ text: buf }); buf = '' } }
    while (i < s.length) {
      if (s.slice(i, i + 2) === '**') {
        flush()
        const end = s.indexOf('**', i + 2)
        if (end !== -1) { parts.push({ text: s.slice(i + 2, end), bold: true }); i = end + 2; continue }
      }
      if (s[i] === '`') {
        flush()
        const end = s.indexOf('`', i + 1)
        if (end !== -1) { parts.push({ text: s.slice(i + 1, end), code: true }); i = end + 1; continue }
      }
      if (s[i] === '*' && s[i + 1] !== '*') {
        flush()
        const end = s.indexOf('*', i + 1)
        if (end !== -1) { parts.push({ text: s.slice(i + 1, end), italic: true }); i = end + 1; continue }
      }
      buf += s[i]; i++
    }
    flush()
    return parts.map((p, j) => {
      if (p.bold) return <strong key={j} className="text-aurora-text font-bold">{p.text}</strong>
      if (p.italic) return <em key={j} className="italic text-violet-200">{p.text}</em>
      if (p.code) return <code key={j} className="rounded bg-violet-500/15 border border-violet-400/20 px-1.5 py-0.5 text-[0.85em] font-mono text-violet-200">{p.text}</code>
      return <span key={j}>{p.text}</span>
    })
  }

  return (
    <div className="space-y-2.5 text-sm text-aurora-text leading-relaxed">
      {blocks.map((b, i) => {
        if (b.type === 'p') return <p key={i}>{renderInline(b.content)}</p>
        if (b.type === 'li') return <div key={i} className="flex gap-2 pl-2"><span className="text-violet-400 shrink-0">•</span><div className="flex-1">{renderInline(b.content)}</div></div>
        if (b.type === 'code') return (
          <pre key={i} className="rounded-xl border border-violet-400/25 bg-black/40 p-3 overflow-x-auto">
            <code className="font-mono text-xs text-cyan-200">{b.content}</code>
          </pre>
        )
        if (b.type === 'table' && b.rows) return (
          <div key={i} className="overflow-x-auto">
            <table className="text-xs w-full border-collapse">
              <thead>
                <tr className="border-b border-violet-400/30">
                  {b.rows[0].map((h, hi) => <th key={hi} className="text-left p-2 text-violet-200 font-bold">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {b.rows.slice(1).map((r, ri) => (
                  <tr key={ri} className="border-b border-white/5">
                    {r.map((c, ci) => <td key={ci} className="p-2 text-aurora-text-muted">{c}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
        return null
      })}
    </div>
  )
}
