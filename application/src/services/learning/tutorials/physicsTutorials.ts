import type { Tutorial } from '../tutorialEngine.ts'

export const physicsTutorials: Tutorial[] = [
  {
    id: 'phys-pendulum-01',
    lab: 'physics',
    title: 'Le pendule simple : oscillations harmoniques',
    summary: "Découvre la période d'un pendule, son indépendance vis-à-vis de la masse et le régime des petites oscillations.",
    difficulty: 'debutant',
    durationMin: 12,
    xpReward: 60,
    tags: ['mécanique', 'oscillations', 'énergie'],
    steps: [
      {
        id: 'intro',
        title: 'Définition du pendule simple',
        objective: 'Identifier les ingrédients physiques du pendule.',
        body:
          'Un **pendule simple** est une masse ponctuelle $m$ suspendue à un fil inextensible de longueur $L$, sans frottement. Seules deux forces agissent : le **poids** $mg$ et la **tension** du fil.\n\nDans le plan vertical, l’angle $\\theta$ par rapport à la verticale suffit à décrire le système.',
        media: [
          { kind: 'formula', tex: '\\ddot{\\theta} + \\frac{g}{L}\\sin\\theta = 0', caption: 'Équation du mouvement exacte (sans frottement).' },
        ],
      },
      {
        id: 'small-angles',
        title: 'Approximation des petits angles',
        objective: "Voir quand sin(θ) ≈ θ est valable.",
        body:
          "Pour $|\\theta| < 15°$, on a $\\sin\\theta \\approx \\theta$ avec moins de 1 % d'erreur. L'équation devient alors **linéaire** :",
        media: [
          { kind: 'formula', tex: '\\ddot{\\theta} + \\omega_0^{2}\\,\\theta = 0, \\quad \\omega_0 = \\sqrt{\\tfrac{g}{L}}' },
          { kind: 'table', headers: ['θ (°)', 'sin θ', 'erreur'], rows: [['5', '0.0872', '0.13 %'], ['15', '0.2588', '1.15 %'], ['30', '0.5000', '4.5 %'], ['60', '0.8660', '17 %']] },
        ],
        quiz: {
          question: "À partir de quel angle l'approximation sin(θ) ≈ θ introduit-elle plus de 1 % d'erreur ?",
          choices: [
            { id: 'a', label: '5°', correct: false, explanation: 'Non, à 5° l’erreur reste sous 0.2 %.' },
            { id: 'b', label: '15°', correct: true, explanation: 'Exact, c’est la limite classique pour rester linéaire.' },
            { id: 'c', label: '45°', correct: false, explanation: "45° induit ~10 % d'erreur, bien trop." },
            { id: 'd', label: '90°', correct: false, explanation: 'À 90° sin θ = 1 alors que θ ≈ 1.57 rad.' },
          ],
          hint: 'Regarde la colonne erreur du tableau.',
        },
      },
      {
        id: 'period',
        title: 'Période des petites oscillations',
        objective: 'Retrouver la formule de la période.',
        body:
          'La période **ne dépend pas de la masse** ni de l’amplitude (pour petits angles). Elle se déduit de ω₀ :',
        media: [
          { kind: 'formula', tex: 'T = 2\\pi\\sqrt{\\frac{L}{g}}' },
          { kind: 'quote', text: "Pendant une messe à la cathédrale de Pise, Galilée observa qu’un lustre oscillant gardait la même période — indépendamment de l’amplitude.", author: 'Physique classique, 1581' },
        ],
        quiz: {
          question: 'Si on double la longueur L, la période T est multipliée par…',
          choices: [
            { id: 'a', label: '2', correct: false, explanation: 'Non, la dépendance est en racine.' },
            { id: 'b', label: '√2 ≈ 1.41', correct: true, explanation: 'Oui, T ∝ √L.' },
            { id: 'c', label: '1/2', correct: false, explanation: 'T augmente avec L, pas l’inverse.' },
            { id: 'd', label: '4', correct: false, explanation: 'Ce serait T ∝ L.' },
          ],
        },
      },
      {
        id: 'energy',
        title: 'Énergie mécanique et conservation',
        objective: 'Identifier les transferts entre Ep et Ec.',
        body:
          'En l’absence de frottement, l’énergie mécanique $E = E_c + E_p$ est **constante**. À l’amplitude maximale, toute l’énergie est potentielle ; au passage à la verticale, elle est entièrement cinétique.',
        media: [
          { kind: 'formula', tex: 'E = \\tfrac{1}{2}mL^{2}\\dot{\\theta}^{2} + mgL(1-\\cos\\theta)' },
        ],
      },
      {
        id: 'damping',
        title: 'Amortissement et régimes',
        objective: 'Classer sous-critique, critique, sur-critique.',
        body:
          "Avec un frottement fluide $-b\\,\\dot\\theta$, trois régimes apparaissent selon le facteur d'amortissement $\\zeta = b/(2\\sqrt{k m_{eq}})$ :\n\n- $\\zeta < 1$ : **pseudo-périodique** (oscillations qui décroissent)\n- $\\zeta = 1$ : **critique** (retour le plus rapide sans dépassement)\n- $\\zeta > 1$ : **apériodique**",
        quiz: {
          question: 'Quel régime retourne le plus vite à l’équilibre sans dépassement ?',
          choices: [
            { id: 'a', label: 'Pseudo-périodique', correct: false, explanation: 'Il dépasse puis revient, donc plus lent.' },
            { id: 'b', label: 'Critique (ζ = 1)', correct: true, explanation: 'Classique : amortissement optimal.' },
            { id: 'c', label: 'Apériodique (ζ > 1)', correct: false, explanation: 'Il rampe lentement vers l’équilibre.' },
          ],
        },
      },
      {
        id: 'conclusion',
        title: 'À retenir',
        body:
          '- L’équation non-linéaire $\\ddot\\theta + (g/L)\\sin\\theta = 0$\n- Période $T = 2\\pi\\sqrt{L/g}$ pour petits angles\n- Indépendance de $m$\n- Trois régimes d’amortissement',
      },
    ],
  },
  {
    id: 'phys-projectile-01',
    lab: 'physics',
    title: 'Tir parabolique et portée maximale',
    summary: 'Décompose le mouvement en deux axes, calcule la portée et la hauteur max.',
    difficulty: 'debutant',
    durationMin: 10,
    xpReward: 55,
    tags: ['cinématique', 'gravité'],
    steps: [
      {
        id: 'decomp',
        title: 'Décomposition du vecteur vitesse',
        body:
          "Le projectile lancé avec vitesse $v_0$ sous un angle $\\theta$ a deux composantes **indépendantes** :",
        media: [
          { kind: 'formula', tex: 'v_{0x} = v_0\\cos\\theta, \\quad v_{0y} = v_0\\sin\\theta' },
        ],
      },
      {
        id: 'equations',
        title: 'Équations horaires',
        body:
          'Sans frottement, la gravité n’agit que sur l’axe vertical :\n\n- $x(t) = v_0\\cos\\theta \\cdot t$\n- $y(t) = v_0\\sin\\theta \\cdot t - \\tfrac{1}{2} g t^{2}$',
      },
      {
        id: 'range',
        title: 'Portée et angle optimal',
        body:
          "La portée est la distance horizontale quand $y = 0$ à nouveau :",
        media: [
          { kind: 'formula', tex: 'R = \\frac{v_0^{2}\\sin(2\\theta)}{g}' },
        ],
        quiz: {
          question: 'Quel angle maximise la portée sur un terrain plat (sans frottement) ?',
          choices: [
            { id: 'a', label: '30°', correct: false },
            { id: 'b', label: '45°', correct: true, explanation: 'sin(2·45°) = 1, maximum.' },
            { id: 'c', label: '60°', correct: false, explanation: 'Trop haut, trop court en distance.' },
            { id: 'd', label: '90°', correct: false, explanation: 'C’est une chute verticale, portée nulle.' },
          ],
        },
      },
      {
        id: 'hmax',
        title: 'Hauteur maximale',
        body:
          "Au sommet, $v_y = 0$. On en déduit :",
        media: [
          { kind: 'formula', tex: 'h_{max} = \\frac{v_0^{2}\\sin^{2}\\theta}{2g}' },
        ],
      },
      {
        id: 'drag',
        title: 'Effet du frottement de l’air',
        body:
          "En réalité, la traînée $F = -\\tfrac{1}{2}\\rho C_d S v^{2}$ asymétrise la trajectoire : la descente est plus courte que la montée. L’angle optimal descend alors autour de 40°–42°.",
        quiz: {
          question: 'Avec frottement, l’angle optimal est…',
          choices: [
            { id: 'a', label: 'Plus grand que 45°', correct: false },
            { id: 'b', label: 'Plus petit que 45°', correct: true, explanation: 'Typiquement 40°.' },
            { id: 'c', label: 'Toujours 45°', correct: false },
          ],
        },
      },
    ],
  },
  {
    id: 'phys-spring-01',
    lab: 'physics',
    title: 'Loi de Hooke et oscillateur harmonique',
    summary: 'Comprends le ressort, sa pulsation propre et la notion de phase.',
    difficulty: 'debutant',
    durationMin: 10,
    xpReward: 55,
    tags: ['oscillations', 'énergie'],
    steps: [
      {
        id: 'hooke',
        title: 'Loi de Hooke',
        body: "Un ressort idéal exerce une force **de rappel** proportionnelle à l’élongation $x$.",
        media: [{ kind: 'formula', tex: 'F = -k\\,x' }],
      },
      {
        id: 'eom',
        title: 'Équation du mouvement',
        body: "Newton : $m\\ddot x = -kx$, donc :",
        media: [{ kind: 'formula', tex: '\\ddot x + \\omega_0^{2} x = 0, \\quad \\omega_0 = \\sqrt{k/m}' }],
        quiz: {
          question: 'Si on double la masse m, la pulsation ω₀ devient…',
          choices: [
            { id: 'a', label: '×2', correct: false },
            { id: 'b', label: '×√2', correct: false },
            { id: 'c', label: '÷√2', correct: true, explanation: 'ω₀ ∝ 1/√m.' },
            { id: 'd', label: '÷2', correct: false },
          ],
        },
      },
      {
        id: 'solution',
        title: 'Solution sinusoïdale',
        body: "La solution générale est :",
        media: [{ kind: 'formula', tex: 'x(t) = A\\cos(\\omega_0 t + \\varphi)' }],
      },
      {
        id: 'energy',
        title: 'Énergie totale',
        body: "L’énergie est partagée entre cinétique et potentielle :",
        media: [
          { kind: 'formula', tex: 'E = \\tfrac{1}{2} k A^{2}' },
        ],
      },
      {
        id: 'phase',
        title: 'Diagramme de phase (x, v)',
        body: "Dans le plan $(x, v)$, le point $(x(t), v(t))$ décrit une **ellipse** fermée : c’est la signature d’un système conservatif. Avec amortissement, l’ellipse se contracte en spirale.",
        quiz: {
          question: 'Sur le diagramme de phase, un système non-amorti dessine…',
          choices: [
            { id: 'a', label: 'Une spirale', correct: false },
            { id: 'b', label: 'Une droite', correct: false },
            { id: 'c', label: 'Une ellipse fermée', correct: true, explanation: 'Énergie constante ⇒ trajectoire fermée.' },
          ],
        },
      },
    ],
  },
  {
    id: 'phys-collision-01',
    lab: 'physics',
    title: 'Chocs 1D : conservation de la quantité de mouvement',
    summary: "Distingue choc élastique vs inélastique et applique les lois de conservation.",
    difficulty: 'intermediaire',
    durationMin: 12,
    xpReward: 70,
    tags: ['mécanique', 'conservation'],
    steps: [
      {
        id: 'momentum',
        title: 'La quantité de mouvement',
        body: "$\\vec p = m\\vec v$ : produit masse × vitesse, vecteur. **Conservée** si aucune force extérieure horizontale.",
      },
      {
        id: 'elastic',
        title: 'Choc élastique',
        body: "Énergie cinétique **et** quantité de mouvement conservées. Pour deux corps 1D :",
        media: [
          { kind: 'formula', tex: "v_1' = \\frac{(m_1-m_2)v_1 + 2m_2 v_2}{m_1+m_2}" },
          { kind: 'formula', tex: "v_2' = \\frac{(m_2-m_1)v_2 + 2m_1 v_1}{m_1+m_2}" },
        ],
      },
      {
        id: 'inelastic',
        title: 'Choc parfaitement inélastique',
        body: "Les corps restent collés. Seule la quantité de mouvement est conservée ; une partie de $E_c$ est perdue en chaleur/déformation.",
        media: [{ kind: 'formula', tex: "v' = \\frac{m_1 v_1 + m_2 v_2}{m_1 + m_2}" }],
        quiz: {
          question: 'Dans un choc parfaitement inélastique…',
          choices: [
            { id: 'a', label: 'Ec et p sont conservées', correct: false },
            { id: 'b', label: 'Seule p est conservée', correct: true, explanation: "Ec diminue (déformation, chaleur)." },
            { id: 'c', label: 'Seule Ec est conservée', correct: false },
            { id: 'd', label: 'Rien n’est conservé', correct: false },
          ],
        },
      },
      {
        id: 'balls',
        title: 'Cas particulier : masses égales',
        body: "Si $m_1 = m_2$ et choc élastique : les vitesses **s’échangent**. C’est le principe du pendule de Newton.",
      },
      {
        id: 'examples',
        title: 'Applications',
        body: "- Billard (presque élastique)\n- Crash test (très inélastique)\n- Désintégrations radioactives (conservation stricte)",
      },
    ],
  },
  {
    id: 'phys-orbit-01',
    lab: 'physics',
    title: 'Orbites et lois de Kepler',
    summary: "De la gravitation newtonienne aux trois lois de Kepler.",
    difficulty: 'avance',
    durationMin: 14,
    xpReward: 90,
    tags: ['gravitation', 'mécanique céleste'],
    steps: [
      {
        id: 'newton',
        title: 'La loi de gravitation universelle',
        body: "Newton, 1687 : deux masses s’attirent selon",
        media: [{ kind: 'formula', tex: 'F = G\\frac{m_1 m_2}{r^{2}}, \\quad G \\approx 6.674\\times10^{-11}\\,\\mathrm{N\\,m^{2}/kg^{2}}' }],
      },
      {
        id: 'kepler1',
        title: '1ère loi : orbites elliptiques',
        body: "Les planètes décrivent des **ellipses** dont le Soleil occupe un foyer. L’excentricité mesure l’aplatissement.",
      },
      {
        id: 'kepler2',
        title: '2ème loi : loi des aires',
        body: "Le rayon vecteur Soleil-planète balaye des **aires égales en temps égaux**. Conséquence : la planète va plus vite au périhélie qu’à l’aphélie.",
        quiz: {
          question: 'Où la Terre va-t-elle le plus vite sur son orbite ?',
          choices: [
            { id: 'a', label: 'À l’aphélie (juillet)', correct: false, explanation: 'Au plus loin, la vitesse est minimale.' },
            { id: 'b', label: 'Au périhélie (janvier)', correct: true, explanation: 'Au plus près, vitesse maximale.' },
            { id: 'c', label: 'Aux équinoxes', correct: false },
          ],
        },
      },
      {
        id: 'kepler3',
        title: '3ème loi : T² ∝ a³',
        body: "Le carré de la période est proportionnel au cube du demi-grand axe :",
        media: [{ kind: 'formula', tex: '\\frac{T^{2}}{a^{3}} = \\frac{4\\pi^{2}}{GM}' }],
      },
      {
        id: 'escape',
        title: 'Vitesse de libération',
        body: "Pour échapper à l’attraction d’un corps de masse $M$ à la distance $r$ :",
        media: [{ kind: 'formula', tex: 'v_{lib} = \\sqrt{\\frac{2GM}{r}}' }],
        quiz: {
          question: "Vitesse de libération depuis la surface terrestre (approximative) ?",
          choices: [
            { id: 'a', label: '7,9 km/s', correct: false, explanation: "C'est la vitesse orbitale basse." },
            { id: 'b', label: '11,2 km/s', correct: true, explanation: 'Exact, la vitesse d’évasion terrestre.' },
            { id: 'c', label: '42 km/s', correct: false, explanation: "C'est la vitesse de libération du système solaire depuis la Terre." },
          ],
        },
      },
    ],
  },
]
