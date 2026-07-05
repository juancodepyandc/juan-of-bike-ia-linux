/**
 * Unit tests for the Cowork planner JSON parser. The parser is the gate
 * between LLM output and the deterministic executor — it must be strict but
 * also resilient (fenced code blocks, trailing prose, etc.).
 * Run: node --experimental-strip-types --test src/__tests__/coworkPlanner.test.ts
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import {
  ensureFinishAction,
  extractJsonObject,
  parsePlan,
  planSignature,
  postProcessPlan,
  repairExtensionBlockedWebResearchPlan,
  repairMetaOnlyReplyPlan,
  stripFinishIfReadOnlyPlan,
  validateAction,
} from '../services/coworkPlanParser.ts'
import type { CoworkPlan } from '../services/coworkTypes.ts'

describe('extractJsonObject', () => {
  test('bare JSON object', () => {
    const out = extractJsonObject('{"a":1}')
    assert.equal(out, '{"a":1}')
  })
  test('JSON with leading prose', () => {
    const out = extractJsonObject('Voici la reponse: {"a":1} fin.')
    assert.equal(out, '{"a":1}')
  })
  test('fenced JSON block', () => {
    const out = extractJsonObject('```json\n{"a":1}\n```')
    assert.equal(out, '{"a":1}')
  })
  test('fenced block without language tag', () => {
    const out = extractJsonObject('```\n{"a":1}\n```')
    assert.equal(out, '{"a":1}')
  })
  test('returns null on garbage', () => {
    assert.equal(extractJsonObject('no json at all'), null)
  })
})

describe('planNextStep - deterministic workspace exploration', () => {
  test('demande image avec references connues -> recherche visuelle puis generation module image', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const prompt = 'créer moi une image avec 2 célébrité : Emmanuel Macron et Kirua dans hunter x hunter et comme fond un décor présidentiel'
    const first = await planNextStep({
      userPrompt: prompt,
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [],
    })

    assert.equal(first.actions[0].kind, 'think')
    assert.equal(first.actions[1].kind, 'web_search')
    if (first.actions[1].kind === 'web_search') {
      assert.match(first.actions[1].query, /Macron/i)
      assert.match(first.actions[1].query, /Kirua|hunter/i)
    }
    assert.equal(first.actions.some((a) => a.kind === 'reply'), false)
    assert.equal(first.actions.some((a) => a.kind === 'finish'), false)

    const referenceSearch = {
      action: first.actions[1],
      result: {
        ok: true,
        durationMs: 12,
        output: [
          '1. Emmanuel Macron - official portrait',
          '   https://www.elysee.fr/emmanuel-macron',
          '   Official profile and presidential imagery.',
          '',
          '2. Killua Zoldyck - character reference',
          '   https://hunterxhunter.fandom.com/wiki/Killua_Zoldyck',
          '   Character design notes and visual traits.',
        ].join('\n'),
        data: {
          hits: [
            { title: 'Emmanuel Macron - official portrait', url: 'https://www.elysee.fr/emmanuel-macron', snippet: 'Official profile and presidential imagery.' },
            { title: 'Killua Zoldyck - character reference', url: 'https://hunterxhunter.fandom.com/wiki/Killua_Zoldyck', snippet: 'Character design notes and visual traits.' },
          ],
        },
      },
    }

    const second = await planNextStep({
      userPrompt: prompt,
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [referenceSearch],
    })

    assert.equal(second.actions[0].kind, 'think')
    assert.equal(second.actions[1].kind, 'fetch')
    assert.equal(second.actions[2].kind, 'fetch')
    if (second.actions[1].kind === 'fetch') {
      assert.match(second.actions[1].url, /elysee/i)
    }

    const third = await planNextStep({
      userPrompt: prompt,
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [
        referenceSearch,
        {
          action: second.actions[1],
          result: {
            ok: true,
            durationMs: 22,
            output: 'Official portrait: formal suit, presidential context, blue-white-red visual codes.',
          },
        },
        {
          action: second.actions[2],
          result: {
            ok: true,
            durationMs: 24,
            output: 'Killua character traits: white hair, agile silhouette, electric blue aura, anime styling.',
          },
        },
      ],
    })

    assert.equal(third.actions[0].kind, 'think')
    assert.equal(third.actions[1].kind, 'connector')
    if (third.actions[1].kind === 'connector') {
      assert.equal(third.actions[1].connector, 'aurora_image')
      assert.equal(third.actions[1].action, 'generate')
      assert.match(String(third.actions[1].params?.prompt), /brief client reel/i)
      assert.match(String(third.actions[1].params?.prompt), /Pack de ressources/i)
      assert.match(String(third.actions[1].params?.prompt), /Official portrait/i)
      assert.match(String(third.actions[1].params?.prompt), /Format de sortie attendu/i)
    }
  })

  test('generation image terminee -> reply final avec chemin et mention des boutons artefact', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'genere une image de chevalier neon',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [
        {
          action: {
            kind: 'connector',
            connector: 'aurora_image',
            action: 'generate',
            params: { prompt: 'chevalier neon' },
          },
          result: {
            ok: true,
            durationMs: 30_000,
            output: 'Image generee : C:/Users/Juan/Desktop/ia/AuroraIA-v2/application/output/cowork/img_123.png',
            data: { path: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application/output/cowork/img_123.png' },
          },
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'reply')
    assert.equal(plan.actions[1].kind, 'finish')
    if (plan.actions[0].kind === 'reply') {
      assert.match(plan.actions[0].message, /Creation terminee/)
      assert.match(plan.actions[0].message, /img_123\.png/)
      assert.match(plan.actions[0].message, /telechargement/i)
    }
  })

  test('demande jeu/app riche -> prompt module impose logo, ressources, app lancable et verification', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'avec ce modele 3D fais le personnage principal d un jeu, avec un vrai logo, une app lancable et des tests',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      projectThread: {
        version: 1,
        updatedAt: Date.now(),
        activeArtifactId: 'model-1',
        artifacts: [
          {
            id: 'model-1',
            kind: 'model3d',
            label: 'Modele 3D v1 - heros reference',
            status: 'ready',
            version: 1,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            path: 'output/cowork/hero.glb',
            active: true,
          },
        ],
        stages: [],
        notes: [],
      },
      history: [],
    })

    assert.equal(plan.actions[0].kind, 'think')
    assert.equal(plan.actions[1].kind, 'connector')
    if (plan.actions[1].kind === 'connector') {
      assert.equal(plan.actions[1].connector, 'aurora_code')
      assert.equal(plan.actions[1].action, 'generate')
      assert.equal(plan.actions[1].params?.model_path, 'output/cowork/hero.glb')
      const prompt = String(plan.actions[1].params?.prompt)
      assert.match(prompt, /Livrable jeu\/app/i)
      assert.match(prompt, /logo/i)
      assert.match(prompt, /Contrat app lancable/i)
      assert.match(prompt, /Tester un chemin utilisateur minimal/i)
      assert.match(prompt, /Reference active Cowork/i)
    }
  })

  test('treats "mon bureau" as the user Desktop and not the repo workspace', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'scan les fichiers de mon bureau et fait moi dans le dossier un pdf sur la seconde guerre mondiale pour avoir tout bon au controle',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [],
    })

    assert.equal(plan.actions[0].kind, 'think')
    assert.equal(plan.actions[1].kind, 'list_dir')
    if (plan.actions[1].kind === 'list_dir') {
      assert.equal(plan.actions[1].path, 'C:/Users/Juan/Desktop')
    }
    assert.equal(plan.actions.some((a) => a.kind === 'shell' && a.command === 'rg'), false)
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
  })

  test('scanne le Bureau utilisateur pour les PDF existants sans demander de chemin', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'scan mon bureau et ressort moi que les fichiers pdf',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [],
    })

    assert.equal(plan.actions[0].kind, 'think')
    assert.equal(plan.actions[1].kind, 'list_dir')
    if (plan.actions[1].kind === 'list_dir') {
      assert.equal(plan.actions[1].path, 'C:/Users/Juan/Desktop')
      assert.equal(plan.actions[1].depth, 8)
    }
    assert.equal(plan.actions.some((a) => a.kind === 'reply'), false)
    assert.equal(plan.actions.some((a) => a.kind === 'write_file'), false)
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
  })

  test('retourne seulement les PDF apres le scan du Bureau utilisateur', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'scan mon bureau et ressort moi que les fichiers pdf',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [
        {
          action: { kind: 'list_dir', path: 'C:/Users/Juan/Desktop', depth: 8 },
          result: {
            ok: true,
            durationMs: 1,
            output: [
              'C:/Users/Juan/Desktop/cours.pdf',
              'C:/Users/Juan/Desktop/photo.png',
              'C:/Users/Juan/Desktop/Sous dossier/fiche.PDF',
              'C:/Users/Juan/Desktop/notes.docx',
            ].join('\n'),
          },
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'reply')
    assert.equal(plan.actions[1].kind, 'finish')
    assert.equal(plan.actions.some((a) => a.kind === 'write_file'), false)
    if (plan.actions[0].kind === 'reply') {
      assert.match(plan.actions[0].message, /cours\.pdf/)
      assert.match(plan.actions[0].message, /fiche\.PDF/)
      assert.doesNotMatch(plan.actions[0].message, /photo\.png/)
      assert.doesNotMatch(plan.actions[0].message, /notes\.docx/)
    }
  })

  test('creates and verifies a PDF after scanning the user Desktop', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'scan les fichiers de mon bureau et fait moi dans le dossier un pdf sur la seconde guerre mondiale pour avoir tout bon au controle',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [
        {
          action: { kind: 'list_dir', path: 'C:/Users/Juan/Desktop', depth: 2 },
          result: { ok: true, durationMs: 1, output: 'photo.png\nraccourci.lnk\n' },
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'write_file')
    assert.equal(plan.actions[1].kind, 'read_file')
    if (plan.actions[0].kind === 'write_file') {
      assert.equal(plan.actions[0].path, 'C:/Users/Juan/Desktop/seconde_guerre_mondiale_revision.pdf')
      assert.match(plan.actions[0].content, /^%PDF-1\.4/)
      assert.match(plan.actions[0].content, /\/Type \/Catalog/)
    }
    if (plan.actions[1].kind === 'read_file') {
      assert.equal(plan.actions[1].path, 'C:/Users/Juan/Desktop/seconde_guerre_mondiale_revision.pdf')
    }
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
  })

  test('finalises Desktop PDF only after write and read verification succeeded', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'scan les fichiers de mon bureau et fait moi dans le dossier un pdf sur la seconde guerre mondiale pour avoir tout bon au controle',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [
        {
          action: { kind: 'list_dir', path: 'C:/Users/Juan/Desktop', depth: 2 },
          result: { ok: true, durationMs: 1, output: 'photo.png\n' },
        },
        {
          action: { kind: 'write_file', path: 'C:/Users/Juan/Desktop/seconde_guerre_mondiale_revision.pdf', content: '%PDF-1.4\n' },
          result: { ok: true, durationMs: 1, output: 'Ecrit.' },
        },
        {
          action: { kind: 'read_file', path: 'C:/Users/Juan/Desktop/seconde_guerre_mondiale_revision.pdf' },
          result: { ok: true, durationMs: 1, output: '%PDF-1.4\n' },
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'reply')
    assert.equal(plan.actions[1].kind, 'finish')
    if (plan.actions[0].kind === 'reply') {
      assert.match(plan.actions[0].message, /C:\/Users\/Juan\/Desktop\/seconde_guerre_mondiale_revision\.pdf/)
    }
  })

  test('does not replay previous PDF task when follow-up asks for a Desktop overview', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'donc fait moi un topo de tout les fichiers et dossier dans mon bureau',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [],
      conversationHistory: [
        {
          role: 'user',
          content: 'scan les fichiers de mon bureau et fait moi dans le dossier un pdf sur la seconde guerre mondiale pour avoir tout bon au controle',
        },
        {
          role: 'aurora',
          content: 'C est fait : j ai scanne le dossier Bureau, cree le PDF et verifie qu il est lisible.',
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'think')
    assert.equal(plan.actions[1].kind, 'list_dir')
    if (plan.actions[1].kind === 'list_dir') {
      assert.equal(plan.actions[1].path, 'C:/Users/Juan/Desktop')
    }
    assert.equal(plan.actions.some((a) => a.kind === 'write_file'), false)
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
  })

  test('summarises Desktop listing for a topo request instead of creating a document', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'donc fait moi un topo de tout les fichiers et dossier dans mon bureau',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/ia/AuroraIA-v2/application',
      history: [
        {
          action: { kind: 'list_dir', path: 'C:/Users/Juan/Desktop', depth: 2 },
          result: { ok: true, durationMs: 1, output: 'seconde_guerre_mondiale_revision.pdf\nCours\nphoto.png\nnotes.txt\n' },
        },
      ],
      conversationHistory: [
        {
          role: 'aurora',
          content: 'C est fait : fichier C:/Users/Juan/Desktop/seconde_guerre_mondiale_revision.pdf',
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'reply')
    assert.equal(plan.actions[1].kind, 'finish')
    assert.equal(plan.actions.some((a) => a.kind === 'write_file'), false)
    if (plan.actions[0].kind === 'reply') {
      assert.match(plan.actions[0].message, /Topo du dossier Bureau/)
      assert.match(plan.actions[0].message, /seconde_guerre_mondiale_revision\.pdf/)
      assert.match(plan.actions[0].message, /aucune creation de fichier n a ete relancee/)
    }
  })

  test('starts broad file navigation with think + rg --files', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'navigue entre tous les fichiers du projet cowork et analyse le repo',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: '/repo',
      history: [],
    })

    assert.equal(plan.actions[0].kind, 'think')
    assert.equal(plan.actions[1].kind, 'shell')
    if (plan.actions[1].kind === 'shell') {
      assert.equal(plan.actions[1].command, 'rg')
      assert.ok(plan.actions[1].args.includes('--files'))
    }
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
  })

  test('reads likely pivot files after workspace inventory', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'parcours tous les fichiers cowork et fais une synthese',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: '/repo',
      history: [
        {
          action: { kind: 'shell', command: 'rg', args: ['--files'] },
          result: {
            ok: true,
            durationMs: 1,
            output: [
              'package.json',
              'src/App.tsx',
              'src/services/coworkPlanner.ts',
              'src/services/coworkOrchestrator.ts',
              'src/__tests__/coworkPlanner.test.ts',
              'public/logo.png',
            ].join('\n'),
          },
        },
      ],
    })

    const readPaths = plan.actions
      .filter((a) => a.kind === 'read_file')
      .map((a) => a.path)
    assert.ok(readPaths.includes('src/services/coworkPlanner.ts'))
    assert.ok(readPaths.includes('src/services/coworkOrchestrator.ts'))
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
  })

  test('synthesises pure workspace analysis after files are read', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'analyse tous les fichiers du projet',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: '/repo',
      history: [
        {
          action: { kind: 'shell', command: 'rg', args: ['--files'] },
          result: { ok: true, durationMs: 1, output: 'package.json\n' },
        },
        {
          action: { kind: 'read_file', path: 'package.json' },
          result: { ok: true, durationMs: 1, output: '{"scripts":{"test":"node --test"}}' },
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'reply')
    assert.equal(plan.actions[1].kind, 'finish')
    if (plan.actions[0].kind === 'reply') {
      assert.match(plan.actions[0].message, /Carte du workspace/)
      assert.match(plan.actions[0].message, /package\.json/)
    }
  })
})

describe('planNextStep - deterministic creative reflection', () => {
  test('starts creative strategic requests with long reflection instead of stopping', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'sois creatif et propose une direction ambitieuse pour mon assistant',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: '/repo',
      history: [],
    })

    assert.equal(plan.actions[0].kind, 'think_long')
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
    if (plan.actions[0].kind === 'think_long') {
      assert.equal(plan.actions[0].topic, 'exploration creative')
      assert.match(plan.actions[0].prompt, /artefact peut etre produit/)
    }
  })
})

describe('planNextStep - native academic web research', () => {
  test('starts BAC/STI2D subject-bank requests with web_search, not Aurora-Connect browser actions', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'recherche en ligne de vrais sujets qui vont tomber dans la banque des fichiers pour le bac sti2d specialite sin et cree une fiche pdf pour les tp',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: '/repo',
      history: [],
    })

    assert.equal(plan.actions[0].kind, 'think')
    assert.equal(plan.actions[1].kind, 'web_search')
    assert.equal(plan.actions.some((a) => a.kind === 'browser'), false)
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
    if (plan.actions[1].kind === 'web_search') {
      assert.match(plan.actions[1].query, /STI2D|sti2d/)
      assert.match(plan.actions[1].query, /SIN|sin/)
    }
  })

  test('uses conversation history when a short follow-up keeps the same academic research mission', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'schema et competence pour tout connaitre',
      conversationHistory: [
        {
          role: 'user',
          content: 'maintenant creer moi une fiche de revision en pdf par rapport a des recherches en ligne au sujet de la banque des fichiers pour le bac sti2d en specialite sin pour les tp',
        },
      ],
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: '/repo',
      history: [],
    })

    assert.equal(plan.actions[0].kind, 'think')
    assert.equal(plan.actions[1].kind, 'web_search')
    assert.equal(plan.actions.some((a) => a.kind === 'browser'), false)
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
    if (plan.actions[1].kind === 'web_search') {
      assert.match(plan.actions[1].query, /STI2D|sti2d/)
      assert.match(plan.actions[1].query, /SIN|sin/)
      assert.match(plan.actions[1].query, /competences|schema|TP|tp/)
    }
  })

  test('treats "oui" after official TP clarification as a continuation that searches, not a chat reply', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'oui',
      conversationHistory: [
        {
          role: 'user',
          content: 'maintenant creer moi une fiche de revision en pdf par rapport a des recherches en ligne au sujet de la banque des fichiers pour le bac sti2d en specialite sin pour les tp',
        },
        {
          role: 'aurora',
          content: 'Pourriez-vous preciser si vous cherchez des fichiers TP officiels sur eduscol.education.fr ou une synthese theorique sans ressources externes ?',
        },
        {
          role: 'user',
          content: 'je cherche des fichiers officiel de tp',
        },
        {
          role: 'aurora',
          content: 'Voulez-vous rechercher specifiquement les fichiers TP officiels sur eduscol.education.fr ou consulter des ressources theoriques complementaires ?',
        },
      ],
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/AuroraIA-v2/application',
      history: [],
    })

    assert.equal(plan.actions[0].kind, 'think')
    assert.equal(plan.actions[1].kind, 'web_search')
    assert.equal(plan.actions.some((a) => a.kind === 'reply'), false)
    if (plan.actions[1].kind === 'web_search') {
      assert.match(plan.actions[1].query, /STI2D|sti2d/)
      assert.match(plan.actions[1].query, /SIN|sin/)
      assert.match(plan.actions[1].query, /officiel|eduscol|education/i)
    }
  })

  test('retries with a targeted official query when the first academic search is empty', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'maintenant creer moi une fiche de revision en pdf par rapport a des recherches en ligne au sujet de la banque des fichiers pour le bac sti2d en specialite sin pour les tp',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: '/repo',
      history: [
        {
          action: { kind: 'web_search', query: 'requete trop vague', limit: 6 },
          result: {
            ok: true,
            durationMs: 1,
            output: '',
            data: { hits: [] },
          },
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'web_search')
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
    if (plan.actions[0].kind === 'web_search') {
      assert.match(plan.actions[0].query, /STI2D|sti2d/)
      assert.match(plan.actions[0].query, /SIN|sin/)
      assert.match(plan.actions[0].query, /officiel|officielles|eduscol|education/i)
    }
  })

  test('fetches useful official URLs after native web_search results', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const plan = await planNextStep({
      userPrompt: 'recherche des sujets officiels bac sti2d sin en ligne pour une fiche de revision',
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: '/repo',
      history: [
        {
          action: { kind: 'web_search', query: 'bac sti2d sin sujets officiels', limit: 6 },
          result: {
            ok: true,
            durationMs: 1,
            output: '1. Sujet officiel\n   https://eduscol.education.fr/sujet-sti2d.pdf\n2. Forum\n   https://example.com/forum',
            data: {
              hits: [
                { title: 'Sujet officiel', url: 'https://eduscol.education.fr/sujet-sti2d.pdf', snippet: 'annales' },
                { title: 'Forum', url: 'https://example.com/forum', snippet: 'discussion' },
              ],
            },
          },
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'fetch')
    if (plan.actions[0].kind === 'fetch') {
      assert.equal(plan.actions[0].url, 'https://eduscol.education.fr/sujet-sti2d.pdf')
    }
    assert.equal(plan.actions.some((a) => a.kind === 'browser'), false)
    assert.equal(plan.actions.some((a) => a.kind === 'finish'), false)
  })

  test('writes and verifies a PDF after academic official sources were fetched', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const sourceUrl = 'https://eduscol.education.fr/document/sti2d-sin-tp.pdf'
    const plan = await planNextStep({
      userPrompt: 'oui',
      conversationHistory: [
        {
          role: 'user',
          content: 'maintenant creer moi une fiche de revision en pdf par rapport a des recherches en ligne au sujet de la banque des fichiers pour le bac sti2d en specialite sin pour les tp',
        },
        {
          role: 'aurora',
          content: 'Voulez-vous rechercher specifiquement les fichiers TP officiels sur eduscol.education.fr ?',
        },
      ],
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/AuroraIA-v2/application',
      history: [
        {
          action: { kind: 'web_search', query: 'STI2D SIN TP officiel eduscol', limit: 6 },
          result: {
            ok: true,
            durationMs: 1,
            output: `1. Ressource officielle\n   ${sourceUrl}\n   TP SIN`,
            data: { hits: [{ title: 'Ressource officielle', url: sourceUrl, snippet: 'TP SIN' }] },
          },
        },
        {
          action: { kind: 'fetch', url: sourceUrl },
          result: {
            ok: true,
            durationMs: 1,
            output: 'Ressource STI2D SIN : chaine information, protocoles, competences, schema fonctionnel.',
            data: { status: 200, contentType: 'text/plain', bytes: 92 },
          },
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'write_file')
    assert.equal(plan.actions[1].kind, 'read_file')
    if (plan.actions[0].kind === 'write_file') {
      assert.equal(plan.actions[0].path, 'C:/Users/Juan/Desktop/fiche_revision_bac_sti2d_sin_banque_fichiers_tp.pdf')
      assert.match(plan.actions[0].content, /^%PDF-1\.4/)
      assert.match(plan.actions[0].content, /Ressource STI2D SIN/)
    }
    if (plan.actions[1].kind === 'read_file') {
      assert.equal(plan.actions[1].path, 'C:/Users/Juan/Desktop/fiche_revision_bac_sti2d_sin_banque_fichiers_tp.pdf')
    }
  })

  test('finalises the academic PDF only after it was read back successfully', async () => {
    const { planNextStep } = await import('../services/coworkPlanner.ts')
    const path = 'C:/Users/Juan/Desktop/fiche_revision_bac_sti2d_sin_banque_fichiers_tp.pdf'
    const plan = await planNextStep({
      userPrompt: 'oui',
      conversationHistory: [
        {
          role: 'user',
          content: 'maintenant creer moi une fiche de revision en pdf par rapport a des recherches en ligne au sujet de la banque des fichiers pour le bac sti2d en specialite sin pour les tp',
        },
        {
          role: 'aurora',
          content: 'Voulez-vous rechercher specifiquement les fichiers TP officiels sur eduscol.education.fr ?',
        },
      ],
      runtime: 'tauri-desktop',
      capabilities: [],
      workspaceRoot: 'C:/Users/Juan/Desktop/AuroraIA-v2/application',
      history: [
        {
          action: { kind: 'web_search', query: 'STI2D SIN TP officiel eduscol', limit: 6 },
          result: {
            ok: true,
            durationMs: 1,
            output: '1. Ressource officielle\n   https://eduscol.education.fr/document/sti2d-sin-tp.pdf\n   TP SIN',
            data: { hits: [{ title: 'Ressource officielle', url: 'https://eduscol.education.fr/document/sti2d-sin-tp.pdf', snippet: 'TP SIN' }] },
          },
        },
        {
          action: { kind: 'fetch', url: 'https://eduscol.education.fr/document/sti2d-sin-tp.pdf' },
          result: { ok: true, durationMs: 1, output: 'Ressource STI2D SIN', data: { status: 200 } },
        },
        {
          action: { kind: 'write_file', path, content: '%PDF-1.4\n' },
          result: { ok: true, durationMs: 1, output: 'Ecrit.' },
        },
        {
          action: { kind: 'read_file', path },
          result: { ok: true, durationMs: 1, output: '%PDF-1.4\n' },
        },
      ],
    })

    assert.equal(plan.actions[0].kind, 'reply')
    assert.equal(plan.actions[1].kind, 'finish')
    if (plan.actions[0].kind === 'reply') {
      assert.match(plan.actions[0].message, /fiche_revision_bac_sti2d_sin_banque_fichiers_tp\.pdf/)
      assert.doesNotMatch(plan.actions[0].message, /pret a vous aider|prêt à vous aider/i)
    }
  })
})

describe('validateAction — happy paths', () => {
  test('reply with string message', () => {
    const v = validateAction({ kind: 'reply', message: 'salut' })
    assert.equal(v.ok, true)
  })
  test('shell with command + args[]', () => {
    const v = validateAction({ kind: 'shell', command: 'git', args: ['status'] })
    assert.equal(v.ok, true)
  })
  test('shell tolerates missing args (defaults to [])', () => {
    const v = validateAction({ kind: 'shell', command: 'ls' })
    assert.equal(v.ok, true)
    if (v.ok) assert.deepEqual(v.action.kind === 'shell' ? v.action.args : null, [])
  })
  test('fetch with all fields', () => {
    const v = validateAction({
      kind: 'fetch',
      url: 'https://example.com',
      method: 'POST',
      headers: { 'X-Auth': 'token' },
      body: 'payload',
    })
    assert.equal(v.ok, true)
  })
  test('web_search with query', () => {
    const v = validateAction({ kind: 'web_search', query: 'bac sti2d sin sujets officiels', limit: 50 })
    assert.equal(v.ok, true)
    if (v.ok && v.action.kind === 'web_search') {
      assert.equal(v.action.limit, 10)
    }
  })
  test('voice_speak with text', () => {
    const v = validateAction({ kind: 'voice_speak', text: 'bonjour' })
    assert.equal(v.ok, true)
  })
  test('dom_query with selector', () => {
    const v = validateAction({ kind: 'dom_query', selector: '.title' })
    assert.equal(v.ok, true)
  })
})

describe('validateAction — error paths', () => {
  test('missing kind', () => {
    const v = validateAction({ message: 'hi' })
    assert.equal(v.ok, false)
  })
  test('unknown kind', () => {
    const v = validateAction({ kind: 'rm_rf' })
    assert.equal(v.ok, false)
  })
  test('reply without message', () => {
    const v = validateAction({ kind: 'reply' })
    assert.equal(v.ok, false)
  })
  test('write_file without content', () => {
    const v = validateAction({ kind: 'write_file', path: 'a.txt' })
    assert.equal(v.ok, false)
  })
  test('edit_file without oldText', () => {
    const v = validateAction({ kind: 'edit_file', path: 'a.txt', newText: 'x' })
    assert.equal(v.ok, false)
  })
  test('fetch with unsupported method', () => {
    const v = validateAction({ kind: 'fetch', url: 'https://x.com', method: 'TRACE' })
    assert.equal(v.ok, false)
  })
  test('web_search without query', () => {
    const v = validateAction({ kind: 'web_search', query: '' })
    assert.equal(v.ok, false)
  })
  test('shell with non-string command', () => {
    const v = validateAction({ kind: 'shell', command: 123 })
    assert.equal(v.ok, false)
  })
})

describe('parsePlan — well-formed', () => {
  test('minimal valid plan', () => {
    const raw = JSON.stringify({
      reasoning: 'demande triviale',
      actions: [{ kind: 'reply', message: 'salut' }, { kind: 'finish', summary: 'fait' }],
      expectedOutcome: 'salutation rendue',
    })
    const r = parsePlan(raw)
    assert.equal(r.ok, true)
    if (r.ok) assert.equal(r.plan.actions.length, 2)
  })
  test('fenced JSON plan', () => {
    const inner = JSON.stringify({
      reasoning: 'lecture',
      actions: [
        { kind: 'read_file', path: 'src/App.tsx' },
        { kind: 'reply', message: 'Voila' },
        { kind: 'finish', summary: 'OK' },
      ],
      expectedOutcome: 'fichier lu',
    })
    const raw = '```json\n' + inner + '\n```'
    const r = parsePlan(raw)
    assert.equal(r.ok, true)
    if (r.ok) assert.equal(r.plan.actions.length, 3)
  })
})

describe('parsePlan — malformed', () => {
  test('empty', () => {
    const r = parsePlan('')
    assert.equal(r.ok, false)
  })
  test('not JSON', () => {
    const r = parsePlan('Sorry, I cannot help.')
    assert.equal(r.ok, false)
  })
  test('JSON without actions[]', () => {
    const r = parsePlan(JSON.stringify({ reasoning: 'x', expectedOutcome: 'y' }))
    assert.equal(r.ok, false)
  })
  test('actions is not an array', () => {
    const r = parsePlan(JSON.stringify({ reasoning: 'x', expectedOutcome: 'y', actions: 'no' }))
    assert.equal(r.ok, false)
  })
  test('actions[0] missing kind', () => {
    const raw = JSON.stringify({
      reasoning: 'x',
      expectedOutcome: 'y',
      actions: [{ path: 'a.txt' }],
    })
    const r = parsePlan(raw)
    assert.equal(r.ok, false)
  })
  test('action with unknown kind rejects whole plan', () => {
    const raw = JSON.stringify({
      reasoning: 'x',
      expectedOutcome: 'y',
      actions: [
        { kind: 'reply', message: 'a' },
        { kind: 'rm_rf', path: '/' },
      ],
    })
    const r = parsePlan(raw)
    assert.equal(r.ok, false)
  })
})

describe('ensureFinishAction', () => {
  test('appends finish if missing', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [{ kind: 'reply', message: 'hi' }],
    }
    const out = ensureFinishAction(plan)
    assert.equal(out.actions.length, 2)
    assert.equal(out.actions[1].kind, 'finish')
  })
  test('keeps plan unchanged if finish already present', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'hi' },
        { kind: 'finish', summary: 'done' },
      ],
    }
    const out = ensureFinishAction(plan)
    assert.equal(out.actions.length, 2)
    assert.deepEqual(out.actions, plan.actions)
  })
  test('does nothing for empty actions list', () => {
    const plan: CoworkPlan = { reasoning: 'r', expectedOutcome: 'o', actions: [] }
    const out = ensureFinishAction(plan)
    assert.equal(out.actions.length, 0)
  })
})

describe('planSignature', () => {
  test('identical plans produce identical signatures', () => {
    const a: CoworkPlan = {
      reasoning: 'x',
      expectedOutcome: 'y',
      actions: [
        { kind: 'read_file', path: 'src/App.tsx' },
        { kind: 'reply', message: 'salut' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const b: CoworkPlan = {
      reasoning: 'autre raisonnement',  // reasoning is irrelevant
      expectedOutcome: 'autre objectif',
      actions: a.actions.map((act) => ({ ...act })) as typeof a.actions,
    }
    assert.equal(planSignature(a), planSignature(b))
  })
  test('different paths produce different signatures', () => {
    const a: CoworkPlan = {
      reasoning: 'x',
      expectedOutcome: 'y',
      actions: [{ kind: 'read_file', path: 'src/App.tsx' }],
    }
    const b: CoworkPlan = {
      reasoning: 'x',
      expectedOutcome: 'y',
      actions: [{ kind: 'read_file', path: 'src/index.tsx' }],
    }
    assert.notEqual(planSignature(a), planSignature(b))
  })
  test('shell command difference is reflected', () => {
    const a: CoworkPlan = {
      reasoning: 'x',
      expectedOutcome: 'y',
      actions: [{ kind: 'shell', command: 'git', args: ['status'] }],
    }
    const b: CoworkPlan = {
      reasoning: 'x',
      expectedOutcome: 'y',
      actions: [{ kind: 'shell', command: 'git', args: ['log'] }],
    }
    assert.notEqual(planSignature(a), planSignature(b))
  })
})

describe('parsePlan — defensive', () => {
  test('arrays as root rejected', () => {
    const r = parsePlan('[]')
    assert.equal(r.ok, false)
  })
  test('null root rejected', () => {
    const r = parsePlan('null')
    assert.equal(r.ok, false)
  })
  test('extra fields are ignored, plan still valid', () => {
    const r = parsePlan(JSON.stringify({
      reasoning: 'x',
      expectedOutcome: 'y',
      actions: [{ kind: 'reply', message: 'a' }],
      extraField: 42,
      anotherExtra: { nested: true },
    }))
    assert.equal(r.ok, true)
  })
})

// ---------------------------------------------------------------------------
// Critical bug-fix coverage : the LLM sometimes emits Plan #1 ending with
// `finish` after only read-only actions (e.g. read_html + screenshot), which
// short-circuits the synthesis pass. stripFinishIfReadOnlyPlan removes that
// rogue finish so the orchestrator MUST re-plan with read results in history.
// ---------------------------------------------------------------------------
describe('stripFinishIfReadOnlyPlan — the analyse-this-page bug fix', () => {
  test('strips finish from a read-only plan (no reply)', () => {
    const plan: CoworkPlan = {
      reasoning: 'analyse cette page',
      expectedOutcome: 'rapport detaille',
      actions: [
        { kind: 'browser', operation: 'get_active_tab', payload: {} },
        { kind: 'browser', operation: 'read_html', payload: {} },
        { kind: 'browser', operation: 'screenshot', payload: {} },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const out = stripFinishIfReadOnlyPlan(plan)
    assert.equal(out.actions.length, 3, 'finish doit etre retire')
    assert.equal(out.actions[out.actions.length - 1].kind, 'browser')
    assert.notEqual(out, plan, 'doit retourner un nouveau plan')
  })

  test('keeps finish if plan contains a reply before it', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'browser', operation: 'read_html', payload: {} },
        { kind: 'reply', message: 'voici le rapport...' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const out = stripFinishIfReadOnlyPlan(plan)
    assert.equal(out, plan, 'plan deja synthetise → ne pas modifier')
    assert.equal(out.actions.length, 3)
  })

  test('keeps finish if plan contains a write action', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'read_file', path: 'src/App.tsx' },
        { kind: 'write_file', path: 'out.txt', content: 'hello' },
        { kind: 'finish', summary: 'ecrit' },
      ],
    }
    const out = stripFinishIfReadOnlyPlan(plan)
    assert.equal(out, plan, 'write n est pas read-only → garder finish')
  })

  test('keeps finish if plan has shell action (terminal side-effect)', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'shell', command: 'git', args: ['status'] },
        { kind: 'finish', summary: 'verifie' },
      ],
    }
    const out = stripFinishIfReadOnlyPlan(plan)
    assert.equal(out, plan, 'shell pas read-only → garder finish')
  })

  test('does not modify plan with single action (length < 2)', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [{ kind: 'finish', summary: 'fini' }],
    }
    const out = stripFinishIfReadOnlyPlan(plan)
    assert.equal(out, plan)
  })

  test('does not modify plan without trailing finish', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'read_file', path: 'a.txt' },
        { kind: 'reply', message: 'lu' },
      ],
    }
    const out = stripFinishIfReadOnlyPlan(plan)
    assert.equal(out, plan)
  })

  test('strips finish from think+vision_describe+finish (multi-modal read-only)', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'think', topic: 'analyse', thought: 'observer' },
        { kind: 'vision_describe', imageDataUrl: 'data:image/png;base64,xyz', question: 'que voit-on?' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const out = stripFinishIfReadOnlyPlan(plan)
    assert.equal(out.actions.length, 2, 'think + vision_describe sont read-only → finish strippe')
  })
})

describe('postProcessPlan — combined heuristic', () => {
  test('strips finish from read-only plan (no reply)', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'browser', operation: 'read_html', payload: {} },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const out = postProcessPlan(plan)
    assert.equal(out.actions.length, 1)
    assert.equal(out.actions[0].kind, 'browser')
  })

  test('appends finish to plan that lacks one', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'reponse delivree',
      actions: [
        { kind: 'read_file', path: 'a.txt' },
        { kind: 'reply', message: 'voici' },
      ],
    }
    const out = postProcessPlan(plan)
    assert.equal(out.actions.length, 3)
    assert.equal(out.actions[out.actions.length - 1].kind, 'finish')
  })

  test('keeps a properly synthesised plan unchanged (reply + finish)', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'browser', operation: 'read_html', payload: {} },
        { kind: 'reply', message: 'rapport...' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const out = postProcessPlan(plan)
    assert.equal(out.actions.length, 3, 'plan complet → inchange')
  })
})

describe('repairMetaOnlyReplyPlan', () => {
  test('turns a final meta-analysis reply into an internal think step', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        {
          kind: 'reply',
          message: "L'utilisateur demande une fiche de revision sur la banque des fichiers. Il est necessaire de consulter le programme officiel pour identifier les concepts cles.",
        },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const out = repairMetaOnlyReplyPlan(plan, { userPrompt: 'cree une fiche de revision' })
    assert.equal(out.actions.length, 1)
    assert.equal(out.actions[0].kind, 'think')
    if (out.actions[0].kind === 'think') {
      assert.match(out.actions[0].thought, /Objectif utilisateur/)
      assert.match(out.actions[0].thought, /rechercher\/lire\/creer\/verifier/)
    }
  })

  test('turns a failed-search diagnosis reply into an internal think step', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        {
          kind: 'reply',
          message: "Les recherches precedentes ont echoue a cause d'une formulation peu precise. Il faut cibler directement les ressources officielles francaises sur le sujet specifique banque des fichiers STI2D SIN TP.",
        },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const out = repairMetaOnlyReplyPlan(plan, {
      userPrompt: 'cree une fiche de revision bac sti2d sin avec recherches en ligne',
    })

    assert.equal(out.actions.length, 1)
    assert.equal(out.actions[0].kind, 'think')
    if (out.actions[0].kind === 'think') {
      assert.match(out.actions[0].thought, /Objectif utilisateur/)
      assert.match(out.actions[0].thought, /rechercher\/lire\/creer\/verifier/)
    }
  })

  test('keeps a real final answer unchanged', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'Voici le resultat verifie avec les sources consultees.' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    assert.equal(repairMetaOnlyReplyPlan(plan), plan)
  })
})

describe('repairExtensionBlockedWebResearchPlan', () => {
  test('turns an Aurora-Connect install reply into native web_search for public research', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: "Installation de l'extension Aurora-Connect necessaire. Merci de vous rendre dans Settings." },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    const out = repairExtensionBlockedWebResearchPlan(plan, {
      userPrompt: 'recherche en ligne des sujets officiels bac sti2d sin banque des fichiers',
    })
    assert.equal(out.actions.length, 2)
    assert.equal(out.actions[0].kind, 'think')
    assert.equal(out.actions[1].kind, 'web_search')
    if (out.actions[1].kind === 'web_search') {
      assert.match(out.actions[1].query, /sti2d/)
    }
  })

  test('does not rewrite extension replies for active-tab browser tasks', () => {
    const plan: CoworkPlan = {
      reasoning: 'r',
      expectedOutcome: 'o',
      actions: [
        { kind: 'reply', message: 'Installe Aurora-Connect pour lire l onglet ouvert.' },
        { kind: 'finish', summary: 'fait' },
      ],
    }
    assert.equal(repairExtensionBlockedWebResearchPlan(plan, {
      userPrompt: 'analyse l onglet ouvert dans mon navigateur',
    }), plan)
  })
})
