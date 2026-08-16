import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyTargetedRepair,
  buildTargetedRepairScope,
} from '../services/codeTargetedRepairScope.ts'
import {
  buildTargetedRepairMessages,
  runTargetedRepairPass,
} from '../services/codeTargetedRepairPass.ts'
import { pickBestDelivery } from '../services/codeBestDeliverySelection.ts'
import { inspectCodePatchRegression } from '../services/codeRegressionGuard.ts'
import { serializeProjectTreeEmission } from '../services/codeProjectEmission.ts'
import type { CodeFile } from '../services/codeOrchestratorTypes.ts'

/** Reduction du projet du run 1061: des emoji dans DEUX fichiers sur six. */
const PROJECT: CodeFile[] = [
  {
    name: 'src/pages/HomePage.tsx',
    language: 'tsx',
    content: [
      'export default function HomePage() {',
      '  return (<section>',
      '    <div><span>☕</span><h3>Torrefaction</h3></div>',
      '    <div><span>🌍</span><h3>Origines</h3></div>',
      '  </section>)',
      '}',
    ].join('\n'),
  },
  {
    name: 'src/components/Footer/Footer.tsx',
    language: 'tsx',
    content: 'export default function Footer() {\n  return <footer><span>📍</span>Lyon</footer>\n}',
  },
  { name: 'src/pages/AdminPage.tsx', language: 'tsx', content: 'export default function AdminPage() {\n  return <main>Commandes</main>\n}' },
  { name: 'src/styles/global.css', language: 'css', content: ':root { --olive: #6b705c; }' },
  { name: 'package.json', language: 'json', content: '{"name":"brulerie","scripts":{"dev":"vite","build":"vite build"}}' },
  { name: 'README.md', language: 'markdown', content: '# Brulerie Nomade' },
]

describe('portee de la passe ciblee — la ou le defaut est OBSERVABLE', () => {
  test('real_iconography ne vise que les fichiers qui portent des emoji', () => {
    const scope = buildTargetedRepairScope({ files: PROJECT, failedChecks: ['real_iconography'] })
    assert.deepEqual(
      scope.targets.map((f) => f.name).sort(),
      ['src/components/Footer/Footer.tsx', 'src/pages/HomePage.tsx'],
    )
    // Le reste du projet est declare intouchable, package.json compris.
    assert.ok(scope.protectedPaths.includes('package.json'))
    assert.ok(scope.protectedPaths.includes('src/pages/AdminPage.tsx'))
  })

  // Cas REEL du run 1061: la porte `real_iconography` echouait sur des etoiles
  // produites par `{'★'.repeat(rating)}`. Le juge mesure le DOM rendu; l analyse
  // de source ne voyait rien entre deux balises. Portee mesuree sur les 36
  // fichiers reellement livres: 0 cible avant, 2 apres.
  test('un emoji dans une EXPRESSION JS est vu, pas seulement entre deux balises', () => {
    const stars: CodeFile = {
      name: 'src/components/Testimonials.tsx',
      language: 'tsx',
      content: "export default function T({ rating }: { rating: number }) {\n"
        + "  return <div className=\"stars\">{'★'.repeat(rating)}{'☆'.repeat(5 - rating)}</div>\n}",
    }
    const data: CodeFile = {
      name: 'src/utils/constants.ts',
      language: 'typescript',
      content: "export const FEATURES = [{ icon: '🌍', label: 'Origines' }]\n",
    }
    const clean: CodeFile = { name: 'src/utils/theme.ts', language: 'typescript', content: 'export const olive = "#6b705c"\n' }

    const scope = buildTargetedRepairScope({ files: [stars, data, clean], failedChecks: ['real_iconography'] })
    assert.deepEqual(
      scope.targets.map((f) => f.name).sort(),
      ['src/components/Testimonials.tsx', 'src/utils/constants.ts'],
    )
    assert.deepEqual(scope.protectedPaths, ['src/utils/theme.ts'])
  })

  test('la portee est bornee: un patch n embarque jamais tout le projet', () => {
    const wide = Array.from({ length: 30 }, (_, i) => ({
      name: `src/pages/P${i}.tsx`, language: 'tsx', content: '<img src="a.png" />',
    }))
    const scope = buildTargetedRepairScope({ files: wide, failedChecks: ['image_dimensions'] })
    assert.equal(scope.targets.length, 8)
    assert.equal(scope.protectedPaths.length, 22)
  })

  test('un critere inconnu retombe sur markup+styles, jamais sur la config', () => {
    const scope = buildTargetedRepairScope({ files: PROJECT, failedChecks: ['critere_invente'] })
    assert.equal(scope.targets.some((f) => f.name === 'package.json'), false)
    assert.equal(scope.targets.some((f) => f.name === 'src/styles/global.css'), true)
  })

  test('la consigne nomme les cibles ET les intouchables', () => {
    const scope = buildTargetedRepairScope({ files: PROJECT, failedChecks: ['real_iconography'] })
    const messages = buildTargetedRepairMessages({ prompt: 'site de brulerie', critique: 'emoji', scope })
    assert.equal(messages.length, 2)
    assert.ok(messages[1].content.includes('src/pages/HomePage.tsx'))
    assert.ok(messages[1].content.includes('package.json'))
    assert.ok(messages[0].content.includes('Tu ne supprimes aucun fichier'))
  })
})

