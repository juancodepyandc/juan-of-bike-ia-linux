// Pre-loaded BAC STI2D · SIN content seed.
// Covers all bac STI2D subjects + SIN specialty.
// Each sub-category gets: 1 cours (markdown), 1 quiz (MCQ JSON), 1 fiche (cards + mindmap JSON), 1 exo (mission JSON).

import type { Category, SubCategory, AcademyItem } from './academyStore'

const uid = (p: string) => `${p}-${Math.random().toString(36).slice(2, 9)}${Date.now().toString(36)}`
const now = () => Date.now()

function sub(name: string, emoji?: string): SubCategory {
  return { id: uid('sub'), name, emoji }
}

function mkCours(subId: string, title: string, content: string): AcademyItem {
  return { id: uid('it'), kind: 'cours', title, content, subCategoryId: subId, createdAt: now(), createdByAI: false }
}
function mkQuiz(subId: string, title: string, questions: any[]): AcademyItem {
  return { id: uid('it'), kind: 'quiz', title, content: JSON.stringify({ title, questions }), subCategoryId: subId, createdAt: now(), createdByAI: false }
}
function mkFiche(subId: string, title: string, cards: any[], mindmap: any): AcademyItem {
  return { id: uid('it'), kind: 'fiche', title, content: JSON.stringify({ title, cards, mindmap }), subCategoryId: subId, createdAt: now(), createdByAI: false }
}
function mkExo(subId: string, title: string, payload: any): AcademyItem {
  return { id: uid('it'), kind: 'exo', title, content: JSON.stringify(payload), subCategoryId: subId, createdAt: now(), createdByAI: false }
}

// Subs --------------------------------------------------------------
const s_math    = sub('Mathématiques', '∑')
const s_phys    = sub('Physique-Chimie', '⚛')
const s_2i2d    = sub('2I2D (Tronc commun)', '⚙')
const s_fr      = sub('Français', '📜')
const s_philo   = sub('Philosophie', '☯')
const s_hg      = sub('Histoire-Géographie', '🌍')
const s_anglais = sub('Anglais (LVA/LVB)', '🇬🇧')
const s_emc     = sub('EMC', '⚖')
const s_eps     = sub('EPS (théorie)', '🏃')
const s_oral    = sub('Grand Oral', '🎤')
const s_algo    = sub('SIN · Algorithmique & Python', '🐍')
const s_reseau  = sub('SIN · Réseaux & Protocoles', '🌐')
const s_micro   = sub('SIN · Microcontrôleurs', '🔌')
const s_signal  = sub('SIN · Acquisition & Signal', '📡')
const s_bdd     = sub('SIN · Bases de données', '🗃')
const s_web     = sub('SIN · Web & IHM', '🕸')
const s_secu    = sub('SIN · Sécurité & Codage', '🔐')
const s_proj    = sub('SIN · Projet technique', '🛠')

// Items ----
const items: AcademyItem[] = []

// ============================================================
// MATHÉMATIQUES
// ============================================================
items.push(mkCours(s_math.id, 'Dérivées et variations',
`## Dérivée d'une fonction

La **dérivée** $f'(x)$ mesure le taux de variation instantané.

### Formules clefs
- $(x^n)' = n \\cdot x^{n-1}$
- $(e^x)' = e^x$, $(\\ln x)' = 1/x$
- $(\\sin x)' = \\cos x$, $(\\cos x)' = -\\sin x$
- $(u \\cdot v)' = u'v + uv'$
- $(u/v)' = (u'v - uv')/v^2$
- $(g \\circ f)'(x) = f'(x) \\cdot g'(f(x))$

### Variations
Le signe de $f'(x)$ donne le sens de variation :
- $f'(x) > 0$ : $f$ est **croissante**
- $f'(x) < 0$ : $f$ est **décroissante**
- $f'(x) = 0$ : $f$ a un **extremum local** (à vérifier par changement de signe)

### Tangente
Équation de la tangente au point $(a, f(a))$ : $y = f'(a)(x - a) + f(a)$.

### Méthode pour étudier une fonction
1. Calculer $f'(x)$
2. Étudier le signe de $f'(x)$
3. Dresser le tableau de variation
4. Rechercher les extrema

### Exemple concret
$f(x) = x^3 - 3x + 2$ → $f'(x) = 3x^2 - 3 = 3(x-1)(x+1)$.
Racines : $x = \\pm 1$. Tableau de signes : $f' > 0$ sur $]-\\infty,-1[ \\cup ]1,+\\infty[$, $f' < 0$ sur $]-1,1[$.
Donc maximum local en $x = -1$, minimum local en $x = 1$.`))

items.push(mkCours(s_math.id, 'Suites numériques',
`## Suites arithmétiques et géométriques

### Suite arithmétique
$u_{n+1} = u_n + r$ où $r$ est la **raison**.
Formule : $u_n = u_0 + nr$ ou $u_n = u_p + (n-p)r$.
Somme : $S = \\frac{(u_0 + u_n)(n+1)}{2}$.

### Suite géométrique
$u_{n+1} = q \\cdot u_n$ où $q$ est la raison.
Formule : $u_n = u_0 \\cdot q^n$.
Somme : $S = u_0 \\cdot \\frac{1 - q^{n+1}}{1 - q}$ si $q \\ne 1$.

### Convergence
- Suite arithmétique : diverge si $r \\ne 0$, converge si $r = 0$.
- Suite géométrique : converge vers 0 si $|q| < 1$, diverge si $|q| > 1$, constante si $q = 1$, oscille si $q = -1$.

### Suites récurrentes
$u_{n+1} = f(u_n)$. On peut étudier :
- le **point fixe** $\\ell$ tel que $f(\\ell) = \\ell$
- la **monotonie** (comparer $u_{n+1}$ et $u_n$)
- la **convergence** (point fixe attracteur si $|f'(\\ell)| < 1$)

### Application STI2D
Une population d'un élevage triple chaque année : $u_{n+1} = 3 u_n$ → géométrique de raison 3.
Une dette diminue de 50 € par mois : $u_{n+1} = u_n - 50$ → arithmétique de raison -50.`))

items.push(mkQuiz(s_math.id, 'Quiz · Dérivées', [
  { q: 'Quelle est la dérivée de f(x) = 3x² + 2x - 5 ?', choices: ['6x + 2', '3x + 2', '6x² + 2', '3x² + 2x'], correct: 0, explain: '(3x²)\' = 6x, (2x)\' = 2, (-5)\' = 0.' },
  { q: 'Si f\'(x) > 0 sur un intervalle, alors sur cet intervalle, f est…', choices: ['décroissante', 'constante', 'croissante', 'nulle'], correct: 2, explain: 'Dérivée positive = fonction croissante.' },
  { q: 'Dérivée de ln(x) ?', choices: ['1/x', 'x', 'ln(x)', 'e^x'], correct: 0, explain: '(ln x)\' = 1/x sur ]0, +∞[.' },
  { q: 'Équation de la tangente à f en x = a ?', choices: ['y = f(a) · x', 'y = f\'(a)(x-a) + f(a)', 'y = f\'(x) · a', 'y = f(a) + f\'(x)'], correct: 1, explain: 'Formule de la tangente : coefficient directeur f\'(a), passe par (a, f(a)).' },
  { q: 'Si f\'(a) = 0 et f\' change de signe autour de a, alors f admet en a un…', choices: ['point d\'inflexion', 'extremum local', 'asymptote', 'point singulier'], correct: 1, explain: 'Changement de signe de la dérivée = extremum local.' },
]))

