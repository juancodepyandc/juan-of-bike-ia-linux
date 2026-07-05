// Multi-format exercise registry for the learning module.
//
// The handoff demands six formats — QCM, vrai/faux, ouvert court, schéma à
// annoter, mini-projet SIN, exercice de programmation. The previous
// `QuizQuestion.kind` only knew "mcq" | "open"; this layer is a strict
// superset that the LLM prompt-builders + view layer can both consume.
//
// Pure compute: no DOM, no LLM call. Validation/scoring is deterministic.

/** Exercise format identifier. Add a new value here AND a discriminator below. */
export type ExerciseKind =
  | 'qcm'
  | 'true_false'
  | 'open_short'
  | 'schema_annotate'
  | 'mini_project_sin'
  | 'code_exercise'

export type DifficultyTier = 'decouverte' | 'consolidation' | 'maitrise' | 'bac'

export type ExerciseBase = {
  id: string
  kind: ExerciseKind
  prompt: string
  difficulty: DifficultyTier
  /** Estimated minutes to attempt. */
  timeBudgetMin: number
  /** Tags used by the spaced repetition deck builder. */
  tags: string[]
  /** Optional reference into the BO STI2D taxonomy. See `bacSti2dCurriculum.ts`. */
  curriculumRefs?: string[]
  /** Pedagogical objective (1 line, displayed below the prompt). */
  objective?: string
  /** TeX/Markdown explanation rendered after submission. */
  explanation?: string
}

// --- 1. QCM (single correct or multi-correct) -------------------------------
export type McqOption = { id: string; label: string; correct: boolean; rationale?: string }
export type McqExercise = ExerciseBase & {
  kind: 'qcm'
  options: McqOption[]
  /** If true, allow several correct answers (≥2). */
  multiAnswer: boolean
  /** Distractor quality flag — used by the LLM auditor downstream. */
  hint?: string
}

// --- 2. Vrai / Faux avec justification --------------------------------------
export type TrueFalseExercise = ExerciseBase & {
  kind: 'true_false'
  expected: boolean
  /** Required free-text justification — the LLM grades the explanation. */
  requireJustification: boolean
  justificationCriteria?: string[]
}

// --- 3. Ouvert court : développement structuré ------------------------------
export type OpenShortExercise = ExerciseBase & {
  kind: 'open_short'
  answerOutline: string[]
  gradingCriteria: Array<{ label: string; points: number }>
  totalPoints: number
  /** Optional minimal-length hint for the UI. */
  minWords?: number
  maxWords?: number
}

// --- 4. Schéma à annoter (drag & drop labels) -------------------------------
export type SchemaSlot = {
  id: string
  /** Pixel coordinates (relative to a 1000×1000 reference frame) of the dot. */
  x: number
  y: number
  /** Correct label id. */
  expectedLabelId: string
}
export type SchemaLabel = { id: string; text: string }
export type SchemaAnnotateExercise = ExerciseBase & {
  kind: 'schema_annotate'
  imageUrl: string
  /** Alt text — required for accessibility. */
  alt: string
  labels: SchemaLabel[]
  slots: SchemaSlot[]
}

// --- 5. Mini-projet SIN -----------------------------------------------------
export type ProjectDeliverable = { id: string; title: string; description: string; required: boolean }
export type ProjectRubricCriterion = { id: string; label: string; weight: number; level1: string; level3: string; level5: string }
export type MiniProjectSinExercise = ExerciseBase & {
  kind: 'mini_project_sin'
  /** Brief énoncé — context, constraints, deliverables. */
  brief: string
  /** Suggested hardware (e.g. ESP32, Arduino Uno R4, Raspberry Pi Pico). */
  hardware: string[]
  /** Suggested software/language stack. */
  stack: string[]
  deliverables: ProjectDeliverable[]
  rubric: ProjectRubricCriterion[]
}

// --- 6. Exercice de programmation ------------------------------------------
export type CodeLanguage = 'python' | 'javascript' | 'typescript' | 'c' | 'cpp' | 'arduino'
export type CodeTestCase = {
  id: string
  /** Stdin or function args, serialised. */
  input: string
  /** Expected stdout / return, serialised. */
  expected: string
  /** Set to true to keep the case private (only counts for grade). */
  hidden: boolean
}
export type CodeExerciseExercise = ExerciseBase & {
  kind: 'code_exercise'
  language: CodeLanguage
  /** Starter scaffold the learner edits. */
  starter: string
  /** Reference solution kept server-side. May be empty when not needed. */
  solution?: string
  /** Public + hidden test cases. */
  tests: CodeTestCase[]
  /** Optional resource limits forwarded to the sandbox. */
  limits?: { wallSeconds: number; memoryMb: number }
}

export type Exercise =
  | McqExercise
  | TrueFalseExercise
  | OpenShortExercise
  | SchemaAnnotateExercise
  | MiniProjectSinExercise
  | CodeExerciseExercise

