import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { hasUndecodedNewlines, repairEscapedNewlines } from '../services/codeEscapedNewlines.ts'
import { sanitizeGeneratedFileContent } from '../services/codeGeneratedFileSanitizer.ts'

// MESURE (run v130, capturee par l archivage d etats intermediaires — invisible
// avant lui). Contenu reellement livre pour src/components/Footer.tsx:
const BROKEN = "import React from 'react'\\n\\nconst Footer: React.FC = () => {\\n  return (\\n    <footer className=\"site-footer\">\\n      <p>Brulerie Nomade</p>\\n    </footer>\\n  )\\n}\\n\\nexport default Footer\\n"
// Erreurs constatees, TOUTES en ligne 1 a des colonnes croissantes:
//   Footer.tsx(1,107): TS1127 Invalid character
//   Footer.tsx(1,120): TS1005 ';' expected

describe('sauts de ligne echappes: le transport avait perdu le decodage', () => {
  test('le cas reel du run v130 est reconnu et decode', () => {
    assert.equal(BROKEN.includes('\n'), false, 'le fichier tient sur une seule ligne')
    assert.ok(hasUndecodedNewlines('src/components/Footer.tsx', BROKEN))
    const { content, repaired } = repairEscapedNewlines('src/components/Footer.tsx', BROKEN)
    assert.equal(repaired, true)
    assert.ok(content.split('\n').length >= 10)
    assert.match(content, /^import React from 'react'$/m)
    assert.match(content, /^export default Footer$/m)
    assert.doesNotMatch(content, /\\n/)
  })

  test('un fichier NORMAL contenant join(\\n) n est jamais touche', () => {
    // Il a de VRAIS sauts de ligne: la garde ne se declenche pas.
    const legit = "const lines = ['a', 'b']\nexport const text = lines.join('\\n')\nexport default text\n"
    assert.equal(hasUndecodedNewlines('src/util.ts', legit), false)
    assert.equal(repairEscapedNewlines('src/util.ts', legit).repaired, false)
  })

  test('un JSON sur une ligne reste intact: ses echappements sont legitimes', () => {
    const json = '{"name":"x","description":"ligne1\\nligne2","scripts":{"build":"vite build"},"dependencies":{"react":"^18.2.0"}}'
    assert.equal(hasUndecodedNewlines('package.json', json), false)
  })

  test('un fichier court n est pas touche', () => {
    assert.equal(hasUndecodedNewlines('src/a.ts', 'const a = 1\\n'), false)
  })

  test('un seul \\n litteral ne suffit pas a declencher', () => {
    const one = `const msg = 'ligne\\n'${' '.repeat(200)}`
    assert.equal(hasUndecodedNewlines('src/a.ts', one), false)
  })

  test('la reparation passe par le sanitizer de production', () => {
    const out = sanitizeGeneratedFileContent('src/components/Footer.tsx', BROKEN)
    assert.ok(out.split('\n').length >= 10, 'le fichier est de nouveau multi-lignes')
    assert.doesNotMatch(out, /\\n/)
  })
})
