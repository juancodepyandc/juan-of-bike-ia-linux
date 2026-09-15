/**
 * Module Code — fidélité de l'analyse et du nettoyage de source.
 *
 * POURQUOI CE FICHIER EXISTE. Trois défauts touchaient tous le code RÉELLEMENT
 * LIVRÉ à l'utilisateur, et aucun n'était couvert :
 *
 *   1. IMPORTS ET EXPORTS FANTÔMES. `readImports` et `readModuleExports`
 *      balayaient la source brute à coups d'expressions régulières : un
 *      `// import X from 'x'` en commentaire, ou un import cité dans une
 *      chaîne, comptaient comme de vrais imports. Sur un fichier portant trois
 *      leurres et un vrai import, quatre étaient rendus. Ce n'est pas
 *      cosmétique : `planImportShapeFixes` compare ce qu'un module importe à
 *      ce que la cible exporte, puis RÉÉCRIT le code. Un export aperçu dans un
 *      commentaire fait croire à un nom disponible, et la « réparation »
 *      transforme un import valide en import d'un symbole inexistant — du code
 *      livré qui ne compile plus.
 *   2. README TRONQUÉ. Le retrait de la balise de bloc de code ouvrante et
 *      celui de la fermante étaient INDÉPENDANTS. Un README qui se termine par
 *      un bloc — le cas le plus banal — perdait sa ligne de clôture, donc
 *      livrait du Markdown cassé, bloc resté ouvert.
 *   3. JSON ALTÉRÉ. La suppression des virgules finales s'appliquait par
 *      expression régulière sur tout le texte, y compris l'INTÉRIEUR des
 *      chaînes : la valeur `"un, deux, }"` ressortait `"un, deux}"`. Le
 *      fichier restait du JSON valide et la donnée était fausse.
 *
 * Reproduction en ligne de commande :
 *   node --experimental-strip-types --test src/__tests__/codeSourceAnalysisFidelity.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { maskNonCode, readImports, readModuleExports } from '../services/codeImportExportShape.ts'
import { stripFormattingArtifacts } from '../services/codeFormattingArtifacts.ts'
import { tryParseJson, sanitizeGeneratedFileContent } from '../services/codeGeneratedFileSanitizer.ts'

const SERVICES = join(fileURLToPath(new URL('.', import.meta.url)), '..', 'services')

// ===========================================================================
describe('masquage — les commentaires et chaînes ne sont plus du code', () => {
  test('la longueur et le découpage en lignes sont préservés', () => {
    // Les positions rendues par le balayage servent à découper la source
    // d'ORIGINE : elles doivent rester valides.
    const sources = readdirSync(SERVICES)
      .filter((f) => f.endsWith('.ts'))
      .slice(0, 150)
      .map((f) => readFileSync(join(SERVICES, f), 'utf8'))
    for (const src of sources) {
      const masked = maskNonCode(src)
      assert.equal(masked.length, src.length, 'la longueur change')
      assert.equal(masked.split('\n').length, src.split('\n').length, 'le nombre de lignes change')
    }
  })

  test('un gabarit avec interpolation ne dévore pas la suite du fichier', () => {
    // Le backtick FERMANT était pris pour l'ouverture d'une nouvelle chaîne :
    // tout le reste du fichier passait en blanc, imports compris.
    const src = "const s = `avant ${valeur} apres`\nimport A from 'a'\nimport B from 'b'"
    assert.deepEqual(readImports(src).map((i) => i.specifier), ['a', 'b'])
  })

  test('gabarits imbriqués', () => {
    const src = "const s = `a ${`b ${x} c`} d`\nimport A from 'a'"
    assert.deepEqual(readImports(src).map((i) => i.specifier), ['a'])
  })

  test('les pièges classiques ne masquent pas du vrai code', () => {
    const PIÈGES: Array<[string, string, string[]]> = [
      ['apostrophe dans un commentaire', "// l'import n'est pas là\nimport B from 'b'", ['b']],
      ['double barre dans une URL', 'const u = "http://x.fr"\nimport C from "c"', ['c']],
      ['ouverture de commentaire dans une chaîne', 'const u = "/* pas un commentaire"\nimport D from "d"', ['d']],
      ['antislash échappé en fin de chaîne', 'const p = "c:\\\\dossier\\\\"\nimport E from "e"', ['e']],
      ['guillemets imbriqués', 'const q = "il a dit \'salut\'"\nimport F from "f"', ['f']],
      ['import multi-lignes', "import {\n  a,\n  b,\n} from './x'", ['./x']],
    ]
    for (const [nom, src, attendu] of PIÈGES) {
      assert.deepEqual(readImports(src).map((i) => i.specifier), attendu, nom)
    }
  })
})

describe('imports — les fantômes ne comptent plus', () => {
  const LEURRES = [
    "// import Faux from 'faux'",
    "/* import Bidon from 'bidon' */",
    'const s = "import Chaine from \'chaine\'"',
    "const t = `import Gabarit from 'gabarit'`",
    "import Vrai from 'vrai'",
    "import { a, b as c } from './reel'",
  ].join('\n')

  test('seuls les deux vrais imports sont rendus', () => {
    const specifiers = readImports(LEURRES).map((i) => i.specifier)
    assert.deepEqual(specifiers, ['vrai', './reel'])
    for (const fantôme of ['faux', 'bidon', 'chaine', 'gabarit']) {
      assert.ok(!specifiers.includes(fantôme), `« ${fantôme} » compté comme import réel`)
    }
  })

  test('les liaisons sont lues correctement', () => {
    const [vrai, reel] = readImports(LEURRES)
    assert.equal(vrai.defaultBinding, 'Vrai')
    assert.deepEqual(vrai.namedBindings, [])
    assert.deepEqual(reel.namedBindings, ['a', 'b'], 'l’alias « b as c » se lit sur le nom SOURCE')
  })

  test('le fragment rendu vient de la source d’origine, pas du texte masqué', () => {
    // `planImportShapeFixes` remplace `statement` par du texte : s'il venait du
    // masque, il réécrirait des espaces à la place du code.
    const [premier] = readImports("import Vrai from 'vrai'")
    assert.equal(premier.statement, "import Vrai from 'vrai'")
    assert.equal(premier.specifier, 'vrai')
  })
})

