import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'

const root = path.resolve(import.meta.dirname, '../..')
const require = createRequire(path.join(root, 'application/package.json'))
const ts = require('typescript')
const output = path.resolve(process.argv[2] || path.join(root, 'audit/cycle-01'))
const files = execFileSync('git', ['ls-files', '-z'], { cwd: root, encoding: 'utf8' })
  .split('\0').filter(file => /\.(?:ts|tsx|js|jsx|mjs)$/.test(file))
const configFile = ts.readConfigFile(path.join(root, 'application/tsconfig.json'), ts.sys.readFile)
const config = ts.parseJsonConfigFileContent(configFile.config, ts.sys, path.join(root, 'application'))
const program = ts.createProgram(files.map(file => path.join(root, file)), {
  ...config.options, allowJs: true, noEmit: true,
})
const checker = program.getTypeChecker()
const tracked = new Set(files)
const units = []
const calls = []
const imports = []
const failures = []

function location(node) {
  const source = node.getSourceFile()
  return {
    file: `AuroraIA/${path.relative(root, source.fileName)}`,
    line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1,
  }
}

for (const file of files) {
  const source = program.getSourceFile(path.join(root, file))
  if (!source) {
    failures.push({ file, error: 'source_missing' })
    continue
  }
  for (const diagnostic of source.parseDiagnostics) {
    failures.push({ file, line: source.getLineAndCharacterOfPosition(diagnostic.start).line + 1,
      error: ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n') })
  }
  function visit(node, scope = [], inFunction = false) {
    let nextScope = scope
    if (ts.isFunctionLike(node) && node.body) {
      const owner = ts.isVariableDeclaration(node.parent) || ts.isPropertyAssignment(node.parent) ? node.parent : node
      const name = owner.name?.getText(source) || `<anonymous:${location(node).line}>`
      nextScope = [...scope, name]
      let exported = false
      for (let ancestor = owner; ancestor && ancestor !== source; ancestor = ancestor.parent) {
        if (ts.getCombinedModifierFlags(ancestor) & ts.ModifierFlags.Export) exported = true
      }
      const privateMember = Boolean(ts.getCombinedModifierFlags(owner) & (ts.ModifierFlags.Private | ts.ModifierFlags.Protected))
      units.push({ ...location(node), name: nextScope.join('.'),
        end: source.getLineAndCharacterOfPosition(node.end).line + 1,
        public: exported && !inFunction && !privateMember && !name.startsWith('<anonymous:'),
        language: source.languageVariant === ts.LanguageVariant.JSX ? 'tsx/jsx' : 'ts/js', review: 'unreviewed' })
    }
    if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
      const signature = checker.getResolvedSignature(node)
      const target = signature?.declaration
      const targetLocation = target && location(target)
      const internal = targetLocation && tracked.has(targetLocation.file.replace(/^AuroraIA\//, ''))
      calls.push({ ...location(node), caller: scope.join('.') || '<module>',
        callee: node.expression.getText(source).slice(0, 300),
        target: internal ? targetLocation : null, resolution: internal ? 'typescript_symbol' : 'unresolved_or_external' })
    }
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier) {
      const module = node.moduleSpecifier.text
      const resolved = ts.resolveModuleName(module, source.fileName, program.getCompilerOptions(), ts.sys).resolvedModule
      const target = resolved && path.relative(root, resolved.resolvedFileName)
      imports.push({ ...location(node), module, target: tracked.has(target) ? `AuroraIA/${target}` : null })
    }
    ts.forEachChild(node, child => visit(child, nextScope, inFunction || (ts.isFunctionLike(node) && Boolean(node.body))))
  }
  visit(source)
}
fs.mkdirSync(output, { recursive: true })
fs.writeFileSync(path.join(output, 'typescript.json'), JSON.stringify({ units, calls, imports, parse_failures: failures }, null, 2) + '\n')
console.log(JSON.stringify({ files: files.length, units: units.length, public: units.filter(unit => unit.public).length,
  calls: calls.length, resolved_calls: calls.filter(call => call.target).length, imports: imports.length,
  parse_failures: failures }, null, 2))
