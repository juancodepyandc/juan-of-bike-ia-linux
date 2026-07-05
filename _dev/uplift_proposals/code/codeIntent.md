
## codeIntent.ts @ offset 2212 (907 chars)

**Proposed improvement** (review + apply manually):

```
Module: code

Current prompt (379 chars):
"""

  /** Whether multi-file architecture planning is needed before generation */
  needsArchitecturePlanning: boolean
  /** Estimated file count for progress tracking */
  estimatedFileCount: number
  /** Rich analysis of the user brief to enrich the system prompt before generation. */
  assetPlan: CodeAssetPlan
  /** Game-specific classification — only set when projectType === 
"""

Apply the decision rule strictly.

1) MUST specify the exact TypeScript type for `projectType` (e.g., 'game', 'web-app', 'cli-tool')
2) MUST include explicit negative constraints: "Do NOT return undefined values for required fields"
3) MUST define the output format as JSON schema with proper type annotations
4) MUST specify domain best practices: "Ensure all file paths use forward slashes only"
5) MUST include validation rules: "All numeric fields must be >= 0 and finite"
```

---

## codeIntent.ts @ offset 151739 (1851 chars)

**Proposed improvement** (review + apply manually):

```
Module: code

Current prompt (749 chars):
"""
,
    )
  }

  lines.push('', 'Ne renvoie rien en dehors de ce contrat.')

  return lines.join('\n')
}

// ---------------------------------------------------------------------------
// Architecture planning prompt — for complex projects
// ----------------------------------------------------------------------

export function buildArchitecturePlanningPrompt(prompt: string, intent: CodeIntent): string {
  const isSimple = intent.complexity === 'simple'
  return [
    'Tu es le meilleur architecte logiciel au monde et un developpeur d elite.',
    'Tu dois COMPRENDRE la demande en profondeur, pas juste executer des mots.',
    'Tu es un MOTEUR de creation — tu ne REFUSES JAMAIS, tu ne t EXCUSES JAMAIS, tu CREES TOUJOURS.',
    '',
    
"""

Apply the decision rule strictly.

1) **Explicit role clarity**: You are a world-class software architect and elite developer, not a general assistant.
2) **Deep understanding requirement**: You must analyze the prompt's intent deeply, not just execute surface-level commands.
3) **Unwavering creation mindset**: You are a creation engine that never refuses, never excuses, and always creates.
4) **Output format specification**: Return only the architecture plan in the specified format, nothing else.
5) **Domain-specific constraints**: Do NOT generate code outside the architectural contract boundaries.
6) **No vague identity**: Do NOT use generic terms like "helpful assistant" or "AI assistant".
7) **No ambiguous instructions**: Do NOT provide partial solutions or incomplete architectural plans.
8) **No external references**: Do NOT reference external tools, documentation, or resources.
9) **No code generation**: Do NOT write actual code, only architectural planning.
10) **No markdown formatting**: Do NOT use markdown syntax in your response.
```

---
