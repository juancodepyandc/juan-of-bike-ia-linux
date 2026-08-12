// Caviardage avant publication.
//
// Le hub sert le code source integral par le tunnel PUBLIC. Rien de sensible n y
// figure aujourd hui, mais c est une propriete a tenir, pas a constater: une
// seule cle ecrite en dur par un modele partirait sur une URL publique.
//
// L equilibre teste ici est le vrai sujet: masquer les secrets SANS mutiler du
// code legitime. Un champ `type="password"`, un `process.env.API_KEY`, un
// placeholder doivent rester lisibles — sinon le viewer ne sert plus a rien.

import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { REDACTION_MARKER, redactSecretsForPublication } from '../services/codeArtifactRedaction.ts'

const file = (name: string, content: string) => ({ name, content })

describe('redaction — ce qui doit etre masque', () => {
  test('une cle assignee en dur', () => {
    const { files, hits } = redactSecretsForPublication([
      file('src/api.ts', 'const apiKey = "sk_live_9f83hf8s7dfhs8df7h"\nexport default apiKey'),
    ])
    assert.match(files[0].content, new RegExp(REDACTION_MARKER.replace(/[[\]]/g, '\\$&')))
    assert.equal(files[0].content.includes('sk_live_9f83hf8s7dfhs8df7h'), false)
    assert.equal(hits.length, 1)
    // La cle reste visible: on masque la valeur, pas l existence du reglage.
    assert.match(files[0].content, /apiKey/)
  })

  test('une ligne de fichier .env', () => {
    const { files } = redactSecretsForPublication([
      file('.env', 'PORT=5173\nSTRIPE_SECRET_KEY=sk_test_51H8vQ2eZvKYlo2C\n'),
    ])
    assert.match(files[0].content, /PORT=5173/)
    assert.equal(files[0].content.includes('sk_test_51H8vQ2eZvKYlo2C'), false)
  })

  test('une cle reconnaissable a sa FORME, meme sans nom revelateur', () => {
    const { files, hits } = redactSecretsForPublication([
      file('src/x.ts', 'const z = "ghp_abcdefghijklmnopqrstuvwxyz0123"'),
    ])
    assert.equal(files[0].content.includes('ghp_abcdefghijklmnopqrstuvwxyz0123'), false)
    assert.equal(hits[0].key, 'cle reconnue a sa forme')
  })

  test('une cle privee PEM', () => {
    const pem = '-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----'
    const { files } = redactSecretsForPublication([file('key.pem', pem)])
    assert.equal(files[0].content.includes('MIIEowIBAAKCAQEA'), false)
  })

  test('ce qui est masque est RAPPORTE, jamais masque en silence', () => {
    const { hits } = redactSecretsForPublication([
      file('a.ts', 'const password = "hunter2hunter2"'),
    ])
    assert.equal(hits[0].file, 'a.ts')
    assert.match(hits[0].preview, /\*\*\*/)
    // L apercu ne doit pas reconstituer le secret.
    assert.equal(hits[0].preview.includes('hunter2hunter2'), false)
  })
})

describe('redaction — ce qui doit rester intact', () => {
  test('un champ de formulaire mot de passe', () => {
    const html = '<label for="password">Mot de passe</label><input type="password" name="password" id="password" />'
    const { files, hits } = redactSecretsForPublication([file('index.html', html)])
    assert.equal(files[0].content, html)
    assert.deepEqual(hits, [])
  })

  test('une lecture de variable d environnement', () => {
    const src = 'const apiKey = process.env.API_KEY\nconst t = import.meta.env.VITE_TOKEN'
    assert.equal(redactSecretsForPublication([file('a.ts', src)]).files[0].content, src)
  })

  test('un placeholder de documentation', () => {
    const src = 'API_KEY=your-api-key-here\nconst secret = "changeme"\n'
    assert.equal(redactSecretsForPublication([file('.env.example', src)]).files[0].content, src)
  })

  test('une valeur trop courte pour etre un secret', () => {
    const src = 'const token = "abc"'
    assert.equal(redactSecretsForPublication([file('a.ts', src)]).files[0].content, src)
  })

  test('un projet sans secret ressort a l identique, meme objet', () => {
    const input = [file('index.html', '<h1>Bonjour</h1>'), file('style.css', 'body{color:red}')]
    const { files, hits } = redactSecretsForPublication(input)
    assert.deepEqual(hits, [])
    assert.equal(files[0], input[0])
  })
})