// --- Validators / sanity checks --------------------------------------------
/**
 * Validate an exercise — used both at registration time (catch authoring bugs)
 * and after an LLM generates one (catch hallucinated structures).
 *
 * Returns the list of issues, empty if valid.
 */
export function validateExercise(ex: Exercise): string[] {
  const issues: string[] = []
  if (!ex.id) issues.push('id requis')
  if (!ex.prompt || ex.prompt.length < 3) issues.push('prompt trop court')
  if (!Array.isArray(ex.tags)) issues.push('tags doit être un tableau')
  if (ex.timeBudgetMin <= 0 || ex.timeBudgetMin > 240) issues.push('timeBudgetMin hors [1, 240]')

  switch (ex.kind) {
    case 'qcm': {
      if (ex.options.length < 2) issues.push('qcm: 2 options minimum')
      const correct = ex.options.filter((o) => o.correct).length
      if (correct < 1) issues.push('qcm: au moins une option correcte')
      if (!ex.multiAnswer && correct > 1) issues.push('qcm: multiAnswer=false impose 1 seule correcte')
      const ids = new Set(ex.options.map((o) => o.id))
      if (ids.size !== ex.options.length) issues.push('qcm: options.id non unique')
      break
    }
    case 'true_false': {
      if (typeof ex.expected !== 'boolean') issues.push('true_false: expected booléen')
      if (ex.requireJustification && (!ex.justificationCriteria || ex.justificationCriteria.length === 0)) {
        issues.push('true_false: requireJustification implique des critères')
      }
      break
    }
    case 'open_short': {
      if (ex.answerOutline.length === 0) issues.push('open_short: outline vide')
      const sum = ex.gradingCriteria.reduce((acc, c) => acc + c.points, 0)
      if (Math.abs(sum - ex.totalPoints) > 1e-6) issues.push(`open_short: somme des critères (${sum}) ≠ totalPoints (${ex.totalPoints})`)
      if (ex.minWords != null && ex.maxWords != null && ex.minWords > ex.maxWords) {
        issues.push('open_short: minWords > maxWords')
      }
      break
    }
    case 'schema_annotate': {
      if (!ex.imageUrl) issues.push('schema_annotate: imageUrl requis')
      if (!ex.alt) issues.push('schema_annotate: alt requis (accessibilité)')
      if (ex.slots.length === 0) issues.push('schema_annotate: slots vides')
      const labelIds = new Set(ex.labels.map((l) => l.id))
      for (const slot of ex.slots) {
        if (!labelIds.has(slot.expectedLabelId)) issues.push(`schema_annotate: slot ${slot.id} pointe vers label inconnu`)
      }
      break
    }
    case 'mini_project_sin': {
      if (!ex.brief) issues.push('mini_project_sin: brief requis')
      if (ex.deliverables.length === 0) issues.push('mini_project_sin: aucun livrable')
      const wsum = ex.rubric.reduce((acc, c) => acc + c.weight, 0)
      if (Math.abs(wsum - 1) > 0.01) issues.push(`mini_project_sin: somme des poids rubric ${wsum.toFixed(3)} ≠ 1`)
      break
    }
    case 'code_exercise': {
      if (!ex.starter) issues.push('code_exercise: starter requis')
      if (ex.tests.length === 0) issues.push('code_exercise: au moins un test')
      const ids = new Set(ex.tests.map((t) => t.id))
      if (ids.size !== ex.tests.length) issues.push('code_exercise: tests.id non unique')
      break
    }
  }
  return issues
}

// --- Submission / scoring helpers ------------------------------------------
export type McqAnswer = { kind: 'qcm'; selected: string[] }
export type TrueFalseAnswer = { kind: 'true_false'; value: boolean; justification?: string }
export type OpenShortAnswer = { kind: 'open_short'; text: string }
export type SchemaAnswer = { kind: 'schema_annotate'; mapping: Record<string, string> /* slotId -> labelId */ }
export type ProjectAnswer = { kind: 'mini_project_sin'; deliverables: Record<string, string /* artifact url or text */ > }
export type CodeAnswer = { kind: 'code_exercise'; source: string; runResults?: Array<{ testId: string; pass: boolean; output: string }> }

export type ExerciseAnswer =
  | McqAnswer
  | TrueFalseAnswer
  | OpenShortAnswer
  | SchemaAnswer
  | ProjectAnswer
  | CodeAnswer

export type ScoredAttempt = {
  ratio01: number
  feedback: string
  /** Pointers into the exercise's structure for the UI to highlight. */
  flagged: string[]
  /** If true, the attempt should send the card to FSRS as Again. */
  shouldRelearn: boolean
}

/**
 * Deterministic scoring for objective formats. Subjective formats
 * (open_short, mini_project_sin, true_false-with-justification, code_exercise
 * partial credit) return a "needs review" hint — the LLM grader takes over
 * from there.
 */
