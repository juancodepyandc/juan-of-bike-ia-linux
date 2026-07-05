import { readFileSync } from 'node:fs'
const code = readFileSync('output/code-tests/game1_platformer_v2/index.html', 'utf8')
const loopFn = code.match(/function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{[\s\S]*?requestAnimationFrame\s*\(\s*\1\b/)
console.log('loopFn match:', loopFn ? loopFn[1] : 'NONE')
if (loopFn) {
  const name = loopFn[1]
  const directCalls = (code.match(new RegExp(`\\b${name}\\s*\\(`, 'g')) || []).length
  const rafKicks = (code.match(new RegExp(`requestAnimationFrame\\s*\\(\\s*${name}\\b`, 'g')) || []).length
  console.log('directCalls:', directCalls, 'rafKicks:', rafKicks)
  console.log('all `'+name+'(` matches:', code.match(new RegExp(`\\b${name}\\s*\\(`, 'g')))
}
// also: is there any self-rescheduling at all?
console.log('has rAF:', /requestAnimationFrame/.test(code))
