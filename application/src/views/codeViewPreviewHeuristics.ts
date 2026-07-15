import type { CodeFile } from '../services/codeOrchestrator'

export function isHeavyWebGLProject(files: CodeFile[]): boolean {
  for (const f of files) {
    if (f.content.length > 80_000) return true
    const head = f.content.slice(0, 4000).toLowerCase()
    if (/three\.js|three\.module|import\s+\*\s+as\s+three|from\s+['"]three['"]/.test(head)) return true
    if (/webglrenderer|getcontext\(\s*['"]webgl/.test(head)) return true
    if (/requestanimationframe.*render|game\s*loop|scene\s*=\s*new/.test(head)) return true
  }
  return false
}