describe('fusion du patch — structurellement incapable de detruire', () => {
  const scope = buildTargetedRepairScope({ files: PROJECT, failedChecks: ['real_iconography'] })

  test('un patch valide remplace les cibles et ne touche a rien d autre', () => {
    const patched = applyTargetedRepair({
      before: PROJECT,
      scope,
      produced: [{
        name: 'src/pages/HomePage.tsx', language: 'tsx',
        content: 'export default function HomePage() {\n  return <section><svg viewBox="0 0 24 24"><path d="M4 4h16" /></svg></section>\n}',
      }],
    })
    assert.deepEqual(patched.patched, ['src/pages/HomePage.tsx'])
    assert.equal(patched.files.length, PROJECT.length)
    assert.equal(patched.files.find((f) => f.name === 'package.json')!.content, PROJECT[4].content)
    assert.ok(patched.files.find((f) => f.name === 'src/pages/HomePage.tsx')!.content.includes('<svg'))
    // Le defaut exact du run 1061: removed_file / removed_script / removed_export.
    assert.equal(inspectCodePatchRegression(PROJECT, patched.files).ok, true)
  })

  test('le modele ne peut PAS supprimer un fichier en l omettant', () => {
    const patched = applyTargetedRepair({ before: PROJECT, scope, produced: [] })
    assert.deepEqual(patched.files.map((f) => f.name), PROJECT.map((f) => f.name))
    assert.deepEqual(patched.patched, [])
  })

  test('une reecriture hors portee est REFUSEE, pas appliquee', () => {
    const patched = applyTargetedRepair({
      before: PROJECT,
      scope,
      produced: [{ name: 'package.json', language: 'json', content: '{"name":"autre"}' }],
    })
    assert.equal(patched.files.find((f) => f.name === 'package.json')!.content, PROJECT[4].content)
    assert.deepEqual(patched.rejected, [{ path: 'package.json', reason: 'fichier protege hors portee de la passe' }])
  })

  test('vider un fichier n est pas le reparer', () => {
    const patched = applyTargetedRepair({
      before: PROJECT, scope,
      produced: [{ name: 'src/pages/HomePage.tsx', language: 'tsx', content: '   \n' }],
    })
    assert.equal(patched.files.find((f) => f.name === 'src/pages/HomePage.tsx')!.content, PROJECT[0].content)
    assert.equal(patched.rejected[0].reason, 'contenu vide')
  })

  test('un fichier neuf n est accepte que s il est reellement importe', () => {
    const withImport = applyTargetedRepair({
      before: PROJECT, scope,
      produced: [
        { name: 'src/pages/HomePage.tsx', language: 'tsx', content: "import Icon from '../components/Icon'\nexport default function HomePage() { return <Icon /> }" },
        { name: 'src/components/Icon.tsx', language: 'tsx', content: 'export default function Icon() { return <svg /> }' },
      ],
    })
    assert.deepEqual(withImport.added, ['src/components/Icon.tsx'])

    const orphan = applyTargetedRepair({
      before: PROJECT, scope,
      produced: [
        { name: 'src/pages/HomePage.tsx', language: 'tsx', content: 'export default function HomePage() { return <svg /> }' },
        { name: 'src/components/Orphelin.tsx', language: 'tsx', content: 'export default function Orphelin() { return null }' },
      ],
    })
    assert.deepEqual(orphan.added, [])
    assert.equal(orphan.rejected[0].reason, 'fichier neuf jamais importe par un fichier patche')
  })
})

