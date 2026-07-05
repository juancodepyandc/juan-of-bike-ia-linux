/**
 * simpleDiff — tiny line-level diff for before/after code comparisons.
 * Uses LCS so insertions / deletions are aligned properly without pulling
 * in `diff-match-patch` or `jsdiff` (saves ~70 kB on bundle).
 */
export type DiffOp = 'eq' | 'add' | 'del'
export interface DiffLine {
  op: DiffOp
  text: string
  /** Line number in the "old" (before) document, 1-based. null for additions. */
  oldLine: number | null
  /** Line number in the "new" (after) document, 1-based. null for deletions. */
  newLine: number | null
}

function lcs(a: string[], b: string[]): number[][] {
  const m = a.length, n = b.length
  // Dynamic programming table of LCS lengths
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  return dp
}

export function diffLines(before: string, after: string): DiffLine[] {
  const a = before.split('\n')
  const b = after.split('\n')
  const dp = lcs(a, b)
  const out: DiffLine[] = []
  let i = 0, j = 0, oi = 1, ni = 1
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ op: 'eq', text: a[i], oldLine: oi++, newLine: ni++ })
      i++; j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ op: 'del', text: a[i], oldLine: oi++, newLine: null })
      i++
    } else {
      out.push({ op: 'add', text: b[j], oldLine: null, newLine: ni++ })
      j++
    }
  }
  while (i < a.length) { out.push({ op: 'del', text: a[i++], oldLine: oi++, newLine: null }) }
  while (j < b.length) { out.push({ op: 'add', text: b[j++], oldLine: null, newLine: ni++ }) }
  return out
}

export function diffStats(lines: DiffLine[]): { added: number; removed: number; unchanged: number } {
  let added = 0, removed = 0, unchanged = 0
  for (const l of lines) {
    if (l.op === 'add') added++
    else if (l.op === 'del') removed++
    else unchanged++
  }
  return { added, removed, unchanged }
}
