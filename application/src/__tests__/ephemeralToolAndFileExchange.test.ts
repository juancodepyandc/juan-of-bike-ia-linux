import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { processIncomingFiles, emitModuleFiles } from '../services/moduleFileExchange.ts'
import type { ModuleFileStorage } from '../services/moduleFileExchange.ts'

describe('moduleFileExchange — Multi-File Ingestion & Generation', () => {
  it('identifie et catégorise correctement divers types de fichiers entrants', () => {
    const files = [
      { filename: 'exploit_poc.py', content: 'import socket\nprint("poc")' },
      { filename: 'network_traffic.pcap', content: 'dummy-pcap-data' },
      { filename: 'schrodinger_derivation.tex', content: '\\frac{d\\psi}{dt}' },
      { filename: 'vulnerabilities.json', content: JSON.stringify({ cve: 'CVE-2026-1001' }) },
    ]

    const processed = processIncomingFiles(files)
    assert.equal(processed.length, 4)
    assert.equal(processed[0].category, 'code')
    assert.equal(processed[1].category, 'security_dump')
    assert.equal(processed[2].category, 'document')
    assert.equal(processed[3].category, 'dataset')
    assert.ok(processed[0].textSummary?.includes('exploit_poc.py'))
  })

  it('génère et structure les fichiers émis par module', async (t) => {
    const workspace = await mkdtemp(join(tmpdir(), 'aurora-file-exchange-'))
    t.after(() => rm(workspace, { recursive: true, force: true }))
    const storage: ModuleFileStorage = {
      workspacePath: async () => join(workspace, 'application'),
      mkdir: async (path) => { await mkdir(path, { recursive: true }) },
      writeText: async (path, content) => { await writeFile(path, content, 'utf8') },
    }
    const outgoing = [
      {
        filename: 'sig_detect_injection.yml',
        content: 'title: Detect DOM XSS\nstatus: stable',
        category: 'rules',
        format: 'yaml' as const,
      },
      {
        filename: 'quantum_proof.md',
        content: '# Conservation de la norme dans H',
        category: 'proofs',
        format: 'markdown' as const,
      },
    ]

    const results = await emitModuleFiles('cyber', [outgoing[0]], storage)
    assert.equal(results.length, 1)
    assert.equal(results[0].filename, 'sig_detect_injection.yml')
    assert.ok(results[0].targetPath.includes('application/output/cyber/rules'))
    assert.equal(await readFile(results[0].targetPath, 'utf8'), outgoing[0].content)

    const acadResults = await emitModuleFiles('academic', [outgoing[1]], storage)
    assert.equal(acadResults.length, 1)
    assert.equal(acadResults[0].filename, 'quantum_proof.md')
    assert.ok(acadResults[0].targetPath.includes('application/output/academy/proofs'))
    assert.equal(await readFile(acadResults[0].targetPath, 'utf8'), outgoing[1].content)
  })

  it('propage les erreurs de stockage au lieu de déclarer un fichier livré', async () => {
    const storage: ModuleFileStorage = {
      workspacePath: async () => '/workspace',
      mkdir: async () => {},
      writeText: async () => { throw new Error('disk full') },
    }
    await assert.rejects(emitModuleFiles('conversation', [{ filename: 'note.md', content: 'é' }], storage), /disk full/)
  })

  it('refuse les traversées de catégorie et les noms réservés avant toute écriture', async () => {
    let writes = 0
    const storage: ModuleFileStorage = {
      workspacePath: async () => '/workspace',
      mkdir: async () => { writes++ },
      writeText: async () => { writes++ },
    }
    for (const category of ['../outside', 'a/../../b', '/tmp', 'a\\b', '..', 'a\0b']) {
      await assert.rejects(emitModuleFiles('cyber', [{ filename: 'ok.txt', category, content: 'x' }], storage), /Catégorie/)
    }
    for (const filename of ['', '.', '..']) {
      await assert.rejects(emitModuleFiles('cyber', [{ filename, content: 'x' }], storage), /Nom de fichier/)
    }
    assert.equal(writes, 0)
  })

  it('compte les octets UTF-8 des fichiers réellement écrits', async () => {
    const storage: ModuleFileStorage = { workspacePath: async () => '/workspace/application/', mkdir: async () => {}, writeText: async () => {} }
    const [result] = await emitModuleFiles('academic', [{ filename: 'note.txt', content: 'é🙂' }], storage)
    assert.equal(result.byteLength, 6)
    assert.ok(result.targetPath.startsWith('/workspace/application/output/academy/'))
  })
})