// Sheet-format fiche (nouveau format: programme complet)
items.push({
  id: uid('it'),
  kind: 'fiche',
  title: 'Fiche · Dérivées & variations (programme complet)',
  subCategoryId: s_math.id,
  createdAt: now(),
  createdByAI: false,
  content: JSON.stringify({
    title: 'PROGRAMME COMPLET — Dérivées',
    subtitle: 'Tout ce qu\'il faut savoir pour le bac !',
    reminder: { label: 'MÉTHODE À TOUJOURS APPLIQUER', content: 'Cours → Comprendre → Exercices → Corriger. Régularité + méthode = Résultat ✨' },
    sections: [
      {
        n: 1, title: 'RÈGLES DE CALCUL', color: 'orange',
        blocks: [
          { kind: 'def', title: 'DÉFINITION', content: 'La dérivée $f\'(x)$ mesure le taux de variation instantané de $f$ au point $x$.' },
          { kind: 'props', title: 'PROPRIÉTÉS', items: ['$(x^n)\' = n \\cdot x^{n-1}$', '$(e^x)\' = e^x$', '$(\\ln x)\' = 1/x$', '$(\\sin x)\' = \\cos x$', '$(\\cos x)\' = -\\sin x$'] },
          { kind: 'formula', label: 'Produit et quotient', formula: '(uv)\' = u\'v + uv\' \\quad\\text{et}\\quad \\left(\\frac{u}{v}\\right)\' = \\frac{u\'v - uv\'}{v^2}' },
          { kind: 'savoirFaire', title: 'À SAVOIR FAIRE', items: ['Dériver un polynôme', 'Dériver un produit / quotient', 'Dériver une composée $(g \\circ f)$'] },
        ],
      },
      {
        n: 2, title: 'VARIATIONS', color: 'green',
        blocks: [
          { kind: 'def', title: 'DÉFINITION', content: 'Le signe de $f\'(x)$ donne le sens de variation de $f$.' },
          { kind: 'variations', label: 'RÈGLE', headers: ['$f\'(x)$', '$> 0$', '$= 0$', '$< 0$'], rows: [['$f$ sur l\'intervalle', 'croissante', 'extremum', 'décroissante']] },
          { kind: 'method', title: 'MÉTHODE', steps: ['Calculer $f\'(x)$', 'Étudier le signe de $f\'(x)$', 'Dresser le tableau de variation', 'Rechercher les extrema'] },
          { kind: 'attention', content: 'Un extremum local existe $\\iff$ $f\'(a) = 0$ ET $f\'$ change de signe en $a$.' },
        ],
      },
      {
        n: 3, title: 'TANGENTE', color: 'blue',
        blocks: [
          { kind: 'formula', label: 'Équation', formula: 'y = f\'(a)\\,(x - a) + f(a)' },
          { kind: 'examples', title: 'EXEMPLES', items: ['$f(x)=x^2$ au point $a=2$ : $y = 4(x-2) + 4 = 4x - 4$', '$f(x)=\\ln x$ au point $a=e$ : $y = \\frac{1}{e}(x-e) + 1$'] },
          { kind: 'savoirFaire', title: 'À SAVOIR FAIRE', items: ['Déterminer l\'équation de la tangente', 'Position relative courbe / tangente', 'Approximation affine au voisinage de $a$'] },
        ],
      },
      {
        n: 4, title: 'ÉTUDE DE FONCTION', color: 'violet',
        blocks: [
          { kind: 'method', title: 'MÉTHODE COMPLÈTE', steps: ['Ensemble de définition', 'Dérivée $f\'(x)$ et son signe', 'Tableau de variation avec limites', 'Points particuliers (extrema, inflexion)', 'Tracé de la courbe'] },
          { kind: 'props', title: 'OUTILS', items: ['Limites en $\\pm\\infty$', 'Asymptotes verticales et horizontales', 'Théorème des valeurs intermédiaires'] },
        ],
      },
      {
        n: 5, title: 'APPLICATIONS', color: 'gold',
        blocks: [
          { kind: 'examples', title: 'CAS CLASSIQUES', items: ['Optimisation : maximiser une aire, un profit', 'Cinématique : vitesse = dérivée de position', 'Économie : coût marginal = dérivée du coût total', 'Physique : accélération = dérivée seconde'] },
          { kind: 'attention', content: 'Toujours donner l\'unité et le contexte ! Ne pas confondre maximum absolu et local.' },
        ],
      },
    ],
    goldenRule: 'Travailler un peu TOUS les jours > Tout faire en 1 jour',
  }),
})

items.push(mkExo(s_math.id, 'Exo · Étude complète d\'une fonction', {
  briefing: "Tu dois étudier complètement la fonction f(x) = x³ - 6x² + 9x + 1.",
  statement: `## Énoncé\n\nSoit $f(x) = x^3 - 6x^2 + 9x + 1$ définie sur $\\mathbb{R}$.\n\n1. Calculer $f'(x)$.\n2. Étudier le signe de $f'(x)$ sur $\\mathbb{R}$.\n3. Dresser le tableau de variation.\n4. Déterminer les extrema locaux.\n5. Donner l'équation de la tangente au point d'abscisse $x = 2$.`,
  objectives: [
    { id: 'o1', text: 'Calculer f\'(x) correctement', hint: 'Appliquer la règle de la puissance terme à terme.' },
    { id: 'o2', text: 'Factoriser f\'(x) et trouver les racines', hint: 'f\'(x) = 3x² - 12x + 9. Mettre 3 en facteur puis discriminant ou Horner.' },
    { id: 'o3', text: 'Construire le tableau de variation', hint: 'Étudier le signe de f\' entre les racines, déterminer f(1) et f(3).' },
    { id: 'o4', text: 'Identifier maximum et minimum locaux', hint: 'Max où f\' passe + à -, min où f\' passe - à +.' },
    { id: 'o5', text: 'Écrire l\'équation de la tangente en x=2', hint: 'y = f\'(2)(x-2) + f(2).' },
  ],
  solution: `## Solution\n\n1. **Dérivée** : $f'(x) = 3x^2 - 12x + 9 = 3(x^2 - 4x + 3) = 3(x-1)(x-3)$.\n\n2. **Signe** : racines 1 et 3, coefficient dominant positif → $f' > 0$ sur $]-\\infty,1[ \\cup ]3,+\\infty[$, $f' < 0$ sur $]1,3[$.\n\n3. **Variations** : $f(1) = 1 - 6 + 9 + 1 = 5$, $f(3) = 27 - 54 + 27 + 1 = 1$.\n\n4. **Extrema** : maximum local en $x = 1$ avec $f(1) = 5$ ; minimum local en $x = 3$ avec $f(3) = 1$.\n\n5. **Tangente en $x = 2$** : $f'(2) = 3(1)(-1) = -3$, $f(2) = 8 - 24 + 18 + 1 = 3$. Équation : $y = -3(x-2) + 3 = -3x + 9$.`,
  environment: 'none',
}))

// ============================================================
// PHYSIQUE-CHIMIE
// ============================================================
items.push(mkCours(s_phys.id, 'Mécanique : forces et mouvement',
`## Deuxième loi de Newton

**Principe fondamental de la dynamique** : $\\vec{F}_{ext} = m \\cdot \\vec{a}$

La somme vectorielle des forces extérieures agissant sur un système de masse $m$ est égale au produit de la masse par l'accélération.

### Forces usuelles
- **Poids** : $\\vec{P} = m \\cdot \\vec{g}$ (vertical vers le bas, $g \\approx 9{,}81\\ m/s^2$)
- **Réaction normale** : perpendiculaire à la surface
- **Frottement** : $\\vec{f} = -\\mu \\cdot \\vec{v} / |\\vec{v}| \\cdot N$ (opposée au mouvement)
- **Tension** : dirigée le long du fil ou du ressort
- **Poussée d'Archimède** : $\\vec{\\Pi} = -\\rho_{fluide} V \\vec{g}$

### Cinématique
- Position : $x(t)$
- Vitesse : $v(t) = \\frac{dx}{dt}$
- Accélération : $a(t) = \\frac{dv}{dt} = \\frac{d^2x}{dt^2}$

### Mouvements types
| Mouvement | Condition | Équation |
|---|---|---|
| Uniforme | $a = 0$ | $x(t) = x_0 + vt$ |
| Uniformément accéléré | $a = cste$ | $x(t) = x_0 + v_0 t + \\frac{1}{2} a t^2$ |
| Chute libre | $a = -g$ | $y(t) = y_0 - \\frac{1}{2}g t^2$ |

### Bilan énergétique
- Énergie cinétique : $E_c = \\frac{1}{2}mv^2$
- Énergie potentielle de pesanteur : $E_{pp} = mgh$
- Théorème de l'énergie cinétique : $\\Delta E_c = W_{F}$`))