describe('execution de la passe ciblee', () => {
  test('un patch emis au protocole VFS est applique sans perte', async () => {
    const result = await runTargetedRepairPass({
      prompt: 'site de brulerie',
      files: PROJECT,
      failedChecks: ['real_iconography'],
      critique: 'Remplace les emoji par des SVG inline.',
      model: 'test',
      generate: async () => serializeProjectTreeEmission([{
        path: 'src/components/Footer/Footer.tsx',
        content: 'export default function Footer() {\n  return <footer><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" /></svg>Lyon</footer>\n}',
      }]),
    })
    assert.equal(result.changed, true)
    assert.deepEqual(result.patched, ['src/components/Footer/Footer.tsx'])
    assert.equal(result.files.length, PROJECT.length)
    assert.equal(inspectCodePatchRegression(PROJECT, result.files).ok, true)
  })

  // Les deux corrections se composent: le modele ecrit des en-tetes NUS
  // (forme reellement observee au run 1061), le parseur les lit, et la fusion
  // n applique que les cibles autorisees.
  test('un patch aux en-tetes NUS (forme reelle du modele) est applique', async () => {
    const patched = 'export default function Footer() {\n  return <footer><svg viewBox="0 0 24 24"><path d="M12 2v20" /></svg>Lyon</footer>\n}'
    const result = await runTargetedRepairPass({
      prompt: 'site de brulerie',
      files: PROJECT,
      failedChecks: ['real_iconography'],
      critique: 'Remplace les emoji par des SVG inline.',
      model: 'test',
      generate: async () => [
        '<<<AURORA_CODE_VFS/1>>>',
        'AURORA_FILE {"path":"src/components/Footer/Footer.tsx","length":123,"encoding":"utf8","language":"tsx"}',
        patched,
        '<<<AURORA_END>>>',
        '',
      ].join('\n'),
    })

    assert.equal(result.changed, true)
    assert.deepEqual(result.patched, ['src/components/Footer/Footer.tsx'])
    assert.equal(result.files.find((f) => f.name === 'src/components/Footer/Footer.tsx')!.content, patched)
    assert.equal(result.files.some((f) => f.name === 'main.js'), false)
    assert.equal(inspectCodePatchRegression(PROJECT, result.files).ok, true)
  })

  test('une reponse illisible laisse le livrable EXACTEMENT intact', async () => {
    const result = await runTargetedRepairPass({
      prompt: 'site de brulerie', files: PROJECT, failedChecks: ['real_iconography'],
      critique: 'emoji', model: 'test',
      generate: async () => 'Je ne peux pas faire cela.',
    })
    assert.equal(result.changed, false)
    assert.deepEqual(result.files, PROJECT)
  })

  test('aucune cible: on ne lance meme pas le modele', async () => {
    let called = 0
    const result = await runTargetedRepairPass({
      prompt: 'x', files: [{ name: 'main.py', language: 'python', content: 'print(1)' }],
      failedChecks: ['real_iconography'], critique: 'emoji', model: 'test',
      generate: async () => { called += 1; return '' },
    })
    assert.equal(called, 0)
    assert.equal(result.changed, false)
    assert.match(result.summary, /rien a patcher/)
  })

  test('deux tentatives au plus, la seconde recoit le motif du refus', async () => {
    const seen: string[] = []
    const result = await runTargetedRepairPass({
      prompt: 'x', files: PROJECT, failedChecks: ['real_iconography'],
      critique: 'emoji', model: 'test',
      generate: async (messages) => { seen.push(messages[1].content); return 'rien' },
    })
    assert.equal(seen.length, 2)
    assert.ok(seen[1].includes('TA TENTATIVE PRECEDENTE A ETE REFUSEE'))
    assert.equal(result.changed, false)
  })
})

describe('arbitrage — reparer la porte qui echouait EST le progres', () => {
  test('composition reparee a score de style egal: adoptee', () => {
    const selection = pickBestDelivery(
      { files: PROJECT, visualScore: 100, compositionOk: false, pipelineFailed: false },
      { files: PROJECT, visualScore: 100, compositionOk: true, pipelineFailed: false },
    )
    assert.equal(selection.adopt, true)
    assert.match(selection.reason, /composition reparee/)
  })

  test('composition reparee mais rendu en baisse: refusee', () => {
    const selection = pickBestDelivery(
      { files: PROJECT, visualScore: 100, compositionOk: false, pipelineFailed: false },
      { files: PROJECT, visualScore: 82, compositionOk: true, pipelineFailed: false },
    )
    assert.equal(selection.adopt, false)
  })

  test('la perte de capacites reste redhibitoire, composition reparee ou non', () => {
    const amputated = PROJECT.filter((f) => f.name !== 'src/pages/AdminPage.tsx')
    const selection = pickBestDelivery(
      { files: PROJECT, visualScore: 100, compositionOk: false, pipelineFailed: false },
      { files: amputated, visualScore: 100, compositionOk: true, pipelineFailed: false },
    )
    assert.equal(selection.adopt, false)
    assert.match(selection.reason, /perd des capacites/)
  })
})

