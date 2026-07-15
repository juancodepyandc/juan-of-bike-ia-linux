import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildProjectTree,
  normalizeProjectPath,
  projectTreeToCodeFiles,
} from '../services/codeProjectTree.ts'

describe('codeProjectTree — chemins et arborescence', () => {
  test('preserve les dossiers multi-niveaux et les fichiers sans extension', () => {
    const tree = buildProjectTree([
      { path: 'src/app/App.tsx', content: 'import { util } from "../lib/util"\nexport default function App(){ return util }' },
      { path: 'src/lib/util.ts', content: 'export const util = 1' },
      { path: 'Dockerfile', content: 'FROM node:22-alpine' },
      { path: 'Makefile', content: 'all:\n\tnpm test' },
    ])

    assert.deepEqual(tree.directories.map((dir) => dir.path), ['src', 'src/app', 'src/lib'])
    assert.equal(tree.files.find((file) => file.path === 'Dockerfile')?.language, 'dockerfile')
    assert.equal(tree.files.find((file) => file.path === 'Makefile')?.language, 'makefile')
    assert.equal(tree.importGraph.unresolved.length, 0)
    assert.equal(tree.importGraph.edges[0].resolvedPath, 'src/lib/util.ts')
  })

  test('normalise les chemins et recupere les chemins dangereux hors racine', () => {
    assert.equal(normalizeProjectPath('src\\main.ts'), 'src/main.ts')
    assert.equal(normalizeProjectPath(''), null)

    const tree = buildProjectTree([
      { path: '../secret.ts', content: 'export const leaked = false' },
      { path: '/absolute/app.ts', content: 'export const app = true' },
      { path: '', content: 'notes' },
    ])

    assert.deepEqual(tree.files.map((file) => file.path), [
      'recovered/absolute/app.ts',
      'recovered/file-3.txt',
      'recovered/secret.ts',
    ])
    assert.equal(tree.collisions.filter((collision) => collision.reason === 'unsafe').length, 2)
    assert.equal(tree.collisions.some((collision) => collision.reason === 'empty'), true)
  })

  test('deduplique les collisions exactes et insensibles a la casse', () => {
    const tree = buildProjectTree([
      { path: 'src/App.tsx', content: 'export const one = 1' },
      { path: 'src/App.tsx', content: 'export const two = 2' },
      { path: 'src/app.tsx', content: 'export const lower = 3' },
      { path: 'LICENSE', content: 'MIT' },
      { path: 'LICENSE', content: 'MIT again' },
    ])

    assert.deepEqual(tree.files.map((file) => file.path), [
      'LICENSE',
      'LICENSE__2',
      'src/App.tsx',
      'src/App__2.tsx',
      'src/app__3.tsx',
    ])
    assert.equal(tree.collisions.some((collision) => collision.reason === 'duplicate'), true)
    assert.equal(tree.collisions.some((collision) => collision.reason === 'case_insensitive_duplicate'), true)
  })
})

describe('codeProjectTree — graphe et encodage', () => {
  test('resout les imports relatifs, signale les imports locaux manquants et ignore les externes', () => {
    const tree = buildProjectTree([
      {
        path: 'src/App.tsx',
        content: [
          'import React from "react"',
          'import "./style.css"',
          'const lib = require("./lib")',
          'import("./missing")',
        ].join('\n'),
      },
      { path: 'src/style.css', content: 'body { margin: 0 }' },
      { path: 'src/lib/index.ts', content: 'export const value = 1' },
    ])

    const localEdges = tree.importGraph.edges.filter((edge) => !edge.external)
    assert.deepEqual(localEdges.map((edge) => edge.resolvedPath), [
      'src/lib/index.ts',
      null,
      'src/style.css',
    ])
    assert.equal(tree.importGraph.edges.some((edge) => edge.external && edge.specifier === 'react'), true)
    assert.deepEqual(tree.importGraph.unresolved.map((edge) => edge.specifier), ['./missing'])
  })

  test('preserve les fichiers binaires base64 et exporte seulement les fichiers texte vers CodeFile', () => {
    const tree = buildProjectTree([
      { path: 'assets/logo.png', content: 'iVBORw0KGgo=', encoding: 'base64', mime: 'image/png' },
      { path: 'src/main.ts', content: 'export const ok = true' },
    ])

    assert.equal(tree.files.find((file) => file.path === 'assets/logo.png')?.encoding, 'base64')
    assert.deepEqual(projectTreeToCodeFiles(tree), [
      { name: 'src/main.ts', language: 'typescript', content: 'export const ok = true' },
    ])
  })
})
