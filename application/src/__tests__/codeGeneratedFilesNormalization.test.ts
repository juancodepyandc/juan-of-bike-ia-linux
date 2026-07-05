/**
 * Regression tests for generated machine files. A real 3D React/Vite run
 * repeatedly produced JSONC tsconfig files and invalid R3F package names.
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'

register('../../scripts/code_harness/hooks.mjs', import.meta.url)

type CodeFile = {
  name: string
  language: string
  content: string
}

const {
  normalizeGeneratedCodeFilesForTest,
  checkInteractive3DFidelity,
  upsertProjectSupportFilesForTest,
} = await import('../services/codeOrchestrator.ts')

function file(name: string, content: string, language = 'text'): CodeFile {
  return { name, content, language }
}

describe('normalizeGeneratedCodeFilesForTest', () => {
  test('tsconfig JSONC is normalized to strict JSON', () => {
    const files = normalizeGeneratedCodeFilesForTest([
      file('tsconfig.json', `{
        "compilerOptions": {
          // Bundler mode
          "moduleResolution": "bundler",
          "jsx": "react-jsx",
        },
        "include": ["src"],
      }`, 'json'),
    ])

    const tsconfig = files[0].content
    assert.doesNotThrow(() => JSON.parse(tsconfig))
    assert.ok(!tsconfig.includes('// Bundler mode'))
    assert.ok(!/,\s*[}\]]/.test(tsconfig))
  })

  test('invalid React Three Fiber package names are repaired', () => {
    const files = normalizeGeneratedCodeFilesForTest([
      file('package.json', JSON.stringify({
        name: 'skyforge-expanse',
        dependencies: {
          react: '^19.0.0',
          'react-dom': '^19.0.0',
          three: '^0.160.0',
          'react-three-fiber': '^8.13.0',
          'react-three/drei': '^9.94.0',
        },
      }), 'json'),
      file('src/App.tsx', `
        import { Canvas } from '@react-three/fiber'
        import { OrbitControls } from '@react-three/drei'
        import { useSpring } from '@react-spring/three'
      `, 'typescript'),
    ])

    const manifest = JSON.parse(files.find((f) => f.name === 'package.json')!.content)
    assert.equal(manifest.dependencies['react-three-fiber'], undefined)
    assert.equal(manifest.dependencies['react-three/drei'], undefined)
    assert.ok(manifest.dependencies['@react-three/fiber'])
    assert.ok(manifest.dependencies['@react-three/drei'])
    assert.ok(manifest.dependencies['@react-spring/three'])
    assert.match(manifest.dependencies['@react-three/fiber'], /^\^9\./)
    assert.match(manifest.dependencies['@react-three/drei'], /^\^10\./)
    assert.match(manifest.devDependencies['@types/react'], /^\^19\./)
    assert.match(manifest.devDependencies['@types/react-dom'], /^\^19\./)
  })

  test('common React 19 R3F and Zustand typing issues are repaired', () => {
    const files = normalizeGeneratedCodeFilesForTest([
      file('src/Scene.tsx', `
        import { useRef } from 'react'
        import * as THREE from 'three'
        const stationRef = useRef<THREE.Mesh>(null)
        stationRef.current = new THREE.Mesh()
      `, 'typescript'),
      file('src/store.ts', `
        import { create } from 'zustand'
        import * as THREE from 'three'
        interface GameState {
          resources: THREE.Mesh[]
          setResources: (resources: THREE.Mesh[]) => void
        }
        export const useStore = create<GameState>((set) => ({
          resources: [],
          setResources: (resources) => set({ resources })
        }))
      `, 'typescript'),
    ])

    assert.match(files.find((f) => f.name === 'src/Scene.tsx')!.content, /useRef<THREE\.Mesh \| null>\(null\)/)
    const store = files.find((f) => f.name === 'src/store.ts')!.content
    assert.match(store, /setResources: \(resources: THREE\.Mesh\[\] \| \(\(prev: THREE\.Mesh\[\]\) => THREE\.Mesh\[\]\)\) => void/)
    assert.match(store, /typeof resources === 'function'/)
  })

  test('package.json is completed from bare package imports', () => {
    const files = normalizeGeneratedCodeFilesForTest([
      file('package.json', JSON.stringify({
        dependencies: {
          react: '^19.0.0',
          'react-dom': '^19.0.0',
          'monaco-editor': '^0.41.0',
        },
        devDependencies: {
          vite: '^5.0.0',
        },
      }), 'json'),
      file('src/RuleEditor.tsx', `
        import MonacoEditor from '@monaco-editor/react'
        import { create } from 'zustand'
        import { Routes } from 'react-router-dom'
        import { FiPlus } from 'react-icons/fi'
        console.log(MonacoEditor, create, Routes, FiPlus)
      `, 'typescript'),
      file('vite.config.ts', `
        import { defineConfig } from 'vite'
        import react from '@vitejs/plugin-react'
        export default defineConfig({ plugins: [react()] })
      `, 'typescript'),
    ])

    const manifest = JSON.parse(files.find((f) => f.name === 'package.json')!.content)
    assert.ok(manifest.dependencies['@monaco-editor/react'])
    assert.ok(manifest.dependencies['zustand'])
    assert.ok(manifest.dependencies['react-router-dom'])
    assert.ok(manifest.dependencies['react-icons'])
    assert.ok(manifest.dependencies['monaco-editor'])
    assert.equal(manifest.devDependencies.vite, '^8.1.3')
    assert.equal(manifest.devDependencies['@vitejs/plugin-react'], '^5.1.2')
    assert.equal(manifest.dependencies['@vitejs/plugin-react'], undefined)
  })

  test('generated generic tables allow action columns without accessorKey', () => {
    const files = normalizeGeneratedCodeFilesForTest([
      file('src/components/ui/Table.tsx', `
        import React from 'react'

        interface TableProps<TData> {
          columns: Array<{
            header: string
            accessorKey: string
            cell?: (props: any) => React.ReactNode
          }>
          data: TData[]
        }

        const Table = <TData,>({ columns, data }: TableProps<TData>) => {
          return (
            <table>
              <thead>{columns.map((column) => <th key={column.accessorKey}>{column.header}</th>)}</thead>
              <tbody>{data.map((row, rowIndex) => (
                <tr key={rowIndex}>{columns.map((column) => (
                  <td key={column.accessorKey}>
                    {column.cell ? column.cell({ row, getValue: () => row[column.accessorKey as keyof TData] }) : (row[column.accessorKey as keyof TData] as React.ReactNode)}
                  </td>
                ))}</tr>
              ))}</tbody>
            </table>
          )
        }
      `, 'typescript'),
    ])

    const table = files.find((f) => f.name === 'src/components/ui/Table.tsx')!.content
    assert.match(table, /accessorKey\?: keyof TData \| string/)
    assert.match(table, /String\(column\.accessorKey \|\| column\.header\)/)
    assert.match(table, /column\.accessorKey \? row\[column\.accessorKey as keyof TData\] : undefined/)
  })

  test('SPA support injects Vite entry files and strips synthetic fallback blocks', () => {
    const intent = {
      projectType: 'spa_react',
      complexity: 'enterprise',
      languages: ['typescript'],
      frameworks: ['react'],
      features: ['multipage'],
      needsDevServer: true,
      needsBundling: true,
      previewType: 'dev_server',
      devCommand: 'npm run dev',
      buildCommand: 'npm run build',
      testCommand: null,
      estimatedFileCount: 20,
      needsArchitecturePlanning: true,
      assetPlan: { wants3D: false, wantsImages: false, imageQueries: [], subject: null },
    }
    const files = upsertProjectSupportFilesForTest([
      file('module-4.ts', "import App from './App'\nexport default App", 'typescript'),
      file('script-3.js', "import App from './App'\nconsole.log(App)", 'javascript'),
      file('style-13.css', 'body { color: red; }', 'css'),
      file('package.json', JSON.stringify({
        scripts: { dev: 'vite', build: 'vite build' },
        dependencies: { react: 'latest', 'react-dom': 'latest' },
        devDependencies: { vite: 'latest', '@vitejs/plugin-react': 'latest', typescript: 'latest' },
      }), 'json'),
      file('src/index.tsx', "import App from './App'\nconsole.log(App)", 'tsx'),
      file('src/App.tsx', 'export default function App(){ return <main>OK</main> }', 'tsx'),
    ], intent)

    const names = files.map((f) => f.name.replace(/\\/g, '/').toLowerCase())
    assert.ok(names.includes('index.html'), names.join(','))
    assert.ok(names.includes('vite.config.ts'), names.join(','))
    assert.ok(!names.includes('module-4.ts'), names.join(','))
    assert.ok(!names.includes('script-3.js'), names.join(','))
    assert.ok(!names.includes('style-13.css'), names.join(','))
    assert.match(files.find((f) => f.name === 'index.html')!.content, /src\/index\.tsx/)
  })

  test('SPA support adds PostCSS config for generated Tailwind projects', () => {
    const intent = {
      projectType: 'spa_react',
      complexity: 'advanced',
      languages: ['typescript'],
      frameworks: ['react'],
      features: ['dashboard'],
      needsDevServer: true,
      needsBundling: true,
      previewType: 'dev_server',
      devCommand: 'npm run dev',
      buildCommand: 'npm run build',
      testCommand: null,
      estimatedFileCount: 12,
      needsArchitecturePlanning: true,
      assetPlan: { wants3D: false, wantsImages: false, imageQueries: [], subject: null },
    }
    const files = upsertProjectSupportFilesForTest([
      file('package.json', JSON.stringify({
        scripts: { dev: 'vite', build: 'vite build' },
        dependencies: { react: 'latest', 'react-dom': 'latest' },
        devDependencies: { vite: '^4.4.5', tailwindcss: '^3.3.3' },
      }), 'json'),
      file('tailwind.config.js', 'export default { content: ["./src/**/*.{ts,tsx}"], theme: { extend: {} }, plugins: [] }', 'javascript'),
      file('src/index.css', '@tailwind base;\\n@tailwind components;\\n@tailwind utilities;\\n.card { @apply p-6 rounded-lg; }', 'css'),
      file('src/main.tsx', "import './index.css'\nimport App from './App'\nconsole.log(App)", 'tsx'),
      file('src/App.tsx', 'export default function App(){ return <main className="card">OK</main> }', 'tsx'),
    ], intent)

    const names = files.map((f) => f.name.replace(/\\/g, '/').toLowerCase())
    assert.ok(names.includes('postcss.config.js'), names.join(','))
    const manifest = JSON.parse(files.find((f) => f.name === 'package.json')!.content)
    assert.equal(manifest.devDependencies.tailwindcss, '^3.4.17')
    assert.equal(manifest.devDependencies.postcss, '^8.5.6')
    assert.equal(manifest.devDependencies.autoprefixer, '^10.4.21')
  })
})