items.push(mkQuiz(s_phys.id, 'Quiz · Mécanique', [
  { q: 'Unité de la force dans le SI ?', choices: ['Joule', 'Newton', 'Pascal', 'Watt'], correct: 1, explain: '1 N = 1 kg·m/s².' },
  { q: 'La 2e loi de Newton s\'écrit…', choices: ['F = ma', 'E = mc²', 'P = mg', 'v = d/t'], correct: 0, explain: 'Principe fondamental de la dynamique.' },
  { q: 'Formule de l\'énergie cinétique ?', choices: ['mgh', '½ mv²', 'Fd', 'mv'], correct: 1, explain: 'Ec = ½ m v².' },
  { q: 'Dans un mouvement uniformément accéléré, v(t) vaut…', choices: ['v₀', 'v₀ + at', 'at²', 'v₀ + ½at²'], correct: 1, explain: 'Intégration de a constant : v = v₀ + at.' },
  { q: 'Un corps en chute libre subit…', choices: ['une poussée', 'uniquement son poids', 'une tension', 'un frottement important'], correct: 1, explain: 'Par définition, en chute libre seul le poids agit.' },
]))

items.push(mkFiche(s_phys.id, 'Fiche · Électricité continue', [
  { q: 'Loi d\'Ohm', r: 'U = R · I (V = Ω · A)' },
  { q: 'Puissance électrique', r: 'P = U · I = R · I² = U²/R' },
  { q: 'Énergie consommée', r: 'E = P · t (Joule ou kWh)' },
  { q: 'Résistances en série', r: 'R_total = R1 + R2 + …' },
  { q: 'Résistances en parallèle', r: '1/R_total = 1/R1 + 1/R2' },
  { q: 'Loi des nœuds (Kirchhoff)', r: 'Σ intensités entrantes = Σ sortantes' },
  { q: 'Loi des mailles', r: 'Σ tensions dans une boucle fermée = 0' },
  { q: 'Capacité condensateur', r: 'C = Q/U (farads)' },
], {
  label: 'Électricité',
  children: [
    { label: 'Lois fondamentales', children: [{ label: 'Ohm' }, { label: 'Kirchhoff nœuds' }, { label: 'Kirchhoff mailles' }] },
    { label: 'Puissance', children: [{ label: 'P=UI' }, { label: 'Effet Joule' }] },
    { label: 'Composants', children: [{ label: 'R' }, { label: 'C' }, { label: 'L' }] },
  ],
}))

// ============================================================
// 2I2D
// ============================================================
items.push(mkCours(s_2i2d.id, 'Chaîne d\'énergie et chaîne d\'information',
`## Approche systémique en 2I2D

Tout produit technologique est modélisé par 2 chaînes fonctionnelles.

### Chaîne d'énergie
Convertir / transmettre / utiliser une énergie.

| Bloc | Rôle | Exemples |
|---|---|---|
| **Alimenter** | Source d'énergie | pile, batterie, secteur 230 V |
| **Distribuer** | Dirige l'énergie | interrupteur, relais, variateur |
| **Convertir** | Change la forme | moteur (élec→méca), LED (élec→lumineuse) |
| **Transmettre** | Transporte | engrenages, poulies, arbres |
| **Agir** | Action sur l'objet | roue, bras, pompe |

### Chaîne d'information
Acquérir / traiter / communiquer l'information.

| Bloc | Rôle | Exemples |
|---|---|---|
| **Acquérir** | Capteurs | température, présence, tension |
| **Traiter** | Microcontrôleur / PC | Arduino, ESP32, Raspberry |
| **Communiquer** | Restitution | écran, LED, buzzer, WiFi/MQTT |

### Lien entre les deux
La chaîne d'information **pilote** la chaîne d'énergie via un **pré-actionneur** (relais, L298N, transistor).

### Développement durable
- **Analyse du cycle de vie (ACV)** : extraction → fabrication → utilisation → fin de vie.
- **Écoconception** : réduire impact à la conception.
- **Indicateurs** : bilan carbone, recyclabilité, efficacité énergétique, durée de vie.

### Exemple concret : portail automatisé
- Acquérir : télécommande, capteur fin de course.
- Traiter : microcontrôleur qui gère les séquences.
- Communiquer : LED état + notification smartphone.
- Alimenter : secteur 230 V + batterie secours.
- Distribuer : relais.
- Convertir : moteur DC.
- Transmettre : crémaillère.
- Agir : déplacement du vantail.`))

items.push(mkQuiz(s_2i2d.id, 'Quiz · Chaînes fonctionnelles', [
  { q: 'Un capteur fait partie de la chaîne…', choices: ['d\'énergie', 'd\'information', 'mécanique', 'hydraulique'], correct: 1, explain: 'Acquérir → chaîne d\'information.' },
  { q: 'Un moteur électrique est un bloc de type…', choices: ['Acquérir', 'Traiter', 'Convertir', 'Communiquer'], correct: 2, explain: 'Convertit énergie électrique en mécanique.' },
  { q: 'L\'ACV analyse…', choices: ['uniquement l\'usage', 'le cycle complet du produit', 'le coût financier', 'le design'], correct: 1, explain: 'Analyse de cycle de vie = extraction → fin de vie.' },
  { q: 'Un relais sert à…', choices: ['acquérir des données', 'distribuer l\'énergie', 'traiter l\'information', 'agir sur l\'extérieur'], correct: 1, explain: 'Le relais dirige/commute l\'énergie.' },
  { q: 'Le bloc "Agir" a pour rôle de…', choices: ['informer l\'utilisateur', 'protéger le circuit', 'réaliser l\'action finale sur l\'objet', 'stocker des données'], correct: 2, explain: 'Action finale sur le système (roue, vantail, bras).' },
]))

// ============================================================
// ALGO / PYTHON
// ============================================================
items.push(mkCours(s_algo.id, 'Structures de contrôle en Python',
`## Contrôler l'exécution d'un programme

### Conditions
\`\`\`python
if x > 0:
    print("positif")
elif x == 0:
    print("nul")
else:
    print("négatif")
\`\`\`

### Boucles
**Boucle pour (for)** — quand on connaît le nombre d'itérations :
\`\`\`python
for i in range(5):
    print(i)  # affiche 0, 1, 2, 3, 4
\`\`\`

**Boucle tant que (while)** — condition d'arrêt :
\`\`\`python
n = 1
while n < 100:
    n = n * 2  # double jusqu'à dépasser 100
\`\`\`

### Fonctions
\`\`\`python
def moyenne(liste):
    return sum(liste) / len(liste)

print(moyenne([12, 15, 18]))  # 15.0
\`\`\`

### Listes et dictionnaires
\`\`\`python
notes = [12, 15, 8, 17]
notes.append(14)
eleves = {"Alice": 15, "Bob": 12}
eleves["Charlie"] = 18
\`\`\`

### Entrées/sorties
\`\`\`python
nom = input("Ton prénom ? ")
print(f"Bonjour {nom}")
\`\`\`

### Complexité
- Parcours simple : $O(n)$
- Double boucle imbriquée : $O(n^2)$
- Recherche dichotomique : $O(\\log n)$`))

