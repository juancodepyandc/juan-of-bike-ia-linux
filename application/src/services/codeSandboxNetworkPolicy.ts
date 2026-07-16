import type { ValidationCommand } from './codeSandboxTypes.ts'

export type SandboxNetworkPolicy = {
  mode: 'none' | 'registry'
  podmanNetwork: string
  env: Array<[string, string]>
  reason: string
}

const REGISTRY_NETWORK = 'slirp4netns:allow_host_loopback=false'

function executableName(executable: string): string {
  return executable
    .replace(/\\/g, '/')
    .replace(/.*\//, '')
    .replace(/\.(cmd|exe)$/i, '')
    .toLowerCase()
}

function commandText(command: ValidationCommand): string {
  return [executableName(command.executable), ...command.args.map((arg) => arg.toLowerCase())].join(' ')
}

function env(entries: Record<string, string>): Array<[string, string]> {
  return Object.entries(entries)
}

function registryPolicy(reason: string, envVars: Record<string, string> = {}): SandboxNetworkPolicy {
  return {
    mode: 'registry',
    podmanNetwork: REGISTRY_NETWORK,
    env: env(envVars),
    reason,
  }
}

export function buildSandboxNetworkPolicy(command: ValidationCommand): SandboxNetworkPolicy {
  const exe = executableName(command.executable)
  const args = command.args.map((arg) => arg.toLowerCase())
  const text = commandText(command)

  if (
    (exe === 'npm' || exe === 'pnpm' || exe === 'yarn')
    && /(^|\s)(install|ci)(\s|$)/.test(text)
  ) {
    return registryPolicy('registry:npm', {
      NPM_CONFIG_REGISTRY: 'https://registry.npmjs.org/',
      NPM_CONFIG_AUDIT: 'false',
      NPM_CONFIG_FUND: 'false',
      NPM_CONFIG_IGNORE_SCRIPTS: 'true',
      npm_config_registry: 'https://registry.npmjs.org/',
      npm_config_audit: 'false',
      npm_config_fund: 'false',
      npm_config_ignore_scripts: 'true',
    })
  }

  const isPythonPip = (exe === 'python' || exe === 'python3' || exe === 'aurora-python')
    && args[0] === '-m'
    && args[1] === 'pip'
    && args[2] === 'install'
  if (isPythonPip || (exe === 'pip' && args[0] === 'install') || (exe === 'pip3' && args[0] === 'install')) {
    return registryPolicy('registry:pypi', {
      PIP_INDEX_URL: 'https://pypi.org/simple',
      PIP_DISABLE_PIP_VERSION_CHECK: '1',
      PIP_NO_INPUT: '1',
    })
  }

  if (exe === 'cargo' && /(^|\s)(check|fetch|build|test)(\s|$)/.test(text)) {
    return registryPolicy('registry:crates.io', {
      CARGO_REGISTRIES_CRATES_IO_PROTOCOL: 'sparse',
      CARGO_REGISTRIES_CRATES_IO_INDEX: 'sparse+https://index.crates.io/',
      CARGO_NET_GIT_FETCH_WITH_CLI: 'false',
    })
  }

  if (exe === 'go' && /(^|\s)(test|build|mod download)(\s|$)/.test(text)) {
    return registryPolicy('registry:go-proxy', {
      GOPROXY: 'https://proxy.golang.org',
      GOSUMDB: 'sum.golang.org',
    })
  }

  if (exe === 'dart' && args[0] === 'pub' && args[1] === 'get') {
    return registryPolicy('registry:pub.dev', {
      PUB_HOSTED_URL: 'https://pub.dev',
    })
  }

  if (exe === 'dotnet' && args[0] === 'restore') {
    return registryPolicy('registry:nuget', {
      NUGET_XMLDOC_MODE: 'skip',
    })
  }

  if (exe === 'mix' && args[0] === 'deps.get') {
    return registryPolicy('registry:hex', {
      HEX_CDN: 'https://repo.hex.pm',
    })
  }

  if (exe === 'bundle' && args[0] === 'install') {
    return registryPolicy('registry:rubygems', {
      BUNDLE_RETRY: '2',
    })
  }

  if (
    (exe === 'mvn' || exe === 'gradle' || exe === 'gradlew')
    && /(compile|build|test|dependency:go-offline)/.test(text)
  ) {
    return registryPolicy('registry:maven', {
      MAVEN_OPTS: '-Dmaven.repo.remote=https://repo.maven.apache.org/maven2',
    })
  }

  return {
    mode: 'none',
    podmanNetwork: 'none',
    env: [],
    reason: 'network:none',
  }
}

export function podmanEnvArgs(policy: SandboxNetworkPolicy): string[] {
  return policy.env.flatMap(([key, value]) => ['--env', `${key}=${value}`])
}
