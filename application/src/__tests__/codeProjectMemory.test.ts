import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { buildCodeProjectMemory, selectCodeProjectMemoryContext } from '../services/codeProjectMemory.ts'
import type { CodeGenerationQueueItem } from '../services/codeGenerationQueue.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'

function item(overrides: Partial<CodeGenerationQueueItem> = {}): CodeGenerationQueueItem {
  return {
    path: 'src/features/billing/BillingPanel.tsx',
    order: 4,
    required: true,
    role: 'billing UI',
    language: 'tsx',
    imports: ['./billingApi', '../../lib/currency'],
    exports: ['BillingPanel'],
    notes: [],
    ...overrides,
  }
}

describe('codeProjectMemory', () => {
  test('indexe imports, importedBy, symboles et termes', () => {
    const files: CodeFile[] = [
      { name: 'src/features/billing/BillingPanel.tsx', language: 'tsx', content: 'import { formatCurrency } from "../../lib/currency"\nexport function BillingPanel() { return formatCurrency(10) }' },
      { name: 'src/lib/currency.ts', language: 'ts', content: 'export function formatCurrency(value) { return `$${value}` }' },
    ]
    const memory = buildCodeProjectMemory(files)
    const panel = memory.byPath.get('src/features/billing/billingpanel.tsx')
    const currency = memory.byPath.get('src/lib/currency.ts')

    assert.ok(panel)
    assert.ok(currency)
    assert.deepEqual(panel.imports, ['src/lib/currency.ts'])
    assert.deepEqual(currency.importedBy, ['src/features/billing/BillingPanel.tsx'])
    assert.ok(panel.symbols.includes('BillingPanel'))
    assert.ok(currency.terms.includes('format'))
  })

  test('selectionne le contexte par cible, imports du plan et termes du prompt', () => {
    const files: CodeFile[] = [
      { name: 'package.json', language: 'json', content: '{"name":"demo"}' },
      { name: 'src/features/billing/BillingPanel.tsx', language: 'tsx', content: 'import { fetchInvoices } from "./billingApi"\nexport function BillingPanel() { return fetchInvoices() }' },
      { name: 'src/features/billing/billingApi.ts', language: 'ts', content: 'export function fetchInvoices() { return [] }' },
      { name: 'src/lib/currency.ts', language: 'ts', content: 'export function formatCurrency(value) { return `$${value}` }' },
      { name: 'docs/huge.md', language: 'markdown', content: 'unrelated '.repeat(5000) },
    ]
    const selected = selectCodeProjectMemoryContext({
      memory: buildCodeProjectMemory(files),
      item: item(),
      prompt: 'Corrige la facturation invoices et formatCurrency',
      maxFiles: 4,
    })

    assert.equal(selected[0].file.path, 'src/features/billing/BillingPanel.tsx')
    assert.deepEqual(new Set(selected.map((entry) => entry.file.path)), new Set([
      'src/features/billing/BillingPanel.tsx',
      'src/lib/currency.ts',
      'src/features/billing/billingApi.ts',
      'package.json',
    ]))
    assert.equal(selected.some((entry) => entry.file.path === 'docs/huge.md'), false)
    assert.ok(selected[0].reasons.includes('target'))
  })
})