items.push(mkQuiz(s_algo.id, 'Quiz · Python de base', [
  { q: 'Quel mot-clé définit une fonction en Python ?', choices: ['func', 'def', 'function', 'fn'], correct: 1, explain: 'On utilise le mot-clé def.' },
  { q: 'range(5) produit…', choices: ['[1,2,3,4,5]', '[0,1,2,3,4]', '[0,1,2,3,4,5]', '[5]'], correct: 1, explain: 'range(n) va de 0 à n-1.' },
  { q: 'Comment ajouter 10 à une liste `L` ?', choices: ['L.add(10)', 'L.push(10)', 'L.append(10)', 'L += 10'], correct: 2, explain: 'append est la méthode Python pour ajouter un élément.' },
  { q: 'Le type de len("abc") est…', choices: ['str', 'float', 'int', 'bool'], correct: 2, explain: 'len retourne un entier (int).' },
  { q: 'Que fait `5 // 2` ?', choices: ['2.5', '2', '3', '5.0'], correct: 1, explain: '// est la division entière : 5 / 2 = 2.5 → tronque à 2.' },
]))

items.push(mkFiche(s_algo.id, 'Fiche · Python express', [
  { q: 'Définir une fonction', r: 'def nom(params): … return …' },
  { q: 'Boucle sur une liste', r: 'for item in liste:' },
  { q: 'Taille d\'une liste', r: 'len(liste)' },
  { q: 'Ajouter à une liste', r: 'liste.append(x)' },
  { q: 'Condition multiple', r: 'if … elif … else …' },
  { q: 'Format de chaîne', r: 'f"texte {variable}"' },
  { q: 'Lire au clavier', r: 'input("prompt")' },
  { q: 'Convertir chaîne en entier', r: 'int(chaine)' },
], {
  label: 'Python',
  children: [
    { label: 'Syntaxe', children: [{ label: 'indentation' }, { label: 'commentaires #' }] },
    { label: 'Structures', children: [{ label: 'if/elif/else' }, { label: 'for' }, { label: 'while' }] },
    { label: 'Données', children: [{ label: 'list' }, { label: 'dict' }, { label: 'tuple' }, { label: 'set' }] },
    { label: 'Fonctions', children: [{ label: 'def' }, { label: 'return' }, { label: 'lambda' }] },
  ],
}))

items.push(mkExo(s_algo.id, 'Exo · Simulation capteur température',
{
  briefing: "Sur Arduino, tu dois lire une thermistance et déclencher un ventilateur quand T > 28°C. Version simulée en Python dans le navigateur.",
  statement: `## Énoncé\n\nÉcris un programme Python qui :\n1. Demande à l'utilisateur 5 relevés de température.\n2. Calcule la moyenne.\n3. Affiche "VENTILATEUR ON" si moyenne > 28°C, sinon "VENTILATEUR OFF".\n4. Détecte si une valeur dépasse 35°C (alarme).`,
  objectives: [
    { id: 'o1', text: 'Lire 5 valeurs avec input()', hint: 'Utilise une boucle for i in range(5).' },
    { id: 'o2', text: 'Stocker les relevés dans une liste', hint: 'mesures.append(float(input(...)))' },
    { id: 'o3', text: 'Calculer la moyenne', hint: 'sum(liste) / len(liste)' },
    { id: 'o4', text: 'Afficher la commande VENTILATEUR', hint: 'if moyenne > 28: print("VENTILATEUR ON")' },
    { id: 'o5', text: 'Ajouter la détection d\'alarme', hint: 'if max(liste) > 35: print("ALARME")' },
  ],
  solution: `## Solution\n\n\`\`\`python\nmesures = []\nfor i in range(5):\n    t = float(input(f"Mesure {i+1} (°C) : "))\n    mesures.append(t)\n\nmoyenne = sum(mesures) / len(mesures)\nprint(f"Moyenne : {moyenne:.1f} °C")\n\nif moyenne > 28:\n    print("VENTILATEUR ON")\nelse:\n    print("VENTILATEUR OFF")\n\nif max(mesures) > 35:\n    print("⚠ ALARME : surchauffe détectée")\n\`\`\`\n\nPoints-clés : conversion \`float()\`, accumulation, \`sum/len\`, \`max()\`.`,
  environment: 'html-sandbox',
  tool: {
    title: 'Simulateur Python (Skulpt inline)',
    html: `<!doctype html><html><head><meta charset="utf-8"><title>Simulateur</title><style>body{margin:0;background:#0e0e14;color:#f3ead4;font-family:'JetBrains Mono',monospace;padding:14px;}h3{color:#ffd24a;margin:0 0 8px;}textarea{width:100%;height:200px;background:#1a140d;color:#f3ead4;border:2px solid #ffd24a;border-radius:4px;padding:8px;font-family:inherit;font-size:12px;}button{margin-top:8px;background:#e63412;color:#fff;border:2px solid #fff;padding:6px 14px;cursor:pointer;border-radius:4px;font-family:inherit;font-weight:700;}pre{background:#000;padding:10px;border:1px solid #ffd24a;max-height:180px;overflow:auto;margin-top:8px;white-space:pre-wrap;}</style></head><body><h3>🐍 Éditeur Python (simulation)</h3><textarea id="code">mesures = [22, 25, 29, 31, 27]\nmoyenne = sum(mesures) / len(mesures)\nprint(f"Moyenne : {moyenne:.1f} °C")\nif moyenne > 28:\n    print("VENTILATEUR ON")\nelse:\n    print("VENTILATEUR OFF")</textarea><button onclick="run()">▶ Exécuter</button><pre id="out">// sortie ici</pre><script>function run(){var code=document.getElementById('code').value;var out=document.getElementById('out');out.textContent='';try{/* micro-interprète f-string + if/else + print + sum + len + max + min */ var lines=code.split(/\\n/);var vars={};function evalExpr(e){e=e.trim();if(/^-?\\d+(\\.\\d+)?$/.test(e))return parseFloat(e);if(e.startsWith('[')&&e.endsWith(']'))return e.slice(1,-1).split(',').map(x=>evalExpr(x.trim()));if(/^sum\\((.+)\\)$/.test(e)){var m=e.match(/^sum\\((.+)\\)$/);var v=evalExpr(m[1]);return v.reduce((a,b)=>a+b,0);}if(/^len\\((.+)\\)$/.test(e)){var m=e.match(/^len\\((.+)\\)$/);var v=evalExpr(m[1]);return v.length;}if(/^max\\((.+)\\)$/.test(e)){var m=e.match(/^max\\((.+)\\)$/);var v=evalExpr(m[1]);return Math.max.apply(null,v);}if(/^min\\((.+)\\)$/.test(e)){var m=e.match(/^min\\((.+)\\)$/);var v=evalExpr(m[1]);return Math.min.apply(null,v);}if(vars[e]!==undefined)return vars[e];try{return Function('vars','with(vars){return '+e+'}')(vars);}catch(err){return e;}}function fstring(s){return s.replace(/\\{([^{}:]+)(:[^}]+)?\\}/g,function(_,expr,fmt){var v=evalExpr(expr);if(fmt&&/\\.(\\d+)f/.test(fmt)){var d=parseInt(fmt.match(/\\.(\\d+)f/)[1]);return Number(v).toFixed(d);}return v;});}var i=0;while(i<lines.length){var l=lines[i];var t=l.replace(/\\s+$/,'');if(!t.trim()){i++;continue;}var ind=(l.match(/^(\\s*)/)[1]||'').length;var ts=t.trimStart();if(/^#/.test(ts)){i++;continue;}var mAssign=ts.match(/^([a-zA-Z_]\\w*)\\s*=\\s*(.+)$/);var mPrint=ts.match(/^print\\((.+)\\)$/);var mIf=ts.match(/^if\\s+(.+):$/);var mElif=ts.match(/^elif\\s+(.+):$/);var mElse=ts.match(/^else:$/);if(mPrint){var arg=mPrint[1].trim();var s;if(arg.startsWith('f"')||arg.startsWith("f'")){s=fstring(arg.slice(2,-1));}else if(arg.startsWith('"')||arg.startsWith("'")){s=arg.slice(1,-1);}else{s=String(evalExpr(arg));}out.textContent+=s+'\\n';i++;}else if(mAssign){vars[mAssign[1]]=evalExpr(mAssign[2]);i++;}else if(mIf||mElif||mElse){var cond=mIf?evalExpr(mIf[1]):(mElif?evalExpr(mElif[1]):true);var block=[];var j=i+1;while(j<lines.length&&((lines[j].match(/^(\\s*)/)[1]||'').length>ind||!lines[j].trim())){block.push(lines[j]);j++;}if(cond){var subcode=block.map(x=>x.slice(ind+4)).join('\\n');/* récursion */out.textContent+='';var saved=document.getElementById('code').value;document.getElementById('code').value=subcode;run();document.getElementById('code').value=saved;}i=j;while(i<lines.length){var mm=lines[i].trimStart();if(mm.match(/^(elif|else)/)){i++;var blk=[];while(i<lines.length&&((lines[i].match(/^(\\s*)/)[1]||'').length>ind||!lines[i].trim())){blk.push(lines[i]);i++;}}else break;}}else{out.textContent+='// ignoré: '+ts+'\\n';i++;}}}catch(err){out.textContent='Erreur: '+err.message;}}<\/script></body></html>`,
  },
}))

