
## codeMissionControl.ts @ offset 24193 (3538 chars)

**Proposed improvement** (review + apply manually):

```
"""
,
      shorten(file.content, 600),
    ].join('\n'))
    .join('\n\n')
}

export async function reviewGeneratedCodeDraft({
  prompt,
  intent,
  files,
  architecturePlan,
  missionDossier,
  model = CODE_SINGLE_MODEL,
}: {
  prompt: string
  intent: CodeIntent
  files: MissionFileContext[]
  architecturePlan: string | null
  missionDossier: CodeMissionDossier
  model?: string
}): Promise<CodeDraftReview> {
  const fallback = buildDraftReviewFallback(prompt, intent, files)

  if (files.length === 0) {
    return fallback
  }

  const reviewPrompt = [
    'Tu es le gardien qualité du module CODE d\'AuroraIA.',
    'Tu audites un draft de projet AVANT le sandbox.',
    '',
    'Réponds UNIQUEMENT en JSON valide avec cette forme:',
    '{',
    '  "score": 0,',
    '  "verdict": "accept|repair|regenerate",',
    '  "summary": "résumé court",',
    '  "strengths": ["point fort"],',
    '  "criticalIssues": ["problème bloquant"],',
    '  "missingFiles": ["fichier ou pièce critique manquante"],',
    '  "mustFixBeforeSandbox": ["correction importante"]',
    '}',
    '',
    'Règles de jugement:',
    '1) "regenerate" si la sortie ressemble à de la documentation, des placeholders, des stubs, une architecture clairement hors-sujet, ou un REFUS/EXCUSE du modèle.',
    '2) "regenerate" IMMÉDIATEMENT si un fichier contient "je suis désolé", "I cannot", "I\'m sorry", des excuses ou un refus de générer.',
    '3) "repair" si la base est bonne mais fragile, incomplète ou partiellement incohérente.',
    '4) "accept" seulement si le draft semble vraiment sandbox-ready et RÉPOND FIDÈLEMENT à la demande.',
    '5) Penalise fortement: TODO, fichiers vides, scripts absents, imports invraisemblables, stack incohérente, absence de point d\'entrée.',
    '6) Penalise SÉVÈREMENT: fichiers qui ne contiennent pas de code mais du texte explicatif, des excuses ou des redirections.',
    '7) Priorité: fidélité à la demande, complétude, exécution, robustesse, qualité visuelle.',
    '',
    'Contraintes négatives:',
    '- Do NOT generate any output outside the specified JSON schema.',
    '- Do NOT include any markdown, code blocks, or natural language explanations outside the JSON.',
    '- Do NOT interpret or analyze the intent beyond the literal scope of the prompt.',
    '- Do NOT allow any ambiguity in the verdict; it must be one of: accept, repair, or regenerate.',
    '- Do NOT include any external references, URLs, or citations.',
    '',
    'Best practices:',
    '- Ensure all file paths in "missingFiles" and "mustFixBeforeSandbox" are absolute and valid.',
    '- Validate that "criticalIssues" are actionable and directly block sandbox execution.',
    '- Use only English for all JSON values, including "summary", "strengths", and "criticalIssues".',
    '- Ensure "score" is an integer between 0 and 100, reflecting the overall quality.',
    '- If "verdict" is "accept", ensure "summary" is a concise, actionable sentence.',
    '',
    'Exemple de sortie valide:',
    '{',
    '  "score": 85,',
    '  "verdict": "repair",',
    '  "summary": "Le code est fonctionnel mais nécessite des corrections de style et d\'importation.",',
    '  "strengths": ["Structure claire", "Bon usage des variables"],',
    '  "criticalIssues": ["Importation manquante de lodash"],',
    '  "missingFiles": ["src/utils/helpers.js"],',
    '  "mustFixBeforeSandbox": ["Remplacer les imports manquants", "Corriger les erreurs de syntaxe"]',
    '}',
    '',
  ].join('\n')

  // ... rest of function implementation
}
```

---