describe('checkInteractive3DFidelity', () => {
  test('rejects a decorative R3F scene when the prompt asks for interactive systems', () => {
    const result = checkInteractive3DFidelity(
      [
        file('src/App.tsx', `
          import { Canvas } from '@react-three/fiber'
          import { OrbitControls } from '@react-three/drei'
          export default function App() {
            return <><Canvas><mesh onClick={() => console.log('station')} /></Canvas><div>Minerals 50 - Dock with station</div></>
          }
        `, 'typescript'),
      ],
      'Gros simulateur 3D React Three Fiber avec WASD, shift boost, espace scan, minimap radar, collecte de minerais et docking station.',
      {
        projectType: 'spa_react',
        complexity: 'complex',
        languages: ['typescript'],
        frameworks: ['react'],
        features: ['3d'],
        needsDevServer: true,
        needsBundling: true,
        previewType: 'dev_server',
        devCommand: 'npm run dev',
        buildCommand: 'npm run build',
        testCommand: null,
        estimatedFileCount: 8,
        needsArchitecturePlanning: true,
        assetPlan: { wants3D: true, wantsImages: false, imageQueries: [], subject: null },
      },
    )

    assert.equal(result.ok, false)
    assert.ok(result.missing.some((item) => item.includes('pilotage')))
    assert.ok(result.missing.some((item) => item.includes('minimap')))
    assert.ok(result.missing.some((item) => item.includes('collecte')))
  })

  test('rejects radar blips generated with Math.random instead of real positions', () => {
    const result = checkInteractive3DFidelity(
      [
        file('src/Radar.tsx', `
          export default function Radar() {
            const angle = Math.random() * Math.PI * 2
            const blip = <div className="radar-blip" style={{ left: angle }} />
            return <div className="radar">{blip}</div>
          }
        `, 'typescript'),
        file('src/Scene.tsx', `
          import { Canvas, useFrame } from '@react-three/fiber'
          import * as THREE from 'three'
          const resource = { position: new THREE.Vector3() }
          resource.position.distanceTo(new THREE.Vector3())
          export default function Scene() { useFrame(() => {}); return <Canvas /> }
        `, 'typescript'),
      ],
      'Projet 3D avec radar/minimap base sur les positions reelles des ressources.',
      {
        projectType: 'spa_react',
        complexity: 'standard',
        languages: ['typescript'],
        frameworks: ['react'],
        features: ['3d'],
        needsDevServer: true,
        needsBundling: true,
        previewType: 'dev_server',
        devCommand: 'npm run dev',
        buildCommand: 'npm run build',
        testCommand: null,
        estimatedFileCount: 5,
        needsArchitecturePlanning: false,
        assetPlan: { wants3D: true, wantsImages: false, imageQueries: [], subject: null },
      },
    )

    assert.equal(result.ok, false)
    assert.ok(result.missing.some((item) => item.includes('aleatoires')))
  })
})
