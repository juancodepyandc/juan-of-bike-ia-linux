import { describe, test } from 'node:test'
import assert from 'node:assert/strict'

const { planNextStep } = await import('../services/coworkPlanner.ts')

describe('cowork mission execution planner', () => {
  test('un ordre de correction cowork commence par inventorier le workspace', async () => {
    const plan = await planNextStep({
      userPrompt: 'reprends le module cowork, corrige son systeme de conversation et fais le vraiment executer les ordres',
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
    assert.equal(plan.actions.some((action) => action.kind === 'reply'), false)
    assert.equal(plan.actions.some((action) => action.kind === 'finish'), false)
  })

  test('une suite courte reprend la mission precedente et lit les fichiers pivots cowork', async () => {
    const plan = await planNextStep({
      userPrompt: 'continue et fais le vraiment fonctionner',
      conversationHistory: [
        {
          role: 'user',
          content: 'corrige le module cowork pour avoir un vrai systeme conversationnel qui execute les ordres',
        },
      ],
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
              'src/services/coworkConversation.ts',
              'src/services/coworkPlanner.ts',
              'src/services/coworkOrchestrator.ts',
              'src/components/CoworkOverlay.tsx',
              'src/services/imagePromptBuilder.ts',
            ].join('\n'),
          },
        },
      ],
    })

    const readPaths = plan.actions
      .filter((action) => action.kind === 'read_file')
      .map((action) => action.path)

    assert.ok(readPaths.includes('src/services/coworkPlanner.ts'))
    assert.ok(readPaths.includes('src/services/coworkOrchestrator.ts'))
    assert.equal(plan.actions.some((action) => action.kind === 'finish'), false)
  })
})
