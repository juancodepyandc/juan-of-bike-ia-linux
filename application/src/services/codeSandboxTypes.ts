export type CodeFile = {
  name: string
  language: string
  content: string
}

export type CodeSandboxStepResult = {
  label: string
  command: string
  ok: boolean
  output: string
}

export type CodeSandboxResult = {
  ok: boolean
  rootPath: string
  summary: string
  question: string | null
  steps: CodeSandboxStepResult[]
  detectedLanguage: string
  normalizedFiles?: CodeFile[]
}

export type ValidationCommand = {
  label: string
  executable: string
  args: string[]
  timeoutMs?: number
  /** If true, failure is logged but does not abort the pipeline */
  optional?: boolean
}

export type AutoInstallSpec = {
  winget?: string
  apt?: string
  brew?: string
  npm?: string
  /** Fallback message when no auto-installer is available */
  message?: string
}

export type DetectedLanguage =
  | 'node' | 'python' | 'rust' | 'go'
  | 'java' | 'c' | 'cpp' | 'bash' | 'ruby' | 'php'
  | 'typescript-standalone' | 'sql' | 'dart' | 'kotlin'
  | 'csharp' | 'swift' | 'zig' | 'lua' | 'elixir'
  | 'haskell' | 'scala' | 'r' | 'powershell'
  | 'unknown'