describe('la passe verifie son propre patch avant de le proposer', () => {
  const withEmoji: CodeFile[] = [
    { name: 'src/components/Footer.tsx', language: 'tsx', content: 'export default function Footer(){ return <footer><span>📷</span>Instagram</footer> }' },
    { name: 'src/assets/styles/index.css', language: 'css', content: '.footer{display:flex}' },
  ]

  // Run 1151: la passe a « corrige » Footer.tsx et l emoji 📷 y etait toujours.
  // Le patch a donc ete refuse par l arbitre et la passe perdue.
  test('un patch qui laisse l emoji est renvoye au modele, avec le fichier nomme', async () => {
    const prompts: string[] = []
    const result = await runTargetedRepairPass({
      prompt: 'site brulerie', files: withEmoji, failedChecks: ['real_iconography'],
      critique: 'emoji', model: 'test',
      generate: async (messages) => {
        prompts.push(messages[1].content)
        return prompts.length === 1
          // 1re tentative: touche le fichier mais garde l emoji.
          ? serializeProjectTreeEmission([{ path: 'src/components/Footer.tsx', content: 'export default function Footer(){ return <footer><span>📷</span>Insta</footer> }' }])
          // 2e: vraie iconographie.
          : serializeProjectTreeEmission([{ path: 'src/components/Footer.tsx', content: 'export default function Footer(){ return <footer><svg viewBox="0 0 24 24"><rect width="18" height="14" /></svg>Insta</footer> }' }])
      },
    })

    assert.equal(prompts.length, 2)
    assert.match(prompts[1], /emoji sont TOUJOURS presents/)
    assert.match(prompts[1], /src\/components\/Footer\.tsx/)
    assert.equal(result.changed, true)
    assert.equal(/📷/u.test(result.files.find((f) => f.name === 'src/components/Footer.tsx')!.content), false)
  })

  test('un patch qui retire vraiment le defaut passe du premier coup', async () => {
    let calls = 0
    const result = await runTargetedRepairPass({
      prompt: 'site brulerie', files: withEmoji, failedChecks: ['real_iconography'],
      critique: 'emoji', model: 'test',
      generate: async () => {
        calls += 1
        return serializeProjectTreeEmission([{ path: 'src/components/Footer.tsx', content: 'export default function Footer(){ return <footer><svg viewBox="0 0 24 24" /></footer> }' }])
      },
    })
    assert.equal(calls, 1)
    assert.equal(result.changed, true)
  })
})

describe('arbitre — une passe est jugee sur le critere qu elle REPARE', () => {
  const base = { files: PROJECT, visualScore: 80, pipelineFailed: false }

  // Run 1161: la passe reparait `no_empty_section` (composition). Le rendu
  // valait 80/100 avant et apres — elle n avait aucune raison de le changer —
  // et l arbitre la rejetait sur ce seul score. Meme piege qu au run 1091,
  // revenu par une autre porte.
  test('composition reparee a rendu constant: adoptee', () => {
    const selection = pickBestDelivery(
      { ...base, compositionOk: false },
      { ...base, compositionOk: true },
    )
    assert.equal(selection.adopt, true)
    assert.match(selection.reason, /composition repare/)
  })

  test('accessibilite ou performance reparee a rendu constant: adoptee', () => {
    const selection = pickBestDelivery(
      { ...base, compositionOk: true, gates: { accessibilite: false, performance: true } },
      { ...base, compositionOk: true, gates: { accessibilite: true, performance: true } },
    )
    assert.equal(selection.adopt, true)
    assert.match(selection.reason, /accessibilite repare/)
  })

  test('une porte CASSEE au passage interdit l adoption', () => {
    const selection = pickBestDelivery(
      { ...base, compositionOk: false, gates: { performance: true } },
      { ...base, compositionOk: true, gates: { performance: false } },
    )
    assert.equal(selection.adopt, false)
    assert.match(selection.reason, /casse performance/)
  })

  test('rien de repare et rendu identique: livrable precedent conserve', () => {
    const selection = pickBestDelivery(
      { ...base, compositionOk: false },
      { ...base, compositionOk: false },
    )
    assert.equal(selection.adopt, false)
  })

  test('une porte reparee ne rachete pas une perte de rendu', () => {
    const selection = pickBestDelivery(
      { ...base, compositionOk: false },
      { ...base, visualScore: 62, compositionOk: true },
    )
    assert.equal(selection.adopt, false)
  })
})