// ============================================================
// RÉSEAUX
// ============================================================
items.push(mkCours(s_reseau.id, 'Modèle OSI et TCP/IP',
`## Modèles en couches

### Modèle OSI (7 couches, théorique)
| # | Couche | Rôle | Exemples |
|---|---|---|---|
| 7 | Application | dialogue app | HTTP, FTP, SMTP, DNS |
| 6 | Présentation | encodage, chiffrement | TLS, ASCII, JPEG |
| 5 | Session | gestion sessions | NetBIOS, RPC |
| 4 | Transport | fiabilité | TCP, UDP |
| 3 | Réseau | adressage, routage | IP, ICMP, ARP |
| 2 | Liaison | trames | Ethernet, Wi-Fi (MAC) |
| 1 | Physique | signaux | câble, radio |

### Modèle TCP/IP (4 couches, pratique)
1. **Accès réseau** (OSI 1+2)
2. **Internet** (OSI 3) : IP
3. **Transport** (OSI 4) : TCP, UDP
4. **Application** (OSI 5+6+7)

### Adressage
- **MAC** : 48 bits, ex. \`AA:BB:CC:11:22:33\` (unique par interface)
- **IPv4** : 32 bits, ex. \`192.168.1.10\` + masque \`/24\`
- **IPv6** : 128 bits, ex. \`2001:db8::1\`

### Sous-réseau
\`192.168.1.0/24\` → 256 adresses, masque \`255.255.255.0\`.
- Adresse réseau : \`192.168.1.0\`
- Adresse broadcast : \`192.168.1.255\`
- Hôtes utilisables : \`192.168.1.1\` à \`.254\`

### Ports courants
| Port | Service |
|---|---|
| 22 | SSH |
| 53 | DNS |
| 80 | HTTP |
| 443 | HTTPS |
| 1883 | MQTT |

### Protocoles
- **TCP** : connecté, fiable (web, mail).
- **UDP** : non connecté, rapide (vidéo, jeux, DNS).
- **ICMP** : ping, diagnostic.`))

items.push(mkQuiz(s_reseau.id, 'Quiz · Réseaux IP', [
  { q: 'L\'adresse MAC appartient à quelle couche OSI ?', choices: ['Application', 'Réseau', 'Liaison', 'Transport'], correct: 2, explain: 'MAC = couche 2 (liaison de données).' },
  { q: 'Port standard HTTPS ?', choices: ['80', '21', '443', '25'], correct: 2, explain: 'HTTPS utilise le port TCP 443.' },
  { q: 'Quel protocole est sans connexion ?', choices: ['TCP', 'UDP', 'HTTPS', 'FTP'], correct: 1, explain: 'UDP n\'établit pas de connexion.' },
  { q: 'Dans 192.168.1.10/24, combien d\'hôtes utilisables ?', choices: ['254', '255', '256', '253'], correct: 0, explain: '2^8 - 2 = 254 (on retire réseau et broadcast).' },
  { q: 'Quel service résout un nom de domaine en IP ?', choices: ['DHCP', 'DNS', 'HTTP', 'ICMP'], correct: 1, explain: 'DNS = Domain Name System.' },
]))

items.push(mkFiche(s_reseau.id, 'Fiche · Protocoles clés', [
  { q: 'HTTP', r: 'Port 80, TCP, transfert web non chiffré' },
  { q: 'HTTPS', r: 'Port 443, TCP, HTTP + TLS (chiffré)' },
  { q: 'SSH', r: 'Port 22, TCP, accès distant sécurisé' },
  { q: 'DNS', r: 'Port 53, UDP (majoritairement), résolution de noms' },
  { q: 'MQTT', r: 'Port 1883 (ou 8883 TLS), publish/subscribe IoT' },
  { q: 'FTP', r: 'Port 21 (contrôle) + 20 (data), transfert fichiers' },
  { q: 'DHCP', r: 'Attribution automatique d\'IP sur un LAN' },
  { q: 'ICMP', r: 'Protocole de diagnostic (ping, traceroute)' },
], {
  label: 'Réseau',
  children: [
    { label: 'OSI', children: [{ label: 'Couches 1 à 7' }, { label: 'Rôles' }] },
    { label: 'TCP/IP', children: [{ label: 'TCP' }, { label: 'UDP' }, { label: 'IP' }] },
    { label: 'Services', children: [{ label: 'HTTP(S)' }, { label: 'DNS' }, { label: 'DHCP' }] },
    { label: 'IoT', children: [{ label: 'MQTT' }, { label: 'CoAP' }] },
  ],
}))

// ============================================================
// MICROCONTRÔLEURS
// ============================================================
items.push(mkCours(s_micro.id, 'Arduino : les bases',
`## Architecture Arduino

Un microcontrôleur Arduino (ATmega328P, ESP32…) possède :
- Un **CPU** exécutant un programme.
- De la **mémoire Flash** (code) et **SRAM** (variables) et **EEPROM** (persistant).
- Des **broches GPIO** (numériques) configurables en entrée ou sortie.
- Des **ADC** (convertisseurs analogique-numérique) sur certaines broches.
- Des **bus** I2C, SPI, UART.

### Structure d'un programme
\`\`\`cpp
void setup() {
  Serial.begin(9600);
  pinMode(13, OUTPUT);
  pinMode(2, INPUT_PULLUP);
}

void loop() {
  if (digitalRead(2) == LOW) {
    digitalWrite(13, HIGH);  // LED ON
  } else {
    digitalWrite(13, LOW);
  }
  delay(100);
}
\`\`\`

### Fonctions essentielles
- \`pinMode(pin, OUTPUT/INPUT/INPUT_PULLUP)\` : configure la broche.
- \`digitalWrite(pin, HIGH/LOW)\` : force un état.
- \`digitalRead(pin)\` : lit un état (0/1).
- \`analogRead(pin)\` : lit une tension (0–1023 sur 5 V).
- \`analogWrite(pin, 0–255)\` : PWM (simule une sortie analogique).
- \`millis()\` : horloge ms.
- \`Serial.print(...)\` : debug via USB.

### PWM (Pulse Width Modulation)
Modulation de largeur d'impulsion → gradation LED, pilotage moteur.
- Période fixe (ex. 2 ms), rapport cyclique variable (0–100 %).

### ADC
10 bits → valeur 0–1023.
Conversion tension : \`V = (analogRead(A0) / 1023) * 5.0\`

### Capteurs courants
- **Thermistance** : résistance variable, lecture via pont diviseur.
- **DHT11/DHT22** : numérique, lib dédiée.
- **Ultrason HC-SR04** : pulseIn() pour mesurer la distance.`))