export function scoreAttempt(ex: Exercise, ans: ExerciseAnswer): ScoredAttempt {
  if (ex.kind !== ans.kind) {
    return { ratio01: 0, feedback: 'Format de réponse incompatible.', flagged: [], shouldRelearn: true }
  }
  switch (ex.kind) {
    case 'qcm': {
      const ansQ = ans as McqAnswer
      const correctIds = new Set(ex.options.filter((o) => o.correct).map((o) => o.id))
      const selected = new Set(ansQ.selected)
      if (!ex.multiAnswer) {
        if (selected.size !== 1) {
          return { ratio01: 0, feedback: 'Sélectionne une seule réponse.', flagged: [], shouldRelearn: true }
        }
        const [picked] = ansQ.selected
        const ok = correctIds.has(picked)
        return {
          ratio01: ok ? 1 : 0,
          feedback: ok ? 'Bonne réponse.' : 'Ce n’est pas la bonne option.',
          flagged: ok ? [] : Array.from(selected),
          shouldRelearn: !ok,
        }
      }
      // Multi-answer: Jaccard between sets.
      const inter = [...correctIds].filter((id) => selected.has(id)).length
      const union = new Set<string>([...correctIds, ...selected]).size
      const ratio = union === 0 ? 0 : inter / union
      return {
        ratio01: ratio,
        feedback: ratio === 1 ? 'Toutes les bonnes options.' : 'Sélection partielle, regarde les pistes.',
        flagged: [...selected].filter((id) => !correctIds.has(id)),
        shouldRelearn: ratio < 0.6,
      }
    }
    case 'true_false': {
      const ansT = ans as TrueFalseAnswer
      const ok = ansT.value === ex.expected
      const needsJustif = ex.requireJustification && (ansT.justification ?? '').trim().length < 20
      const ratio = ok ? (needsJustif ? 0.5 : 1) : 0
      return {
        ratio01: ratio,
        feedback: ok ? (needsJustif ? 'Bonne intuition — étaie ta justification (≥ 20 caractères).' : 'Bonne réponse.') : 'Affirmation incorrecte.',
        flagged: [],
        shouldRelearn: ratio < 0.5,
      }
    }
    case 'schema_annotate': {
      const ansS = ans as SchemaAnswer
      const total = ex.slots.length
      let ok = 0
      const flagged: string[] = []
      for (const slot of ex.slots) {
        if (ansS.mapping[slot.id] === slot.expectedLabelId) ok += 1
        else flagged.push(slot.id)
      }
      const ratio = total === 0 ? 0 : ok / total
      return {
        ratio01: ratio,
        feedback: `${ok}/${total} étiquettes correctement placées.`,
        flagged,
        shouldRelearn: ratio < 0.6,
      }
    }
    case 'open_short':
    case 'mini_project_sin':
      return {
        ratio01: 0,
        feedback: 'Réponse à corriger par Aurora (rubric).',
        flagged: [],
        shouldRelearn: false,
      }
    case 'code_exercise': {
      const ansC = ans as CodeAnswer
      const runs = ansC.runResults
      if (!runs || runs.length === 0) {
        return { ratio01: 0, feedback: 'Lance les tests pour évaluer.', flagged: [], shouldRelearn: false }
      }
      const total = ex.tests.length
      const passed = runs.filter((r) => r.pass).length
      const ratio = total === 0 ? 0 : passed / total
      return {
        ratio01: ratio,
        feedback: `${passed}/${total} tests passent.`,
        flagged: runs.filter((r) => !r.pass).map((r) => r.testId),
        shouldRelearn: ratio < 0.5,
      }
    }
  }
}

/** Translate a scored attempt to the FSRS rating the scheduler expects. */
export function attemptToRating(scored: ScoredAttempt): 1 | 2 | 3 | 4 {
  if (scored.ratio01 <= 0.25) return 1 // Again
  if (scored.ratio01 < 0.6) return 2 // Hard
  if (scored.ratio01 < 0.95) return 3 // Good
  return 4 // Easy
}

// --- Registry --------------------------------------------------------------
const EXERCISE_REGISTRY = new Map<string, Exercise>()

export function registerExercise(ex: Exercise): void {
  const issues = validateExercise(ex)
  if (issues.length > 0) throw new Error(`Exercise ${ex.id} invalid: ${issues.join('; ')}`)
  if (EXERCISE_REGISTRY.has(ex.id)) return
  EXERCISE_REGISTRY.set(ex.id, ex)
}

export function listExercises(): Exercise[] {
  return Array.from(EXERCISE_REGISTRY.values())
}

export function getExercise(id: string): Exercise | undefined {
  return EXERCISE_REGISTRY.get(id)
}

export function clearExerciseRegistry(): void {
  EXERCISE_REGISTRY.clear()
}
