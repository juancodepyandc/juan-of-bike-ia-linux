import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { buildSandboxNetworkPolicy, podmanEnvArgs } from '../services/codeSandboxNetworkPolicy.ts'
import type { ValidationCommand } from '../services/codeSandboxTypes.ts'

function command(executable: string, args: string[], label = 'cmd'): ValidationCommand {
  return { label, executable, args }
}

describe('codeSandboxNetworkPolicy', () => {
  test('npm install utilise seulement le reseau registre avec scripts desactives', () => {
    const policy = buildSandboxNetworkPolicy(command('npm', ['install'], 'Installer les dependances'))

    assert.equal(policy.mode, 'registry')
    assert.equal(policy.podmanNetwork, 'slirp4netns:allow_host_loopback=false')
    assert.deepEqual(
      policy.env.find(([key]) => key === 'NPM_CONFIG_REGISTRY'),
      ['NPM_CONFIG_REGISTRY', 'https://registry.npmjs.org/'],
    )
    assert.deepEqual(
      policy.env.find(([key]) => key === 'NPM_CONFIG_IGNORE_SCRIPTS'),
      ['NPM_CONFIG_IGNORE_SCRIPTS', 'true'],
    )
  })

  test('npm view utilise aussi le registre pour la resolution de versions sandboxee', () => {
    const policy = buildSandboxNetworkPolicy(command('npm', ['view', 'react', 'versions', '--json']))

    assert.equal(policy.mode, 'registry')
    assert.deepEqual(
      policy.env.find(([key]) => key === 'NPM_CONFIG_REGISTRY'),
      ['NPM_CONFIG_REGISTRY', 'https://registry.npmjs.org/'],
    )
  })

  test('pip install fixe PyPI et desactive les prompts', () => {
    const policy = buildSandboxNetworkPolicy(
      command('aurora-python', ['-m', 'pip', 'install', '-r', 'requirements.txt']),
    )

    assert.equal(policy.mode, 'registry')
    assert.deepEqual(policy.env.find(([key]) => key === 'PIP_INDEX_URL'), ['PIP_INDEX_URL', 'https://pypi.org/simple'])
    assert.deepEqual(policy.env.find(([key]) => key === 'PIP_NO_INPUT'), ['PIP_NO_INPUT', '1'])
  })

  test('cargo et go passent par leurs registres/proxy officiels', () => {
    const cargo = buildSandboxNetworkPolicy(command('cargo', ['check']))
    const go = buildSandboxNetworkPolicy(command('go', ['test', './...']))

    assert.equal(cargo.mode, 'registry')
    assert.deepEqual(
      cargo.env.find(([key]) => key === 'CARGO_REGISTRIES_CRATES_IO_PROTOCOL'),
      ['CARGO_REGISTRIES_CRATES_IO_PROTOCOL', 'sparse'],
    )
    assert.equal(go.mode, 'registry')
    assert.deepEqual(go.env.find(([key]) => key === 'GOPROXY'), ['GOPROXY', 'https://proxy.golang.org'])
  })

  test('une commande inconnue contenant install reste sans reseau', () => {
    const policy = buildSandboxNetworkPolicy(command('curl', ['https://example.test/install.sh'], 'Installer outil externe'))

    assert.equal(policy.mode, 'none')
    assert.equal(policy.podmanNetwork, 'none')
    assert.deepEqual(policy.env, [])
  })

  test('podmanEnvArgs serialise les variables de registre', () => {
    const policy = buildSandboxNetworkPolicy(command('dart', ['pub', 'get']))

    assert.deepEqual(podmanEnvArgs(policy), ['--env', 'PUB_HOSTED_URL=https://pub.dev'])
  })
})