items.push(mkQuiz(s_micro.id, 'Quiz · Arduino', [
  { q: 'Quelle fonction configure le mode d\'une broche ?', choices: ['setPin()', 'pinMode()', 'digitalWrite()', 'init()'], correct: 1, explain: 'pinMode(pin, mode) dans setup().' },
  { q: 'Résolution de l\'ADC Arduino Uno ?', choices: ['8 bits', '10 bits', '12 bits', '16 bits'], correct: 1, explain: 'ADC 10 bits → 0 à 1023.' },
  { q: 'analogWrite(9, 127) produit…', choices: ['une tension de 2.5V analogique', 'un signal PWM 50%', 'une lecture capteur', 'rien'], correct: 1, explain: 'PWM à 50% de rapport cyclique.' },
  { q: 'INPUT_PULLUP active…', choices: ['une LED', 'une résistance interne à 5V', 'la masse', 'une sortie'], correct: 1, explain: 'Pull-up interne, bouton actif à LOW.' },
  { q: 'Quel bus utilise SDA et SCL ?', choices: ['UART', 'SPI', 'I2C', 'CAN'], correct: 2, explain: 'I2C = SDA (data) + SCL (clock).' },
]))

// ============================================================
// SIGNAL / ACQUISITION
// ============================================================
items.push(mkCours(s_signal.id, 'Acquisition analogique-numérique',
`## Échantillonnage d'un signal

Un signal **analogique** continu doit être converti en valeurs numériques discrètes par un **ADC** (Convertisseur Analogique-Numérique).

### Théorème de Shannon
Pour reconstruire un signal de fréquence max $f_{max}$, il faut échantillonner à :
$$f_e \\geq 2 f_{max}$$

Sinon : **repliement** (aliasing).

### Quantification
Un ADC $N$ bits propose $2^N$ niveaux.
- 8 bits → 256 niveaux
- 10 bits (Arduino) → 1024 niveaux
- 12 bits (ESP32) → 4096 niveaux

Résolution en tension : $\\Delta V = V_{ref} / 2^N$.
Exemple : $V_{ref} = 5V$, 10 bits → $\\Delta V \\approx 4{,}88\\ mV$.

### Chaîne d'acquisition
1. **Capteur** : transforme grandeur physique en tension.
2. **Conditionnement** : amplifier, filtrer, décaler (pont diviseur, AOP).
3. **Filtre anti-repliement** : passe-bas en amont de l'ADC.
4. **ADC** : échantillonnage + quantification.
5. **Traitement** : moyennage, FFT, seuil.

### Bruits et précautions
- **Bruit thermique** : réduire par moyennage.
- **Parasites HF** : filtre passe-bas.
- **Offset** : soustraire la valeur à vide.

### Exemple
Thermistance + pont diviseur → Arduino \`analogRead(A0)\` → conversion en °C via formule de Steinhart-Hart.`))

items.push(mkQuiz(s_signal.id, 'Quiz · Signal', [
  { q: 'Théorème de Shannon : fe doit être au moins…', choices: ['fmax', '2 · fmax', 'fmax / 2', '10 · fmax'], correct: 1, explain: 'fe ≥ 2·fmax pour éviter le repliement.' },
  { q: 'Un ADC 12 bits propose combien de niveaux ?', choices: ['256', '1024', '4096', '65536'], correct: 2, explain: '2^12 = 4096.' },
  { q: 'Le filtre anti-repliement est un filtre…', choices: ['passe-haut', 'passe-bas', 'passe-bande', 'coupe-bande'], correct: 1, explain: 'On coupe les fréquences > fe/2.' },
  { q: 'Résolution en tension d\'un ADC 10 bits alimenté en 5 V ?', choices: ['4.88 mV', '48.8 mV', '0.488 V', '5 mV'], correct: 0, explain: '5 V / 1024 ≈ 4.88 mV.' },
  { q: 'Pour réduire le bruit thermique…', choices: ['on augmente fe', 'on moyenne plusieurs mesures', 'on utilise un coupe-bande', 'on réduit la résolution'], correct: 1, explain: 'Moyennage diminue le bruit aléatoire.' },
]))

// ============================================================
// BASES DE DONNÉES
// ============================================================
items.push(mkCours(s_bdd.id, 'SQL : requêtes essentielles',
`## Requêtes SQL de base

### SELECT
\`\`\`sql
SELECT nom, prenom FROM eleves WHERE classe = 'TSI2D';
SELECT * FROM notes WHERE matiere = 'SIN' ORDER BY note DESC LIMIT 5;
\`\`\`

### Opérateurs
| Opérateur | Usage |
|---|---|
| \`=\`, \`<>\` | égal, différent |
| \`<\`, \`>\`, \`<=\`, \`>=\` | comparaison |
| \`LIKE 'A%'\` | commence par A |
| \`BETWEEN 10 AND 15\` | intervalle |
| \`IN ('A', 'B')\` | appartenance |
| \`IS NULL\` | valeur absente |

### Fonctions d'agrégation
\`\`\`sql
SELECT COUNT(*) FROM eleves;
SELECT AVG(note) FROM notes WHERE matiere = 'Math';
SELECT MAX(note), MIN(note) FROM notes;
SELECT classe, COUNT(*) FROM eleves GROUP BY classe;
\`\`\`

### Jointures
\`\`\`sql
SELECT e.nom, n.note, n.matiere
FROM eleves e
INNER JOIN notes n ON e.id = n.eleve_id
WHERE n.note >= 15;
\`\`\`

### Insertion / Mise à jour / Suppression
\`\`\`sql
INSERT INTO eleves (nom, prenom, classe) VALUES ('Dupont', 'Léa', 'TSI2D');
UPDATE eleves SET classe = '1SI2D' WHERE id = 42;
DELETE FROM notes WHERE matiere = 'Latin';
\`\`\`

### Création de table
\`\`\`sql
CREATE TABLE capteurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    valeur REAL,
    horodatage DATETIME DEFAULT CURRENT_TIMESTAMP
);
\`\`\`

### Clés et intégrité
- **Clé primaire** (PRIMARY KEY) : identifiant unique.
- **Clé étrangère** (FOREIGN KEY) : référence une autre table.
- **Contraintes** : NOT NULL, UNIQUE, CHECK.`))

items.push(mkQuiz(s_bdd.id, 'Quiz · SQL', [
  { q: 'Pour compter les lignes, on utilise…', choices: ['LEN()', 'SIZE()', 'COUNT(*)', 'TOTAL()'], correct: 2, explain: 'COUNT(*) est la fonction d\'agrégation.' },
  { q: 'Quelle clause filtre les lignes ?', choices: ['FILTER', 'WHERE', 'IF', 'HAVING'], correct: 1, explain: 'WHERE filtre avant agrégation. HAVING après GROUP BY.' },
  { q: 'Pour relier 2 tables par une colonne commune, on utilise…', choices: ['INNER JOIN', 'MERGE', 'COMBINE', 'LINK'], correct: 0, explain: 'INNER JOIN est la jointure SQL standard.' },
  { q: 'Pour trier par ordre croissant…', choices: ['SORT BY', 'ORDER BY … ASC', 'GROUP BY', 'INDEX BY'], correct: 1, explain: 'ORDER BY col ASC (ou DESC pour descendant).' },
  { q: 'Une clé primaire est…', choices: ['toujours un entier', 'unique et non nulle', 'optionnelle', 'partagée'], correct: 1, explain: 'Clé primaire = identifie chaque ligne de manière unique.' },
]))

// ============================================================
// WEB / IHM
// ============================================================
items.push(mkCours(s_web.id, 'HTML / CSS / JS pour IHM embarquée',
`## Architecture d'une IHM web

Une IHM (Interface Homme-Machine) moderne en STI2D SIN est souvent une page web servie par un microcontrôleur (ESP32) ou un Raspberry Pi.

### HTML — structure
\`\`\`html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Dashboard capteur</title>
</head>
<body>
  <h1>Température</h1>
  <div id="valeur">—</div>
  <button onclick="refresh()">Rafraîchir</button>
</body>
</html>
\`\`\`

### CSS — style
\`\`\`css
body { font-family: sans-serif; background: #111; color: #fff; }
h1 { color: #ffd24a; }
#valeur { font-size: 48px; font-weight: bold; color: #e63412; }
\`\`\`

### JavaScript — comportement
\`\`\`javascript
async function refresh() {
  const r = await fetch('/api/temp');
  const data = await r.json();
  document.getElementById('valeur').textContent = data.celsius + '°C';
}
setInterval(refresh, 1000);
\`\`\`

### API REST côté ESP32
- \`GET /api/temp\` → \`{"celsius": 23.4}\`
- \`POST /api/led\` avec body \`{"on": true}\` → allume la LED.

### WebSocket (temps réel)
- Push du serveur vers le client dès qu'une mesure arrive.
- Pas de polling → léger et réactif.

### MQTT (IoT)
Protocole publish/subscribe, idéal pour des dizaines de capteurs sur un broker (Mosquitto).`))

