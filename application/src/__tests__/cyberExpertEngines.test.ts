import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { runSymbolicExecution } from '../services/cyber/symbolicExecutionEngine.ts'
import { analyzeBinaryPayload } from '../services/cyber/binaryAnalysisEngine.ts'
import { generateEbpfPolicyBundle, EBPF_KERNEL_PROBES } from '../services/cyber/ebpfKernelEngine.ts'
import { executeSoarPlaybook } from '../services/cyber/soarPlaybookEngine.ts'

describe('SymbolicExecutionEngine', () => {
  test('runSymbolicExecution explore les branches et prouve mathématiquement les violations d invariants', () => {
    const report = runSymbolicExecution('uint32_t offset; uint32_t size;', 'parse_packet')
    assert.equal(report.analyzedFunction, 'parse_packet')
    assert.ok(report.symbolicVars.length >= 3)
    assert.ok(report.exploredPaths.length >= 3)
    assert.ok(report.exploredPaths.some((p) => p.reachedState === 'INTEGER_OVERFLOW'))
    assert.ok(report.mathematicalProof.includes('Z3 Theorem Prover'))
    assert.ok(report.provablyCorrectCode.includes('__builtin_add_overflow'))
  })
})

describe('BinaryAnalysisEngine', () => {
  test('analyzeBinaryPayload génère le CFG, les gadgets ROP et l entropie', () => {
    const report = analyzeBinaryPayload('test_binary.elf')
    assert.equal(report.arch, 'x86_64')
    assert.ok(report.basicBlocks.length >= 3)
    assert.ok(report.ropGadgets.length >= 5)
    assert.ok(report.ropGadgets.some((g) => g.category === 'SYSCALL'))
    assert.ok(report.sections.length >= 4)
    assert.ok(report.securityMitigations.pie)
  })
})

describe('EbpfKernelEngine', () => {
  test('generateEbpfPolicyBundle synthétise des sondes C LSM et XDP', () => {
    const bundle = generateEbpfPolicyBundle()
    assert.ok(bundle.probes.length >= 3)
    assert.ok(bundle.probes.some((p) => p.hookType === 'lsm'))
    assert.ok(bundle.probes.some((p) => p.hookType === 'xdp'))
    assert.ok(bundle.exportPayload.content.includes('security_bprm_check'))
  })
})

describe('SoarPlaybookEngine', () => {
  test('executeSoarPlaybook déroule le pipeline DAG et génère les artefacts de mitigation', () => {
    const res = executeSoarPlaybook('soar-anti-ransomware')
    assert.equal(res.playbook.isSuccess, true)
    assert.ok(res.playbook.steps.length >= 5)
    assert.ok(res.playbook.totalExecutionTimeMs > 0)
    assert.ok(res.playbook.mitigationArtifacts.length >= 3)
    assert.ok(res.exportPayload.content.includes('Rapport d\'Exécution SOAR'))
  })
})
