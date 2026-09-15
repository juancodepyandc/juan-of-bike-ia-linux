// Consigne de sortie du planificateur d architecture.
// Extrait de codeArchitecturePlan.ts: le schema, son template et l interdiction
// des dependances a generateur pesaient a eux seuls un quart du fichier, qui
// depassait la limite de 400 lignes verrouillee par codeModuleStructure.

import {
  CODE_ARCHITECTURE_PLAN_SCHEMA,
  CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
} from './codeArchitecturePlan.ts'
import { buildCodegenDependencyBan } from './codeCodegenDependencies.ts'

export function buildArchitecturePlanJsonInstructions() {
  return [
    '## FORMAT DE SORTIE OBLIGATOIRE — JSON SCHEMA',
    '',
    'Reponds UNIQUEMENT avec un objet JSON valide. Aucun markdown, aucun texte avant/apres, aucun bloc ``` ni balise <think>. Sortie directe { ... }.',
    'Le plan est un contrat machine: s il ne valide pas ce schema, il sera rejete et ignore par l executeur.',
    '',
    buildCodegenDependencyBan(),
    '',
    'Schema JSON attendu (champs requis):',
    JSON.stringify(CODE_ARCHITECTURE_PLAN_SCHEMA, null, 2),
    '',
    'Template minimal a respecter exactement:',
    JSON.stringify({
      schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
      projectType: '<type detecte>',
      summary: '<20+ caracteres: intention et strategie de livraison>',
      stack: {
        runtime: '<node/python/rust/web/etc>',
        packageManager: '<npm/pnpm/pip/cargo/aucun>',
        languages: ['<langage>'],
        frameworks: ['<framework ou aucun>'],
        dependencies: [{ name: '<package>', version: '<version exacte si utile>', type: 'runtime', reason: '<pourquoi>' }],
        scripts: [{ name: '<script>', command: '<commande exacte>', purpose: '<validation ou lancement>' }],
      },
      files: [{
        path: '<chemin relatif sur POSIX>',
        role: '<responsabilite concrete>',
        language: '<langage>',
        required: true,
        imports: ['<imports locaux attendus>'],
        exports: ['<exports attendus>'],
        notes: ['<points d attention>'],
      }],
      dataFlow: ['<flux utilisateur/donnees/etat>'],
      execution: {
        install: ['<commande install ou aucune>'],
        dev: ['<commande dev/lancement>'],
        build: ['<commande build ou verification>'],
        test: ['<commande test ou validation manuelle stricte>'],
        preview: '<comment voir le resultat>',
      },
      generationOrder: ['<chemin fichier dans ordre de generation>'],
      validation: ['<critere vert mesurable>', '<autre critere vert mesurable>'],
      risks: [{ risk: '<risque>', mitigation: '<mitigation concrete>' }],
      design: {
        palette: ['<tokens/couleurs ou contrainte>'],
        typography: ['<polices/echelle>'],
        ux: ['<interactions et ergonomie>'],
        responsive: ['<breakpoints et comportements>'],
      },
    }, null, 2),
  ].join('\n')
}

