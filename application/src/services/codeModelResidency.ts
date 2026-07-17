// ---------------------------------------------------------------------------
// Garde anti-crash de residence memoire (16GB VRAM + 32GB RAM = 48GB).
// Deux gros modeles code (devstral 14GB, qwen3-coder 18GB, deepseek-r1 20GB) ne
// PEUVENT PAS coexister: la somme deborde en swap -> gel machine (crash constate).
// Le routage multi-modeles (agent -> codeur -> verifieur) charge des modeles
// DIFFERENTS par role. Sans OLLAMA_MAX_LOADED_MODELS=1, Ollama les empile.
// Avant qu un role charge SON modele, on decharge tout AUTRE gros modele code
// deja resident -> un seul gros modele a la fois, jamais de swap.
// ---------------------------------------------------------------------------

const OLLAMA = 'http://localhost:11434'
// Prefixes des gros modeles code qu on ne doit jamais empiler. On ne touche PAS
// aux modeles partages legers (vision qwen3-vl, embeddings nomic, main instruct)
// qui peuvent coexister.
const HEAVY_CODE_MODEL_PREFIXES = ['devstral', 'qwen3-coder', 'deepseek-r1', 'qwen3.6']

function norm(model: string): string {
  return (model || '').trim().replace(/:latest$/i, '').toLowerCase()
}

function isHeavyCodeModel(name: string): boolean {
  const n = norm(name)
  return HEAVY_CODE_MODEL_PREFIXES.some((p) => n.startsWith(p))
}

let lastEnsured: string | null = null

/**
 * Garantit qu au plus UN gros modele code est charge en memoire: decharge tout
 * autre gros modele code avant que `model` prenne la main. Best-effort et
 * non-bloquant (ne fait jamais echouer une generation). Idempotent tant que le
 * modele ne change pas (evite un /api/ps a chaque token).
 */
export async function ensureExclusiveCodeModel(model: string): Promise<void> {
  const target = norm(model)
  if (!target || target === lastEnsured) return
  try {
    const res = await fetch(`${OLLAMA}/api/ps`)
    const data = (await res.json()) as { models?: Array<{ name?: string }> }
    const loaded = (data.models ?? []).map((m) => m.name ?? '').filter(Boolean)
    for (const other of loaded) {
      if (norm(other) === target) continue
      if (!isHeavyCodeModel(other)) continue
      // keep_alive:0 => Ollama decharge ce modele immediatement.
      await fetch(`${OLLAMA}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: other, keep_alive: 0 }),
      }).catch(() => undefined)
    }
    lastEnsured = target
  } catch {
    // Ollama injoignable ou schema inattendu: on ne bloque pas la generation.
  }
}

/** Pour les tests: reset du cache de residence. */
export function __resetModelResidencyCacheForTest(): void {
  lastEnsured = null
}