items.push(mkQuiz(s_web.id, 'Quiz · Web IHM', [
  { q: 'Quelle balise HTML marque le titre principal ?', choices: ['<h1>', '<title>', '<head>', '<header>'], correct: 0, explain: '<h1> est le titre de plus haut niveau dans le body.' },
  { q: 'Quel protocole est optimal pour l\'IoT publish/subscribe ?', choices: ['HTTP', 'MQTT', 'FTP', 'TCP'], correct: 1, explain: 'MQTT = publish/subscribe léger, idéal IoT.' },
  { q: 'fetch() retourne…', choices: ['une String', 'une Promise', 'un Object', 'un Array'], correct: 1, explain: 'fetch retourne une Promise qu\'on await.' },
  { q: 'Pour du temps réel bidirectionnel on utilise…', choices: ['AJAX', 'WebSocket', 'DNS', 'RSS'], correct: 1, explain: 'WebSocket = canal bidirectionnel persistant.' },
  { q: 'setInterval(fn, 1000) exécute fn…', choices: ['une fois', 'toutes les secondes', 'toutes les minutes', 'au chargement'], correct: 1, explain: '1000 ms = 1 s.' },
]))

// ============================================================
// SÉCURITÉ / CODAGE
// ============================================================
items.push(mkCours(s_secu.id, 'Codage de l\'information',
`## Systèmes de numération

### Binaire (base 2)
Chiffres : 0 et 1. Un bit = une position.
Un octet = 8 bits → 256 valeurs (0 à 255).

### Conversion décimale → binaire
Méthode des divisions successives par 2 :
- 25 / 2 = 12 reste 1
- 12 / 2 = 6 reste 0
- 6 / 2 = 3 reste 0
- 3 / 2 = 1 reste 1
- 1 / 2 = 0 reste 1
→ Lire les restes de bas en haut : **11001**.

### Hexadécimal (base 16)
Chiffres : 0–9, A–F.
Chaque chiffre hex = 4 bits.
\`0xFF = 255 = 11111111\`.

### ASCII et UTF-8
- **ASCII** : 128 caractères (anglais) sur 7 bits.
- **UTF-8** : extension variable 1 à 4 octets, compatible ASCII, gère tous les caractères Unicode.

### Codage texte → bits
"Hi" → 'H' = 72 = 01001000, 'i' = 105 = 01101001.

### Chiffrement symétrique vs asymétrique
- **Symétrique** (AES) : une seule clé pour chiffrer et déchiffrer. Rapide. Problème : transmettre la clé.
- **Asymétrique** (RSA) : paire clé publique/privée. La publique chiffre, seule la privée déchiffre. Lent.
- **Hybride** (TLS/HTTPS) : RSA échange une clé AES, puis AES chiffre les données.

### Fonctions de hachage
- Entrée : message quelconque. Sortie : condensat de taille fixe (SHA-256 → 256 bits).
- Irréversibles, détectent l'intégrité.
- Mots de passe : bcrypt, argon2, avec **sel**.`))

items.push(mkQuiz(s_secu.id, 'Quiz · Codage & Crypto', [
  { q: '0b1010 en décimal ?', choices: ['5', '8', '10', '12'], correct: 2, explain: '8+0+2+0 = 10.' },
  { q: '0xFF vaut…', choices: ['15', '128', '255', '256'], correct: 2, explain: 'F=15, FF = 15·16 + 15 = 255.' },
  { q: 'UTF-8 code un caractère sur…', choices: ['toujours 1 octet', 'toujours 2 octets', 'toujours 4 octets', '1 à 4 octets'], correct: 3, explain: 'UTF-8 est variable (1 à 4 octets).' },
  { q: 'AES est un chiffrement…', choices: ['symétrique', 'asymétrique', 'de hachage', 'de compression'], correct: 0, explain: 'AES utilise une clé secrète unique.' },
  { q: 'Une fonction de hachage est…', choices: ['réversible avec la clé', 'irréversible et déterministe', 'aléatoire', 'variable'], correct: 1, explain: 'Hash = condensat irréversible.' },
]))

// ============================================================
// FRANÇAIS
// ============================================================
items.push(mkCours(s_fr.id, 'Méthodologie de la dissertation',
`## Dissertation littéraire

### Les trois étapes
1. **Analyser le sujet** : repérer les mots-clés, reformuler.
2. **Élaborer le plan** en deux ou trois parties (thèse, antithèse, synthèse) ou progressif.
3. **Rédiger** en soignant l'introduction, les transitions et la conclusion.

### L'introduction
- **Amorce** : citation, contexte historique, fait culturel.
- **Présentation du sujet / de l'œuvre** : auteur, titre, époque, courant.
- **Problématique** : question posée sous forme interrogative.
- **Annonce du plan** : sans lourdeur (I. … II. … III. …).

### Le développement
- Chaque partie = une idée principale.
- Chaque sous-partie = un argument + exemple précis (citation, référence).
- Transitions fluides entre parties.

### La conclusion
- **Bilan** des arguments.
- **Ouverture** vers une autre œuvre ou une réflexion contemporaine.

### Conseils pratiques
- Brouillon indispensable (20 min).
- Utiliser des connecteurs logiques (d'une part, toutefois, en outre).
- Varier le vocabulaire.
- Orthographe et syntaxe : relire 5 min en fin.

### Exemple de problématique
Sujet : "La poésie doit-elle avoir un but ?"
- Problématique : "Dans quelle mesure la poésie est-elle une forme d'art autonome plutôt qu'un outil au service d'une cause ?"
- Plan : I. La poésie engagée. II. La poésie pour la poésie (art pour art). III. Synthèse : la fonction plurielle de la poésie.`))

// ============================================================
// PHILO
// ============================================================
items.push(mkCours(s_philo.id, 'Notion : la liberté',
`## La liberté

### Définitions
- **Libre** : qui agit sans contrainte.
- **Liberté** : pouvoir d'agir selon sa volonté.

### Trois types
1. **Liberté naturelle / physique** : absence d'entrave.
2. **Liberté politique / civile** : droits garantis par la loi.
3. **Liberté morale** : autonomie (Kant) — obéir à une loi qu'on s'est donnée à soi-même.

### Le problème du déterminisme
Le principe de causalité semble contredire la liberté :
- **Déterminisme physique** : mon corps suit les lois de la nature.
- **Déterminisme social** (Bourdieu) : le milieu façonne les choix.
- **Déterminisme psychique** (Freud) : l'inconscient guide.

### Sommes-nous libres malgré cela ?
- **Descartes** : liberté de l'esprit par le doute méthodique.
- **Spinoza** : liberté = comprendre la nécessité qui nous traverse.
- **Sartre** : l'homme est "condamné à être libre" (existentialisme).
- **Alain** : "Penser, c'est dire non."

### Liberté et responsabilité
Être libre, c'est pouvoir répondre de ses actes. Sans liberté, pas de morale.

### Citations clés
- "L'homme est né libre, et partout il est dans les fers." — Rousseau
- "Je suis condamné à être libre." — Sartre
- "La liberté consiste à pouvoir faire tout ce qui ne nuit pas à autrui." — DDHC 1789`))