describe('exports — les fantômes ne comptent plus', () => {
  const LEURRES = [
    '// export const faux = 1',
    '/* export function bidon() {} */',
    'const t = "export const chaine = 2"',
    'export const vrai = 3',
    'export function aussiVrai() {}',
    'export default function App() {}',
  ].join('\n')

  test('seuls les exports réels sont rendus', () => {
    const e = readModuleExports(LEURRES)
    assert.deepEqual([...e.named].sort(), ['aussiVrai', 'vrai'])
    assert.equal(e.hasDefault, true)
  })

  test('un « export default » en commentaire ne crée pas de défaut', () => {
    const e = readModuleExports('// export default App\nexport const a = 1')
    assert.equal(e.hasDefault, false, 'un défaut fantôme fait rater une réparation d’import')
  })

  test('la ré-exportation nommée est lue', () => {
    const e = readModuleExports("export { c, d as e } from './autre'")
    assert.deepEqual([...e.named].sort(), ['c', 'e'])
  })
})

// ===========================================================================
describe('balises de bloc de code — retirées par PAIRE', () => {
  test('un fichier entièrement emballé est déballé', () => {
    assert.equal(stripFormattingArtifacts('```ts\nconst a = 1\n```'), 'const a = 1')
    assert.equal(stripFormattingArtifacts('```\nconst a = 1\n```'), 'const a = 1')
  })

  test('un README qui se TERMINE par un bloc garde sa clôture', () => {
    const readme = '# Titre\n\n```bash\nnpm install\n```'
    assert.equal(
      stripFormattingArtifacts(readme, { markdown: true }), readme,
      'la ligne de clôture a été retirée : le bloc reste ouvert et le Markdown est cassé.',
    )
  })

  test('un README emballé EN PLUS est bien déballé', () => {
    const emballé = '````md\n# Titre\n\n```bash\nnpm install\n```\n````'
    const r = stripFormattingArtifacts(emballé, { markdown: true })
    assert.ok(r.startsWith('# Titre'), r)
  })

  test('un bloc INTERNE à un Markdown n’est jamais touché', () => {
    const src = '# Titre\n\n```js\nconst a = 1\n```\n\nFin.'
    assert.equal(stripFormattingArtifacts(src, { markdown: true }), src)
    assert.equal(stripFormattingArtifacts(src), src)
  })

  test('sur un fichier de code, une balise finale orpheline reste un artefact', () => {
    assert.equal(stripFormattingArtifacts('const a = 1\n```'), 'const a = 1')
  })

  test('BOM, balise de réflexion et code nu', () => {
    assert.equal(stripFormattingArtifacts('\uFEFFconst a = 1'), 'const a = 1')
    assert.equal(stripFormattingArtifacts('<think>bla</think>const a = 1'), 'const a = 1')
    assert.equal(stripFormattingArtifacts('const a = 1'), 'const a = 1')
  })

  test('bout en bout : le README livré reste intact', () => {
    const readme = '# Projet\n\nInstallation :\n\n```bash\nnpm install\nnpm run dev\n```'
    assert.equal(sanitizeGeneratedFileContent('README.md', readme), readme)
  })

  test('bout en bout : les autres documents de prose aussi', () => {
    for (const nom of ['docs/guide.md', 'NOTES.txt', 'a.mdx', 'b.markdown']) {
      const src = 'Texte.\n\n```sh\nls\n```'
      assert.equal(sanitizeGeneratedFileContent(nom, src), src, nom)
    }
  })
})

