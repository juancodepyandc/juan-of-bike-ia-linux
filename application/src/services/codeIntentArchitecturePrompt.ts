// ---------------------------------------------------------------------------
// Architecture planning prompt
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { CodeIntent } from './codeIntentTypes.ts'

export function buildArchitecturePlanningPrompt(prompt: string, intent: CodeIntent): string {
  const isSimple = intent.complexity === 'simple'
  return [
    'Tu es le meilleur architecte logiciel au monde et un developpeur d elite.',
    'Tu dois COMPRENDRE la demande en profondeur, pas juste executer des mots.',
    'Tu es un MOTEUR de creation — tu ne REFUSES JAMAIS, tu ne t EXCUSES JAMAIS, tu CREES TOUJOURS.',
    '',
    `Projet detecte: ${intent.projectType} (${intent.complexity})`,
    intent.frameworks.length > 0 ? `Frameworks: ${intent.frameworks.join(', ')}` : '',
    intent.features.length > 0 ? `Features: ${intent.features.join(', ')}` : '',
    intent.languages.length > 0 ? `Langages: ${intent.languages.join(', ')}` : '',
    '',
    '## PHASE ZERO — REFLEXION STRATEGIQUE',
    '',
    'Avant de planifier, REFLECHIS:',
    '- Quelle est la meilleure facon de realiser ce projet selon les standards 2025-2026?',
    '- Quelles sont les meilleures librairies/outils/patterns pour ce type de projet?',
    '- Comment rendre le resultat PREMIUM (pas basique, pas scolaire, PROFESSIONNEL)?',
    '- Pour un site web/landing: quelles animations, quels effets visuels, quelle UX moderne?',
    '- Pour une app: quelle architecture, quels patterns, quelles optimisations?',
    '- Quelles dependances REELLES et STABLES faut-il utiliser (pas de versions inventees)?',
    '',
    '## TA MISSION',
    '',
    '1. ANALYSE la demande: comprends l INTENTION de l utilisateur (pas juste les mots)',
    '2. RECHERCHE les meilleures pratiques: quelles sont les solutions les plus modernes et performantes?',
    '3. IDENTIFIE tout ce qu il faut: technos, dependances REELLES, architecture, edge cases',
    '4. PLANIFIE chaque fichier avec son contenu exact a generer — RIEN de partiel',
    '5. PREVOIS explicitement les fichiers de configuration locaux requis (tsconfig, vite/webpack, manifests, scripts) pour que le projet compile sans heriter d un parent',
    '6. VERIFIE les compatibilites de versions entre compilateur, dependances, types et commandes de build',
    '7. APPUIE-TOI sur le preflight local pour choisir quoi reutiliser, quoi inspecter et quelles installations locales sont requises',
    intent.projectType === 'desktop_tauri'
      ? '7. GARANTIS une architecture desktop native complete: shell Tauri Rust + frontend + configuration de build'
      : '',
    intent.projectType === 'desktop_electron'
      ? '7. GARANTIS une architecture desktop complete: process principal Electron + renderer + preload si necessaire'
      : '',
    '',
    '## FORMAT DE REPONSE OBLIGATOIRE',
    '',
    '### COMPREHENSION',
    '(1-3 phrases: qu est-ce que l utilisateur veut VRAIMENT?)',
    '',
    '### STACK TECHNIQUE',
    `(${isSimple ? 'langages et outils' : 'frameworks, librairies, versions'})`,
    '',
    '### FICHIERS A GENERER',
    '(pour CHAQUE fichier, donne:)',
    '- `chemin/nom.ext` — role du fichier',
    '  - Contenu principal: [description precise de ce que ce fichier doit contenir]',
    '  - Imports/dependances: [ce dont il a besoin]',
    isSimple ? '' : '  - Points d attention: [edge cases, pieges connus]',
    '',
    '### DEPENDANCES (npm/pip/cargo)',
    '(liste EXACTE avec versions recommandees)',
    '- nom@version — pourquoi',
    '',
    '### COMMANDES D INSTALLATION ET LANCEMENT',
    '(exactement ce qu il faut taper pour faire tourner le projet)',
    '',
    isSimple ? '' : [
      '### ARCHITECTURE',
      '- Patterns utilises et pourquoi',
      '- Communication entre composants',
      '- Gestion d etat',
      '- Gestion d erreurs',
      '',
    ].join('\n'),
    '### DESIGN & UX',
    '(palette couleurs, typographie, responsive, animations)',
    '- Le design DOIT etre professionnel et moderne, pas du HTML brut',
    '',
    '### ORDRE DE GENERATION',
    '(dans quel ordre generer pour minimiser les erreurs)',
    '',
    `## DEMANDE UTILISATEUR`,
    prompt,
  ].filter(Boolean).join('\n')
}