// ============================================================
// HISTOIRE-GÉO
// ============================================================
items.push(mkCours(s_hg.id, 'La mondialisation',
`## La mondialisation : processus et acteurs

### Définition
Mise en relation généralisée des espaces, des sociétés et des économies à l'échelle planétaire.

### Dynamiques
- **Flux** croissants : marchandises (conteneurs), capitaux, informations, personnes.
- **Firmes transnationales (FTN)** : stratégies de production éclatée (fordisme → toyotisme → délocalisations).
- **Division internationale du travail (DIT)** : pays du Nord conçoivent, pays du Sud fabriquent.

### Acteurs
- **États** : politiques économiques, zones de libre-échange (UE, ALENA/USMCA, ASEAN).
- **Organisations internationales** : OMC, FMI, ONU, OMS.
- **FTN** : Apple, Toyota, TotalEnergies, Samsung.
- **ONG** : Greenpeace, Amnesty.

### Centres et périphéries
- **Centres** : Amérique du Nord, Europe occidentale, Asie orientale (Triade).
- **Périphéries intégrées** : BRICS, NPI.
- **Périphéries marginalisées** : Afrique subsaharienne (en partie).

### Critiques et contestations
- **Inégalités** Nord/Sud.
- **Crises environnementales** (GES, biodiversité).
- **Altermondialisme**, Forum social mondial.
- **Démondialisation** post-Covid, repli protectionniste.

### Exemple : chaîne d'un smartphone
Conception (Californie) → composants (Taïwan, Corée) → assemblage (Chine) → distribution mondiale → recyclage/e-déchets (Ghana, Nigeria).`))

// ============================================================
// ANGLAIS
// ============================================================
items.push(mkCours(s_anglais.id, 'Grammaire : prétérit vs present perfect',
`## Two confusing tenses

### Simple past (prétérit)
Action **finished** in the past, often with a time marker.
- "I **watched** the movie yesterday."
- "He **went** to Paris last summer."

Time markers: yesterday, last week, in 1997, ago, when…

### Present perfect
Past action with a **link to the present**: experience, result, duration up to now.
- "I **have never seen** such a movie." (experience)
- "He **has just finished** his homework." (result)
- "We **have lived** here **for** 5 years / **since** 2020." (duration)

Markers: just, already, yet, ever, never, for, since, so far.

### Quick rule
- If the action is **finished and dated** → simple past.
- If the action has a **present relevance** → present perfect.

### Common mistakes
- ❌ "I have seen him yesterday." → ✅ "I saw him yesterday."
- ❌ "He works here since 2020." → ✅ "He has worked here since 2020."

### Questions
- "Did you go to Tokyo?" (past)
- "Have you ever been to Tokyo?" (experience)

### Practice sentence
"She **[finish]** her project last week and **[not / send]** it yet."
→ finished / has not sent.`))

// ============================================================
// EMC
// ============================================================
items.push(mkCours(s_emc.id, 'Démocratie et citoyenneté numérique',
`## Citoyenneté à l'ère numérique

### Droits et devoirs en ligne
- **Liberté d'expression** (art. 11 DDHC), mais limites : diffamation, injure, incitation à la haine.
- **Respect de la vie privée** (RGPD) : consentement, droit à l'effacement.
- **Droit à l'image** : autorisation obligatoire pour diffuser.

### Fake news et désinformation
- Vérifier les sources : 3 sources indépendantes.
- Attention aux **deepfakes** (images / vidéos IA).
- Rôle des **fact-checkers** (Le Monde, AFP Factuel).

### RGPD (Règlement Général sur la Protection des Données)
- Consentement explicite pour la collecte.
- Droit d'accès, de rectification, d'effacement.
- Amendes jusqu'à 4 % du CA mondial.

### Traces numériques
Chaque clic laisse une trace. Réfléchir à son **e-réputation** avant de publier.

### Cyberharcèlement
Délit puni par le Code pénal. Numéro d'écoute : 3018 (France).

### Inclusion et fracture numérique
- Accès inégal : zones rurales, seniors, précarité.
- Accessibilité obligatoire des services publics (RGAA).`))

// ============================================================
// Grand Oral
// ============================================================
items.push(mkCours(s_oral.id, 'Méthodologie du Grand Oral',
`## Le Grand Oral en terminale

### Format
- Coef 14 en STI2D.
- 20 min : 5 min présentation + 10 min échange + 5 min projet d'orientation.
- Deux questions préparées avec l'enseignant·e.

### Choisir ses questions
- Une question par enseignement de spécialité.
- Lien avec un enjeu actuel, une application concrète, un projet perso.
- Ex. STI2D SIN : "Comment un drone autonome peut-il cartographier une zone inaccessible ?"

### Les 5 minutes de présentation
1. **Accroche** (20 s) : fait marquant, chiffre choc.
2. **Problématique** clairement énoncée.
3. **Plan** annoncé (II–III parties).
4. **Développement** : arguments + exemples concrets + démonstrations courtes.
5. **Conclusion** : réponse à la problématique + ouverture.

### Posture
- Debout, regard vers le jury, mains libres.
- Ton vivant, pas récité.
- Vocabulaire précis mais accessible.
- Rythme : 150 mots / minute.

### Les 10 minutes d'échange
Le jury interroge sur :
- Les notions évoquées (maîtrise disciplinaire).
- La méthode, les choix.
- Des prolongements.

### Les 5 dernières minutes
Présenter **son projet d'orientation** : filière visée, motivations, lien avec la question traitée.

### Conseils pratiques
- S'entraîner **à voix haute** devant quelqu'un.
- Se filmer pour corriger tics et posture.
- Préparer une **fiche mémo** (mais lecture interdite le jour J).
- Anticiper 5 questions types et leurs réponses.`))

// ============================================================
// PROJET technique
// ============================================================
items.push(mkCours(s_proj.id, 'Gestion de projet : méthode et jalons',
`## Conduite de projet technique SIN

### Les étapes classiques (cycle en V)
1. **Analyse du besoin** : cahier des charges, diagramme SysML des exigences.
2. **Conception** : solutions candidates, choix argumenté.
3. **Réalisation** : prototype, code, câblage.
4. **Validation** : tests unitaires et d'intégration.
5. **Mise en service** : documentation, formation.

### Méthodes
- **Cascade** : étapes séquentielles, classique.
- **Agile / Scrum** : itérations courtes (sprints), rétrospectives.
- **Kanban** : flux tiré, colonnes "À faire / En cours / Fait".

### Outils
- **Gantt** : planning jalonné.
- **SysML** : modélisation du système (blocs, exigences, cas d'usage, activités).
- **Git** : versionnage de code, travail collaboratif.
- **Tableau Kanban** (Trello, GitHub Projects).

### Rôles dans une équipe
- **Chef de projet** : pilotage, jalons.
- **Architecte** : conception technique.
- **Développeur** : code.
- **Intégrateur** : assemble les briques.
- **Testeur** : validation.

### Jalons et livrables
- Revue de conception à mi-parcours.
- Démonstration intermédiaire.
- Dossier final + soutenance.

### Grille d'évaluation STI2D
- Qualité technique (20 %).
- Autonomie / initiative (20 %).
- Communication (20 %).
- Respect du cahier des charges (20 %).
- Démarche de projet (20 %).`))

// ============================================================
// Build final category
// ============================================================

export const BAC_STI2D_SIN_ID = 'cat-bac-sti2d-sin'

export function buildBacSTI2DSINCategory(): Category {
  const subCategories: SubCategory[] = [
    s_math, s_phys, s_2i2d, s_algo, s_reseau, s_micro, s_signal, s_bdd, s_web, s_secu,
    s_fr, s_philo, s_hg, s_anglais, s_emc, s_eps, s_oral, s_proj,
  ]
  return {
    id: BAC_STI2D_SIN_ID,
    name: 'BAC STI2D · Spécialité SIN',
    description: "Programme complet préchargé : tronc commun général + tronc commun technologique + spécialité SIN. Cours, quiz, fiches et exercices pour tout réviser.",
    emoji: '🎓',
    tone: '#1f4ec9',
    subCategories,
    items,
    createdByAI: false,
    createdAt: now(),
  }
}