// ===========================================================================
describe('JSON approximatif — réparé sans altérer les chaînes', () => {
  test('les vraies virgules finales et commentaires partent', () => {
    assert.deepEqual(tryParseJson('{"a":1,}'), { a: 1 })
    assert.deepEqual(tryParseJson('{"a":1 // note\n}'), { a: 1 })
    assert.deepEqual(tryParseJson('{"a":1 /* note */}'), { a: 1 })
    assert.deepEqual(tryParseJson('{"l":[1,2,],}'), { l: [1, 2] })
  })

  test('le CONTENU des chaînes est rendu tel quel', () => {
    const CAS: Array<[string, unknown]> = [
      ['{"note":"un, deux, }","a":1,}', { note: 'un, deux, }', a: 1 }],
      ['{"l":["a, ]"],}', { l: ['a, ]'] }],
      ['{"url":"https://x.fr", // note\n "a":1}', { url: 'https://x.fr', a: 1 }],
      ['{"motif":"/* pas un commentaire */", /* vrai */ "a":1}', { motif: '/* pas un commentaire */', a: 1 }],
      ['{"t":"virgule finale, ]","b":2,}', { t: 'virgule finale, ]', b: 2 }],
    ]
    for (const [src, attendu] of CAS) {
      assert.deepEqual(
        tryParseJson(src), attendu,
        `réparation destructrice sur ${src} — le fichier reste valide mais la donnée est fausse.`,
      )
    }
  })

  test('un JSON déjà valide traverse sans être touché', () => {
    const src = '{"note":"un, deux, }","liste":[1,2,3],"vide":{}}'
    assert.deepEqual(tryParseJson(src), JSON.parse(src))
  })

  test('un JSON irréparable rend null plutôt qu’une invention', () => {
    assert.equal(tryParseJson("{'a':1,}"), null)
    assert.equal(tryParseJson('pas du json'), null)
    assert.equal(tryParseJson(''), null)
  })

  test('bout en bout : un package.json approximatif est réparé sans perte', () => {
    const brut = '{\n  "name": "demo", // le nom\n  "version": "1.0.0",\n}'
    const r = sanitizeGeneratedFileContent('package.json', brut)
    const relu = JSON.parse(r)
    assert.equal(relu.name, 'demo')
    assert.equal(relu.version, '1.0.0')
  })
})
