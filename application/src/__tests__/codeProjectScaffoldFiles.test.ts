// Fichiers de reprise: ce qu il faut pour recuperer un projet sans deviner.
//
// Constat mesure sur les sept projets publies: aucun `.gitignore`. Un projet
// React livre sans `.gitignore`, la premiere chose que fera son proprietaire
// est de commiter `node_modules/`.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import {
  buildGitignore,
  collectEnvVariables,
  resolveNodeMajor,
  upsertProjectScaffoldFiles,
} from '../services/codeProjectScaffoldFiles.ts'

const file = (name: string, content = '') => ({ name, language: 'text', content })
const pkg = (extra: string) => file('package.json', `{"name":"x",${extra}}`)

describe('scaffold — .gitignore suit la pile reellement livree', () => {
  test('un projet Node ignore node_modules, dist et .env', () => {
    const out = buildGitignore([pkg('"devDependencies":{}')])
    for (const entry of ['node_modules/', 'dist/', '.env']) assert.match(out, new RegExp(entry.replace('.', '\\.')))
    assert.doesNotMatch(out, /__pycache__/)
  })

  test('un projet Python ajoute ses propres artefacts', () => {
    assert.match(buildGitignore([file('main.py', 'print(1)')]), /__pycache__\//)
  })

  test('un projet Rust ajoute target/', () => {
    assert.match(buildGitignore([file('Cargo.toml', '[package]')]), /target\//)
  })
})

describe('scaffold — .env.example ne liste que le REEL', () => {
  test('extrait les variables effectivement lues', () => {
    const vars = collectEnvVariables([
      file('src/api.ts', 'const u = import.meta.env.VITE_API_URL\nconst k = process.env.STRIPE_KEY'),
      file('server.py', 'os.environ["DATABASE_URL"]'),
    ])
    assert.deepEqual(vars, ['DATABASE_URL', 'STRIPE_KEY', 'VITE_API_URL'])
  })

  test('ignore ce que l outillage fournit', () => {
    assert.deepEqual(collectEnvVariables([file('a.ts', 'process.env.NODE_ENV')]), [])
  })

  test('ne lit jamais une dependance installee', () => {
    // Mesure reelle: un node_modules egare faisait remonter APPDATA et
    // ANTIGRAVITY_AGENT — les variables de la MACHINE — dans le .env.example.
    const vars = collectEnvVariables([file('node_modules/vite/dist/node.js', 'process.env.APPDATA')])
    assert.deepEqual(vars, [])
  })

  test('aucune variable lue => aucun fichier invente', () => {
    const out = upsertProjectScaffoldFiles([file('index.html', '<h1>x</h1>')])
    assert.equal(out.some((f) => f.name === '.env.example'), false)
  })
})

describe('scaffold — version de Node', () => {
  test('engines fait foi quand il est declare', () => {
    assert.equal(resolveNodeMajor([pkg('"engines":{"node":">=22.1.0"}')]), 22)
  })

  test('sinon la version se deduit du bundler declare', () => {
    assert.equal(resolveNodeMajor([pkg('"devDependencies":{"vite":"^8.1.0"}')]), 20)
    assert.equal(resolveNodeMajor([pkg('"devDependencies":{"vite":"^5.4.0"}')]), 18)
  })

  test('sans package.json, on n affirme rien', () => {
    assert.equal(resolveNodeMajor([file('index.html')]), null)
  })
})

describe('scaffold — idempotence', () => {
  test('un fichier deja fourni par le modele n est jamais ecrase', () => {
    const mine = file('.gitignore', '# a moi\nfoo/')
    const out = upsertProjectScaffoldFiles([mine, pkg('"devDependencies":{"vite":"^5"}')])
    assert.equal(out.filter((f) => f.name === '.gitignore').length, 1)
    assert.equal(out.find((f) => f.name === '.gitignore')!.content, '# a moi\nfoo/')
  })

  test('deux passages donnent le meme resultat', () => {
    const once = upsertProjectScaffoldFiles([pkg('"devDependencies":{"vite":"^5"}')])
    const twice = upsertProjectScaffoldFiles(once)
    assert.deepEqual(twice.map((f) => f.name).sort(), once.map((f) => f.name).sort())
  })
})
