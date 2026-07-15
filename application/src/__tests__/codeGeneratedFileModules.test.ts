import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { isLLMRefusal } from '../services/codeLLMRefusal.ts'
import {
  detectContentLanguage,
  detectNonCodePlanningNarrative,
  extractNotes,
  parseCodeFiles,
  serializeCodeFiles,
} from '../services/codeGeneratedFileParser.ts'
import {
  manifestUsesPackage,
  sanitizeGeneratedFileContent,
  stripFormattingArtifacts,
  tryParseJson,
  upsertPackageDevDependency,
} from '../services/codeGeneratedFileSanitizer.ts'
import { serializeProjectTreeEmission } from '../services/codeProjectEmission.ts'

describe('codeLLMRefusal', () => {
  test('detecte un refus mais pas une sortie avec fichiers', () => {
    assert.equal(isLLMRefusal("I'm sorry, I cannot help generate that code."), true)
    assert.equal(isLLMRefusal('--- FICHIER: index.html ---\n```html\n<html></html>\n```'), false)
    assert.equal(isLLMRefusal(serializeProjectTreeEmission([
      { path: 'index.html', content: '<!doctype html><html></html>' },
    ])), false)
  })
})

describe('codeGeneratedFileParser', () => {
  test('parse le contrat FICHIER et serialise sans perdre le chemin', () => {
    const files = parseCodeFiles('--- FICHIER: src/App.tsx ---\n```tsx\nexport function App(){ return <main /> }\n```')
    assert.equal(files.length, 1)
    assert.equal(files[0].name, 'src/App.tsx')
    assert.equal(files[0].language, 'typescript')
    assert.ok(serializeCodeFiles(files).includes('--- FICHIER: src/App.tsx ---'))
  })

  test('parse le protocole structure WS2 a longueur declaree', () => {
    const source = [
      'const body = ````ts`',
      'const separator = "---"',
      'export { body, separator }',
    ].join('\n')
    const files = parseCodeFiles(serializeProjectTreeEmission([
      { path: 'src/tricky.ts', content: source, language: 'typescript' },
    ]))

    assert.equal(files.length, 1)
    assert.equal(files[0].name, 'src/tricky.ts')
    assert.equal(files[0].content, source)
  })

  test('detecte le langage depuis un bloc texte generique', () => {
    assert.equal(detectContentLanguage('<!DOCTYPE html><html><body></body></html>'), 'html')
    assert.equal(detectContentLanguage('import React from "react"\nexport function App(){}'), 'javascript')
    assert.equal(detectContentLanguage('def main():\n    return 1'), 'python')
  })

  test('extrait les notes et rejette une narration de preflight comme non-code', () => {
    assert.equal(extractNotes('--- NOTES ---\nLance npm run dev'), 'Lance npm run dev')
    const narrative = [
      'Projet detecte: spa_react',
      'Frameworks: react',
      'Preflight local: inspecter package.json',
    ].join('\n')
    assert.ok(detectNonCodePlanningNarrative(narrative))
    assert.equal(detectNonCodePlanningNarrative('export const ok = true'), null)
  })
})

describe('codeGeneratedFileSanitizer', () => {
  test('nettoie les artefacts de format et repare le JSONC', () => {
    assert.equal(stripFormattingArtifacts('```json\n{"ok":true}\n```'), '{"ok":true}')
    assert.deepEqual(tryParseJson('{\n  // commentaire\n  "ok": true,\n}'), { ok: true })
  })

  test('repare les manifests et expose les helpers package', () => {
    const content = sanitizeGeneratedFileContent('package.json', JSON.stringify({
      scripts: { dev: 'vite' },
      dependencies: {
        vite: '^4.0.0',
        'react-three-fiber': '^6.0.0',
      },
    }))
    const manifest = JSON.parse(content)
    assert.equal(manifest.devDependencies.vite, '^8.1.3')
    assert.equal(manifest.devDependencies['@vitejs/plugin-react'], '^5.1.2')
    assert.equal(manifest.dependencies['@react-three/fiber'], '^6.0.0')
    assert.equal(manifest.dependencies['react-three-fiber'], undefined)

    const next = upsertPackageDevDependency(manifest, 'tailwindcss', '^3.4.17', true)
    assert.equal(manifestUsesPackage(next, 'tailwindcss'), true)
  })
})
